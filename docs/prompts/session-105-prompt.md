# Session 105 — Eliminate DATA_SOURCE Split-Brain (P0)

**Context:** docs/session_context/session-105-context.md
**Priority:** P0 — every future contributor upload will hit this bug
**Predecessor:** Session 104b (face tagging fix was symptom, this is the disease)

## The Problem

`DATA_SOURCE=postgres` on production means the app reads from Supabase. But the ingest pipeline and sync API write to JSON files. New photos are invisible on production until manually inserted into Supabase. This has caused 3 separate P0 incidents in Session 104/104b alone.

## Phase 0: Orient + Lesson (5 min)
1. Read `docs/session_context/session-105-context.md`
2. Read `tasks/lessons.md` and `tasks/lessons/data-lessons.md`
3. Add Lesson 144: DATA_SOURCE split-brain — ingest writes JSON, production reads Supabase. Every write path must cover BOTH.
4. Confirm current state: `make test-fast` passes

## Phase 1: Make `/api/sync/push` write to Supabase (30 min)
The sync push endpoint writes identities.json and photo_index.json to disk but doesn't update Supabase. When `DATA_SOURCE=postgres`, this means the pushed data is ignored.

1. In `app/sync_routes.py`, after writing each JSON file, also write to Supabase:
   - `identities` → call `shadow_write_identities_batch()` synchronously (not fire-and-forget)
   - `photo_index` → call `shadow_write_photos_batch()` synchronously
2. Make these writes SYNCHRONOUS — if Supabase fails, return an error (not silent swallow)
3. Add test: push endpoint updates Supabase when `DATA_SOURCE=postgres`
4. Verify: push data, then check Supabase has it

## Phase 2: Make shadow-writes reliable (30 min)
The `except: pass` pattern in shadow writes (Lesson 136) means Supabase failures are invisible.

1. In `app/supabase_data.py`, change `shadow_write_identity` and `shadow_write_photo`:
   - Log at ERROR level (not WARNING) on failure
   - Add a `strict=False` parameter. When `strict=True`, re-raise the exception
   - `save_registry()` and `save_photo_registry()` call with `strict=True` when `DATA_SOURCE=postgres`
2. Add a Sentry breadcrumb on every shadow-write failure so we see patterns
3. Add test: shadow-write failure with `strict=True` raises, with `strict=False` logs

## Phase 3: Auto-assign community on ingest (20 min)
When photos are ingested, they must be assigned to a community. Currently this is manual.

1. In `_background_ingest()` (app/upload_routes.py or app/main.py):
   - After creating photo records, call `add_photo_to_community(photo_id, community_id)`
   - Get the community from the request context (CommunityMiddleware sets it)
2. In `core/ingest_inbox.py` CLI path:
   - Add `--community` flag (default: "rhodes")
   - Auto-assign to the specified community after ingest
3. Add test: ingested photo appears in community photo set

## Phase 4: Startup parity check (15 min)
On app startup, verify JSON and Supabase are in sync.

1. In the startup event (after `init_railway_volume.py` runs):
   - Count photos in JSON vs Supabase
   - Count identities in JSON vs Supabase
   - If mismatch > 5%, log ERROR with counts
   - If mismatch > 0, log WARNING listing the missing IDs
2. Add health endpoint field: `"data_parity": {"photos_json": N, "photos_pg": M, "synced": true/false}`
3. Add test: parity check detects and reports mismatches

## Phase 5: Remove debug endpoint + regression tests (10 min)
1. Remove `/api/sync/debug-cache` endpoint (temporary from Session 104b)
2. Add integration test: full ingest → verify photo appears in Supabase AND community AND workstation grid
3. Add CI test: JSON photo count == Supabase photo count (catches future drift)
4. Update docs/assessments/session-105-assessment.md

## Phase 6: Verify + deploy (15 min)
1. Run full test suite
2. Deploy
3. Push test data via sync API
4. Verify: pushed photo appears in workstation grid on production
5. Verify: health endpoint shows `data_parity.synced: true`

## Verification Gate
- [ ] `/api/sync/push` writes to both JSON AND Supabase
- [ ] Shadow-write failures are visible (not swallowed)
- [ ] Ingested photos auto-assigned to community
- [ ] Startup parity check logs mismatches
- [ ] Health endpoint shows parity status
- [ ] Debug endpoint removed
- [ ] All tests pass
- [ ] Production browser verified

## Key Files
- `app/sync_routes.py` — sync push endpoint
- `app/supabase_data.py` — shadow writes, community assignments
- `app/main.py` — `_invalidate_all_caches()`, `load_photo_registry()`, `_background_ingest()`
- `app/upload_routes.py` — upload pipeline
- `core/ingest_inbox.py` — CLI ingest
- `scripts/init_railway_volume.py` — deploy startup sync

## Non-Goals
- Full migration to Supabase-only (Option A) — too large for one session
- Fixing egress budget (separate concern, OD-011)
- pgvector migration (deferred)
