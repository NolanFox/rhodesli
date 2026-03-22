# Session 133 Phase 6 — Community Middleware Audit Report

**Date:** 2026-03-22
**Predecessor:** Session 115 PRD-052 audit (27 safety tests)
**Scope:** All route files in app/, file-by-file, route-by-route

## Methodology

Audited each route file for:
1. Does every handler that renders page content extract `community_slug` from `request.state`?
2. Do all internal links/redirects use `community_url_prefix()`?
3. Do Supabase queries filter by community where appropriate?
4. Do POST routes validate community context?

## Summary

| Route File | Routes | Community-Aware | Gaps Found | Risk |
|------------|--------|-----------------|------------|------|
| browse_routes.py | 7 | All 7 | 0 | LOW |
| person_routes.py | 4 | All 4 | 0 | LOW |
| identity_routes.py | 32 | All relevant | 0 | LOW |
| admin_routes.py | 30+ | Most | 3 (FIXED) | MEDIUM |
| cluster_review_routes.py | 15 | All | 1 (documented) | LOW |
| estimate_routes.py | 4 | All 4 | 2 (acceptable) | LOW |
| compare_routes.py | 20+ | All | 1 (acceptable) | LOW |
| tools_routes.py | 3 | 0 (by design) | 0 | NONE |
| match_facecompare_routes.py | 5 | 1 page route | 0 | LOW |
| page_routes.py | 30+ | All | 0 | LOW |
| notification_routes.py | 5 | 2 page routes | 0 | LOW |
| auth_routes.py | 10 | 0 (by design) | 0 | NONE |
| upload_routes.py | 3 | All 3 | 1 (FIXED) | LOW |
| discoveries_routes.py | 3 | All 3 | 0 | LOW |
| engagement_routes.py | 3 | All 3 | 0 | LOW |
| event_routes.py | 3 | All 3 | 0 | LOW |
| photo_routes.py | 2 | All 2 | 0 | LOW |
| relationship_routes.py | 7 | N/A (all /api/) | 0 | NONE |
| sync_routes.py | 12 | N/A (all /api/) | 0 | NONE |

## Gaps Found and Fixed

### GAP-1: `_admin_nav_bar()` links hardcoded without nav_prefix (FIXED)
- **File:** admin_routes.py:2074-2089
- **Issue:** All admin nav links (Uploads, Approvals, Proposals, etc.) were hardcoded as `/admin/...` without `nav_prefix`. When accessed via `/c/fox-family/admin/pending`, clicking nav links dropped the community prefix.
- **Fix:** Changed `href=href` to `href=f"{nav_prefix}{href}"` in the nav bar link builder.
- **Impact:** HIGH — admin navigating between pages in non-Rhodes community lost context.

### GAP-2: Batch-approve "Refresh page" link hardcoded (FIXED)
- **File:** admin_routes.py:1708
- **Issue:** After batch-approving uploads, the "Refresh page" link went to `/admin/pending` without community prefix.
- **Fix:** Added community_slug extraction and used `f"{_batch_prefix}/admin/pending"`.

### GAP-3: Upload "View in Pending Uploads" link hardcoded (FIXED)
- **File:** upload_routes.py:836
- **Issue:** After uploading files, the "View in Pending Uploads" link went to `/admin/pending` without community prefix.
- **Fix:** Used `f"{_main_mod.community_url_prefix(community_slug)}/admin/pending"`.

## Documented Non-Issues (Acceptable)

### DOC-1: HTMX POST paths in admin pages lack community prefix
- **Files:** admin_routes.py (lines 625, 636, 662, 791, etc.)
- **Why acceptable:** These HTMX POST requests target specific records by ID (e.g., `/admin/pending/{job_id}/approve`). The community_slug is not needed for data correctness since the operation targets a specific entity. The middleware defaults to "rhodes" but the operation works correctly regardless.

### DOC-2: `tools_routes.py` and `auth_routes.py` have no community awareness
- **Why acceptable:** Tools pages are intentionally community-agnostic (Lesson 82). Auth routes are global (login/signup/logout work identically for all communities).

### DOC-3: Estimate/Compare "Browse the Archive" links go to /photos
- **Files:** estimate_routes.py:782, 1044; compare_routes.py:4589
- **Why acceptable:** Tools pages are community-agnostic by design. The `/photos` link goes to the default Rhodes archive, which is correct for a standalone tool context.

### DOC-4: Cluster review HTMX GET uses query param for community_slug
- **File:** cluster_review_routes.py:2017, 2232, 2749
- **Pattern:** `hx_get=f"/admin/cluster-review/next?{prefetch_params}"` where prefetch_params includes `community_slug=...`
- **Why acceptable:** The handler at line 2438 reads `community_slug` from query params directly. This is the dual-path pattern (Lesson 109) — fragile but functional.

### DOC-5: Community management pages don't pass request to `_admin_nav_bar`
- **Files:** admin_routes.py:4490, 4528, 4589
- **Why acceptable:** Community management (`/admin/communities`) is a global admin function, not community-scoped.

### DOC-6: Admin GEDCOM/birth-year API POST handlers lack request
- **Files:** admin_routes.py:3117 (accept-all-high), 3942 (apply), 4066 (cancel)
- **Why acceptable:** These are admin-only operations on global data. The response links to admin pages will default to Rhodes prefix, which is acceptable for the current single-admin setup.

## Route File Details

### browse_routes.py (7 routes)
- `/photos` (GET) — community_slug extracted, nav_prefix used
- `/api/photos/more` (GET) — community_slug extracted
- `/people` (GET) — community_slug extracted
- `/people/{id}/similar` (GET) — community_slug extracted
- `/api/find-similar/{id}` (GET) — community_slug extracted
- `/collections` (GET) — community_slug extracted
- `/collection/{slug}` (GET) — community_slug extracted

### person_routes.py (4 routes)
- `public_person_page()` — accepts community_slug parameter
- `/person/{id}` (GET) — community_slug extracted
- `/api/person/{id}/gallery` (GET) — community_slug extracted
- `/api/person/{id}/comment` (POST) — community_slug extracted
- `/api/person/{id}/comment/{cid}/hide` (POST) — admin only, no community needed

### identity_routes.py (32+ routes)
- `_nav_prefix_from_request()` helper at line 65 — centralizes extraction
- `_community_from_request()` helper at line 71
- All page-rendering routes use these helpers
- POST routes under `/api/` are skipped by middleware (correct)

### admin_routes.py (30+ routes)
- Admin page routes extract community from request.state
- `_admin_nav_bar()` now uses nav_prefix for all links (FIXED)
- HTMX POST endpoints target entities by ID (community context not needed for data ops)

### cluster_review_routes.py (15 routes)
- `/admin/upload-review` — community_slug from request.state
- Speed-run cluster cards pass community_slug as query parameter
- Batch cluster review extracts community_slug from request.state

### All Other Files — see summary table above.

## Test Coverage

Existing tests:
- `test_community_routing_safety.py`: 27 tests covering middleware, upload assignment, admin guards
- `test_community_prefix_audit.py`: Regex-based regression test for hardcoded links

New tests added:
- `TestAdminNavBarCommunityPrefix`: Verifies `_admin_nav_bar` uses nav_prefix
- `TestAdminPageCommunityExtraction`: Verifies admin page handlers extract community_slug
- `TestHtmxAdminPaths`: Documents that HTMX POST paths in admin context are acceptable without prefix

## Recommendations for Future Work
1. Add `request` parameter to `/admin/communities` GET handler for nav_bar prefix
2. Consider middleware approach for HTMX requests: extract community from Referer header
3. Move admin POST routes under `/api/admin/` prefix for consistency with middleware skip
