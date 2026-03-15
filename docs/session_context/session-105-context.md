# Session 105 Context — Eliminate DATA_SOURCE Split-Brain

**Predecessor:** Session 104b (P0 face tagging fix)
**Priority:** P0 — blocks all future contributor uploads

## Problem Statement

The app has `DATA_SOURCE=postgres` on production but `DATA_SOURCE=json` locally. This creates a split-brain where:

1. **Ingest pipeline writes to JSON only** — `process_directory()` in `core/ingest_inbox.py` writes photos/identities to `photo_index.json` and `identities.json`. The post-ingest background sync in `_background_ingest()` shadow-writes to Supabase, but this is fire-and-forget with silent exception handling.

2. **`load_photo_registry()` reads from Supabase when `DATA_SOURCE=postgres`** — so any photo not in the Supabase `photos` table is invisible to `_build_caches()`, even if it's in `photo_index.json` on disk.

3. **`/api/sync/push` writes JSON only** — doesn't update Supabase. Pushing data from local doesn't reach the source of truth.

4. **`_invalidate_all_caches()` was missing 4 caches** — `_photo_registry_cache`, `_community_photo_ids_cache`, `_community_identity_ids_cache`, `_face_data_cache`. Fixed in Session 104b but the root cause remains.

5. **Community assignments are manual** — `photo_communities` must be populated for photos to appear in community-scoped views. No automatic assignment on ingest.

## Impact (Session 104b)

- Claude Benatar (real contributor) uploaded 2 photos with 20 faces
- Photos ingested locally, pushed to production via sync API
- Face tagging fixed (Supabase string-encoded anchor_ids)
- But photos invisible in workstation grid because:
  - Not in Supabase `photos` table → `load_photo_registry()` skipped them
  - Not in `photo_communities` table → community filter excluded them
  - `_invalidate_all_caches()` didn't clear `_photo_registry_cache` → stale metadata
- Required 4 separate debugging rounds to find all the gaps
- User said: "this is a really big oversight we were supposed to be explicitly building to avoid"

## Root Cause Analysis

The system was designed with JSON as source of truth (DATA_SOURCE=json). Session 93 flipped production to DATA_SOURCE=postgres. But the ingest pipeline, sync API, and several cache paths were never updated for the new data flow. The result:

```
LOCAL (DATA_SOURCE=json):
  ingest → writes JSON → reads JSON → works ✓

PRODUCTION (DATA_SOURCE=postgres):
  ingest → writes JSON → shadow-writes Supabase (fire-and-forget)
  load_photo_registry() → reads Supabase (ignores JSON)
  If shadow-write silently fails → photo invisible on production
```

## Audit Results (Session 104b)

| Write Path | JSON | Supabase | Gap |
|---|---|---|---|
| `save_registry()` | ✓ | ✓ (shadow) | Fire-and-forget, silent failures |
| `save_photo_registry()` | ✓ | ✓ (shadow) | Fire-and-forget, silent failures |
| `/api/sync/push` | ✓ | ✗ | **CRITICAL: doesn't write to Supabase** |
| `process_directory()` (ingest) | ✓ | ✗ (post-ingest sync) | Sync is in background thread |
| `photo_communities` assignment | ✗ | ✓ | No JSON fallback |
| `_invalidate_all_caches()` | N/A | N/A | Was missing 4 caches (fixed) |

Photos missing from Supabase after audit: 2 (fixed manually)
Photos missing from community: 0 (after Robert Mattatia fix)

## What Needs to Happen

### Option A: Make Supabase the ONLY write path (clean architecture)
- All writes go through Supabase
- JSON files become read-only caches rebuilt from Supabase
- `init_railway_volume.py` pulls from Supabase, not Docker bundle
- Ingest pipeline writes directly to Supabase
- **Pros:** Single source of truth, no split-brain possible
- **Cons:** Large refactor, Supabase egress concerns, offline ingest breaks

### Option B: Make shadow-writes reliable + add verification (pragmatic)
- Shadow-writes become synchronous (not fire-and-forget)
- `/api/sync/push` also writes to Supabase
- Add startup verification: compare JSON vs Supabase, log discrepancies
- Add community auto-assignment in ingest pipeline
- Add data integrity CI test: JSON photo count == Supabase photo count
- **Pros:** Incremental, doesn't break offline ingest
- **Cons:** Still dual-write, complexity remains

### Option C: Add Postgres CHECK + sync push writes to Supabase (minimum viable)
- `/api/sync/push` writes to Supabase in addition to JSON (immediate fix)
- Ingest pipeline auto-assigns community
- Add CI test for JSON/Supabase parity
- Postgres CHECK constraints already applied (Session 104b)
- **Pros:** Smallest change, fixes the immediate gap
- **Cons:** Doesn't address fire-and-forget reliability

## Recommendation

Option B with urgency. The fire-and-forget shadow writes with `except: pass` are the root of Lesson 136 and now Lesson 144. Making them synchronous + adding the sync push Supabase write + auto-community-assignment covers all the gaps found in Session 104b.

## Breadcrumbs
- Lesson 136: Fire-and-forget Supabase syncs with `except: pass` create invisible data loss
- Lesson 142: Supabase JSONB columns can silently store string-encoded arrays
- Lesson 143: Hook audit must be exhaustive
- Lesson 144: (to be added) DATA_SOURCE split-brain — ingest writes JSON, production reads Supabase
- AD-135: User-entered data must be in Supabase
- BACKLOG: DATA-013 (shadow-write reliability)
- Session 104b assessment: docs/assessments/session-104b-assessment.md
