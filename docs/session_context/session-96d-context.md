# Session 96d Context — Fix Fox Family to Usable State

**Predecessor:** [Session 96c-cont4 assessment](../assessments/session-96c-cont4-assessment.md)
**Date:** 2026-03-10
**Type:** Critical bug fix — Fox Family is unusable
**Related ADs:** AD-216 (community-scoped review), AD-179 (auto-clustering)
**BACKLOG items:** COMMUNITY-007 through COMMUNITY-013

---

## Problem Statement

After 4 continuation sessions (96c through 96c-cont4), the Fox Family community is still unusable. The user explicitly said "totally unusable" and "I haven't been able to do even the most basic thing with the Fox family."

## What Works (verified in browser, 96c-cont4)
- Fox Family landing page loads with "Fox Family Archive" branding
- Photos section: 635 photos (correctly scoped)
- To Review section: 1602 faces render (correctly scoped)
- Discoveries page: 182 discoveries (community-scoped, cross-community matching enabled)
- Admin pages load via `/c/fox-family/admin/*` URLs
- JS link rewriter handles community URL prefixes client-side

## What's Broken (ALL must be fixed in 96d)

### 1. COMMUNITY-007: Sidebar counts not community-scoped
**Current:** Sidebar shows global counts instead of Fox Family counts.
**Fix:** `_compute_sidebar_counts()` in `app/main.py` needs `community_identity_ids` parameter. Pass community from `sidebar()` function. Filter identity lists by community set before counting.
**File:** `app/main.py` — `_compute_sidebar_counts()` (~line 2805) and `sidebar()` (~line 4331)

### 2. COMMUNITY-008: Bottom nav community prefix
**Current:** Bottom nav bar uses `/?section=...` instead of `/c/fox-family/?section=...`.
**Fix:** Bottom nav in `page_routes.py` needs to use `community_url_prefix()`.
**File:** `app/page_routes.py` — look for bottom navigation generation

### 3. COMMUNITY-009: Upload Review + GEDCOM not in sidebar
**Current:** `/admin/upload-review` and `/admin/gedcom-triage` exist but aren't in Fox Family sidebar.
**Fix:** Add sidebar links. Check `sidebar()` function in `app/main.py` (~line 4331+).
**File:** `app/main.py` — `sidebar()` function

### 4. COMMUNITY-010: Proposals not surfaced in sidebar count
**Current:** Sidebar shows "0 Proposals" despite 35 valid proposals in `proposals.json`.
**Evidence:** `proposals.json` has 30 Roland Fox, 4 Betty Capeluto Fox, 1 Ray Franco — all valid.
**Fix:** Sidebar "Proposals" count must read from `proposals.json` and filter by community.
**File:** `app/main.py` — sidebar count logic

### 5. COMMUNITY-011: Cluster review page not community-scoped
**Current:** `/admin/upload-review` loads ALL proposals globally.
**Fix:** `_load_proposals()` in `app/cluster_review_routes.py` needs community filtering.
**File:** `app/cluster_review_routes.py`

### 6. COMMUNITY-012: To Review shows flat 1602 faces, no proposal info
**Current:** Every face card says "Unidentified Person" with no match suggestion.
**Expected:** Faces with proposals should show "Matches Roland Fox (74%)" or similar.
**Fix:** In the identity card renderer for To Review, check if identity has proposals and show match info.
**File:** `app/page_routes.py` — identity card rendering in `render_to_review_section()`

### 7. COMMUNITY-013: Admin page headers show "Rhodesli"
**Current:** Admin pages show "Rhodesli" header instead of community name.
**Fix:** Admin route handlers need to read `request.state.community` and pass name to templates.
**File:** Admin route files (`admin/*` routes in main.py or separate files)

### 8. COMMUNITY-014: Cross-community photos/faces have no community indicator
**Current:** When viewing Fox Family, a person matched to a Rhodes photo shows the Rhodes photo in Photo Context modal with NO indication it's from another community. Other faces not labeled or clickable. Can't navigate to the full photo page.
**User feedback:** "it should be obvious from the UX every time I see the photo or the face that it is from another community"
**Evidence:** Screenshot — Roland Fox wedding photo (Image 978_compress.jpg) in Fox Family Photo Context modal, no community badge, bride face not labeled, no photo link.
**Fix:** (a) "From [Community Name]" badge on cross-community content in all surfaces, (b) Photo Context modal links to photo page, (c) All faces in photo labeled + clickable, (d) Cross-community navigation says "View in Rhodes"
**Files:** Photo Context modal rendering, identity card, discovery card

## Clustering Data (EXISTS — just not surfaced)

### proposals.json (35 entries, generated 2026-03-09T14:57:29)
- 30 × Roland Fox (distances 0.741–1.049)
- 4 × Betty Capeluto Fox (distances 1.005–1.045)
- 1 × Ray Franco (distance 1.019)

### discovery_log.json (1248 entries)
- 16 Fox-related entries
- 120 Betty Capeluto entries (Rhodes)
- 112 Ray Franco entries (Rhodes)

### Why Roland matched more than Betty
Roland Fox is CONFIRMED with face embeddings that closely match many Fox Family INBOX faces (distances 0.74–1.05). Betty Capeluto Fox has fewer similar faces in the Fox photos (4 matches) and Ray Franco has just 1 marginal match. This is expected — it's Roland's family archive.

## Architecture Notes

### CommunityMiddleware (app/main.py:462-506)
- Rewrites `/c/{slug}/path` → `/path` and sets `request.state.community`
- SKIPS paths starting with `/api/` — sets community=None
- Consequence: all HTMX URLs must include `/c/{slug}/` prefix for non-Rhodes
- JS rewriter in `page_routes.py` handles this client-side (runs on load + htmx:afterSwap)

### Community identity resolution
- `_get_community_identity_ids(community)` returns photo-derived identity set (AD-216)
- `_get_community_photo_ids(community)` returns photo IDs including SHA256 aliases
- Both cached for 60s via `_community_ids_cache_ts`
- Returns `None` when community is None (no filtering) or Supabase unavailable

### Key functions to modify
- `sidebar()` — app/main.py:4331+ — generates all sidebar nav + counts
- `_compute_sidebar_counts()` — app/main.py:2805+ — computes counts for sidebar
- `render_to_review_section()` — app/page_routes.py — renders To Review cards
- `_load_proposals()` — app/cluster_review_routes.py — loads proposals.json
- `_build_discovery_card()` — app/discoveries_routes.py — builds discovery cards

## Lessons from 96c-cont4

### Lesson 108: Performance filters must preserve cross-community matching
My early community filter in `_compute_discoveries()` accidentally filtered `confirmed_list` by community, which broke cross-community matching (Fox faces → Rhodes confirmed identities). Fix: only filter `unreviewed` by community, keep `confirmed_list` global.

### Lesson 109: CommunityMiddleware /api/ skip creates dual-path problem
Bare `/api/` paths bypass middleware, so `request.state.community=None`. Routes must handle both: prefixed paths (middleware sets community) and bare paths (need Rhodes fallback). This is a recurring source of bugs.

### Lesson 110: Existing data not surfaced is worse than missing data
Clustering ran correctly (35 proposals), but the UI showed 0 proposals. User concluded "clustering is completely missing." The data pipeline was fine — the UI surfacing was the failure.

## Browser Verification Checklist (ALL must PASS before session complete)

For each check, navigate in Claude Chrome and verify visually:

### Fox Family (`/c/fox-family/`)
1. [ ] Sidebar counts are Fox-only (not global)
2. [ ] Bottom nav links include `/c/fox-family/` prefix
3. [ ] Proposals count shows 35 (or community-filtered count)
4. [ ] Upload Review + GEDCOM visible in sidebar
5. [ ] To Review cards show proposal match info (e.g., "Matches Roland Fox")
6. [ ] Admin pages show "Fox Family Archive" header
7. [ ] Discoveries page shows Betty Capeluto and Ray Franco matches
8. [ ] Cross-community photos show "From Rhodes" badge
9. [ ] Photo Context modal links to full photo page with all faces labeled

### Rhodes (`/`)
10. [ ] Sidebar counts unchanged/correct
11. [ ] Discoveries still work
12. [ ] No regressions on main functionality
