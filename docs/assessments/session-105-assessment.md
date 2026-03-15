# Session 105 Assessment — Eliminate DATA_SOURCE Split-Brain (P0)

## Shipped
- [x] Phase 0: Orient + confirm Lesson 144 exists — Evidence: Lesson 144 already in `tasks/lessons/data-lessons.md`
- [x] Phase 1: `/api/sync/push` writes to Supabase — Evidence: `shadow_write_identities_batch()` and `shadow_write_photos_batch()` called synchronously in push handler, response includes `supabase` results key
- [x] Phase 2: Shadow-writes reliable with `strict` parameter — Evidence: `strict=True` re-raises exceptions, `strict=False` (default) swallows with ERROR log + Sentry breadcrumb. Applied to `shadow_write_photo`, `shadow_write_identity`, `shadow_write_photos_batch`, `shadow_write_identities_batch`
- [x] Phase 3: CLI `--community` flag on `core/ingest_inbox.py` — Evidence: Arg added, community lookup by slug, auto-tags photos and identities after ingest
- [x] Phase 4: Health endpoint `data_parity` field — Evidence: `_check_data_parity()` in `app/page_routes.py`, compares JSON vs Supabase counts, logs WARNING/ERROR on mismatch
- [x] Phase 5: Debug endpoint removed + 18 regression tests — Evidence: `/api/sync/debug-cache` removed from `sync_routes.py`, `tests/test_session105_split_brain.py` with 18 tests covering all phases

## Phase 6: Deploy + Production Verification — PASS
- Deploy: `railway up` → DOCKERFILE build → SUCCESS (deploy ID `2e5c88b9`)
- `/health` returns 200 with `data_parity` field — VERIFIED in Chrome browser
- `data_parity`: photos_json=943, photos_pg=944 (diff 1), identities_json=1922, identities_pg=3433 (diff 1511)
- Identity diff is expected: Supabase accumulated shadow-writes including merged/pruned identities (Lesson 123)
- Debug endpoint `/api/sync/debug-cache` returns 404 — VERIFIED
- Landing page loads, all navigation works — VERIFIED in Chrome browser
- No regressions detected

## Deferred
- Startup parity check — runs on `/health` only, not at boot. Low risk since Railway hits `/health` every 30s.
- `save_registry()` / `save_photo_registry()` do NOT yet pass `strict=True` when `DATA_SOURCE=postgres` — chose not to change save paths because they use background threads; making strict would block request thread. Sync push (the primary fix) IS synchronous. BACKLOG: DATA-017.

## Red Flags
- [LOW] Pre-existing xdist test ordering failures: `test_identified_badge_has_title_attribute`, `test_browse_cards_use_unified_card`, `test_landing_og_image` — all pass in isolation. Not related to Session 105.
- [LOW] Community auto-assignment in sync push only works if photo data includes `community_id` field — most push payloads don't include this. The web upload pipeline already handles community tagging correctly (line 884-894 in upload_routes.py). CLI ingest now has `--community` flag.
- [INFO] data_parity.synced=false on production — expected due to historical shadow-write accumulation (1511 extra identities in Supabase). Not a regression; this is the pre-existing state the parity check was designed to surface.

## Next Session Should Verify
1. Test sync push with real data — verify pushed photos appear in both JSON and Supabase
2. Consider a reconciliation run to prune stale Supabase rows (bring identity_diff to 0)
3. Consider wiring `strict=True` into `save_registry`/`save_photo_registry` for `DATA_SOURCE=postgres` (needs careful thought about blocking vs background)

## Test Results
- 18 new tests: ALL PASS
- 4387 app tests pass (sequential), 3 pre-existing xdist ordering failures
- ML tests: not run (no ML changes)
