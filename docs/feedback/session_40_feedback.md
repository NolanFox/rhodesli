# Session 40 Production Walkthrough Feedback

**Date:** 2026-02-17
**Source:** Admin production walkthrough
**Reporter:** Nolan Fox (admin)

---

## CRITICAL

### FB-40-01: /map returns Internal Server Error
- **Page:** /map
- **Expected:** Interactive map with 267 geocoded photos
- **Actual:** 500 Internal Server Error
- **Root Cause:** Missing `_build_caches()` call — `_photo_cache` is `None`, all photo lookups fail
- **Status:** FIXING

### FB-40-02: /connect returns Internal Server Error
- **Page:** /connect
- **Expected:** Six Degrees connection finder
- **Actual:** 500 Internal Server Error
- **Root Cause:** `registry.get_identity()` raises `KeyError` on invalid/missing IDs, but code uses `or {}` pattern expecting `None` return
- **Status:** FIXING

### FB-40-03: Collection/Source metadata confusion
- **Page:** /collections, photo detail pages
- **Expected:** Collection tied to "Jews of Rhodes: Family Memories & Heritage" Facebook group
- **Actual:** 116 photos show under "Community Submissions" collection
- **Root Cause:** Photos ingested in Session 26 batch with `collection: "Community Submissions"`. 4 Facebook photos have correct metadata but files stranded in `raw_photos/pending/batch_facebook/`
- **Status:** INVESTIGATING

---

## HIGH

### FB-40-04: Sharing needs to be more prominent and intuitive
- **Context:** Sharing is how Rhodesli grows — every shareable view needs one-click share with clean standalone URL
- **Specific issues:**
  - Help Identify share goes to source photo, not standalone identification page
  - No per-person "Can you identify this person?" shareable page
  - No specific match confirmation shareable page
- **Solution:** Create /identify/{id} and /identify/{a}/match/{b} pages

### FB-40-05: Person page "Return to Inbox" visible to public
- **Page:** /person/{id}
- **Expected:** Public-facing page without admin actions
- **Actual:** "Return to Inbox" button visible on shareable public page
- **Solution:** Only show admin actions when user is admin

### FB-40-06: Person page missing cross-feature links
- **Page:** /person/{id}
- **Expected:** Prominent links to Timeline, Map, Tree, Connections
- **Actual:** Links missing or buried
- **Solution:** Add horizontal action bar under person name

### FB-40-07: /admin/approvals unstyled
- **Page:** /admin/approvals
- **Expected:** Consistent admin styling with sidebar
- **Actual:** Looks completely unstyled, missing admin sidebar
- **Solution:** Wrap in admin layout

---

## MEDIUM

### FB-40-08: Person page field order arbitrary
- **Expected:** Identity → Life Events → Relationships → Notes
- **Actual:** Fields in inconsistent order
- **Solution:** Reorganize field display order

### FB-40-09: No geographic autocomplete for place fields
- **Context:** birthplace/death place fields should suggest known Rhodesli places
- **Solution:** Use existing location_dictionary.json with historical aliases

### FB-40-10: No comments section on person pages
- **Context:** Person pages should be mini social posts that encourage engagement
- **Solution:** Add comment form (no login required) with admin moderation

### FB-40-11: GEDCOM page confusing — test data not labeled
- **Page:** /admin/gedcom
- **Expected:** Clear labeling of test vs real data
- **Actual:** Shows 14 confirmed matches from test_capeluto.ged without context

### FB-40-12: Tree link missing from public nav
- **Page:** Multiple public pages
- **Expected:** Photos | Collections | People | Tree | Map | Timeline | Connect | Compare
- **Actual:** Tree sometimes missing

### FB-40-13: Compare UX unclear — no clear mode separation
- **Page:** /compare
- **Expected:** Two clear modes: "Upload to find matches" and "Compare two photos"
- **Actual:** Single confusing interface

### FB-40-14: Edit Details too buried on person page
- **Context:** Edit fields hidden behind link at bottom
- **Solution:** Inline edit icons (admin), "Suggest correction" link (public)

---

## LOW

### FB-40-15: Upload/approval logging incomplete
- **Context:** No log of approval actions or upload history
- **Solution:** Add audit log to admin views

### FB-40-16: Photo upload attribution not displayed
- **Context:** Each photo should show who uploaded it
- **Solution:** Store uploader info in photo metadata, display on detail page

### FB-40-17: Sidebar consistency enforcement needed
- **Context:** Admin pages should have sidebar, public pages top nav only
- **Solution:** Audit all routes and enforce consistent layout
