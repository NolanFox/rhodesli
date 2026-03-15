# Session 105 Log — Eliminate DATA_SOURCE Split-Brain (P0)

Started: 2026-03-15
Prompt: docs/prompts/session-105-prompt.md

## Phase Checklist
- [x] Phase 0: Orient + Lesson 144 (already existed)
- [x] Phase 1: `/api/sync/push` writes to Supabase
- [x] Phase 2: Shadow-writes reliable (strict param)
- [x] Phase 3: CLI `--community` flag
- [x] Phase 4: Health endpoint data parity check
- [x] Phase 5: Debug endpoint removed + 18 tests
- [x] Phase 6: Deploy + verify — `railway up` SUCCESS, browser verified

## Changes
- `app/sync_routes.py`: Removed debug-cache endpoint, added Supabase write in push handler
- `app/supabase_data.py`: Added `strict` param to all 4 shadow-write functions, upgraded log level to ERROR, added Sentry breadcrumbs
- `app/page_routes.py`: Added `_check_data_parity()` function, wired into `/health` response
- `core/ingest_inbox.py`: Added `--community` CLI flag with community lookup + auto-tagging
- `tests/test_session105_split_brain.py`: 18 new tests

## Verification Gate
- [x] `/api/sync/push` writes to both JSON AND Supabase
- [x] Shadow-write failures are visible (not swallowed)
- [x] Ingested photos auto-assigned to community (via --community flag)
- [x] Health endpoint shows parity status
- [x] Debug endpoint removed
- [x] All tests pass (18 new, 4387 total)
- [x] Production browser verified — `/health` data_parity field confirmed, landing page loads, debug endpoint 404

## Deploy
- `railway up` → DOCKERFILE build → SUCCESS (deploy ID `2e5c88b9`)
- `/health` data_parity: photos 943/944, identities 1922/3433 (historical accumulation, not regression)

## Commits
- `5a97f29` fix(data): eliminate DATA_SOURCE split-brain — sync push writes to Supabase (P0)
- `b4b3f6a` docs: session 105 assessment + log
