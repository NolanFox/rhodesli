# Session 105b Continuation — Complete Data Integrity Closeout

**Context:** docs/session_context/session-105b-context.md
**Predecessor assessment:** docs/assessments/session-105b-assessment.md
**Priority:** P0 — this must be the last session we ever work on split-brain

## Background

Session 105 + the first half of 105b shipped code fixes for the DATA_SOURCE split-brain. The code is deployed but the session was not properly completed. This continuation finishes everything.

## What is already deployed (DO NOT re-implement)
- `/api/sync/push` writes to Supabase alongside JSON (Session 105)
- `shadow_write_photo_faces_batch()` wired into all 4 write paths (105b)
- `save_registry()` and `save_photo_registry()` postgres paths are synchronous with `strict=True` (105b)
- Both save functions always write JSON as backup first (105b)
- Upload pipeline uses `logging.error` instead of `print()` for Supabase sync failures (105b)
- `shadow_write_*` functions have `strict` parameter, log at ERROR, add Sentry breadcrumbs (105)
- `/health` endpoint has `data_parity` field comparing JSON vs Supabase counts (105)
- `/api/admin/reconcile` endpoint: audit, backfill, prune actions (105b)
- `scripts/reconcile_supabase.py`: CLI audit/export/prune/backfill (105b)
- CLI `--community` flag on `core/ingest_inbox.py` (105)
- Debug endpoint `/api/sync/debug-cache` removed (105)
- Lesson 144 (split-brain) + Lesson 145 (photo_faces write gap) added
- BACKLOG DATA-014 updated
- 28 new tests across `test_session105_split_brain.py` + `test_session105b_write_through.py`

## What must be done in this session

### Phase 0: Orient (5 min)
1. Read this prompt, the context file, and both assessments
2. Read `tasks/lessons.md`
3. Confirm `make test-fast` passes (known pre-existing: `test_identified_badge_has_title_attribute` xdist ordering)
4. Verify deploy is live: `curl https://rhodesli.nolanandrewfox.com/health` — confirm `data_parity` field exists

### Phase 1: Execute production reconciliation (15 min)
The 1,511 stale Supabase identity rows must be pruned. This is non-destructive — the endpoint exports all rows before deleting.

1. In Chrome browser (admin is logged in), hit `/api/admin/reconcile?action=audit` — record the exact counts
2. Hit `/api/admin/reconcile?action=prune&confirm=true` — this exports stale rows to `data/reconcile_export.json` on the Railway volume, then deletes them
3. Verify `/health` shows `data_parity.synced: true` (or close to it — small diffs are OK if explainable)
4. Verify landing page still loads, photos visible, no regressions
5. If prune fails or causes issues: the stale rows are just extra data, they don't break anything. Document the failure and move on.

### Phase 2: Startup parity check (15 min)
The original Session 105 prompt asked for a parity check on app startup, not just on `/health`. This was never implemented.

1. Add `_startup_parity_check()` in `app/main.py`, called from the startup event
2. It should run `_check_data_parity()` from `page_routes.py` in a background thread (don't block startup)
3. If photos differ: log WARNING, auto-backfill missing photos from JSON → Supabase
4. If identities in JSON > PG: log WARNING, auto-backfill missing identities
5. If identities in PG > JSON by >100: log ERROR (stale rows detected, needs admin reconcile)
6. Never auto-prune (deletion requires explicit admin action)
7. Add test: startup parity check logs warning on mismatch

### Phase 3: Structural prevention tests (15 min)
Add tests that prevent future split-brain regression:

1. `tests/test_data_parity_invariants.py`:
   - Scan `save_photo_registry()` source — assert it calls both `shadow_write_photos_batch` AND `shadow_write_photo_faces_batch`
   - Scan `save_registry()` source — assert it calls `shadow_write_identities_batch`
   - Scan `_background_ingest()` source — assert it calls `shadow_write_photo_faces_batch`
   - Scan `/api/sync/push` handler source — assert it calls `shadow_write_photo_faces_batch`
   - Scan `supabase_data.py` — assert NO `except Exception` blocks use bare `pass` (must at minimum log)
2. These are structural tests — they read source code and verify patterns. They catch if someone removes a write path in a future session.

### Phase 4: AD entry + harness documentation (10 min)
1. Add AD-XXX to `docs/ml/ALGORITHMIC_DECISIONS.md`:
   - Title: Write-Through Architecture for Dual-Store Data Integrity
   - Decision: When DATA_SOURCE=postgres, Supabase is primary write (synchronous), JSON is always-written backup. photo_faces written alongside photos. Parity check on /health + startup.
   - Context: 3 P0 incidents in Session 104/104b from split-brain. Root cause: write paths diverged from read paths.
   - Alternatives considered: Full Supabase-only (too large), outbox pattern (over-engineering), dual-write with eventual consistency (current, improved)
2. Update `docs/session_context/session-105b-context.md` with what was actually done

### Phase 5: Update all harness docs (10 min)
1. Update `CHANGELOG.md` with Session 105 + 105b entries
2. Update `ROADMAP.md` — mark relevant items complete, add any new items
3. Update `docs/session_logs/session-105b-log.md` with final state
4. Update `docs/assessments/session-105b-assessment.md` — mark all phases as shipped or properly deferred
5. Verify `docs/roadmap/SESSION_HISTORY.md` has Sessions 105 + 105b

### Phase 6: Full verification gate (15 min)
1. Run `make test-fast` — all new tests must pass
2. Run both session 105 test files: `pytest tests/test_session105_split_brain.py tests/test_session105b_write_through.py -x -q`
3. Deploy if any code changed
4. Browser verify on production:
   - `/health` — `data_parity.synced` should be `true` (or near-true)
   - Landing page loads with photos
   - Person pages load
   - No console errors
5. Final git status must be clean

## Verification Gate Checklist (from original Session 105 prompt + 105b additions)
- [ ] `/api/sync/push` writes to both JSON AND Supabase ← already done
- [ ] Shadow-write failures are visible (not swallowed) ← already done
- [ ] `photo_faces` written in ALL write paths ← already done
- [ ] `save_registry()` postgres path is synchronous ← already done
- [ ] `save_photo_registry()` postgres path is synchronous ← already done
- [ ] JSON always written as backup ← already done
- [ ] Ingested photos auto-assigned to community ← already done (CLI flag + web upload)
- [ ] Startup parity check logs mismatches ← Phase 2
- [ ] Health endpoint shows parity status ← already done
- [ ] Production stale rows pruned ← Phase 1
- [ ] `data_parity.synced` is true (or close) on production ← Phase 1
- [ ] Structural prevention tests exist ← Phase 3
- [ ] AD entry written ← Phase 4
- [ ] CHANGELOG updated ← Phase 5
- [ ] Debug endpoint removed ← already done
- [ ] All tests pass ← Phase 6
- [ ] Production browser verified ← Phase 6

## Key Files
- `app/sync_routes.py` — reconcile endpoint (deployed, needs to be executed)
- `app/main.py` — startup event (needs parity check addition)
- `app/page_routes.py` — `_check_data_parity()` (already exists)
- `tests/test_data_parity_invariants.py` — structural tests (to create)
- `docs/ml/ALGORITHMIC_DECISIONS.md` — AD entry (to add)
- `CHANGELOG.md` — needs Session 105/105b entry

## Non-Goals
- Full migration to Supabase-only
- Egress budget optimization
- Fixing pre-existing flaky xdist tests (separate concern)
