# UX-103 Fix: Full-Bleed Photo View Dead End

## Problem
The full-bleed photo view at `/photo/{photo_id}` was a dead end with no back navigation, no metadata overlay on the photo itself, and limited mobile navigation.

## Changes Made

### 1. Back Navigation (Breadcrumb Bar)
- Added a breadcrumb navigation bar below the top nav with "Back to Photos" link
- Breadcrumb includes collection name as a clickable link when the photo belongs to a collection
- Visible on all screen sizes (not hidden on mobile)
- Uses `data-testid="photo-breadcrumb"` and `data-testid="back-to-photos"` for testing

### 2. Mobile Hamburger Menu
- Replaced the inline `Nav()` with `_public_page_nav()` which includes a mobile hamburger menu
- Previously, the photo page had `hidden sm:flex` on nav links, making them invisible on mobile
- Now uses the same mobile-friendly navigation pattern as all other public pages

### 3. Metadata Overlay on Photo
- Added a metadata overlay on the photo hero image showing:
  - Date estimate (e.g., "c. 1930s") when available
  - Face identification count (e.g., "2/3 identified")
  - Collection name
- Overlay uses `group-hover:opacity-100` -- visible on desktop via hover, always visible on mobile (sm:opacity-100)
- Positioned bottom-left with backdrop blur for readability
- Uses `data-testid="photo-metadata-overlay"` for testing

### 4. Preserved Existing Features
- Keyboard navigation (ArrowLeft/ArrowRight) still works
- Face overlay toggle (Show/Hide Faces) still works
- Share, Download, Flip buttons still present
- Person cards strip still renders
- CTA section ("Do you recognize someone?") still appears for unidentified faces

## Files Modified
- `app/main.py` -- `public_photo_page()` function: replaced inline Nav, added breadcrumb bar, added metadata overlay, added `group` class to photo container
- `tests/test_public_photo_viewer.py` -- Updated 3 existing tests, added 14 new tests across 3 test classes

## Tests Added (14 new tests)
- `TestUX103BackNavigation` (5 tests): back link present, breadcrumb bar, collection in breadcrumb, mobile hamburger, breadcrumb visible on mobile
- `TestUX103MetadataOverlay` (6 tests): overlay present, face count, collection, group class, anonymous access, keyboard nav preserved
- `TestUX103FaceOverlayToggle` (3 tests): toggle button, share button, download button still present

## Tests Updated (3 tests)
- `test_page_contains_nav_links`: Updated to check for "Back to Photos" instead of "Explore More Photos"
- `test_overlay_legend_present`: Fixed pre-existing fragile assertion about "Unidentified" text
- `test_overlay_links_to_person_or_identify`: Added skip condition for worktrees without photo files

## Test Results
- 43 passed, 1 skipped in `test_public_photo_viewer.py`
- 2997 passed in full suite (11 failures are pre-existing worktree issues due to missing raw_photos directory, all pass on main)
