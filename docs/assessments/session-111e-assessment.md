# Session 111e Assessment

## Shipped
- [x] Phase 1: Performance caches — TTL cache for `_get_confirmed_identity_suggestions()` and `_get_speed_run_clusters()` (30s, invalidated on save_registry). Evidence: 4 tests pass, production focus mode loads.
- [x] Phase 2: FB-077 Confirm button UX — inline error for unidentified persons on person page. Evidence: 2 tests pass, verified code path.
- [x] Phase 3: FB-075 Face overlay fix — `_load_photo_dimensions_cache()` also reads Supabase photo registry. Evidence: 23 overlays on production photo f1ae3676f59943b2.
- [x] Phase 4a: Focus URL stripping — `hx_push_url="false"` on all focus mode action buttons. Evidence: JS verification on production confirms attribute present.
- [x] Phase 4b: FB-072 Approval history — "Recently Approved" section on /admin/approvals. Evidence: 20 items displayed on production with timestamps and contributor emails.
- [x] Phase 5: Deploy SUCCESS via `railway up` (Dockerfile builder). Evidence: Railway deployment ed8d2035 status=SUCCESS.

## Deferred
- Phase 1C: Profile `find_nearest_neighbors()` — the caching fixes address the immediate performance issue. Deeper profiling needs timing data from production admin sessions. BACKLOG: PERF-002.
- Source URL not saving — needs production investigation with network inspection. May be transient cache issue resolved by TTL cache changes.
- FB-076: Community awareness on approve — needs production verification with actual approval flow. Low confidence this is broken.

## Red Flags
- [LOW] Pre-existing test ordering issue: `test_suggestions_have_community_badge` fails when run in full suite order but passes alone. Fixed by adding cache clearing to `_mock_registry()`, but root cause is test isolation.
- [LOW] Git push triggered RAILPACK builder (not DOCKERFILE) — had to use `railway up` CLI. Known issue (Lesson 117). Previous deploy also had this; railway.toml corrects it.

## Next Session Should Verify
1. Performance improvement is noticeable during triage sessions (qualitative feedback from Nolan)
2. Confirm button error is visible on person page for unidentified persons
3. Focus mode URL stays stable through multiple actions (intermittent issue)
