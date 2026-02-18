# Feature Matrix: Bugs + Front-End / UX

For navigation see [docs/BACKLOG.md](../BACKLOG.md). For backend/ML/ops see other FEATURE_MATRIX files.

---

## 1. BUGS

**Status**: All P0 bugs resolved. No active P0 bugs as of v0.14.1.

### BUG-001: Lightbox Arrow Buttons Disappear After First Photo — FIXED
**Fixed**: 2026-02-08 (v0.11.0) — event delegation pattern, 16 regression tests
**Root cause**: JS event handlers bound directly to DOM nodes that HTMX swapped out. Fix: global event delegation via `data-action` attributes on `document`.

### BUG-002: Face Count Label Incorrect in Photo View — FIXED
**Fixed**: 2026-02-08 (v0.11.0)
**Root cause**: Count read from raw detection results, not filtered/displayed faces. Fix: count matches visible face boxes.

### BUG-003: Merge Direction Bug — FIXED
**Fixed**: 2026-02-08 (v0.11.0) — `resolve_merge_direction()` with 18 direction-specific tests
**Root cause**: Already fixed in code before investigation. Tests confirmed auto-correction working.

### BUG-004: Collection Stats Inconsistency — FIXED
**Fixed**: 2026-02-08 (v0.11.0) — canonical `_compute_sidebar_counts()`, 11 regression tests
**Root cause**: 4 inline computations with inconsistent logic. Fix: single canonical function.

### BUG-005: Face Count Badges Wildly Wrong — FIXED
**Fixed**: 2026-02-09 (v0.12.1) — filter to registered faces from photo_index.json, 5 tests
**Root cause**: Badge denominator used raw embedding count (63 for a 3-person newspaper photo).

### BUG-006: Photo Navigation Dies After Few Clicks — FIXED
**Fixed**: 2026-02-09 (v0.12.1) — removed duplicate keydown handler, 6 tests

### BUG-007: Logo Doesn't Link Home — FIXED
**Fixed**: 2026-02-09 (v0.12.1) — wrapped in `<a href="/">`, 2 tests

### BUG-008: Client-Side Fuzzy Search Not Working — FIXED
**Fixed**: 2026-02-09 (v0.12.1) — JS Levenshtein distance added, 4 tests

---

## 2. FRONT-END / UX

### 2.1 Navigation & Lightbox (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-001 | Fix lightbox arrows (BUG-001) | DONE | Fixed 2026-02-08 via event delegation + 16 regression tests |
| FE-002 | Keyboard arrow navigation in Match Mode | DONE | Y/N/S for same/different/skip (2026-02-08) |
| FE-003 | Universal keyboard shortcuts | DONE | Consolidated global handler for all views (2026-02-08) |
| FE-004 | Consistent lightbox across all sections | DONE | Consolidated #photo-lightbox into #photo-modal (2026-02-08) |
| FE-005 | Swipe navigation on mobile | IMPLEMENTED | Phase 3 (commit d1d14c8). Needs real-device testing. |

### 2.2 Mobile Experience (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-010 | Mobile sidebar — hamburger menu or slide-over | DONE | Fixed 2026-02-06 |
| FE-011 | Bottom tab navigation on mobile | DONE | Photos/Confirmed/Inbox/Search tabs, 6 tests (2026-02-08) |
| FE-012 | Touch targets >=44px | IMPLEMENTED | Phase 3. Needs real-device verification. |
| FE-013 | Mobile-optimized face cards | IMPLEMENTED | Stacked layout. Needs testing. |
| FE-014 | Responsive photo grid | DONE | 2-col mobile, 4-col desktop (2026-02-06) |
| FE-015 | Mobile match mode — vertical stacking with swipe | DONE | 2026-02-06 |

### 2.3 Face Tagging & Overlays (MEDIUM-HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-020 | Face overlay color system | IMPLEMENTED | Green=confirmed, indigo=proposed, amber=skipped, red=rejected, dashed=unreviewed |
| FE-021 | Photo completion badges on gallery thumbnails | IMPLEMENTED | Green check, amber partial, red warning |
| FE-022 | Inline confirm/skip/reject from photo view | DONE | Hover-visible icon buttons on face overlays, 17 tests (2026-02-08) |
| FE-023 | Single tag dropdown (no multiple simultaneous) | DONE | Commit bf6a99c |
| FE-024 | "+ Create New Identity" in autocomplete | DONE | Commit bf6a99c |
| FE-025 | Face count label bug (BUG-002) | DONE | Fixed 2026-02-08, count matches visible boxes |

### 2.4 Search & Discoverability (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-030 | Global search improvements | DONE | Client-side instant name search with 150ms debounce (2026-02-08) |
| FE-031 | Fast name lookup with typeahead | DONE | Instant-filter in sidebar (2026-02-08) |
| FE-032 | Search result navigation | DONE | Hash fragment scroll + 2s highlight animation (2026-02-08) |
| FE-033 | Fuzzy name search | DONE | Levenshtein edit distance, 11 tests (2026-02-08) |
| FE-034 | Search results highlighting | DONE | Matched portion highlighted in amber (2026-02-08) |

### 2.5 Skipped Faces Workflow (MEDIUM-HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-040 | Surface skipped faces to other users | OPEN | Skipped faces visible to logged-in users for identification. |
| FE-041 | "Help Identify" mode for non-admin users | OPEN | Browse skipped faces, propose names. Admin reviews proposals. |
| FE-042 | Re-surface skips when new photos/faces are added | OPEN | New context from clustering triggers re-surfacing. |
| FE-043 | Skipped section should show ML suggestions | OPEN | Show similar confirmed identities as hints. |

### 2.6 Landing Page & Onboarding (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-050 | Welcome/about landing page | DONE | Heritage photos, community explanation (2026-02-06) |
| FE-051 | Interactive hero with real archive photos | DONE | Carousel with real archive photos (2026-02-06) |
| FE-052 | First-time user welcome modal | DONE | 3-step surname onboarding, cookie-based (2026-02-12) |
| FE-053 | Progress dashboard | DONE | "X of Y faces identified", 5 tests (2026-02-08) |
| FE-054 | Landing page stats + historical content | DONE | Fixed stats, Rhodes history rewrite (2026-02-10) |
| FE-055 | UI clarity pass | DONE | Section renames, empty states (2026-02-12) |
| FE-056 | Button prominence | DONE | View All Photos + Find Similar as styled buttons (2026-02-10) |
| FE-057 | Compare faces UX overhaul | DONE | Face/photo toggle, 90vw, filter preservation (2026-02-11) |
| FE-058 | Login prompt modal | DONE | HTMX 401 interceptor, contextual messages (2026-02-10) |
| FE-059 | Bulk photo select mode | DONE | Select toggle, checkboxes, collection reassignment (2026-02-10) |

### 2.7 Workflow Speed & First-Time Value (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-060 | Anonymous guest contributions | DONE | Guest-or-login modal, stash-and-login flow (2026-02-10) |
| FE-061 | Quick Compare from Find Similar | OPEN | Side-by-side with Merge/Not Same buttons. |
| FE-062 | Batch confirmation for obvious matches | OPEN | >95% confidence batch review. |
| FE-063 | Browser performance audit | OPEN | Stress test page load, HTMX swap latency. |
| FE-064 | Preload adjacent photos in gallery | PARTIAL | Implemented Phase 2, needs verification. |

### 2.8 Shareable Photo Experience (HIGH Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-070 | Public photo viewer at /photo/{id} | DONE | Museum-like page, 16 tests (2026-02-12) |
| FE-071 | Front/back photo flip | DONE | CSS 3D flip animation, 11 tests (2026-02-12) |
| FE-072 | Open Graph meta tags | DONE | og:title/description/image/url, Twitter Card (2026-02-12) |
| FE-073 | Share + download buttons | DONE | Web Share API + clipboard fallback, 12 tests (2026-02-12) |
| FE-074 | Internal links to public viewer | DONE | "Open Full Page" from modal, 5 tests (2026-02-12) |
| FE-078 | Public person page | DONE | /person/{id}, 23 tests (2026-02-13) |
| FE-079 | Public photos/people browsing | DONE | /photos and /people, 21 tests (2026-02-13) |
| FE-090 | Person links from photo viewer | DONE | Cards link to /person/{id}, 4 tests (2026-02-13) |
| FE-091 | Public Page link on identity cards | DONE | "Public Page" link, 3 tests (2026-02-13) |
| FE-092 | Triage bar active state | DONE | Ring-2 highlight, clickable "+N more", 4 tests (2026-02-13) |
| FE-114 | Unified sharing design system | DONE | og_tags() + share_button(), deduplicated JS (2026-02-17) |
| FE-115 | Compare page upload-first redesign | DONE | Upload above fold, archive search collapsible (2026-02-17) |
| FE-116 | Calibrated match confidence labels | DONE | Very likely/Strong/Possible/Unlikely, AD-091 (2026-02-17) |
| FE-117 | Shareable comparison result pages | DONE | /compare/result/{id} with OG tags + response form (2026-02-17) |
| FE-118 | Site-wide OG tags + share buttons | DONE | /photos, /people, /collections (2026-02-17) |

### 2.9 User Analytics & Logging (MEDIUM Priority)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| FE-080 | Client-side event logging | OPEN | Page views, clicks, time-on-page, nav patterns. |
| FE-081 | Session recording / heatmaps | OPEN | Plausible, PostHog, or custom. Privacy-respecting. |
| FE-082 | Admin analytics dashboard | OPEN | Visitors, duration, clicks, conversion. |
| FE-083 | Action logging for admin review | PARTIAL | Decision logging exists, needs admin UI. |
