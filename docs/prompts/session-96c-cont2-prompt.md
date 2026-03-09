# Session 96c Continuation 2 — Fix Remaining Issues + Browser Verify

## Context
Session 96c-cont fixed the "0 identities" Fox Family bug by backfilling data to Supabase and adding community scoping for ALL communities (including Rhodes). Two deploys shipped: bd11424 and ad28af8.

**What shipped (96c-cont):**
- Supabase backfill: 2533 identities, 931 photos, 2633 photo_faces
- Community scoping for ALL communities (removed Rhodes exemption)
- Photo ID alias resolution in `_get_community_photo_ids`
- face_to_photo from photo_index.json for non-embedding faces
- Null name guard in `create_identity()` and `shadow_write_identities_batch`
- Upload pipeline Supabase sync after ingest
- Backfill script: `scripts/backfill_identities_to_supabase.py`

**Current state after deploy (ad28af8):**
- Rhodes: 775 identities, 85/86 confirmed showing (was 69, now nearly fixed)
- Fox Family: 1603 identities, 636 photos
- 1 confirmed identity still missing from Rhodes (investigate which one)

## Remaining Issues (from Nolan's feedback)

### P0: Fox Family admin view unreachable
- `/c/fox-family/` always shows the community landing page, even for admins
- Need: admin users should see the sidebar + to_review section, not the landing page
- The landing page redirect is at `page_routes.py:1818-1821`: non-Rhodes communities always show landing page when `section is None`
- Fix: admin users should get the admin view, not the landing page

### P0: Fox Family Photos page shows "0 photos" / "No photos found"
- Sidebar says 636 but the photos grid shows 0
- Root cause: `render_photos_section` at line 6745 filters `_photo_cache` by community_photo_ids
- `_photo_cache` uses SHA256 IDs, community_photo_ids has inbox_* IDs
- The alias resolution in `_get_community_photo_ids` was added but may need verification after deploy

### P1: 1 confirmed identity missing — David Capeloto (LOST DATA from previous session)
- Identity `e9ee215c` has face `inbox_aca56b9475f5` but:
  - Face not in photo_index.json face_to_photo
  - Photo `family_search_david_capeloto_declaration_of_intent_image.jpg` not in photo_index at all
  - File not on R2 (401), not on local disk
  - Provenance: job_id=658979c2, ingested 2026-03-07, source=inbox_ingest
  - The ingest created the identity + face but failed to write the photo_index entry and upload to R2
- **Action needed**: Re-ingest from original source (FamilySearch). The original image must be re-downloaded.
- This is NOT caused by Session 96c changes — it's a pre-existing incomplete ingest from Session 93 era.

### P1: Fox Family People page empty
- `/c/fox-family/people` shows no people (user reported)
- The People page likely loads confirmed identities, and Fox Family only has 1 confirmed
- This is correct behavior BUT should show the 1 confirmed identity

### P1: Notifications not community-scoped
- `/notifications` shows a test notification from Session 92: "Identity Confirmed: Unidentified Person 494"
- This test notification should be cleaned up (delete from Supabase)
- Nolan's feedback: notifications need clear UX boundaries between communities
- Either scope notifications to community context, or label which community they're from

### P1: Cross-community matches not showing
- Nolan expected Betty Capeluto Fox, Roland Fox, and Ray Franco to appear as cross-community matches
- The auto-clustering (Session 96b) found 35 matches (27 Roland, 4 Betty, 1 Ray Franco)
- These cluster results should be in proposals.json
- But they may not be visible in the current UI — the cluster review / upload review page needs investigation
- Where is the Upload Review page? It's in the Fox Family sidebar as "Upload Review"

### P2: "Photo not found" in Dismissed section (Rhodes)
- Clicking photos in the Dismissed section shows "Photo not found for this face"
- Affects REJECTED identities with inbox_* face IDs
- Root cause: the photo context modal uses a different lookup path than the main photos section

### P2: Face card size in Dismissed section too large
- Nolan: "the face cards in the dismissed section are not the same size as the rest of the app (they are so large it's hard to navigate)"
- Compare card sizing in `render_rejected_section` vs other sections

### P2: CONTESTED identity investigation
- Identity 224495e8: state=CONTESTED, face=Image 026_compress:face2
- Created via web with name=None (before name defaulting was added)
- This is the back of Betty Capeluto's head — Nolan previously rejected it
- Should be in Dismissed section, which it is. The null name was fixed.
- Nolan says this should be "dismissed" which matches CONTESTED/REJECTED behavior.

### P3: Community boundary UX
- Nolan: "We need to make sure we are being thoughtful in how all this is served and what the boundaries between communities are"
- Need clear visual indicators when content is from a different community
- Notifications, search results, and shared people should all show community labels

## Act 1: Fix Fox Family Admin View + Photos (15 min)
1. Fix non-Rhodes community landing page to allow admin section access
2. Verify Fox Family photos section shows 636 photos after alias resolution deploy
3. Verify Fox Family to_review shows faces

## Act 2: Verify All Sidebar Pages for Both Communities (10 min)
Browser verify every sidebar page for BOTH Rhodes and Fox Family:
- Rhodes: to_review, confirmed (People), dismissed, photos, discoveries
- Fox Family: to_review, confirmed (People), photos, discoveries, upload review, GEDCOM
- Check counts match expectations
- Check no cross-community leakage

## Act 3: Clean Up + Cross-Community Investigation (10 min)
1. Delete test notification (Unidentified Person 494)
2. Remove debug endpoint `/api/debug/community-ids`
3. Check proposals.json for cross-community cluster matches (Betty, Roland, Ray)
4. Find where Upload Review page is and verify it shows cluster results
5. Investigate 1 remaining missing confirmed identity

## Act 4: Assessment + Session Wrap (10 min)
1. Write assessment
2. Update CHANGELOG, ROADMAP, BACKLOG with all issues
3. Log all Nolan feedback as BACKLOG items

## Key Files
| File | What to check |
|------|---------------|
| `app/main.py:532` | `_get_community_photo_ids()` — alias resolution |
| `app/main.py:558` | `_get_community_identity_ids()` — photo-derived set |
| `app/main.py:3553` | `_build_caches()` — face_to_photo from photo_index |
| `app/page_routes.py:1818` | Community landing page redirect (needs admin fix) |
| `app/main.py:6703` | `render_photos_section()` — photo grid rendering |
| `app/page_routes.py:157` | Debug endpoint (REMOVE) |
| `data/proposals.json` | Cross-community cluster results |

## Nolan Feedback Log (MUST be preserved)
1. "Please make sure you don't lose any data" — Data integrity is top priority
2. "This needs to be the case that this doesn't fail every time I start a new community" — Upload pipeline must auto-sync to Supabase
3. "Clean all this up" — Remove debug endpoints, test notifications
4. "All communities going forward will always need scoping" — No more Rhodes exemptions
5. "Shouldn't there be at least two identities over both archives (Betty and Roland)?" — Cross-community matches expected
6. "What happened to Ray Franco and other ones you mentioned?" — Cluster results not visible
7. "Dismissed faces from Rhodesli showing up in Fox" — Fixed by community scoping
8. "Face cards in dismissed section are not the same size" — UX issue
9. "Please direct me to the post upload page that had the cluster review" — Upload Review in sidebar
10. "Notifications section — test notification should be reset" — Clean up test data
11. "If notifications is not community specific, needs UX to make it visible" — Community labels needed
12. "Going through each sidebar page for fox family" — Full browser audit needed
13. "Can't get to admin view for fox family" — Landing page blocks admin
14. "Fox Family people page not showing fox family people" — Investigate
15. "You are being thoughtful in how all this is served and boundaries between communities" — UX boundaries
