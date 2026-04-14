# PRD-060: Self-Service Archive Creation (TOOLS-006)

**Status:** Specified
**Author:** Session 150
**Date:** 2026-04-14
**Related:** PRD-036 (workspace vision), PRD-035 (multi-community), WORKSPACE-001, TOOLS-002 (ML service)

---

## Problem Statement

Rhodesli has proven its value for the Rhodes and Fox Family archives, but expanding to new communities requires admin intervention: creating the community record, configuring R2 storage, uploading photos, and running the ML pipeline. Families who want to preserve their own photo collections have no self-service path. This bottleneck limits growth to communities where the admin is personally involved.

**Goal:** Any signed-up user can create a family photo archive, upload photos, get automatic face detection and date estimation, and share results with family members -- all without admin involvement.

---

## Builds On

- **WORKSPACE-001** (Sessions 122 + 133): `create_personal_archive()` in `app/supabase_data.py` already creates a `communities` row with `owner_id`, `is_personal=True`, `privacy='private'`, and an R2 prefix. Schema columns `owner_id`, `is_personal`, `privacy` exist.
- **Existing community middleware**: Routes already scope data by community slug (`/c/{slug}/...`).
- **ML service** (TOOLS-002, Sessions 115-118): Deployed on Railway. `detect_faces()` wrapper with fallback to local InsightFace. Upload pipeline calls it via `ML_SERVICE_URL`.
- **Upload pipeline**: `_background_ingest()` handles face detection, R2 upload, Supabase writes, and auto-clustering.
- **Gemini date estimation**: Batch and single-photo estimation via `rhodesli_ml/`.

---

## User Flows

### Flow 1: Create Archive

1. User signs up (existing flow) or logs in
2. From landing page or sidebar, user sees "Create Your Archive" CTA
3. User enters: archive name (required), description (optional)
4. System creates `communities` row: `owner_id=user.id`, `is_personal=False`, `slug=slugify(name)`, `admin_emails=[user.email]`, `r2_prefix=archives/{slug}`, `privacy='unlisted'`
5. User is redirected to `/c/{slug}/` (empty archive dashboard with upload prompt)

**Edge cases:** Duplicate slug (append random suffix), name too long (cap at 100 chars), user already has 3+ archives (rate limit).

### Flow 2: Upload Photos

1. From archive dashboard, user clicks "Upload Photos"
2. Drag-and-drop zone or file picker (reuse existing upload UI at `/c/{slug}/upload`)
3. Photos upload to R2 under `archives/{slug}/raw_photos/`
4. Existing `_background_ingest()` runs: face detection (ML service), Supabase writes, thumbnail generation
5. Progress shown via existing upload status polling
6. Results: photo grid populates, face counts shown in sidebar

**Constraints:** Max 50 photos per upload (free tier). Max 500 photos per archive (v1). File size limit 20MB per photo.

### Flow 3: ML Processing (Background)

After upload completes, the existing pipeline runs automatically:
1. Face detection via ML service (or local fallback)
2. Face crops generated and uploaded to R2
3. Cross-batch clustering creates identity proposals
4. Date estimation queued (Gemini, if configured)
5. Results surface in archive: face cards, identity groups, date labels on photos

No new ML code needed -- this reuses the existing pipeline. The archive owner sees the same triage UI that admins see today (speed-run, proposals, identify mode).

### Flow 4: Share with Family

1. Archive owner clicks "Share" on archive settings page
2. Gets a shareable URL: `rhodesli.nolanandrewfox.com/c/{slug}`
3. Privacy options: `private` (owner only), `unlisted` (anyone with link), `public` (discoverable)
4. Optional: generate invite link that grants viewer or contributor role
5. Family members visit the link, can browse photos, and optionally help identify faces

---

## Data Model

### Existing (no changes needed)

- `communities` table: `owner_id`, `is_personal`, `privacy`, `slug`, `name`, `description`, `admin_emails`, `r2_prefix`, `config` (JSONB)
- `photo_communities` table: links photos to communities
- `identity_communities` table: links identities to communities

### New Table: `archive_invites`

```sql
CREATE TABLE archive_invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    community_id UUID REFERENCES communities(id) NOT NULL,
    invite_code TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',  -- 'viewer', 'contributor', 'admin'
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ,
    max_uses INT,
    use_count INT DEFAULT 0
);
```

### New Column on `communities`

```sql
ALTER TABLE communities ADD COLUMN IF NOT EXISTS max_photos INT DEFAULT 500;
```

### Storage

Each archive gets its own R2 prefix: `archives/{slug}/raw_photos/` and `archives/{slug}/crops/`. This reuses the existing `r2_prefix` field on `communities` and the `get_photo_url()` / `get_crop_url()` functions in `core/storage.py` (which already support per-community prefixes).

---

## Scope

### v1 (3-4 sessions)
- Create archive flow (CTA, form, redirect)
- Upload photos to own archive (reuse upload UI + pipeline)
- Face detection runs automatically via ML service
- Share view-only link (privacy toggle)
- Archive owner sees triage UI (speed-run, proposals)
- Rate limits: 3 archives per user, 500 photos per archive, 50 per upload

### v1.1 (2 sessions)
- Date estimation on uploaded photos (Gemini, with cost guard)
- Face clustering results in triage UI
- Invite links with viewer/contributor roles
- Archive settings page (rename, description, delete)

### Deferred
- Cross-archive person matching (needs privacy consent model)
- GEDCOM upload per archive
- Collaborative editing (multiple admins per archive)
- Google Drive / bulk import integration
- Community discovery page (`/communities`)
- Billing / paid tiers

---

## Acceptance Criteria

- [ ] Logged-in user can create an archive from a CTA on the landing page
- [ ] Archive appears in user's sidebar immediately after creation
- [ ] User can upload 1-50 photos via drag-and-drop
- [ ] Uploaded photos appear in the archive's photo grid within 60 seconds
- [ ] Face detection runs automatically; face cards appear on photo pages
- [ ] Archive owner can toggle privacy between private/unlisted
- [ ] Unlisted archive is viewable by anyone with the URL
- [ ] Non-owner visitors see photos but cannot modify data
- [ ] Rate limits enforced: 3 archives, 500 photos, 50 per upload
- [ ] All data stored in Supabase (no JSON files)
- [ ] R2 storage uses per-archive prefix (no cross-archive file leaks)

---

## Risks and Dependencies

| Risk | Mitigation |
|------|-----------|
| ML service unavailable | Existing fallback to local InsightFace (AD-229) |
| R2 storage costs grow | Per-archive limits (500 photos). Monitor via R2 dashboard. |
| Abuse (spam archives) | Rate limit: 3 archives/user. Require verified email. Admin can disable. |
| Upload pipeline breaks | Existing upload tests + smoke tests cover this path |
| Permission leaks | Reuse existing `_check_admin` pattern, scoped to archive owner. Add community-owner permission check. |
| Supabase egress | Per-archive caches with TTL. Small archives = small payloads. |

---

## Estimates

| Phase | Sessions | Key Work |
|-------|----------|----------|
| v1: Core flow | 3-4 | Create archive, upload, face detection, share link |
| v1.1: Intelligence | 2 | Date estimation, clustering triage, invite links |
| Full feature | 6-8 | All of the above + settings, roles, delete |
