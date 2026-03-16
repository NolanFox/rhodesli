# Session 108b — Bug Fix Sprint: Compare, Photo Links, Search

## Context
Session 108 shipped data integrity fixes + collage override but discovered 3 UX bugs during user triage. All 3 are diagnosed with root causes identified.

## Bug 1: FB-013 — Compare Button Broken on Person Page
**Reproduction:** Go to `/c/fox-family/person/{id}`, scroll to Similar Identities, click "Compare" — nothing happens.
**Root cause:** The person page layout does not include `compare_modal()`. The Compare button targets `#compare-modal-content` which doesn't exist in the DOM. Fix: add `_main_mod.compare_modal()` to the person page return value in `app/page_routes.py` where the person detail view is rendered.
**Files:** `app/page_routes.py` (person detail route)

## Bug 2: FB-014 — Photo Context Modal Missing Obvious "View Photo" Link
**Reproduction:** Go to To Review browse view, click a face card thumbnail. Photo Context modal opens. No obvious way to navigate to the full photo page.
**Root cause:** There IS a link labeled "Public Page" at `app/page_routes.py:4333-4343` but it's: (a) labeled "Public Page" not "View Photo", (b) `text-xs` tiny text, (c) buried next to the filename. Users can't find it.
**Fix:** Rename to "View Photo →", make it more prominent (larger, better positioned), consider adding it near the top of the modal too.
**Files:** `app/page_routes.py` (photo_view_content function, lines ~4333-4343)

## Bug 3: FB-015 — Sidebar Search Doesn't Find Photos by Filename
**Reproduction:** Type "02150_p_13akf5twbc1950.jpg" in the sidebar search bar. Shows "No matches found."
**Root cause:** The sidebar search endpoint (`GET /api/search` in `app/identity_routes.py:648`) only calls `registry.search_identities(q)` which searches identity names/aliases. It never checks photo filenames. FB-007 (Session 106b) added filename search to the Photos section filter only.
**Fix:** Extend the `/api/search` handler to also search photo filenames (via `_photo_cache`). Show photo results in a separate section below identity results. Link to `/photo/{photo_id}` with thumbnail.
**Files:** `app/identity_routes.py` (lines 648-733, search endpoint + result renderer)

## Verification
For each bug:
1. Fix the code
2. Write a test
3. Browser-verify on production

## Session Outputs
- Updated BACKLOG (FB-013/014/015 → DONE)
- Assessment + log
- CHANGELOG v0.99.13
