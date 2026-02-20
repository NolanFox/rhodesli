# Session 49B Comprehensive Audit — 2026-02-20

## Test Results Summary
- Total pages tested: 18 (landing, photos, people, person detail, timeline, map, tree, collections, collection detail, compare, compare upload, estimate, connect, about, login, person 404, photo 404, generic 404)
- Total user actions tested: 25+ (page loads, file upload, sort routing, navigation, mobile viewport, face selection, error handling)
- Passed: 18/18 page loads, 1 critical upload flow
- Failed: 1 HIGH (mobile nav), 4 MEDIUM, 3 LOW

## Triage Fixes Verified
- [x] Bug 1 (Upload stuck at 0%): FIXED — subprocess logs to file, not DEVNULL
- [x] Bug 2 (Compare): **WORKS** — uploaded 6.5KB photo, got 3 faces detected, 20 matches, 1 strong match at 93%. Results visible in viewport without scrolling.
- [x] Bug 3 (Sort routing): FIXED — all sort links include `view=browse` parameter

## Critical Failures (blocks core functionality)
None found.

## High Priority (degrades experience significantly)
| # | Route | Action | Expected | Actual | Root Cause |
|---|-------|--------|----------|--------|------------|
| H1 | ALL public pages | View on mobile (<640px) | Hamburger menu for navigation | Nav links hidden with `hidden sm:flex`, no hamburger alternative. Mobile users have ZERO navigation. | `mobile_header()` exists (line 2465) but only used in admin sidebar layout, not public pages. All 15+ public page navs use `hidden sm:flex` without mobile fallback. |

## Medium Priority (noticeable but usable)
| # | Route | Action | Expected | Actual | Root Cause |
|---|-------|--------|----------|--------|------------|
| M1 | /nonexistent-page | Visit unknown route | Styled 404 page | Bare "404 Not Found" text | No catch-all 404 handler for unrecognized routes. `/person/X` and `/photo/X` have custom 404s, but arbitrary paths get default Starlette 404. |
| M2 | /compare | Select file via Choose File | Preview of selected file | Dropzone still shows "Drop a photo here" — no filename or thumbnail feedback | File input onchange handler missing preview logic. |
| M3 | /admin/pending (approve) | Approve upload with PROCESSING_ENABLED | Subprocess output logged | `subprocess.DEVNULL` at line 20739-20740 silences all output. Same class of bug as Bug 1 (triage). | Approve handler wasn't updated during triage fix. |
| M4 | / (landing) | Load page | favicon loads | favicon.ico returns 404 (console error) | No favicon file served |

## Low Priority (polish)
| # | Route | Action | Expected | Actual |
|---|-------|--------|----------|--------|
| L1 | /login | Page load | No browser warnings | Inputs missing `autocomplete` attribute |
| L2 | ALL pages | Page load | No console warnings | Tailwind CDN development warning |
| L3 | / (landing) | View stats section | Numbers visible | Counters show "0" until scrolled into viewport (IntersectionObserver animation). Not broken, but looks odd if user sees it before scroll triggers. |

## Passed (working correctly)
| Route | Actions Verified |
|-------|-----------------|
| / (landing) | Loads, photos render, nav links, stats animate on scroll, identified ticker, CTAs link correctly |
| /photos | 271 photos lazy-loaded, all R2 URLs work, photo links present |
| /people | 46 people, sort dropdown (A-Z, Most Photos, Newest), photo counts correct |
| /person/{id} | Face grid (25 for Big Leon), family tree, connections, "Often appears with", comments section, share button, birth/death/from fields |
| /timeline | 271 images, person filter dropdown |
| /map | Leaflet map, 10 location clusters, collection/person/decade filters, zoom |
| /tree | SVG family tree, person focus dropdown, show speculative toggle |
| /collections | 8 collections with photo counts, identified/unknown stats |
| /collection/{slug} | 108 photos (Vida NYC), 27 people listed, breadcrumb, share/timeline links |
| /compare | Upload form, file input, "Search Archive" button |
| /compare (upload) | File accepted, 3 faces detected, 20 matches returned, Strong/Possible/Similar categories, face selection (1/2/3), photo links, confidence scores (93% top), share results |
| /estimate | Photo grid with face counts (1-6), upload zone, "Load More" pagination |
| /connect | Person A/B dropdowns, community network graph, family/photo connection legend |
| /about | Community history, project description, how to help, how it works, roles, FAQ |
| /login | Email/password form, Google OAuth, forgot password, signup link |
| /person/99999 | Proper styled 404 page with "Explore the Archive" link |
| /photo/99999 | Proper styled 404 page with "Explore the Archive" link |
| Sort routing | All sort links (A-Z, Faces, Newest) preserve `view=browse` parameter |

## Architecture Notes
- Compare upload is fast for small photos (~few seconds for 6.5KB, 3 faces)
- All 271 photos load via lazy loading from R2 CDN
- No console errors on any page (except favicon 404 and Tailwind CDN warning)
- Person detail pages are feature-rich (family tree, connections, AI analysis, comments)
