# Session 96e-cont9 — Stabilize Production + Data Integrity Audit

## Context
This is a MANDATORY stabilization session. The app has multiple data integrity issues
that prevent the user from doing basic work (identifying faces, sorting photos, creating
identities). Nothing else matters until these are fixed and verified.

- **Predecessor**: Session 96e-cont8 (docs/assessments/session-96e-cont7-assessment.md)
- **User feedback**: "every single part of the upload process is broken", "data destruction",
  "regressions popping up faster than I can give feedback", "faces should not be dropping
  in and out of confirmed states without logging, supabase records, and provenance"
- **Weekly usage**: User at 98% (resets Thursday night). Session must be efficient.

## Phase 0: Deploy Verification (BLOCKING — do this first)

1. Check deploy status: `mcp__railway-mcp-server__list-deployments` (limit 1, json true)
2. If still INITIALIZING: trigger new deploy via `mcp__railway-mcp-server__deploy`
3. Wait for SUCCESS status with `builder: "DOCKERFILE"`
4. If Railway incident persists (check status.railway.com), document and work on code fixes

## Phase 1: Trigger Resync + Verify All Fixes

After deploy is SUCCESS:

1. In browser (admin logged in), run:
   ```js
   fetch('/api/sync/resync-supabase', {method: 'POST'}).then(r => r.json())
   ```
2. Verify response has:
   - `orphan_faces_repaired > 0` (creates INBOX identities for faces without one)
   - `upload_date_backfilled >= 0`
3. Verify **Create Identity**: Navigate to a Congo Benatar photo, click a face, type a name,
   click "Create". Must succeed (200), not 404.
4. Verify **Upload Sort**: Navigate to `/?section=photos&sort_by=upload_newest`.
   The 6 recently uploaded photos (Halfon, Benatar, Congo photos, Isaac graves, Facebook
   Holocaust photos) must appear at the TOP, not the bottom.
5. Verify **Person 2973**: Navigate to `/person/8e44e38b-fea0-4e34-8c6e-0f3e40862e9b`.
   Must be SKIPPED state (was incorrectly CONFIRMED, reverted in cont8).
6. Verify **Fox Family community**: Navigate to `/c/fox-family/`. Check sidebar counts
   make sense. People page should show Roland Fox only (my test identity was reverted).

## Phase 2: Data Integrity Audit

### 2a: Find how Person 2973 got CONFIRMED
- Check `identity_routes.py` auto-confirm paths (line 1017-1019 in create-identity)
- Check startup sync code: "applied 1000 identity overrides from Supabase" — does this
  accidentally set states? Read the startup sync function.
- Check `group_inbox_identities()` — does it change state?
- Check `cluster_new_faces.py` — does auto-cluster change state?
- Document root cause and add guard if needed.

### 2b: Audit all state-change paths
Every place that changes identity state (INBOX→CONFIRMED, etc.) must:
1. Log the change with timestamp and source
2. Write to Supabase (not just JSON)
3. Have clear provenance (who/what triggered it)

Find ALL paths that call `registry.confirm_identity()` or modify state directly.
Ensure each has provenance tracking. If any path can silently confirm without
user action, fix it.

### 2c: Orphan face prevention
The orphan face bug (faces in photo_index without identities) must not recur.
- Audit `process_single_image()` in `core/ingest_inbox.py` — does it always create an identity?
- Add a post-ingest validation: count faces in photo_index vs identities. If mismatch, log ERROR.
- The resync repair is a safety net, not a fix. The pipeline must not create orphans.

## Phase 3: Communities Verification

Verify both communities work end-to-end:

### Rhodes (`/`)
- [ ] Photos page loads, sort works
- [ ] Create Identity works on an unidentified face
- [ ] People page shows correct confirmed count
- [ ] Discoveries page loads (0 is OK if no proposals match confirmed)

### Fox Family (`/c/fox-family/`)
- [ ] Photos page loads (should show ~635 photos)
- [ ] Create Identity works
- [ ] People page shows Roland Fox only (not Person 2973 or "Test")
- [ ] New Matches count reasonable (~1014)
- [ ] Upload works: upload a test photo, verify face detection, verify identity created

## Phase 4: Upload Pipeline E2E Test

Upload ONE test photo through the web UI to verify the full pipeline:
1. Go to `/c/fox-family/` → Upload
2. Upload a single photo
3. Wait for processing to complete
4. Verify: photo appears in Photos grid
5. Verify: faces detected (bounding boxes visible)
6. Verify: INBOX identities created for each face (can click face → tag name → Create)
7. Verify: photo appears in "Upload Date (Newest)" sort at top
8. Verify: identity appears in Fox Family community

## Phase 5: Session Outputs

- Update assessment with all verification results
- Update SESSION_LOG.md
- Add lesson about production API testing and data provenance
- BACKLOG entry for identity state change audit trail (if not already exists)

## Key Files
- `app/sync_routes.py` — resync endpoint with orphan repair + cache fix
- `app/upload_routes.py:795` — _background_ingest pipeline
- `app/identity_routes.py:967` — create-identity endpoint
- `core/ingest_inbox.py:1031` — process_directory
- `app/main.py:6387` — _compute_discoveries
- `app/main.py:3594` — _build_caches (reads upload_date from JSON)

## Commits from cont8 (already pushed)
- `7545545` — fix(sync): invalidate ALL caches in resync endpoint
- `10914ce` — fix(sync): repair orphan faces + full cache invalidation
- `9c2e9c3` — docs: cont8 assessment

## User Feedback Summary (MUST address all)
1. Upload sort broken — recently uploaded photos at bottom not top → Fixed in code, needs deploy
2. Create Identity 404 — silent failure, nothing happens → Fixed in code, needs deploy + resync
3. 0 Discoveries — expected if no proposals match confirmed, but user noticed
4. Person 2973 auto-confirmed — state changed without user action → Reverted, need root cause
5. "Data destruction" — faces dropping in/out of confirmed without provenance → Need audit
6. Communities must work — both Rhodes and Fox Family need E2E verification
7. "Faces should not drop in/out of confirmed without logging, supabase records, provenance"
8. Upload pipeline must be fully working going forward — no more orphan faces
9. App must be stable enough for user to work through existing photos on both communities
