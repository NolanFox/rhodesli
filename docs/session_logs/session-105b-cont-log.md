# Session 105b Log — Data Integrity Final Fix

Started: 2026-03-15
Prompt: docs/prompts/session-105b-prompt.md

## Phase Checklist
- [x] Phase 0: Orient — tests pass, health endpoint confirmed with data_parity
- [x] Phase 1: Production reconciliation — audit shows 0 stale identities, 1 stale photo. Pruned 1 photo. Photos now synced (943/943). Identity diff (1922 vs 3433) is expected — active vs total including merged.
- [x] Phase 2: Startup parity check — `_startup_parity_check()` added as background thread in startup_event
- [x] Phase 3: Structural prevention tests — 8 tests in `tests/test_data_parity_invariants.py`
- [x] Phase 4: AD-225 written in ALGORITHMIC_DECISIONS.md
- [x] Phase 5: CHANGELOG, ROADMAP, session log, assessment updated
- [x] Phase 6: All tests pass, deploy + browser verify

## Phase 1 Detail: Reconciliation
- Audit result: json_identities=3433, pg_identities=3433, stale_identities=0, stale_photos=1
- Health showed identities_json=1922 because it used `list_identities()` (excludes merged)
- Fix: health now uses `include_merged=True` → proper 3433 vs 3433 comparison
- Prune: 1 stale photo deleted, exported to reconcile_export.json on Railway volume

## Changes (continuation)
- `app/page_routes.py`: Health parity uses include_merged=True
- `app/main.py`: Added `_startup_parity_check()` background thread in startup_event
- `tests/test_data_parity_invariants.py`: NEW — 8 structural tests
- `docs/ml/ALGORITHMIC_DECISIONS.md`: AD-225
- `CHANGELOG.md`: v0.99.9 entry
- `ROADMAP.md`: Session 105/105b in Recently Completed

## Prior Changes (Session 105b first half)
- `app/supabase_data.py`: Added `shadow_write_photo_faces_batch()`
- `app/main.py`: save_registry postgres path synchronous, save_photo_registry writes photo_faces + always JSON
- `app/upload_routes.py`: _background_ingest writes photo_faces, logging.error replaces print
- `app/sync_routes.py`: push + resync endpoints write photo_faces, reconcile endpoint
- `scripts/reconcile_supabase.py`: NEW — audit/export/prune/backfill
- `tests/test_session105b_write_through.py`: NEW — 10 tests
- `tasks/lessons/data-lessons.md`: Lesson 145

## Commits
- `f16b4c2` fix(data): write-through architecture + photo_faces gap fix
- `73734f3` feat(data): reconciliation script + 10 tests + Lesson 145
- `a8286e6` docs: session 105b assessment + log — deploy verified
- `401133e` feat(data): /api/admin/reconcile endpoint for production prune
