# Session 98B Log

**Date:** 2026-03-12  
**Worktree:** `/tmp/rhodesli-gedcom-hotfix`  
**Branch:** `codex/gedcom-search-hotfix`

## Trigger

- User reported that the live GEDCOM link panel took about a minute to load.
- User also reported duplicate-looking GEDCOM search results and general app
  sluggishness while using the person page.
- Session 99 work was active in parallel, so all diagnosis and fixes were
  isolated to a separate worktree.

## Investigation

- Confirmed live route slowness with direct timing checks.
- Measured Supabase page timings for current GEDCOM views.
- Verified production now has `21,944` current GEDCOM individuals after Session
  98.
- Verified the user-linked person
  `a0a845d7-4eca-4255-b741-77ff310dc619` is linked to
  `@I132559748883@`.

## Findings

- Session 98 moved request-path GEDCOM loading onto the full rich mirror.
- The GEDCOM link search auto-runs on page load, so the expensive scan happens
  immediately on admin person pages.
- The minute-scale behavior was therefore a real regression, not user error.

## Hotfix Work

- Added exact single-record GEDCOM lookup helper.
- Switched GEDCOM search to database-prefiltered thin candidates.
- Kept link/save routes off the full mirror load path.
- Restored the explicit Dockerfile ML-package copy contract required by the
  repo's deployment/runtime coverage tests.
- Added regression tests for:
  - candidate dedupe by `gedcom_id`
  - link route exact-row lookup
  - thin-field bulk load contract

## Verification

- `pytest tests/test_gedcom_routes.py -q` -> `48 passed`
- `pytest tests/test_tree_api.py -q` -> `27 passed`
- `pytest tests/test_sync_api.py::TestDockerfileModuleCoverage -q` -> `10 passed`
- `pytest tests/ -x -q` -> `4137 passed, 21 skipped`
- `pytest rhodesli_ml/tests/ -x -q` -> `588 passed, 2 skipped`
- Real-env patched timings captured in
  `docs/assessments/session-98b-gedcom-search-hotfix.json`

## Follow-Up

- Tree-wide full-mirror GEDCOM consumers still deserve a separate cold-start
  performance pass.
- Session 99 was explicitly told not to touch GEDCOM/person-route/deploy paths
  while this hotfix was in progress.
