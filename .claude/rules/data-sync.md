---
paths:
  - "scripts/push_to_production.py"
  - "scripts/sync_from_production.py"
  - "scripts/download_staged.py"
  - "scripts/process_uploads.py"
  - "app/main.py"
---

# Data Sync Rules

## Push-to-Production Safety
1. **Never blind-overwrite production data.** `push_to_production.py` fetches production state and merges before pushing. Production wins on conflicts (state changes, name changes, face set changes, merges, rejections).
2. **sync before ML work**: Every ML session MUST start with `python scripts/sync_from_production.py` to get fresh data from production.
3. **Route handlers must use canonical save functions** (`save_registry()`, `save_photo_registry()`), never call `.save()` directly — bypasses test mocks and can corrupt real data (Lesson #48).

## Cache Invalidation
4. After any data write in a route handler, invalidate the relevant caches:
   - `_photo_registry_cache` + `_face_data_cache` for photo data
   - `_proposals_cache` for proposals.json
   - `_annotations_cache` for annotations

## Staging Lifecycle
5. Staging jobs follow: STAGED → APPROVED → PROCESSED. Mark jobs processed via `POST /api/sync/staged/mark-processed` after pipeline completion.

## Sync API Endpoints
- `GET /api/sync/status` — public status
- `GET /api/sync/identities` — requires Bearer token
- `GET /api/sync/photo-index` — requires Bearer token
- `POST /api/sync/push` — requires Bearer token, writes data + invalidates caches
- `POST /api/sync/staged/mark-processed` — requires Bearer token
