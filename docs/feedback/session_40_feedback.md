# Session 40 Production Walkthrough Feedback

**Date:** 2026-02-17
**Source:** Admin production walkthrough
**Reporter:** Nolan Fox (admin)

---

## CRITICAL

### FB-40-01: /map returns Internal Server Error — FIXED
- **Root Cause:** Missing `_build_caches()` call
- **Fix:** Added `_build_caches()` to /map route handler

### FB-40-02: /connect returns Internal Server Error — FIXED
- **Root Cause:** `registry.get_identity()` raises KeyError, code expected None
- **Fix:** Added `_safe_get_identity()` helper, replaced all 6 call sites

### FB-40-03: Collection/Source metadata — FIXED
- **Root Cause:** Session 26 batch ingest used generic "Community Submissions"
- **Fix:** 114 photos reassigned to "Jews of Rhodes: Family Memories & Heritage" / "Facebook"

---

## HIGH — Photo Page UX

### FB-40-18: Face click behavior broken
- Clicking face overlay scrolls to thumbnail; clicking thumbnail scrolls back up (circular)
- **Correct:** Overlay click → tag dialog (unidentified) or /person/{id} (identified). Thumbnail click → /person/{id} or /identify/{id}

### FB-40-19: Collection/source metadata not prominent on photo page
- Need: "From: Vida Capeluto NYC Collection → [View Collection]" — one-click discovery path

### FB-40-20: Photo carousel / gallery mode needed
- Left/right arrows to browse adjacent photos in collection. Keyboard + swipe. "Photo 3 of 108" indicator

### FB-40-21: Admin-only elements visible to non-admin on photo page — VERIFIED CORRECT
- Back image upload, orientation tools correctly guarded by `if is_admin else None`
- Local dev shows admin elements because auth disabled = is_admin=True by design
- Production (auth enabled) correctly hides admin elements for anonymous users

### FB-40-22: Photo upload attribution not displayed — DEFERRED
- Show "Uploaded by [name] on [date]" on photo detail page
- Requires adding `uploaded_by` field to photo_index.json data model

---

## HIGH — Collection Management

### FB-40-23: "Add Photos" button on collection detail pages — DONE (Session 42)
- Admin-only button next to Share button, links to /upload

### FB-40-24: Bulk collection/source editing in admin Photos view
- "Move to Collection...", "Set Source...", "Create New Collection..."

### FB-40-25: Individual photo collection/source editable by admin
- On photo detail page

### FB-40-26: Upload flow collection assignment unclear
- Dropdown of existing collections + "Create New Collection", required field

---

## HIGH — Identification UX

### FB-40-04: Sharing needs to be more prominent and intuitive
- Sharing is how Rhodesli grows — every view needs one-click share
- Create /identify/{id} and /identify/{a}/match/{b} pages

### FB-40-27: Searching unknown identity goes to wrong person in Focus mode
- Should navigate to that person's page, not first person in Focus queue

### FB-40-28: Help Identify workflow too many clicks for context
- /identify pages solve this by showing photo context inline

---

## HIGH — Prevention

### FB-40-29: Create scripts/verify_data_integrity.py
- Check all JSON files parse, collection counts, relationship counts

### FB-40-30: Create tests/e2e/test_critical_routes.py
- GET every public route returns 200 — would have caught /map and /connect 500s

### FB-40-31: Session Completion Checklist in CLAUDE.md
- All tests pass, smoke tests pass, data integrity check, all routes return 200

### FB-40-32: Create docs/postmortems/session_40_production_bugs.md

---

## MEDIUM — Person Page

### FB-40-05: "Return to Inbox" visible on public /person/{id} — admin-only
### FB-40-06: Missing cross-feature action links (Timeline, Map, Tree, Connections)
### FB-40-14: Edit Details too buried — inline edit icons (admin), "Suggest correction" (public)
### FB-40-08: Field order: Identity → Life Events → Relationships → Notes
### FB-40-09: Geographic autocomplete with location_dictionary.json + historical variants
### FB-40-10: Comments section — no login required, admin moderation, rate limited by IP

---

## MEDIUM — Consistency

### FB-40-17: Sidebar rule enforcement — admin pages get sidebar, public get top nav
### FB-40-07: /admin/approvals unstyled — needs sidebar + consistent styling
### FB-40-12: Tree link missing from public nav on some pages
### FB-40-11: GEDCOM page — label test data — DONE (Session 42)
- Warning banner shown when source file contains "test" in name
### FB-40-13: Compare UX — two clear modes — DONE (Session 42)
- Numbered sections: "1. Search the Archive" and "2. Upload a Photo"
### FB-40-15: Upload/approval logging — who/what/when for all actions
