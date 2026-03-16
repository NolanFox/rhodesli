# Session 111b Context — Community Prefix Sweep + UX Fix Sprint

## Predecessor
- Session 111: Interactive Fox Family triage with Nolan
- Session 111 context: `docs/session_context/session-111-context.md` (if exists)
- Session 110: James Fields UX bug sprint

## Problem Statement
Community prefix (`/c/{slug}/`) is missing from 66+ user-facing links across 8 route files. This causes the #1 recurring user complaint: navigation drops community context, showing Rhodes data when user is in Fox Family, and breaking merge/compare/identify workflows.

Session 111 fixed community prefix in compare_routes.py (13 routes), engagement_routes.py, upload_routes.py, admin_routes.py, page_routes.py, and identity_routes.py. But the audit revealed 66 MORE gaps that weren't caught.

## Audit Results (from Session 111 subagent)

### discoveries_routes.py — 9 gaps
Helper `_build_discovery_card()` (line 651) doesn't receive nav_prefix. Caller computes it but doesn't pass it. Lines: 725, 737, 763, 784, 886, 908, 953, 1041, 1175.

### identity_routes.py — 17 gaps
All `HttpHeader("HX-Redirect", f"/person/{canonical_id}")` need nav_prefix. Most handlers already have `request` parameter. Lines: 96, 368, 1545, 1548, 1604, 1607, 1773, 1776, 2162, 2238, 2554, 3339, 3443, 3540, 3629, 3757, 3871.

### compare_routes.py — 9 gaps (ADDITIONAL to Session 111 fix)
Main GET route (line 42) missing `request` parameter. Lines: 702, 826, 2577, 2582, 2963, 3556, 3559, 5795, 5808.

### estimate_routes.py — 3 gaps
Lines: 102, 216, 443.

### match_facecompare_routes.py — 2 gaps
Lines: 715, 724.

### event_routes.py — 2 gaps
Lines: 303, 905.

### page_routes.py — 5 gaps
Lines: 516, 919, 12607, 12674, 733-734.

### admin_routes.py — minor gaps

## Correct Pattern (from browse_routes.py)
```python
community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
nav_prefix = _main_mod.community_url_prefix(community_slug)
href=f"{nav_prefix}/person/{identity_id}"
```

## Session 111 Feedback Summary (62 items)
- P0 (8): FB-029 (FIXED), FB-034 (FIXED), FB-036 (partial fix), FB-041 (FIXED), FB-047 (FIXED), FB-052 (BACKLOG), FB-054 (clarified as P1), FB-062 (partial fix), FB-063 (FIXED)
- P1 (24): FB-025-028, FB-030-033, FB-037-040, FB-042-046, FB-048-051, FB-055 (FIXED), FB-056-061
- P2 (7): FB-028, FB-035, FB-038, FB-045, FB-046, FB-053

## What Session 111 Already Shipped (4 commits)
1. `b38c360` — Community filter on speed-run + CI test + people page scoping
2. `bdee81b` — Community prefix on all compare_routes.py links
3. `b3ee59a` — Community prefix on 5 more route files + FB-041 through FB-057
4. `e400f94` — Person page auto-redirect + merge error messages + Select All checkbox

## Known Pre-Existing Test Failure
- `test_partial_has_public_page_link` in tests/test_internal_photo_links.py — pre-existing, not caused by session 111 changes

## Deferred to Future Sessions
- FB-052: "Confirm as {Name}" merge UX — needs PRD-level design
- PERF-008/009: Speed-run and Discovery performance — needs profiling
- FB-036/037: Tagging persistence — partial fix shipped, needs production verification
- UX-102 through UX-113: Various UX improvements logged in BACKLOG
