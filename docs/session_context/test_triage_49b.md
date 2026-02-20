# Test Triage — Session 49B Final

## Summary
- Total tests: 2494 (excluding e2e)
- Passing: 2367
- Failing: 127
- Skipped: 19
- **Real bugs: 0**
- **State pollution: 127 (100% of failures)**

## Classification

| Category | Count | Examples | Action |
|----------|-------|----------|--------|
| State pollution | 127 | All 127 — every failing test passes in isolation | Test infra debt |
| Real bugs | 0 | — | — |
| Missing fixture | 0 | — | — |
| Stale tests | 0 | — | — |

## State Pollution Details

All 127 failures are caused by test ordering — some earlier test(s) modify module-level state in `app.main` (likely `_identities`, `_photo_index`, or geocoding data) via MagicMock patches that leak across test boundaries. Every single failing test passes when run in isolation.

### Failures by file (all pass in isolation)

| Test File | Failures | Verified Isolation |
|-----------|----------|-------------------|
| test_public_photo_viewer.py | 30 | 30/30 pass alone |
| test_public_person_page.py | 28 | 35/35 pass alone |
| test_skipped_focus.py | 14 | 58/58 pass alone |
| test_share_download.py | 12 | 12/12 pass alone |
| test_triage.py | 6 | passes alone |
| test_photo_viewer_polish.py | 6 | passes alone |
| test_photo_id_consistency.py | 6 | passes alone |
| test_storage.py | 4 | passes alone |
| test_ux_enhancements.py | 3 | passes alone |
| test_person_links.py | 3 | passes alone |
| test_people_page_links.py | 3 | passes alone |
| test_timeline.py | 2 | passes alone |
| test_sync_api.py | 2 | passes alone |
| test_public_browsing.py | 2 | passes alone |
| test_photo_validation.py | 2 | passes alone |
| test_sequential_identify.py | 1 | passes alone |
| test_process_uploads.py | 1 | passes alone |
| test_photo_nav_persistence.py | 1 | passes alone |
| test_nav_consistency.py | 1 | passes alone |

### Root cause indicator
First failure: `test_nav_consistency.py::test_nav_links_present[/map]` with error `TypeError: Object of type MagicMock is not JSON serializable`. A mock object is leaking into the map route's data path.

### Pre-existing
This is documented in BACKLOG.md under "Deferred from Session 49B Audit":
> **Pre-existing test ordering bug**: `test_nav_consistency` `/map` test fails in full suite (state pollution), passes in isolation. Not caused by audit session.

## Recommendation
- **Immediate**: Run tests with `pytest -x` (stop at first failure) for CI — catches real bugs while avoiding cascade
- **Future session**: Add `autouse` fixture to reset `app.main` module-level caches between tests, or use `pytest-randomly` to detect and fix pollution sources
- **Root cause**: Bisect the test suite to find which test file leaks MagicMock into `app.main` module state
