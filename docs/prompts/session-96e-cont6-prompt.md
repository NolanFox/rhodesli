# Session 96e-cont6: Fix Upload Pipeline — 9 Bugs

## Predecessor
Session 96e-cont5. See `docs/session_context/session-96e-cont5-upload-bugs.md` for full investigation.

## User Feedback (verbatim)
- "It looks like Facial detection was not run on the photos" — Actually it WAS run (logs show "2 faces extracted"). The issue is faces aren't visible in the UI because dimensions are missing from Supabase (BUG-2, caused by BUG-1 Supabase sync crash).
- "The upload data is not present in the photo view" — uploaded_by and upload_date not passed to process_directory (BUG-3).
- "The faces aren't showing up in the photo view" — Face overlay boxes require dimensions (BUG-2).
- "The sorting for Upload Newest is in reverse order" — upload_date is NULL because not passed (BUG-3/4).
- "The faces aren't showing up in new matches" — Need to verify. New Matches shows 358 but user can't find the newly uploaded faces. May be identity tagging issue (BUG-8).
- "Discoveries still seems non functional" — Shows 0 despite auto-cluster finding 13 matches (BUG-7).
- "is it logging who uploaded this, in this case me?" — No, uploaded_by not passed (BUG-3).
- "Source: Facebook" displayed twice in photo context modal (BUG-5).

## Screenshots to review (saved on disk)
Review these in the continuation session to extract any additional issues:
- `/var/folders/3l/m8xry57s49x2hz932q7xvffr0000gn/T/TemporaryItems/NSIRD_screencaptureui_rqq0DH/Screenshot 2026-03-10 at 12.07.20 PM.png` — Immigration Records, 1 photo only (before backfill)
- `/var/folders/3l/m8xry57s49x2hz932q7xvffr0000gn/T/TemporaryItems/NSIRD_screencaptureui_U080zY/Screenshot 2026-03-10 at 12.37.42 PM.png` — Photo Context modal: dimensions unavailable, no face descriptions, duplicate source
- `/var/folders/3l/m8xry57s49x2hz932q7xvffr0000gn/T/TemporaryItems/NSIRD_screencaptureui_qxim2n/Screenshot 2026-03-10 at 12.37.52 PM.png` — Holocaust collection: 2 photos with "1 face" badges
- `/var/folders/3l/m8xry57s49x2hz932q7xvffr0000gn/T/TemporaryItems/NSIRD_screencaptureui_licNCQ/Screenshot 2026-03-10 at 12.38.11 PM.png` — All Photos sorted "Estimated Date (Newest)": old photos at top, 278 total
- `/var/folders/3l/m8xry57s49x2hz932q7xvffr0000gn/T/TemporaryItems/NSIRD_screencaptureui_b2LpYN/Screenshot 2026-03-10 at 12.38.27 PM.png` — New Matches: 358 unmatched, Person 4099 at top
- `/var/folders/3l/m8xry57s49x2hz932q7xvffr0000gn/T/TemporaryItems/NSIRD_screencaptureui_TzHz66/Screenshot 2026-03-10 at 12.38.45 PM.png` — Photos scrolled down: recent uploads at BOTTOM
- `/Users/nolanfox/Desktop/Screenshot 2026-03-10 at 12.36.18 PM.png` — Upload page: "2 faces extracted from 2 images, 2 added to Inbox"
- `/var/folders/3l/m8xry57s49x2hz932q7xvffr0000gn/T/TemporaryItems/NSIRD_screencaptureui_hn9536/Screenshot 2026-03-10 at 12.41.20 PM.png` — Discoveries: 0 matches, "All discoveries reviewed!"
- Photo Context with face overlays working (uriel_galante) — proves overlays work when dimensions exist

## Phase 0: Orient
Read `docs/session_context/session-96e-cont5-upload-bugs.md` for the full 9-bug investigation.

## Phase 1: Fix BUG-1 — Supabase sync crash (CRITICAL)
**Error**: `'list' object has no attribute 'get'`
**Location**: `app/upload_routes.py:984-989`
**Investigation**:
1. Check what `load_identities()` from `scripts/cluster_new_faces.py` returns
2. Check what `apply_suggestions()` returns and what gets written to identities.json
3. The issue is likely that `json_registry._identities` iterates over items that include non-dict values
4. Fix the iteration to handle the data structure correctly
**Test**: Upload a photo locally with PROCESSING_ENABLED=true, verify Supabase sync succeeds

## Phase 2: Fix BUG-3 — uploaded_by and upload_date not passed
**Location**: `app/upload_routes.py` line ~814 in `_background_ingest()`
**Fix**: Add `uploaded_by=uploader_email, upload_date=datetime.now(timezone.utc).isoformat()` to the `process_directory()` call
**Test**: Upload a photo, verify photo_index.json has uploaded_by and upload_date fields

## Phase 3: Fix BUG-8 — Identity community tagging loads from wrong source
**Location**: `app/upload_routes.py:955` — `registry = _main_mod.load_registry()` loads from Postgres
**Fix**: Change to `registry = IdentityRegistry.load(data_path / "identities.json")`
**Also**: For `get_identity_for_face`, need a local version that searches the JSON registry, not the Postgres one.
**Test**: Upload a photo, check logs show "Tagged N identities to community" where N > 0

## Phase 4: Fix BUG-5 — Duplicate "Source: Facebook" display
**Location**: `app/page_routes.py` in photo context modal rendering
**Fix**: Find and remove the duplicate source line
**Test**: Open Photo Context for any photo, verify source appears only once

## Phase 5: Investigate BUG-7 — Discoveries empty
**Investigation**:
1. Check proposals.json on production via sync API
2. Check discoveries route filtering logic
3. Determine if proposals format matches what discoveries expects
4. Check if the proposals generated by auto-cluster in the upload pipeline are the right format

## Phase 6: Deploy + Browser Verify
1. `railway up` to deploy
2. Upload a new test photo
3. Verify in browser:
   - Photo appears in correct collection
   - Face overlays visible in Photo Context
   - Dimensions shown
   - uploaded_by and upload_date present
   - Sort "Upload Date (Newest)" shows new photo at top
   - Source not duplicated
   - New Matches includes the new faces
   - Discoveries shows matches (if any to confirmed identities)

## Verification Gate
- [ ] All 7 fixable bugs addressed
- [ ] Tests pass (make test-fast)
- [ ] Deploy SUCCESS
- [ ] Browser verification of upload end-to-end
- [ ] Session log updated
- [ ] Assessment written
