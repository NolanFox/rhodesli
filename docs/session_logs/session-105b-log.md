# Session 105b Log — Data Integrity Final Fix

Started: 2026-03-15
Prompt: Continuation of Session 105, user directive to fix all remaining data issues

## Phase Checklist
- [x] photo_faces write gap: shadow_write_photo_faces_batch() in all write paths
- [x] Synchronous save paths: save_registry + save_photo_registry use strict=True for postgres
- [x] JSON always written as backup first
- [x] Reconciliation script: scripts/reconcile_supabase.py
- [x] Tests: 10 new tests in test_session105b_write_through.py
- [x] Lesson 145 + BACKLOG DATA-014 update
- [x] Session 106 prompt + context
- [ ] Deploy + verify
- [ ] Production reconciliation run
- [ ] ROADMAP split merge

## Changes
- `app/supabase_data.py`: Added `shadow_write_photo_faces_batch()`
- `app/main.py`: save_registry postgres path synchronous, save_photo_registry writes photo_faces + always JSON
- `app/upload_routes.py`: _background_ingest writes photo_faces, logging.error replaces print
- `app/sync_routes.py`: push + resync endpoints write photo_faces
- `scripts/reconcile_supabase.py`: NEW — audit/export/prune/backfill
- `tests/test_session105b_write_through.py`: NEW — 10 tests
- `tasks/lessons/data-lessons.md`: Lesson 145
- `docs/BACKLOG.md`: DATA-014 updated

## Commits
- `f16b4c2` fix(data): write-through architecture + photo_faces gap fix
- `73734f3` feat(data): reconciliation script + 10 tests + Lesson 145
