# Session 105b Context — Data Integrity Final Fix

**Predecessor:** Session 105 (sync push Supabase write)
**Priority:** P0 — platform data reliability is existential

## Problem Statement

Session 105 fixed the sync push endpoint but left 4 critical gaps:

### Gap 1: photo_faces table never written after migration
- `PhotoRegistry.load_from_postgres()` reads `photo_faces` for face-to-photo mapping
- But NO write path populates `photo_faces` — not `save_photo_registry()`, not `_background_ingest()`, not `/api/sync/push`
- Only the one-time migration script (`scripts/migrate_core_tables.py`) ever wrote to it
- New uploads get faces in JSON + `photos` table but NOT `photo_faces`
- Result: face-to-photo mapping incomplete on production

### Gap 2: save_registry() uses background thread for Supabase writes
- `save_registry()` line 1161: `threading.Thread(target=_background_postgres_save, ...).start()`
- If thread fails, data silently lost on next cache reload (120s TTL)
- `save_photo_registry()` line 3350-3362: same pattern

### Gap 3: 1,511 stale Supabase identity rows
- identities_json=1922 vs identities_pg=3433
- photos_json=943 vs photos_pg=944
- Accumulated from shadow-writes of merged/pruned identities
- Harmless but makes parity check noisy

### Gap 4: Upload pipeline Supabase sync uses print() error handling
- `_background_ingest()` lines 1016-1017: `except Exception as e: print(f"...")`
- Silent failure path

## Architecture Decision: Write-Through with JSON Backup
- When DATA_SOURCE=postgres: Supabase is primary write, JSON is backup
- Writes are synchronous (not background thread)
- If Supabase fails: log ERROR + Sentry, write JSON, surface to admin
- Reconciliation endpoint for manual drift recovery

## Key Files
- `app/main.py:1107` — save_registry()
- `app/main.py:3341` — save_photo_registry()
- `app/supabase_data.py:760` — shadow_write_photos_batch()
- `app/upload_routes.py:990` — _background_ingest() Supabase sync
- `app/sync_routes.py:486` — /api/sync/push Supabase write
- `core/photo_registry.py:344` — load_from_postgres() reads photo_faces

## Breadcrumbs
- Lesson 123: Additive-only shadow sync is not reconciliation
- Lesson 136: Fire-and-forget Supabase syncs create invisible data loss
- Lesson 144: DATA_SOURCE split-brain
- BACKLOG: DATA-013 (proposals sync), DATA-014 (silent sync failures), DATA-015 (dead sync functions)
- AD-135: User-entered data must be in Supabase
