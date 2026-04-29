# Session 154 — GEDCOM Bloat Root-Cause Analysis (Phase E0.5, Read-Only)

**Captured:** 2026-04-29 (UTC) via session pooler `aws-0-us-west-2.pooler.supabase.com:5432`
**Source data:** `session-154-supabase-bloat-root-cause.json` (machine-readable)
**Auditor:** Track E worktree subagent, Phase E0.5
**Scope:** `gedcom_*` only. E0 already cleared other tables as non-issues.

> **TL;DR for Nolan:** Your intuition was right. The base GEDCOM is ~22K individuals.
> A handful of imports should not produce 197K rows. They did because **7 of 9
> imports `status='failed'` and the importer left their full row sets behind**
> (~21,944 rows × ~67 MB raw_record_json each, plus full change_log writes per attempt).
> `payload_hash` is populated but **never used to dedup at INSERT**. Three
> identifiable causes account for ~1.42 GB of the 2.17 GB GEDCOM footprint. None
> of them is "preserving valuable history."

---

## Headline numbers (the duplication factor)

| Metric | Value |
|---|---|
| Distinct individuals (`COUNT(DISTINCT gedcom_id)`) | **22,010** |
| Total rows in `gedcom_individuals` | **196,645** |
| **Duplication factor** | **8.94×** |
| `gedcom_versions` rows | 9 (versions 1-9) |
| Versions with `status='applied'` | 2 (v7, v9) |
| Versions with `status='failed'` | 7 (v1-6, v8) |
| Rows with `version_id IS NULL` (pre-Migration-002 legacy) | 21,809 |
| Rows with `payload_hash IS NOT NULL` | 174,836 (89%) |
| Rows with `payload_hash IS NULL` | 21,809 (the legacy null-version set) |

**Headline interpretation:** the duplication factor is *almost exactly the
import count* (9). The schema *did* what `Migration 002` told it to do —
keep every version. The schema was wrong: failed imports should have been
rolled back, and unchanged individuals should have been deduplicated by
hash. Neither happened.

---

## Per-version row counts

| Version | UUID prefix | `imported_at` | `status` | Rows in `gedcom_individuals` | `is_current=TRUE` rows |
|---:|---|---|---|---:|---:|
| (legacy) | `NULL` | — | — | 21,809 (all `is_current=FALSE`) | 0 |
| 1 | `f008b3d1` | 2026-03-11 20:43 | **failed** | 21,944 | 0 |
| 2 | `443003ab` | 2026-03-11 21:17 | **failed** | 21,944 | 0 |
| 3 | `a23b6c40` | 2026-03-11 21:26 | **failed** | 21,944 | 0 |
| 4 | `9ad4aaad` | 2026-03-11 21:34 | **failed** | 21,944 | 0 |
| 5 | `d5327cf1` | 2026-03-11 22:22 | **failed** | 21,944 | 0 |
| 6 | `96a5fda5` | 2026-03-11 22:58 | **failed** | 21,944 | 0 |
| 7 | `05ffeee9` | 2026-03-11 23:58 | **applied** | 21,944 (770 `is_current=TRUE`, 21,174 retained) | 770 |
| 8 | `ad077b5f` | 2026-03-29 03:30 | **failed** | **0 individual rows** (failed before write?) | 0 |
| 9 | `5d380adc` | 2026-03-29 03:46 | **applied** | 21,228 | 21,228 |

**Notes:** Versions 1-6 fired in 2h15m on 2026-03-11. All failed. All left full
row sets behind. Version 7 succeeded but only 770 of its 21,944 rows are still
`is_current=TRUE` (rest superseded by v9 four months later). v9 is the canonical
state (21,228 current rows). The `version_id IS NULL` bucket (21,809 rows) is
pre-Migration-002 legacy — also fully retained (Lesson 165 territory).

**This is dead weight, not history.** A failed import is a failed import — we
don't keep half-written individual rows around. Migration 003's importer wrote
them anyway and never rolled back.

---

## Top-20 duplicated `payload_hash` groups (proof: dedup is BROKEN)

The query asked: "are any payload_hash values repeated?" The answer is:

| `payload_hash` (first 16 hex) | Duplicate count |
|---|---:|
| `00036506d65b68ea…` | 7 |
| `000873ec7e382d0b…` | 7 |
| `000c30b209148000…` | 7 |
| `000ca53fd8b9be5c…` | 7 |
| `000d6b29c043d0fb…` | 7 |
| `000db4d40c680054…` | 7 |
| `000dbe01e717f058…` | 7 |
| `000eae9ee6fdbb9e…` | 7 |
| `000f127284004fa0…` | 7 |
| `001088da29412814…` | 7 |
| (…and 10 more, all `dup_count=7`) | 7 |

**Smoking gun.** Every top-20 hash repeats *exactly 7 times* — the number of
versions where imports physically wrote rows. The same payload (byte-identical,
by SHA-256 hash) is sitting in 7 separate rows for 7 different `version_id`s.
Migration 003 added `idx_gedcom_individuals_payload_hash` (line 41) — the
importer never reads it before INSERT. It writes blindly.

A single example individual confirms it. For `gedcom_id = '@I132506612777@'`
(from prompt — Harry Isaackovitz from Session 153), the row history is:

| Created at | Version | `payload_hash` (first 16) | `raw_bytes` | `is_current` |
|---|---|---|---:|---|
| 2026-02-23 06:55 | NULL (legacy) | NULL | 2 | false |
| 2026-03-11 20:45 | f008b3d1 | `bcdb1c1fb2bf95e9…` | 3,182 | false |
| 2026-03-11 21:20 | 443003ab | `bcdb1c1fb2bf95e9…` | 3,182 | false |
| 2026-03-11 21:28 | a23b6c40 | `bcdb1c1fb2bf95e9…` | 3,182 | false |
| 2026-03-11 21:36 | 9ad4aaad | `bcdb1c1fb2bf95e9…` | 3,182 | false |
| 2026-03-11 22:24 | d5327cf1 | `bcdb1c1fb2bf95e9…` | 3,182 | false |
| 2026-03-11 22:58 | 96a5fda5 | `bcdb1c1fb2bf95e9…` | 3,182 | false |
| 2026-03-11 23:58 | 05ffeee9 | `bcdb1c1fb2bf95e9…` | 3,182 | false |
| 2026-03-29 03:46 | 5d380adc | `6177caf0547aec5d…` | 3,246 | **true** |

Seven byte-identical writes inside 3 hours, then a real change in March
(64 bytes added to `raw_record_json`). Six of seven failed-import writes are
**pure overhead with no historical value** — they're not snapshots of state,
because the import never committed. Only v7 (05ffeee9) deserved retention
between 2026-03-11 and 2026-03-29.

---

## raw_record_json runtime footprint

| Scope | Total |
|---|---:|
| `is_current = TRUE` only | **67 MB** (over 22,228 current rows; 67 MB of v7+v9 combined) |
| All versions | **533 MB** (Lesson 162-style waste) |
| Net waste from raw_record_json alone | **~466 MB** |

`raw_record_json` is the raw GEDCOM record stored verbatim, alongside parsed
structured columns (`names_json`, `events_json`, etc.) totaling another
~683 MB across all versions. Combined: 1.2 GB of JSON inside the 783 MB
`gedcom_individuals` table (Postgres TOAST compresses, hence the gap).

The same problem repeats in `gedcom_records.root_json` (106 MB) +
`gedcom_records.raw_text` (39 MB) — an entire copy of the GEDCOM file
re-stored. AD-098 Migration 003 calls this "preserve full GEDCOM lineage."
It preserves it 8 times.

### Per-column footprint inside `gedcom_individuals` (all rows)

| Column | Footprint |
|---|---:|
| `raw_record_json` | **533 MB** |
| `names_json` | 199 MB |
| `events_json` | 168 MB |
| `birth_event_json` | 131 MB |
| `citations_json` | 127 MB |
| `death_event_json` | 55 MB |
| `family_as_spouse_json` | 1.3 MB |
| `family_as_child_json` | 1.5 MB |
| `notes_json` | 1.8 MB |

`raw_record_json` alone is 41% of the column-level total. The structured
columns parse subsets of it; if the importer ever finalizes a version and we
trust the structured parse, **`raw_record_json` should be evictable to
archive**.

---

## `gedcom_change_log` — the elephant in the room

| Metric | Value |
|---|---:|
| Total rows | **1,646,688** |
| Total size | 397 MB (Migration 002 design) |
| Rows by `change_type` | added: 785,872 / modified: 438,958 / removed: 421,858 |
| Rows with `old_value IS NOT NULL OR new_value IS NOT NULL` | 410,010 (24.9%) |
| **Rows where BOTH `old_value` AND `new_value` are NULL** | **1,236,678 (75.1%)** |

**75% of change_log rows are payload-empty.** They record only `(version_id,
xref_id, change_type, entity_type)` with no `field_name`/`old_value`/`new_value`.
These are phantom journal rows from `change_type='added'` and `'removed'`
(Migration 002 schema, lines 70-77). They were never intended to carry payload
but carry full per-row uuid + version_id overhead anyway.

Per-version breakdown:

| Version | Status | `change_log` rows |
|---|---|---:|
| 5d380adc (v9, applied) | applied | **686,500** |
| 05ffeee9 (v7, applied) | applied | 370,594 |
| 96a5fda5 (v6, failed) | failed | 370,594 |
| 9ad4aaad (v4, failed) | failed | 219,000 |
| (versions 1, 2, 3, 5, 8 absent from change_log) | — | 0 |

**Three failed imports (v4, v6) plus one rolled-back run wrote 590K change_log
rows that have no functional purpose.** Combined with v7+v9's legitimate
1.06M rows, the table holds 397 MB. If we trim the failed-version rows AND
the all-NULL rows, we recover ~75-90% of the table.

### What does change_log do?
Migration 002 lines 67-77 declare the schema intent (audit/rollback). Lesson 163
noted the importer crashes when this table grows. **No app feature reads it in
the request path** — it's a versioning artifact for a workflow Nolan ran twice
(v7, v9). Not a hot table.

---

## Index usage on `gedcom_*` (full audit)

The `pg_stat_user_indexes` audit revealed **5 indexes with `idx_scan = 0`**:

| Table | Index | Bytes | Scans |
|---|---|---:|---:|
| `gedcom_relationships` | `uq_gedcom_relationships_current` | 26 MB | 0 |
| `gedcom_events` | `uq_gedcom_events_current` | 2.7 MB | 0 |
| `gedcom_versions` | `gedcom_versions_community_id_version_number_key` | 16 KB | 0 |
| `gedcom_enrichment_queue` | `gedcom_enrichment_queue_pkey` | 16 KB | 0 |
| `gedcom_entity_redirects` | `uq_gedcom_entity_redirects_old_key` | 8 KB | 0 |

The big one: `uq_gedcom_relationships_current` is **26 MB** of index that's
never been used (partial unique on `edge_key WHERE is_current = TRUE` — for
upsert paths but never queried). Same story smaller for
`uq_gedcom_events_current` (2.7 MB).

Three indexes have `idx_scan ≤ 1` (suspicious): `gedcom_change_log_pkey` (64 MB),
`idx_gedcom_change_log_xref` (56 MB), `idx_gedcom_relationships_payload_hash`
(46 MB). **Reclaimable from indexes alone: ~30 MB definite, +~166 MB if
change_log + payload_hash indexes are dropped (only safe if Phase E2 also
truncates the underlying tables).** Most-used: `gedcom_versions_pkey` (3.3M
scans), `gedcom_relationships_pkey` (135K) — keep.

---

## Verdict — what's actually causing the bloat

Three causes, each independently confirmed by the queries above. Estimated
storage attribution:

| # | Cause | Evidence | Storage attribution |
|---|---|---|---:|
| **1** | **Failed imports retained, never rolled back** | 7 of 9 versions are `status='failed'`, all but v8 have ~21,944 rows in `gedcom_individuals` and proportional rows in `gedcom_records` / `gedcom_events` / `gedcom_relationships` | **~1.0 GB** (7 versions × ~67 MB raw_record_json + structured-JSON multiples + per-version change_log entries + relationships + events) |
| **2** | **`payload_hash` populated but never used at INSERT** | Top-20 duplicated hashes all have `dup_count=7`. Same byte-identical payload re-written for every version of the same individual. Migration 003 created the index but the importer doesn't query it. | **~400 MB** (additional duplication on top of #1 — ~80% of bytes inside non-current rows are byte-identical to a prior version) |
| **3** | **`change_log` writes phantom rows** | 1.24M of 1.65M rows have NULL old_value AND NULL new_value. Three of those are failed-import writes (v4, v6) and one full v7+v9 set. | **~300 MB** of `change_log` is recoverable; the table is 397 MB |
| 4 | **`raw_record_json` double-stores parsed data** | Same record exists in `raw_record_json` (full payload) AND `names_json` / `events_json` / etc. (structured subset). | (subsumed in #1, #2 — already counted) |
| 5 | **Unused indexes** | 5 indexes with `idx_scan=0`, totaling ~30 MB | ~30 MB |

**Causes #1 and #2 are coupled: if the importer dedup'd on `payload_hash`,
the failed-import rows would still be there but they'd write zero new bytes
past the first version. Fixing one without the other still leaves the row
count high.** Redesign (Phase E4) attacks both. Stopgap (Phase E2) attacks
#1 and #3 — the cleanest wins: drop failed-version rows, drop NULL/NULL
change_log rows, drop unused indexes, VACUUM FULL. Gets under 900 MB. The
rest (legacy NULL-version rows, raw-vs-structured double-storage, change_log
for v7+v9) is a redesign concern.

---

## What the user said vs what we found

> "I'm still not following how the gedcom file has ballooned… base file is
> MB-order… handful of updates shouldn't generate 2-3 orders of magnitude
> more data."

**The user is correct.** Base GEDCOM ~22K individuals × ~3 KB raw = ~67 MB.
Actual on-disk: ~2 GB across `gedcom_*`. The 30× multiplier:

- **9× from version retention** (one row per version per individual)
- **~3-4× per row** from raw + structured JSON double-storage
- **change_log** adds 397 MB on top
- 7 of those 9 versions are *failed imports* and shouldn't be there

Removing failed-version rows (E2 stopgap) drops effective version-retention
from 9× to 2× (v7 + v9), plausible for "keep one rollback step." The
remaining 2× is fixable in redesign by collapsing `is_current=FALSE` to
R2 archive.

---

## Estimated storage if all three causes fixed

| Action | Reclaim estimate |
|---|---:|
| Drop rows for v1-v6 (failed) in `gedcom_individuals` (6 × 21,944 rows × ~3.2 KB raw + structured cols) | **~840 MB** |
| Drop rows for v1-v6 in `gedcom_records`, `gedcom_events`, `gedcom_relationships` | **~520 MB** |
| Drop `change_log` rows for failed versions + NULL/NULL phantom rows | **~300 MB** |
| Drop 5 unused indexes | ~30 MB |
| Drop `raw_record_json` from `is_current=FALSE` v7 rows (kept in archive) | ~50 MB |
| VACUUM FULL on touched tables | reclaims to disk |
| **Total reclaim estimate** | **~1.65 GB → ~600 MB final** (target: ≤900 MB ✓) |

These are **estimates from per-version row counts × per-row average bytes**.
Actual savings depend on per-version row distribution in `gedcom_records`,
`gedcom_events`, `gedcom_relationships` (not yet captured per-version).
Phase E1 refines.

---

## Open questions for Phase E1

1. **Why did v8 fail with 0 rows in `gedcom_individuals`?** Good — suggests
   v8 aborted before INSERT (what we want). But what aborted v1-v6 *after*
   full INSERT? Lesson 163 hypothesis fits: writes rows, dies on change_log
   batch, doesn't roll back.
2. **`gedcom_records.root_json` (272 MB / 119K rows)** — per-version
   snapshots of the same parsed AST? Same per-version cleanup.
3. **`gedcom_relationships` (873K / 406 MB) and `gedcom_events` (226K / 273 MB)** —
   need per-version row counts before E2 commits to predicates.

None of these change the verdict that Phase E2 should DELETE failed-version rows.
