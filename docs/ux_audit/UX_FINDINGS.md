# UX Findings — Session 53 Production Audit (2026-02-20)

## Route-by-Route Assessment

### `/` — Landing Page
**Status:** OK | **Load time:** 0.38s | **Images:** 10
- First impression: Clean, heritage-themed with sepia tones. Clear purpose.
- CTAs present: Browse Photos, View Timeline, Compare Faces
- Featured photos carousel loads correctly
- Mobile: viewport meta present, Tailwind responsive classes used

### `/timeline` — Photo Timeline
**Status:** OK | **Load time:** 0.88s | **Images:** 271
- All 271 photos render with R2 URLs
- Person filtering works (`?person=<id>`)
- Largest page by size (443KB) — consider lazy loading images
- Mobile: grid responsive, touch targets adequate

### `/compare` — Compare Faces
**Status:** OK (with fixes applied) | **Load time:** 0.29s | **Images:** 46
- Upload form prominent above the fold (PRD-016)
- Archive search collapsible below
- **Fixed (this session):** Loading indicator now shows with spinner + duration warning
- **Fixed (this session):** Uploaded photo now displays in results
- **Fixed (this session):** Resize target reduced from 1280 to 1024 for faster processing
- File validation: client-side + server-side (JPG/PNG, 10MB max)

### `/people` — People Listing
**Status:** OK | **Load time:** 0.16s | **Images:** 46
- Fastest page. Confirmed identities listed with face crops
- Links to person detail pages work correctly
- No admin elements visible to anonymous users

### `/photos` — Photo Browse
**Status:** OK | **Load time:** 0.63s | **Images:** 271
- All photos load from R2
- Collection/source filter available
- Sort options present

### `/collections` — Collections Overview
**Status:** OK | **Load time:** 0.29s | **Images:** 8
- 5 collections listed with cover images
- Links to collection detail pages work

### `/collection/vida-capeluto-nyc-collection` — Collection Detail
**Status:** OK | **Load time:** 0.64s | **Images:** 108
- Largest collection. All thumbnails load correctly

### `/map` — Geographic Map
**Status:** OK | **Load time:** 0.33s | **Images:** 1
- Map view renders with Leaflet
- Location markers present

### `/tree` — Family Tree
**Status:** OK | **Load time:** 0.62s | **Images:** 0
- Tree structure renders (text/SVG-based)
- No images expected for this page type

### `/connect` — Connection Finder
**Status:** OK | **Load time:** 0.21s | **Images:** 0
- Person-to-person connection UI loads
- Dropdown selectors populated with people

### `/estimate` — Date Estimation
**Status:** OK | **Load time:** 0.20s | **Images:** 1
- Upload zone present
- Photo grid for archive-based estimation
- Same HTMX indicator pattern as compare (fixed CSS applies here too)

### `/about` — About Page
**Status:** OK | **Load time:** 0.19s | **Images:** 0
- Historical context and project information

### `/activity` — Activity Feed
**Status:** OK | **Load time:** 0.26s | **Images:** 0
- 2 activity entries (both "Name suggestion approved" from 2026-02-13)
- Thin content — may want to highlight more activity types

### `/person/<id>` — Person Detail
**Status:** OK | **Load time:** 0.27s
- Name, face crops, photo links all render correctly
- Face overlays link to photo pages

### `/photo/<id>` — Photo Detail
**Status:** OK | **Load time:** 0.27s
- Photo loads from R2, face overlays render
- AI Analysis section present
- "Name These Faces" button visible for admin

### Admin Routes (10 tested)
**Status:** All correctly return 401 for unauthenticated users
- No admin forms leak to public visitors

## Cross-Feature Issues

### None found in this audit
All cross-feature journeys (People->Person->Photo, Collection->Photos, Timeline filtered, Compare->Upload) work correctly.

## Patterns Observed

1. **Loading states are now addressed**: Compare and estimate have HTMX indicators. The CSS fix ensures they display correctly on the triage dashboard.
2. **No broken images**: All R2 URLs resolve correctly. The storage layer is solid.
3. **Auth guards are consistent**: All 10 admin routes return 401. No leakage.
4. **Large pages could benefit from lazy loading**: Timeline (271 imgs) and Photos (271 imgs) load all images upfront. At 500+ photos, this will need pagination or lazy loading.
5. **Activity feed is thin**: Only 2 entries. Consider surfacing more event types (photo additions, identity confirmations, compare uploads).
