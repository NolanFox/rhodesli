# Session 159: Rhodesli Ingestion Contract

**Date**: May 11, 2026  
**Purpose**: Define the JSON contract that `rhodes-wiki` will produce for Session 161 to integrate into rhodesli's existing approval queue.

---

## 1. Photo Upload Entry Points

All photo uploads into rhodesli flow through **`/upload` (POST)** in `app/upload_routes.py:526`.

| HTTP Method | Route | Auth | Input | Status |
|---|---|---|---|---|
| POST | `/upload` | Login required | `files[]`, `source`, `collection`, `source_url`, `upload_community` (admin only) | 200 OK → pending or processing |

**Signature** (app/upload_routes.py:527-535):
```python
async def post(
    files: list[UploadFile],
    source: str = "",
    collection: str = "",
    source_url: str = "",
    upload_community: str = "",
    sess=None,
    request=None
):
```

**User Flows**:
- **Non-admin**: Upload → saved to `data/staging/{job_id}/` → R2 backup → pending_uploads.json entry → admin email notification → status="pending"
- **Admin (PROCESSING_ENABLED=true)**: Upload → saved to `data/staging/{job_id}/` → background thread spawns `core/ingest_inbox.py` → creates identities + photos → R2 upload → community tagging
- **Admin (PROCESSING_ENABLED=false)**: Upload → saved to `data/staging/{job_id}/` → entry in pending_uploads.json with status="staged"

**Community scoping** (app/upload_routes.py:571-605):
- Middleware defaults to `community_slug="rhodes"` (hardcoded fallback)
- Form field `upload_community` is source of truth for admins only
- Non-admins cannot override community (security fix Session 118)
- Resolved to `community_id` via `get_community_by_slug()` for background tagging

---

## 2. Identity & Face Creation

When admin approves a pending upload or admin uploads directly:

1. **Ingest Stage** (`core/ingest_inbox.py:process_directory()`):
   - Detects faces with InsightFace
   - Generates PFE embeddings
   - Creates `INBOX` identities via `IdentityRegistry.create_identity()` (one per detected face)
   - Each identity gets: `anchor_ids=[face_id]`, `state=INBOX`, auto-generated name "Unidentified Person N"

2. **Photo Registry** (`core/photo_registry.py`):
   - Registers each photo: `photo_id` → `{path, face_ids[], source, collection, source_url}`
   - Face-to-photo mapping stored in `_face_to_photo`

3. **Auto-Clustering** (`app/upload_routes.py:949-973`):
   - On upload completion, runs `cluster_new_faces.find_matches()` with `MATCH_THRESHOLD_HIGH`
   - Writes suggestions to `data/proposals.json` (NOT auto-applied—Lesson BUG-7)
   - Proposals await admin review in `/admin/proposals`

4. **Supabase Sync** (app/supabase_data.py:shadow_write_*):
   - Photos: upserted to `photos` table with `{photo_id, path, source, collection, source_url, upload_date, width, height, face_count, uploaded_by, job_id}`
   - Faces: upserted to `photo_faces` table with `{face_id, photo_id}` (one row per face per photo)
   - Identities: upserted to `identities` table with `{identity_id, name, state, anchor_ids[], candidate_ids[], metadata}`

---

## 3. Provenance Fields

Rhodesli tracks three **separate** provenance concepts on each photo:

| Field | Purpose | Set by | Editable | Example |
|---|---|---|---|---|
| `source` | Origin/donor | form input, ingest metadata | Yes (annotation) | "Newspapers.com", "Betty's Album" |
| `collection` | Classification/archive | form input, ingest metadata | Yes (annotation) | "Immigration Records", "Miami Collection" |
| `source_url` | Citation link | form input | Yes (photo metadata) | "https://newspapers.com/image/123" |
| `uploaded_by` | Actor who uploaded | session email | No | "admin@example.com" |
| `job_id` | Ingest job identifier | UUID prefix[:8] | No | "a1b2c3d4" |

**Storage**:
- PhotoRegistry (JSON): `photo_id` → `{path, source, collection, source_url, width, height, ...}`
- Supabase `photos` table: columns `{photo_id, path, source, collection, source_url, uploaded_by, job_id, upload_date, ...}`

---

## 4. Supabase Tables Touched

### Core Tables

| Table | Purpose | Upsert Keys | Relevant Columns |
|---|---|---|---|
| `photos` | Photo metadata | `photo_id` | `photo_id, path, source, collection, source_url, upload_date, width, height, face_count, uploaded_by, job_id` |
| `photo_faces` | Face-photo mapping | `(face_id, photo_id)` | `face_id, photo_id` |
| `identities` | Identity metadata | `identity_id` | `identity_id, name, state, anchor_ids[], candidate_ids[], metadata, created_at, updated_at` |
| `pending_uploads` | Upload queue | `job_id` | `job_id, user_id, status, filename, data (JSONB), reviewed_at, reviewed_by, rejection_reason` |

### Community Linking

| Table | Purpose | Upsert Keys | Relevant Columns |
|---|---|---|---|
| `photo_communities` | Photo→community many-to-many | `(photo_id, community_id)` | `photo_id, community_id` |
| `identity_communities` | Identity→community many-to-many | `(identity_id, community_id)` | `identity_id, community_id, is_primary` |
| `communities` | Community metadata | `id` (PK) | `id, slug, name, owner_id, is_personal, created_at` |

### Audit & Sync

| Table | Purpose | Insert Only | Relevant Columns |
|---|---|---|---|
| `audit_log` | Admin actions | N/A | `action, admin_email, target_id, details, created_at` |
| `gemini_api_calls` | Date/location API usage | N/A | `photo_id, endpoint, status, error, cost_usd, latency_ms` |

---

## 5. Pending Upload Approval Flow

**Route**: `POST /admin/pending/{job_id}/approve` (app/admin_routes.py:1180)

1. Admin clicks "Approve" on pending upload card
2. Status updated: `pending` → `approved`
3. If `PROCESSING_ENABLED=true`:
   - Files copied: `data/staging/{job_id}` → `data/uploads/{job_id}`
   - Background thread spawned: calls `core/ingest_inbox.process_directory()`
   - Results: photos + faces created, synced to Supabase
4. If `PROCESSING_ENABLED=false`:
   - Status stays `approved` but no processing (staged for local run)

**Metadata flow**:
- `source`, `collection`, `source_url` from pending upload → passed to `process_directory()` → stored in photo registry + Supabase
- `uploaded_by` (uploader email) → stored in pending_uploads.json + passed to ingest

---

## 6. Community Model

**Definition** (app/supabase_data.py:1550-1588):
- "Rhodes" is the default community (hardcoded fallback if lookup fails)
- Communities are rows in Supabase `communities` table: `{id UUID, slug text, name text, owner_id, is_personal bool}`
- Lookup by `slug` (cached 5 min TTL)

**Scoping Rules** (Session 107b, Lesson 108):
- Every photo must be tagged to at least one community (or "Rhodes" default)
- Upload form: hidden field `upload_community` defaults to middleware's `request.state.community_slug` (from URL prefix `/c/{slug}/`)
- Admin override: form field `upload_community` can override middleware (non-admin denied)
- After ingest: photos + identities added to community via `add_photo_to_community()` + `add_identity_to_community()`

**Cross-Community Matching** (Lesson 108):
- Confirmed faces from ANY community can match new INBOX faces (no filtering by community_id in clustering)
- Communities are filtering/display constructs, not ML barriers

---

## 7. Recommended Rhodes-Wiki JSON Contract

For Session 161, rhodes-wiki inbox entries should produce JSON files at `inbox/pending/{id}/post.json`:

```json
{
  "post_id": "facebook_post_12345",
  "post_url": "https://www.facebook.com/group/id/posts/12345",
  "source": "Rhodes Family Facebook Group",
  "collection": "Rhodes Family Photos",
  "uploaded_by": "facebook_sync_bot",
  "uploaded_at": "2026-05-11T14:30:00Z",
  "caption": "Family gathering 1985 at Miami beach",
  "date_estimate": "1985-06",
  "location_hint": "Miami Beach, Florida",
  "images": [
    {
      "image_id": "img_001",
      "filename": "post_12345_img1.jpg",
      "s3_url": "s3://rhodes-wiki-bucket/posts/12345/img1.jpg",
      "size_bytes": 245000,
      "width": 1024,
      "height": 768
    }
  ],
  "metadata": {
    "facebook_album": "Family Photos",
    "facebook_author": "Sarah Rhodes",
    "facebook_likes": 12,
    "facebook_comments": 3,
    "external_notes": "Posted in Rhodes Family group"
  }
}
```

**Mapping to Rhodesli**:
| rhodes-wiki field | → Rhodesli column | Notes |
|---|---|---|
| `images[].filename` | `photos.path` | Relative filename for registry |
| `source` | `photos.source` | Provenance label ("Rhodes Family Facebook") |
| `collection` | `photos.collection` | Classification ("Family Photos") |
| `post_url` | `photos.source_url` | Citation link to original post |
| `uploaded_by` | `photos.uploaded_by` | Actor (bot or user) |
| `uploaded_at` | `photos.upload_date` | Timestamp ISO 8601 |
| `caption` + `metadata` | Annotation or notes field | Future: attach to identity metadata |
| `date_estimate` | `date_labels` table (separate) | Gemini-estimated date |
| `location_hint` | `photo_locations` table (separate) | Gemini-estimated location |

---

## 8. Integration Recommendations for Session 161

**Cleanest approach** (opt for this):

1. Create a new Supabase table `rhodes_inbox_entries`:
   ```sql
   CREATE TABLE rhodes_inbox_entries (
     id UUID PRIMARY KEY,
     post_id TEXT NOT NULL,
     post_url TEXT,
     status TEXT DEFAULT 'pending',  -- pending, approved, rejected, processed
     job_id TEXT,  -- link to upload job_id after approval
     raw_data JSONB,  -- full rhodes-wiki JSON
     created_at TIMESTAMP DEFAULT NOW(),
     reviewed_at TIMESTAMP,
     reviewed_by TEXT
   );
   ```

2. New route `POST /admin/rhodes-inbox/{entry_id}/approve`:
   - Reads `inbox/pending/{entry_id}/post.json`
   - Converts to upload batch metadata
   - Calls **existing** `process_directory()` with:
     - `directory` = temp dir containing downloaded images
     - `source` = entry.source
     - `collection` = entry.collection
     - `source_url` = entry.post_url
     - `uploaded_by` = "rhodes_wiki_sync"
   - Result: photos + identities created via existing pipeline
   - Insert row to `rhodes_inbox_entries` with `status=processed`, `job_id={result.job_id}`

3. UI in `/admin/rhodes-inbox`:
   - List pending entries from `inbox/pending/*/post.json`
   - Preview: image thumbnails + caption + source info
   - "Approve" button → POSTs to `/admin/rhodes-inbox/{entry_id}/approve`
   - "Reject" button → moves to `inbox/rejected/{entry_id}/`

**Why this works**:
- Reuses 100% of existing ingest logic (`process_directory`, photo registry, Supabase sync)
- No duplication of face detection, clustering, or community tagging
- Single table tracks rhodes-wiki provenance separately from general uploads
- Audit trail via `audit_log` (existing)

**Gotchas to watch**:
- Lesson 146: Orphaned faces if photo detection fails partway through batch (handle gracefully)
- Lesson 168: Auto-side-effects (clustering, R2 upload) trigger immediately—OK for batch ops
- Lesson 108: Always tag to "Rhodes" community by default (pass `community_slug="rhodes"` to `process_directory`)

---

## References

- **Upload routes**: `/Users/nolanfox/rhodesli/app/upload_routes.py:526-1000`
- **Ingest pipeline**: `/Users/nolanfox/rhodesli/core/ingest_inbox.py:1242-1669`
- **Photo registry**: `/Users/nolanfox/rhodesli/core/photo_registry.py:41-300`
- **Identity registry**: `/Users/nolanfox/rhodesli/core/registry.py:123-300`
- **Supabase sync**: `/Users/nolanfox/rhodesli/app/supabase_data.py:582-890`
- **Admin approval**: `/Users/nolanfox/rhodesli/app/admin_routes.py:1180-1300`
- **Community model**: `/Users/nolanfox/rhodesli/app/supabase_data.py:1512-1790`

---

**Deliverable for Session 161**: This contract defines the exact JSON shape rhodes-wiki should produce and the cleanest integration point (reuse `process_directory`). Session 161 can now build the `/admin/rhodes-inbox` route with confidence that it feeds the existing approval queue.

