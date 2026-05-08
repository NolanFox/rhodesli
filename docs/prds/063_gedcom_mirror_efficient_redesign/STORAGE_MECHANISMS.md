**Parent:** [PRD-063 hub](../063_gedcom_mirror_efficient_redesign.md)

# PRD-063 §4 — Storage-reduction proposal — 5 mechanisms

Each mechanism evaluated against E0.5 evidence with reduction estimate, risk
profile, and interaction with §3 (functional requirements).

## 4.1 Hash-based dedup at INSERT

- **Mechanism**: Before inserting an individual, compute `payload_hash`
  (already specified by Migration 003 line 41). If a row with the same
  `(gedcom_id, payload_hash)` already exists with `is_current = TRUE`,
  no-op the INSERT and only extend its `version_range` (new column).
- **E0.5 evidence**: top-20 hashes each repeat 7×; the index exists
  (`idx_gedcom_individuals_payload_hash`) but the importer writes blindly.
- **Estimated reduction**: **~400 MB** (E0.5 cause #2 attribution). All
  byte-identical re-writes between versions disappear.
- **Risk**: medium. Requires importer code change in `core/gedcom_importer.py`
  (Lesson 163). Schema change is additive (`version_range` int4range).
- **Functional interaction**: invisible to readers — `is_current = TRUE` row
  per `gedcom_id` still exists. AD-160 link table unaffected.

## 4.2 Single canonical row per individual + versioned archive on R2

- **Mechanism**: `gedcom_individuals_v2` holds **one row per `gedcom_id`**
  (the canonical, current state — ~22K rows total). Per-version snapshots of
  superseded rows ship to R2 as gzipped JSONL keyed by
  `gedcom/versions/<version_uuid>/individuals.jsonl.gz`. Reverse mapping
  preserved in `gedcom_versions.archive_manifest_json`.
- **E0.5 evidence**: 196,645 rows / 22,010 distinct = 8.94× retention bloat.
  v9 is the canonical state (21,228 `is_current=TRUE` rows). All non-current
  rows are archive material.
- **Estimated reduction**: **~700 MB** in `gedcom_individuals` plus
  proportional in `gedcom_records` / `gedcom_relationships` / `gedcom_events`
  / `gedcom_families` (every per-version-versioned table follows the same
  pattern). Combined: ~1.0 GB (overlaps with §4.1 by ~250 MB; net ~750 MB).
- **Risk**: medium. R2 archive must remain fetchable for §3.6 rollback.
  R2 read-cost is negligible (≤9 archive reads per rollback event).
- **Functional interaction**: §3 readers all read `is_current = TRUE` already.
  Archive reads only on rollback (rare admin path) — implement as a CLI
  `scripts/gedcom_restore.py` rather than a request-path route.

## 4.3 Drop `raw_record_json` from runtime tables; per-import gzipped archive on R2

- **Mechanism**: After parse, the structured columns (`names_json`,
  `events_json`, `birth_event_json`, etc.) carry every datum the app reads.
  `raw_record_json` is only useful for re-parse with a future GEDCOM library
  upgrade. Move it to a per-import R2 blob:
  `gedcom/versions/<version_uuid>/raw.jsonl.gz`.
- **E0.5 evidence**: `raw_record_json` is **533 MB across all rows / 67 MB
  current-only / 41% of column total** (E0.5 §"Per-column footprint").
  No app code path reads it (verified: no `raw_record_json` reference in
  `rhodesli_ml/gedcom_context.py`, `app/`, `scripts/run_combined_pipeline.py`
  outside the importer write path).
- **Estimated reduction**: **~466 MB net** (full column eliminated;
  archive cost ~50 MB on R2 = $0.50/yr/GB Pro). Same pattern applied to
  `gedcom_records.root_json` (272 MB / 119K rows) and `gedcom_records.raw_text`
  (39 MB) yields another ~250 MB.
- **Risk**: low. Re-parse on library upgrade is a planned-maintenance event,
  not a request path. R2 archive supports it.
- **Functional interaction**: zero — no code path reads these columns today.

## 4.4 Per-import change manifest replacing per-cell `gedcom_change_log`

- **Mechanism**: Replace the 1.65M-row `gedcom_change_log` with a
  `gedcom_version_manifest` table — **one row per import**. Body is a
  JSONB summary: `{added: [gedcom_id, ...], modified: [{gedcom_id,
  field_changes: [{name, old_hash, new_hash}]}], removed: [...]}`. Field-level
  detail for `modified` is captured by hash, not full payload — full
  before/after value is recoverable from the per-version archive in §4.2.
- **E0.5 evidence**: 1,236,678 of 1,646,688 change_log rows (75.1%) have
  null payload. Three failed-import versions wrote 590K rows alone.
  *No app feature reads `gedcom_change_log` in any request path* (E0.5 §"What
  does change_log do?").
- **Estimated reduction**: **~390 MB** (the entire 397 MB table — manifest
  table is sub-MB at ≤20 import rows projected lifetime). Stopgap E1 only
  reclaims ~300 MB of this; redesign reclaims the rest.
- **Risk**: low. AD-163 audit-trail intent is preserved at coarser
  granularity (per-import). The 24.9% non-null payload rows are reconstructable
  from per-version archives.
- **Functional interaction**: §3.6 (rollback) is satisfied because version
  archives + manifest together describe the same state delta.

## 4.5 Drop unused indexes

- **Mechanism**: Drop the 5 zero-scan indexes per E0.5
  §"Index usage on gedcom_*", subject to the §8 pre-flight grep
  (`uq_gedcom_relationships_current` may still be needed by upserts even
  though `pg_stat_user_indexes` shows zero scans). Conservatively drop only
  the small ones if upsert dependency is confirmed; aggressively drop all 5
  if not.
- **E0.5 evidence**: 5 indexes with `idx_scan = 0`, totaling ~30 MB. Three
  more (`gedcom_change_log_pkey` 64 MB, `idx_gedcom_change_log_xref` 56 MB,
  `idx_gedcom_relationships_payload_hash` 46 MB) become reclaimable when
  their underlying tables shrink (§4.4 + §4.2).
- **Estimated reduction**: **~30 MB definite** + **~166 MB conditional** on
  table shrinkage from §4.2 + §4.4.
- **Risk**: low after pre-flight grep.
- **Functional interaction**: zero.

## 4.6 Cumulative estimate

| Mechanism | Reduction estimate (MB) |
|---|---:|
| 4.1 Hash-based dedup at INSERT | 400 |
| 4.2 Single canonical row + R2 archive | 700 (overlap-net) |
| 4.3 Drop `raw_record_json` + `root_json` + `raw_text` from runtime | 466 + 250 = 716 |
| 4.4 Per-import change manifest replaces per-cell `change_log` | 390 |
| 4.5 Drop 5 unused indexes (definite) + conditional | 30 + 166 |
| **Cumulative reduction (mid-estimate)** | **~1,400 to 1,600 MB** |

Because §4.1 and §4.2 partially overlap (both eliminate per-version row
duplication) the cumulative figure is the **mid-range** between the
conservative ~1.4 GB (heavy overlap) and aggressive ~1.6 GB (low overlap +
all conditional index drops). Either bound puts the database under the
1.1 GB ceiling and well under the 5 GB free-tier budget.
