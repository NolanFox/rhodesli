# Session 105b Assessment — Data Integrity Final Fix

## Shipped
- [x] Phase 0: Orient — `make test-fast` passes (1 pre-existing xdist flake), `/health` data_parity confirmed
- [x] Phase 1: Production reconciliation — audit=0 stale identities, 1 stale photo pruned, photos_pg now matches photos_json (943). Identity parity fix: health uses include_merged=True
- [x] Phase 2: Startup parity check — `_startup_parity_check()` in background thread, logs WARNING on drift, ERROR on >100 stale rows
- [x] Phase 3: Structural prevention tests — 8 tests in `tests/test_data_parity_invariants.py` covering all 4 write paths, no-bare-except, health parity, startup check
- [x] Phase 4: AD-225 written — Write-Through Architecture for Dual-Store Data Integrity
- [x] Phase 5: CHANGELOG v0.99.9, ROADMAP Recently Completed, session log, assessment updated
- [x] Phase 6: All tests pass, deployed, browser verified

## Prior Session Shipped (105b first half)
- [x] photo_faces write gap closed — `shadow_write_photo_faces_batch()` in ALL 4 write paths
- [x] save_registry() + save_photo_registry() postgres paths made synchronous with strict=True
- [x] JSON always written as backup first
- [x] Upload pipeline uses logging.error instead of print()
- [x] Reconciliation endpoint + CLI script
- [x] 10 regression tests + Lesson 145 + BACKLOG DATA-014

## Key Finding
The 1,511 "stale identity" count on /health was a false alarm — it compared active identities (1922) vs all Supabase identities (3433 including merged). The reconcile audit confirmed 0 actual stale rows. Fixed by using `include_merged=True`.

## Red Flags
- [LOW] 1 pre-existing xdist ordering flake (test_person_page_no_admin_bar_anonymous) — passes alone, fails in parallel. Not a regression.

## Verification Gate
- [x] `/api/sync/push` writes to both JSON AND Supabase
- [x] Shadow-write failures are visible (not swallowed)
- [x] `photo_faces` written in ALL write paths
- [x] `save_registry()` postgres path is synchronous
- [x] `save_photo_registry()` postgres path is synchronous
- [x] JSON always written as backup
- [x] Ingested photos auto-assigned to community
- [x] Startup parity check logs mismatches
- [x] Health endpoint shows parity status (with correct include_merged comparison)
- [x] Production stale rows pruned (1 photo)
- [x] Structural prevention tests exist (8 tests)
- [x] AD-225 entry written
- [x] CHANGELOG updated
- [x] Debug endpoint removed (prior session)
- [x] All tests pass
- [x] Production browser verified
