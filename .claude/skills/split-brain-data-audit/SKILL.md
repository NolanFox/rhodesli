---
name: split-brain-data-audit
description: >
  Audit + verification protocol for rhodesli's #1 recurring bug class (10+ documented
  occurrences): data divergence between write paths and read paths — local JSON vs Railway
  volume vs Supabase Postgres, batch-script output vs app read path, merged sources vs
  surviving targets. Load BEFORE touching any data write path, data repair, merge logic,
  batch script that produces app-consumed data, or new Supabase table read/write.
  DO NOT USE FOR: pure UI changes, docs-only work, or read-only analysis that writes nothing.
---

# Split-Brain Data Audit — single-source-of-truth discipline

## Why this skill exists (the scar tissue)
The same failure recurred 10+ times (Lessons 56→69→78→85→141→144→147→150→153→154 in
`tasks/lessons.md`): data written to one store while the app reads from another. Costliest
incidents: `identity_overrides` stale-snapshot overwrite silently deleted 36 faces over 4 days
(Lesson 153); a merge orphaned 175 faces across 18 identities and was declared "FIXED" without
verifying the affected page (Lesson 154); an ingest wrote JSON while production read Postgres —
photos invisible, 4 debugging rounds (Lesson 144).

## Triggers — WHEN to load
- Editing any save/load path: `save_registry`, `save_photo_registry`, `load_from_postgres`,
  `shadow_write_*`, `_build_caches`, anything in `app/supabase_data.py`
- Writing/altering a batch script whose output the app reads (`scripts/*.py`)
- Any data repair, un-merge, backfill, or reconciliation against production
- Adding a NEW Supabase table read (a read path with no write path is a latent split-brain)
- Adding a field to the in-memory identity/photo dict
WHEN NOT: UI-only, docs-only, or analysis that produces no persisted data.

## Required reading (before writing code)
1. `tasks/lessons.md` — "REPEAT-OFFENDER FAILURE MODES" table (top of file)
2. `tasks/lessons/data-lessons.md` — Lessons 104, 105, 123, 142, 144, 145, 146, 150, 151, 153, 154, 155
3. `.claude/rules/data-layer.md` + `.claude/rules/batch-data-pipeline.md`
4. `tests/test_data_layer_invariants.py` — the structural guards you must not weaken
5. `docs/architecture/DATA_MODEL.md` — CAUTION: describes the legacy JSON model. Postgres became
   the sole read source in Session 112 (PRD-051 Phase 1); the JSON fallback was fully eliminated
   in Session 143 (AD-232, `ALGORITHMIC_DECISIONS.md`). Treat all JSON-canonical language as stale.

## The invariants (each maps to a real incident)
1. **Postgres is the ONLY read source** (since Session 112 / PRD-051 Phase 1). JSON files are
   backup/cache. If your change makes any request path read identities/photos from JSON when
   `DATA_SOURCE=postgres`, it is wrong.
2. **Every read path must have a write path.** If `load_from_*()` queries a table, EVERY caller
   of the corresponding `save_*()` must populate that table (Lesson 145: `photo_faces` was read
   but never written → invisible faces).
3. **Remove legacy layers in the SAME commit as the migration.** "Keep the old path as a
   fallback" is the 9-time root cause. A stale layer + `dict.update()` = silent data loss.
4. **Never cache a failure state that disables scoping/filtering.** Caching `None` for a
   community-ID lookup leaked cross-community data for the TTL window (Lesson 151). Non-default
   scopes fail CLOSED (empty set), never open.
5. **Batch scripts write to the store the app READS, at the exact key path.** Grep the loader
   first; verify the write landed by re-loading with the app's own loader (Lessons 104, 162).
6. **Coerce JSONB on read AND write.** Supabase stores string-encoded arrays without complaint;
   iterating one yields characters (Lesson 142). Use `_ensure_list()` / `_ensure_list_for_supabase()`.
7. **Post-write verification is part of the write.** Merges: every source face must appear in
   the target after save (Lesson 154). Ingest: identity count must match face count post-sync
   (Lesson 146). No fire-and-forget `except: pass` around Supabase writes (Lessons 123/136).
8. **Fields added to in-memory dicts must be explicitly persisted.** Any top-level key not
   mapped to a Supabase column or preserved in `metadata` JSONB silently drops on round-trip
   (Lesson 179: notes lost for ~50 sessions).

## Verification gates (run in order; ALL must pass before "done")
1. `pytest tests/test_data_layer_invariants.py -q` — structural guards intact
2. For merge/repair work: `pytest tests/test_merge_face_transfer.py tests/test_merge_orphan_audit.py -q`
3. Grep gate: `grep -n "except.*:\s*pass" <changed files>` — no new silent swallows around writes
4. Round-trip gate: write via the changed path, read via the app's canonical loader, assert the
   exact field survives (not a mock — mocks accept any column name; Lessons 105/152/208)
5. Production gate (post-deploy): load the SPECIFIC affected page in a browser and verify the
   exact record renders correctly. "Fixed in the DB" without page verification is theater.
6. Repairs only: per-step snapshot exists in `data_backup_session{N}/` + a tested restore
   script + `--dry-run` mode BEFORE `--execute` (Lesson 155). Audit-log rows written (`app/audit.py`).

## Anti-patterns (hard NOs)
- "I'll keep the old sync as a backup" → 9th-occurrence root cause. Delete it.
- Declaring a data fix done from a successful script exit code.
- Testing a Supabase sync function with mocks only.
- `git add data/<anything>` — production-origin files; trust the .gitignore allowlist (Lesson 141).
- Direct `.save(path)` in a route handler instead of the canonical save function (Lesson 48).
- Fixing data in Supabase directly without a deploy/restart — module-global caches serve stale
  data until the app restarts (Lessons 150, 206).

## Escalation
If the work requires deleting/pruning production rows, dropping a table/layer, or running any
`--execute` repair: STOP and get explicit user approval with the snapshot + restore evidence
attached. These are user-gated by project convention.
