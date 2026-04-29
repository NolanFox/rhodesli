# Session 154 — Supabase Stopgap Prune Plan (Phase E1)

**Auditor:** Track E worktree subagent, Phase E1
**Date:** 2026-04-29 (UTC)
**Predecessor:** [session-154-supabase-bloat-root-cause.md](session-154-supabase-bloat-root-cause.md) (E0.5)
**Status:** PROPOSAL ONLY — STOPS HERE pending user authorization (see §6)

> Phase E2 (DELETE/VACUUM) is OUT OF SCOPE for this Track-E run. The plan below
> is text only. No `--execute` flag has been added or invoked. The pruning
> script exists as `scripts/session154_supabase_prune.py` but its default is
> `--dry-run` and we do NOT call it with `--execute`. The orchestrator (or a
> follow-up session) gates E2 on the user authorization message in §6.

---

## 1. Goal

Get the database from **2,269 MB** to **≤ 900 MB** (target) / **≤ 1,100 MB**
(mandatory) before the **2026-05-29** grace deadline.

Attack high-confidence wins from E0.5:
- **Cause #1 (failed imports, ~1 GB):** drop rows for 6 failed versions.
- **Cause #3 (change_log phantoms, ~300 MB):** drop NULL/NULL + failed-version rows.
- **Cause #5 (unused indexes, ~30 MB):** drop 5 zero-scan indexes.

DO NOT touch: v7 + v9 (applied — real history); broken `payload_hash` dedup
(Cause #2 is an importer code change, Phase E4); `gemini_api_calls`
(< 90 days); `raw_record_json` on `is_current=FALSE` v7 rows (E4 archives
later); legacy `version_id IS NULL` bucket (needs view-exposure audit
beyond E1's scope).

---

## 2. Table-by-table verdict

| # | Table | Total | Verdict | Reason |
|---:|---|---:|---|---|
| 1 | `gedcom_individuals` | 783 MB | **PRUNE_OLD** | Drop rows where `version_id IN <failed>`. ~131,664 rows. |
| 2 | `gedcom_relationships` | 406 MB | **PRUNE_OLD** | Drop rows where `version_id IN <failed>`. ~439,776 rows. |
| 3 | `gedcom_change_log` | 397 MB | **PRUNE_OLD** | Drop rows where `version_id IN <failed>` OR (`old_value IS NULL AND new_value IS NULL` AND `version_id NOT IN <applied>`). ~1.24M rows. |
| 4 | `gedcom_events` | 273 MB | **PRUNE_OLD** | Drop rows where `version_id IN <failed>`. ~143,578 rows. |
| 5 | `gedcom_records` | 272 MB | **PRUNE_OLD** | Drop rows where `version_id IN <failed>`. ~60,308 rows. |
| 6 | `gedcom_families` | 75 MB | **PRUNE_OLD** | Drop rows where `version_id IN <failed>`. ~20,166 rows. |
| 7 | `gemini_api_calls` | 12 MB | **KEEP_ALL** | All rows < 90 days old. Retention is E3, not E2. |
| 8 | `gedcom_media_objects` | 8.7 MB | **VACUUM_ONLY** | Small; just needs VACUUM. |
| 9 | `gedcom_sources` | 6.7 MB | **VACUUM_ONLY** | Small; just needs VACUUM. |
| 10 | (everything else) | < 7 MB | **KEEP_ALL** | Negligible. |

PLUS: drop 5 indexes with `idx_scan = 0`. See §3.

---

## 3. Per-table proposed actions

Each action specifies: predicate, row-count estimate, byte-savings estimate,
snapshot path, and restore command.

### 3.1–3.5 Drop failed-version rows from 5 tables (same predicate pattern)

**Common predicate template:**
```sql
DELETE FROM <table>
 WHERE version_id IN (
   SELECT id FROM gedcom_versions WHERE status = 'failed'
 )
   AND is_current = FALSE;
```

The `is_current = FALSE` clause is a safety guard: never delete a current row
even if a `status='failed'` version somehow still owns one (it shouldn't, per
E0.5 q4, but belt+suspenders).

| § | Table | Rows | Bytes saved | Snapshot path |
|---|---|---:|---:|---|
| 3.1 | `gedcom_individuals` | 131,664 | ~530 MB | `backups/session-154/gedcom_individuals_pre-prune-<UTC>.jsonl.gz` |
| 3.2 | `gedcom_records` | 60,308 | ~140 MB | `backups/session-154/gedcom_records_pre-prune-<UTC>.jsonl.gz` |
| 3.3 | `gedcom_events` | 143,578 | ~115 MB | `backups/session-154/gedcom_events_pre-prune-<UTC>.jsonl.gz` |
| 3.4 | `gedcom_relationships` | 439,776 | ~210 MB | `backups/session-154/gedcom_relationships_pre-prune-<UTC>.jsonl.gz` |
| 3.5 | `gedcom_families` | 20,166 | ~30 MB | `backups/session-154/gedcom_families_pre-prune-<UTC>.jsonl.gz` |

**Snapshot manifest** (every snapshot, every table): primary keys deleted,
total row count, SHA-256 of serialized rows (sorted by PK), verbatim
predicate, generated restore command:
```bash
python scripts/session154_supabase_prune.py --restore \
  --snapshot backups/session-154/<table>_pre-prune-<UTC>.jsonl.gz
```

**Reversibility:** snapshot replay. No FK cascades — all refs are within the
failed-version row set. **Note on §3.4:** `gedcom_relationships` also carries
136 MB of indexes; ~46 MB is `idx_gedcom_relationships_payload_hash` (only 1
scan ever — see §3.7 for index drops).

### 3.6 `gedcom_change_log` — drop failed-version + NULL/NULL phantom rows

**Predicate (two-step within one snapshot):**
```sql
-- Step A: drop rows tied to failed versions (~590K rows)
DELETE FROM gedcom_change_log
 WHERE version_id IN (
   SELECT id FROM gedcom_versions WHERE status = 'failed'
 );

-- Step B: drop remaining NULL-payload phantom rows for v7+v9 only
-- (additive 'added'/'removed' rows that were written without value payload —
--  if NULL/NULL, they're audit no-ops, not actual change records)
DELETE FROM gedcom_change_log
 WHERE old_value IS NULL
   AND new_value IS NULL
   AND change_type IN ('added', 'removed')
   AND version_id IN (
     SELECT id FROM gedcom_versions WHERE status = 'applied'
   );
```
- **Row count estimate:** ~1,239,990 total (Step A: ~590K, Step B: ~650K).
  Deleted simultaneously per the snapshot, but written in two snapshot files
  (one per step) so we can roll back step-by-step.
- **Byte-savings estimate:** **~300 MB** (60% of the 397 MB table after
  account for overhead)
- **Snapshot path:**
  - `backups/session-154/gedcom_change_log_step_a_pre-prune-<UTC>.jsonl.gz`
    (failed-version rows)
  - `backups/session-154/gedcom_change_log_step_b_pre-prune-<UTC>.jsonl.gz`
    (NULL/NULL applied-version phantoms)
- **Reversibility:** restore replays. NOTE: these rows are recreated by the
  importer if a future re-import happens — restoring is purely defensive.
- **Risk note:** step B targets `change_type IN ('added', 'removed')` — the
  Migration 002 schema (line 70-77) explicitly says these are write-only audit
  rows whose payload (`field_name`, `old_value`, `new_value`) is NULL by design
  for adds/removes. Confirmed by E0.5 query 13 (785,872 added + 421,858
  removed = 1,207,730, vs the 1,236,678 NULL-payload total). The 28,948
  delta is "modified" rows that happen to have null values — leave those
  alone (`change_type IN ('added', 'removed')` filter ensures it).

### 3.7 Drop 5 unused indexes

```sql
-- These have idx_scan = 0 in pg_stat_user_indexes (full scan history).
DROP INDEX IF EXISTS uq_gedcom_relationships_current;     -- 26 MB
DROP INDEX IF EXISTS uq_gedcom_events_current;            -- 2.7 MB
DROP INDEX IF EXISTS gedcom_versions_community_id_version_number_key;  -- 16 KB
DROP INDEX IF EXISTS gedcom_enrichment_queue_pkey;        -- 16 KB
DROP INDEX IF EXISTS uq_gedcom_entity_redirects_old_key;  -- 8 KB
```
- **Row count estimate:** 0 (indexes only)
- **Byte-savings estimate:** **~30 MB**
- **Snapshot:** none needed — indexes are reproducible from DDL. Snapshot
  step writes the original `CREATE INDEX` statements to
  `backups/session-154/dropped_indexes_pre-prune-<UTC>.sql` for reversibility.
- **Risk note:** **before dropping `gedcom_enrichment_queue_pkey` and
  `uq_gedcom_relationships_current`,** verify nothing in `app/` or
  `rhodesli_ml/` UPSERTs to these tables expecting the unique constraint to
  exist. If the importer's `ON CONFLICT (edge_key) WHERE is_current = TRUE`
  upsert path uses `uq_gedcom_relationships_current`, dropping it would
  silently break uniqueness. **E2 must run `grep -r "ON CONFLICT" app/ core/
  rhodesli_ml/ scripts/`** before this DROP.

  Alternative: leave `uq_gedcom_relationships_current` and `uq_gedcom_events_current`
  in place — they cost 29 MB combined, well within tolerance, and may be
  needed by the v9-style importer even though `pg_stat_user_indexes` hasn't
  recorded a scan since whatever session reset stats.

---

## 4. VACUUM FULL plan

After DELETEs, `pg_total_relation_size` won't shrink (Postgres returns space
to the table free-list, not the OS). VACUUM FULL is required.

| Table | VACUUM | Estimate | Notes |
|---|---|---|---|
| `gedcom_individuals` | FULL | 783 MB → ~250 MB | brief lock |
| `gedcom_relationships` | FULL | 406 MB → ~196 MB | exclusive lock |
| `gedcom_change_log` | FULL | 397 MB → ~100 MB | (or TRUNCATE if no read path — flag) |
| `gedcom_events` | FULL | 273 MB → ~158 MB | |
| `gedcom_records` | FULL | 272 MB → ~132 MB | |
| `gedcom_families` | FULL | 75 MB → ~45 MB | brief |
| `gedcom_media_objects` | brief VACUUM | small | stats refresh |
| `gedcom_sources` | brief VACUUM | small | stats refresh |

**Lock duration:** ~65K remaining individual rows post-prune → seconds. App's
GEDCOM read path is not request-critical (only `/tools/estimate` batch and
`/tree`); brief outage acceptable. **Sequencing:** all DELETEs across all
tables finish FIRST, then VACUUM FULL — TOAST tables are shared.

---

## 5. Target final size — arithmetic

| Source | Reclaim |
|---|---:|
| `gedcom_individuals` failed-version DELETE | -530 MB |
| `gedcom_records` failed-version DELETE | -140 MB |
| `gedcom_events` failed-version DELETE | -115 MB |
| `gedcom_relationships` failed-version DELETE | -210 MB |
| `gedcom_families` failed-version DELETE | -30 MB |
| `gedcom_change_log` Step A + B DELETE | -300 MB |
| Unused index DROPs (conservative) | -30 MB |
| TOAST + index reclaim from VACUUM FULL | -75 MB |
| **Total reclaim estimate** | **~1,430 MB** |
| **Final size estimate** | **~840 MB** |

**Headroom:** 60 MB under 900 MB target, 260 MB under 1,100 MB ceiling.
Comfortable. The estimate is conservative — VACUUM FULL TOAST reclaim is
typically larger.

---

## 6. Authorization gate (DEFAULT: STOP)

> **USER AUTHORIZATION REQUIRED.** The user must reply with a message that
> explicitly names:
>
> 1. The commit hash of THIS plan (`docs/feedback/session-154-supabase-prune-plan.md`).
> 2. Every table being touched (the 6 PRUNE_OLD tables in §2 + the 5 indexes
>    in §3.7).
> 3. Every DELETE predicate (the SQL blocks in §3.1 through §3.6 verbatim).
> 4. Every snapshot path (the 7 paths listed across §3 — one per table, plus
>    the dropped-indexes SQL artifact).
> 5. The full VACUUM FULL list from §4.
>
> **Default behavior in the absence of that message: STOP.** "Approved" alone
> is NOT sufficient. "Looks good, run it" is NOT sufficient. The user must
> name (a) through (e) so we have an unambiguous audit trail of what they
> approved and we cannot expand scope under cover of a vague approval.
>
> The captured authorization message must be saved verbatim to
> `docs/feedback/session-154-supabase-prune-authorization.md` BEFORE Phase
> E2's `--execute` flag is invoked.

---

## 7. Snapshot validation pattern (re-read before mutate)

Every DELETE step (matches Lessons 155, 156):

1. **Pre-snapshot:** `SELECT ... INTO snapshot_file`, gzipped, header with:
   `total_rows`, `sha256_of_rows` (sorted by PK), verbatim `predicate`,
   full `pk_list`, copy-paste `restore_command`.
2. **Re-read:** decompress, deserialize, verify `total_rows` + recomputed
   sha256 match header.
3. **Only then** issue the DELETE.
4. **Post-DELETE:** verify `affected_rows == snapshot.total_rows`.
5. **If mismatch:** abort, do NOT proceed.

Implemented as the contract for `scripts/session154_supabase_prune.py`'s
`--execute` mode (Track E owns this script; not invoked with `--execute`
in this run).

## 8. Pre-flight checks for E2

Before sending the user the authorization-request:

- `grep -rn "ON CONFLICT" app/ core/ rhodesli_ml/ scripts/` — confirm no upsert
  path needs `uq_gedcom_relationships_current` or `uq_gedcom_events_current`.
- `grep -rn "gedcom_change_log\|gedcom_enrichment_queue" app/ core/ rhodesli_ml/` —
  confirm no request-path read. If any: revise §3.6.
- `grep -rn "is_current IS NULL\|is_current = FALSE" app/ core/ rhodesli_ml/` —
  confirm legacy NULL bucket isn't exposed outside views.
- Verify `scripts/session154_supabase_prune.py` exists, `--dry-run` default,
  tests passing.

---

## 9. Out of scope for E2

- Legacy `version_id IS NULL` bucket (21,809 individuals + 145,574
  relationships + 40,140 events). ~75 MB bonus reclaim possible but needs
  more audit than E1's scope.
- `raw_record_json` column drops (Phase E4 redesign).
- `payload_hash` dedup fix in importer (Phase E4 code change).
- `gemini_api_calls` (all rows < 90 days; retention is E3).
- Retention sweep installation (E3).
- Scheduler enablement (per Codex P1: not until OD-013 approved in writing).

## 10. Risk register

| # | Risk | Likelihood | Mitigation |
|---|---|---|---|
| 1 | Failed-version row that's actually `is_current=TRUE` | Low (E0.5 q4: 0 such rows) | `AND is_current = FALSE` in every DELETE |
| 2 | Unique-index drop breaks future upsert | Medium | §8 pre-flight grep before E2 |
| 3 | VACUUM FULL long lock | Low (small tables) | run in quiet window |
| 4 | Snapshot-restore replay diverges (e.g., autogen PKs) | Low | snapshot stores ALL columns; restore explicit PK |
| 5 | 840 MB estimate wrong | Low | step-by-step measure after each DELETE |
| 6 | Importer regenerates dropped state | Medium | E3 retention prevents; E4 redesign fixes root |

## 11. After E2 success

Final size → `session-154-supabase-size-progress.json`. E3 retention =
steady-state guard. E4 redesign (PRD-063) = next session, gated on user
PRD review. Supabase 2026-05-29 grace deadline met. If final > 1,100 MB:
revisit, audit legacy NULL bucket, rerun with expanded scope.

---

**End of plan.** Next step: user authorization message per §6. Plan does NOT
execute itself.
