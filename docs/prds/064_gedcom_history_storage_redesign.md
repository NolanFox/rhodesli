# PRD-064 — GEDCOM History Storage Redesign

**Session:** 163 · **Date:** 2026-06-09 · **Status:** DESIGN (pre-implementation)
**Predecessor:** PRD-063 (efficient mirror redesign — only half-completed)
**Driver:** Session 163 Supabase Free-tier recovery. User requirement: *"always record
the changes, structured so the most recent version is easy to retrieve, but also make
sure we can always unwind any change / track when changes are made."*

---

## 1. Established facts (Session 163 investigation)

- DB reduced 1,309 MB → 423 MB this session by dropping vestigial `gedcom_events` +
  `gedcom_records` and deleting 731,942 superseded `gedcom_relationships` rows
  (all archived to R2, no data loss). Remaining footprint:
  - `gedcom_individuals_v2` **267 MB (63%)**, `gedcom_relationships` 66 MB,
    `gedcom_families_v2` 27 MB, all other (incl. ALL app heritage data) ~63 MB.
- **Only 2 real GEDCOM files ever imported** (source hashes `1e0d…`=21,944 indiv,
  `f778…`=21,998 indiv). `gedcom_versions` has 9 rows but **7 are `failed`** retries;
  only v7 and v9 are `applied`. The relationships bloat we cleaned was mostly
  failed-retry duplication.
- `individuals_v2` stores ~2.0 distinct state-rows/person (≈ the 2 real versions),
  deduped by `payload_hash`. Hash is over-sensitive: some "states" differ only on a
  cosmetic field (observed: identical name/birth/death/events, different hash).
- **Version history is NOT user-facing.** Only one admin page reads `gedcom_versions`
  (a version list). The serving path (`gedcom_dual_read.py`) reads current state only
  (orders by `last_seen_version DESC`). `get_individual_history()` exists but is not
  wired to any route.
- The importer (`scripts/import_gedcom_version.py`) **already computes field-level
  diffs** (`diff_individual`, `_flatten_change_log_entries`) and tracks
  `is_current`/`superseded_by`/`first_seen`/`last_seen`.
- Raw GEDCOM files + per-version structured snapshots are **already archived in R2**
  (`gedcom-version-snapshots/`, `gedcom-source-snapshots/`).
- Imports are **rare** (2 real in ~4 months) and admin-initiated.

## 2. Requirements

| # | Requirement | Source |
|---|---|---|
| R1 | Always record every change made by an import | user |
| R2 | Most-recent version is fast/cheap to retrieve (serving path) | user |
| R3 | Always unwind any change + track WHEN each change was made (audit) | user |
| R4 | Stay comfortably under Free-tier 500 MB (headroom) | Session 163 |
| R5 | Failed/partial imports must never leave orphan/duplicate rows | Lesson (7 failed versions caused the bloat) |

## 3. Options

### Option A — Current-state tables + append-only field-level change-log + R2 raw archive  **(RECOMMENDED)**
- `gedcom_individuals` / `families` / `relationships`: **one row per entity = current
  state**. No `is_current` filter, no multi-state rows. Fast (R2) + small (~135 MB for
  individuals, roughly halving the 267 MB).
- `gedcom_change_log` (append-only): `(version, entity_type, entity_id, field,
  old_value, new_value, change_type, changed_at, changed_by)`. Compact — only *actual*
  field changes. Satisfies R1 (records every change) + R3 (query "what changed when";
  reverse-replay to unwind a specific change).
- `gedcom_versions`: import metadata (exists). Raw GEDCOM + structured snapshot per
  **successful** import in R2 = coarse full-version unwind + ultimate backup.
- Imports write to staging then swap atomically; failures roll back (R5).
- **Pros:** meets R1–R5; fast latest read; compact (deltas tiny since changes are
  small); both fine-grained (per-field) and coarse (per-version) unwind; reuses the
  diff infra that already exists.
- **Cons:** import path must compute/store diffs + support reconstruction; moderate
  one-time engineering. Reconstructing an arbitrary old version requires replaying the
  log (acceptable — rare, admin-only).

### Option B — Current-state only in DB; ALL history (raw GEDCOM + snapshots) in R2
- DB holds only latest state (smallest, fastest). Unwind = re-import a prior GEDCOM
  from R2. Audit = offline diff of two R2 snapshots.
- **Pros:** simplest + smallest DB; trivially free-viable; raw history fully preserved.
- **Cons:** no *in-DB queryable* "what changed when" (R3 satisfied only via offline R2
  diffing, not a live feature); unwind is a heavier batch operation; loses the
  already-built diff infra.

### Option C — Keep multi-state-row design, just fix it
- Keep `individuals_v2` multi-state, but: normalize `payload_hash` (semantic, not
  cosmetic), purge failed-version rows, make imports atomic.
- **Pros:** least code churn. **Cons:** still stores full JSON rows per state (far less
  compact than a delta log); doesn't realize the user's delta idea; R4 headroom weaker.

## 4. Recommendation

**Adopt Option A.** It is the user's "log only the changes, reconstruct as needed"
instinct done correctly, satisfies every requirement, stays compact, and builds on the
diff machinery that already exists. R2 raw archive is the belt-and-suspenders coarse
unwind. Failed-import atomicity (R5) is the critical correctness fix that prevents the
whole bloat class from recurring.

**Sequencing:**
1. (Quick, safe, independent) Snapshot-first purge of the older-version state-rows from
   `individuals_v2` → ~290 MB total DB, comfortable Free headroom. Keeps current state;
   prior version stays in R2. *Does NOT lift the current billing restriction* (separate
   billing decision).
2. (Deliberate engineering, own session) Build Option A: current-state tables +
   `gedcom_change_log` deltas + atomic staged imports + reconstruction utility +
   structural tests (incl. a "failed import leaves zero rows" test).

## 5. Open questions for Codex / review
- Is a field-level change-log the right granularity, or entity-level snapshot-on-change?
- Reverse-replay correctness for unwinding a single mid-history change.
- Do we need point-in-time reconstruction in-DB at all, or is R2 re-import enough (→ B)?
- Atomic-swap mechanism on Supabase (staging table + rename vs transaction).
