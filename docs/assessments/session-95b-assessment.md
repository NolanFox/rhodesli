# Session 95b Assessment — Community Data Scoping

## Shipped

- [x] **Act 0: Orient** — Session set, tests baseline 2491 pass
- [x] **Act 1: Foundation Utilities** — `community_url_prefix()`, `_get_community_photo_ids()`, `_get_community_identity_ids()`, `_compute_sidebar_counts(community=)`. 18 tests.
- [x] **Act 2 Track B: Sidebar + Workspace Switcher** — Sidebar community params, dynamic header/subtitle, community-prefixed links, conditional sections (Review/Admin/Advanced Browse hidden for non-Rhodes), workspace switcher (admin "Switch" link + HTMX dropdown). 21 tests.
- [x] **Act 2 Track C: Route Handler Scoping** — `/photos` filters by community photo IDs, `/` command center filters identity lists, `/upload` POST tags photos to community, empty states for non-Rhodes. 38 tests.
- [x] **Act 2 Track D: Empty States + PRD-036** — Enhanced community landing page (Upload CTA, archive description, tool links). PRD-036 workspace/onboarding vision (250 lines). ROADMAP + BACKLOG updates. 7 tests.
- [x] **Docs: OD-008/009** — Dev vs prod environment separation, observability retention (Nolan feedback). ENV-001, OBS-001/002 in BACKLOG + ROADMAP.

## Browser Verification (6/6 PASS)

| Route | Expected | Result |
|-------|----------|--------|
| `/c/fox-family/` | Fox Family name, empty state + Upload CTA + tools | PASS |
| `/c/fox-family/photos` | "No photos yet" (filtered to 0) | PASS |
| `/c/fox-family/upload` | Fox sidebar, scoped links | PASS |
| `/` (Rhodes) | "Jewish Community of Rhodes", all sections | PASS |
| `/photos` (Rhodes) | "Showing 297 photos" | PASS |
| Workspace switcher | "Switch" link visible for admin | PASS |

## Deferred

- Upload test at `/c/fox-family/upload` → verify photo appears in Fox not Rhodes (needs actual upload test, deferred to next session)
- Pre-existing flaky tests: `test_my_contributions_page_accessible`, `test_scene_analysis_method_label`, `test_rejects_too_many_files` — all test ordering issues or stale assertions, not from this session

## Red Flags

- **LOW**: Pre-existing flaky tests (4-14 failures depending on order) — not new, but should be fixed. See BACKLOG.
- **LOW**: Sentry error PYTHON-ASGI-7 (circular import `_load_corrections_log`) — pre-existing, fires on local dev. Documented in OD-008.

## Test Count

- 84 new tests (18 + 21 + 38 + 7)
- All pass in isolation and sequential runs
- Pre-existing flaky tests unrelated to changes

## Next Session Should Verify

1. Upload a real photo at `/c/fox-family/upload` and confirm it appears in Fox community only
2. Fix pre-existing flaky tests (test ordering issues)
3. Add `SENTRY_ENVIRONMENT=development` to local `.env`
