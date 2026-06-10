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

## 4. Recommendation (REVISED after Codex audit — `session-163-codex-audit.md`)

**Adopt Option "B-plus"** (Codex-recommended; rejects Option A's field-level log).
This is the user's own "save history in R2, keep only current in the table" instinct —
and the audit confirms it's the *best* design, not a compromise.

**Design:**
- **Postgres (current state only):** `gedcom_individuals` / `families` / `relationships`
  = one row per entity (latest state). No `is_current`, no multi-state rows. Fast (R2),
  smallest footprint (R4) — drops individuals from 267 MB toward ~135 MB.
- **Postgres (tiny per-version manifest):** `gedcom_versions` keeps when/who/counts/
  source-hash + **SHA-256 of each R2 artifact**. Satisfies "track when changes made."
- **R2 (immutable per successful version):** raw GEDCOM + canonical snapshot +
  **entity-level `{before, after, hashes}` diff artifact** (compressed). Satisfies R1
  (every change recorded, typed/lossless) + R3 (exact audit + unwind).
- **Atomic import = ONE Postgres transaction** (port 5432, `pg_advisory_xact_lock`):
  R2 upload+verify first, then a single txn applies all current-table mutations +
  manifest; any exception → full rollback. Fixes R5 (the real bloat root cause).
- **Unwind = conflict-checked compensating version** (NOT reverse-replay): safe only if
  current hash == original `after_hash`, else flag conflict for explicit resolution.

**Why not Option A:** field-level rows recreate the 1.65M-row problem; and adds/removes
stored NULL→NULL can't actually reconstruct (fails R3). Entity-level diffs in R2 are
lossless and free of DB bloat.

**Codex P0s to fix (current importer):** (1) import is NOT atomic — per-batch commits
leave partial rows on failure (THE bloat cause; a test even asserts this); (2) change-log
adds/removes lose payloads; (3) `--skip-change-log` makes audit optional. See audit doc.

## 4b. Use-case fit — "what's new version-over-version" (user, Session 163)
We don't need fast in-DB recall of old versions, but we WILL want to surface *what
changed* between GEDCOM versions (e.g. "added 54 people, changed 12 — list") — for
rhodesli and for fox-genealogy / rhodes-wiki. B-plus serves this natively:
- The R2 `diff.json.gz` artifact (typed `{added, modified, removed}` before/after) IS
  the change record → a "what's new" view reads one artifact.
- `gedcom_versions` caches a tiny diff summary (counts + changed entity-IDs only) for an
  instant overview without reading R2.
- Document the artifact schema as a cross-repo standard (`GEDCOM_HISTORY.md`). The diff
  artifact is therefore a first-class deliverable, not just a backup.

## 5. Sequencing
1. **Immediate, safe, reversible:** snapshot-first purge of older-version state-rows in
   `individuals_v2` (keep latest per `gedcom_id`; prior version already in R2) →
   ~290 MB DB, comfortable Free headroom. *Does NOT lift the current billing
   restriction* (separate decision). Also a stepping-stone to current-state tables.
2. **Deliberate engineering (own session):** implement B-plus — current-state tables,
   manifest + R2 artifact hashes, single-transaction atomic importer, entity-diff R2
   artifacts, conflict-checked compensating-unwind utility, and structural tests
   (mandatory: "failed import leaves ZERO rows", "import without R2 archive is refused").
3. **Then** upgrade to Pro when ready (user pays for a full month → do it when the data
   layer is solid), or let it auto-restore Free on ~25 Jun if downtime is acceptable.
