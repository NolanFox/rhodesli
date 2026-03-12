# Session 100 Fox Family Hotfix Log

## Purpose
Preserve the active performance/context audit and hotfix work for the Fox Family workflow before further implementation.

## Branches
- `codex/session-100-perf-hotfix` — preserved the Fox Family performance/context recovery
- `codex/session-100-speed-loop` — layered the Session 100 tagging-loop implementation on top

## User Feedback Captured
- Tree page looked broken, then eventually loaded after multiple minutes.
- Tree expand actions felt dead.
- Tree UX is unusable for real tagging/linking work.
- Person pages in Fox Family take too long to load to be usable.
- Photo navigation from a person page incorrectly falls back to collection order instead of person-gallery order.
- Community context is being dropped:
  - Fox Family flows fall back to Rhodes/default routes.
  - Admin/share mode boundaries become unclear after route transitions.
  - Identify/admin links can land in Rhodes instead of Fox Family.
- Public/admin visual language is inconsistent across Fox Family workflow steps.
- Sorting by earliest is not trustworthy when date-estimation/Gemini enrichment has not run.
- Upload-review -> identify -> person -> tree flow is not fast enough for “speed run” tagging/linking.

## Screenshots Referenced In This Pass
- Fox Family person page -> photo page -> wrong next/previous behavior.
- Fox Family photo page -> identify page dropping into Rhodes/public UX shell.
- Identify page “View in Admin Queue” going to Rhodes/default workstation.
- Tree page eventually loading but too slowly to be operational.

## Findings So Far
- Live `/api/tree/data?...` and `/api/tree/expand?...` were taking about `74s` cold for a linked person.
- Root cause: tree endpoints were cold-loading the full GEDCOM relationship mirror and full GEDCOM individuals mirror for single-person tree requests.
- Local hotfix work now introduces targeted GEDCOM slice loading for linked tree requests/expands instead of full-mirror loads.
- Local timing after the targeted tree hotfix:
  - `/api/tree/data?...` down to about `6.4s` cold / `2.4s` warm
  - `/api/tree/expand?...` down to about `0.25s`
- Local person-page timing after the social-graph and GEDCOM-panel fixes:
  - Fox Family person page about `1.46s` anonymous
  - Fox Family person page about `1.79s` admin
- This is a real recovery, but tree first-load performance still needs more work.
- A second root issue is context leakage:
  - community prefix not preserved consistently
  - photo/person/identify/tree routes drop workflow context
  - some route transitions drop admin/community expectations
- A third root issue is workflow shape:
  - Rhodesli is still too single-item and too mode-fragmented for best-in-class tagging
  - the user expectation is closer to Mylio/Lightroom/Apple cluster workflows

## Code Work In Progress
- Added targeted GEDCOM helpers in [app/relationship_routes.py](/Users/nolanfox/rhodesli/app/relationship_routes.py)
- Added targeted tree-slice builder in [app/page_routes.py](/Users/nolanfox/rhodesli/app/page_routes.py)
- Exported new helpers via [app/main.py](/Users/nolanfox/rhodesli/app/main.py)
- Added tree regression tests in [tests/test_tree_api.py](/Users/nolanfox/rhodesli/tests/test_tree_api.py)
- Added community-prefixed tree fetch support in [app/static/js/family-tree.js](/Users/nolanfox/rhodesli/app/static/js/family-tree.js)
- Began person/photo context fixes in [app/person_routes.py](/Users/nolanfox/rhodesli/app/person_routes.py) and [app/page_routes.py](/Users/nolanfox/rhodesli/app/page_routes.py)
- Replaced the `get_closest_connections()` hot path in [rhodesli_ml/graph/social_graph.py](/Users/nolanfox/rhodesli/rhodesli_ml/graph/social_graph.py)
  with a single-source traversal
- Simplified the admin GEDCOM status panel in [app/relationship_routes.py](/Users/nolanfox/rhodesli/app/relationship_routes.py)
  so it no longer blocks person-page render on extra GEDCOM detail fetches
- Added community-prefix regression coverage for identify and person/photo flows
  in [tests/test_identify.py](/Users/nolanfox/rhodesli/tests/test_identify.py) and
  [tests/test_public_person_page.py](/Users/nolanfox/rhodesli/tests/test_public_person_page.py)

## Tests Run
- `pytest tests/test_tree.py tests/test_tree_api.py -q`
  - `41 passed`
- `pytest tests/test_tree.py tests/test_tree_api.py tests/test_public_person_page.py tests/test_public_photo_viewer.py tests/test_photo_navigation.py -q`
  - `115 passed, 2 skipped`
- `pytest tests/test_identify.py tests/test_public_person_page.py tests/test_tree.py tests/test_tree_api.py tests/test_public_photo_viewer.py tests/test_photo_navigation.py -q`
  - `156 passed, 2 skipped`
- `pytest rhodesli_ml/tests/test_social_graph.py -q`
  - `34 passed`
- `pytest tests/ -x -q`
  - `4157 passed, 7 skipped`
- `pytest rhodesli_ml/tests/ -x -q`
  - `590 passed`

## Verification Notes
- The full app suite passed when run on its own.
- A prior parallel run of full app + full ML suites produced an e2e startup timeout,
  which appears to have been resource contention rather than a functional regression.
- Local performance checks after the latest fixes:
  - Fox Family person page: about `1.46s` anonymous / `1.79s` admin
  - Fox Family tree data: about `6.43s` cold / `2.36s` warm
  - Fox Family tree expand: about `0.25s`

## Concerns Still Open
- Tree local timing is improved but still too slow on first load.
- Need full audit of person/photo/identify/admin context transitions under community prefix.
- Need consistent route contracts for:
  - community context
  - admin/public mode
  - person-photo navigation context
  - review-section context
- Need explicit plan for upload review -> identify -> person -> tree “speed run” workflow.
- Need a true batch/cluster tagging surface to match best-in-class photo software.

## External Product Research Logged
- See [session-100-face-tagging-and-fox-family-audit.md](/Users/nolanfox/rhodesli/docs/assessments/session-100-face-tagging-and-fox-family-audit.md)
  for the cross-product tagging benchmark and Rhodesli implications.
- See [session-100-fox-family-screenshot-audit.md](/Users/nolanfox/rhodesli/docs/assessments/session-100-fox-family-screenshot-audit.md)
  for the screenshot-by-screenshot workflow audit and fix-status mapping.

## Attribution

- User: live Fox Family workflow feedback, expectations, and screenshot evidence
- Codex: screenshot audit, root-cause mapping, hotfix status evaluation
- Antigravity: critical workflow review prioritizing batch/cluster tagging and auto-advance

## Antigravity Workflow Update

- The hotfix successfully stabilized request-path performance and route leakage.
- The tagging workflow is still too single-item and mode-fragmented to allow "speed-running" 600 photos.
- Session 100 Implementation MUST include Batch Cluster Confirmation, Auto-Advance, and explicit "Ignore Noise" actions to be considered complete.
- The multi-face expanded gallery MUST grid-wrap to handle dense photos (15+ faces).

## Antigravity Mockup Pack Status

- **Date:** 2026-03-12
- **Files Read:** session-100-antigravity-mockup-prompt.md, session-100-context.md, 040_multi_community_bootstrap_and_face_cards.md
- **Files Written:** docs/assessments/session-100-antigravity-mockup-pack.md
- **Mockups Created:**
  1. `Mockup A: The Cluster Queue` - A bulk confirmation surface for highly-confident matches.
  2. `Mockup B: The Speed Loop` - A 2-pane triage UI with auto-advance and 1-click "Ignore Stranger".
  3. `Mockup C: The Wrap Grid` - A progressively disclosed expanded grid for dense group photos.
- **Top Conclusion:** The highest ROI, lowest-risk first step is implementing `Mockup B (The Speed Loop)`. By simply adding an auto-advance behavior driven by a `queue_id` or query parameter directly in the existing Identify route, the process changes from a CMS to a triage engine without requiring complex new backend cluster logic upfront.

## Session 100 Speed Loop Implementation (Codex)

### Scope Implemented
- Preserved gallery/archive context through sequential photo tagging
- Added cross-photo auto-advance in sequential mode when working from a person-gallery context
- Added explicit `Ignore Stranger` action using the existing `SKIPPED` state
- Added dense multi-face grid fallback on the public photo page
- Added regression coverage for the new context/auto-advance/grid behavior

### Files Touched
- [app/page_routes.py](/Users/nolanfox/rhodesli/app/page_routes.py)
- [app/photo_routes.py](/Users/nolanfox/rhodesli/app/photo_routes.py)
- [app/identity_routes.py](/Users/nolanfox/rhodesli/app/identity_routes.py)
- [tests/test_sequential_identify.py](/Users/nolanfox/rhodesli/tests/test_sequential_identify.py)
- [tests/test_public_photo_viewer.py](/Users/nolanfox/rhodesli/tests/test_public_photo_viewer.py)
- [docs/assessments/session-100-speed-loop-implementation.md](/Users/nolanfox/rhodesli/docs/assessments/session-100-speed-loop-implementation.md)

### Verification
- Focused gates:
  - `ruff check app/page_routes.py app/photo_routes.py app/identity_routes.py tests/test_sequential_identify.py tests/test_public_photo_viewer.py`
  - `pytest tests/test_sequential_identify.py tests/test_public_photo_viewer.py tests/test_photo_navigation.py tests/test_inline_face_actions.py tests/test_public_person_page.py tests/test_identify.py -x -q`
    - `151 passed, 2 skipped`
- Follow-up CI stabilization:
  - GitHub fast tests exposed one additional failure in
    `tests/test_photo_sorting.py::TestPhotoSortBySource::test_by_source_option_in_dropdown`
    caused by live iteration over `_photo_cache.items()` under patched test dictionaries.
  - Codex fixed that with a snapshot iteration in [app/main.py](/Users/nolanfox/rhodesli/app/main.py).
  - Focused re-check after the fix:
    - `ruff check app/main.py`
    - `pytest tests/test_photo_sorting.py tests/test_sequential_identify.py tests/test_public_photo_viewer.py -x -q`
      - `45 passed`
- Full ML suite:
  - `pytest rhodesli_ml/tests/ -x -q`
    - `590 passed`
- Full app suite in this working tree:
  - blocked by active local `data/identities.json` drift from live app usage, not by the code changes
  - failure surfaced in `tests/test_data_integrity.py::TestOrphanedIdentities::test_confirmed_anchors_in_face_to_photo`
- Clean-worktree verification from commit `0605f95`:
  - `pytest rhodesli_ml/tests/ -x -q`
    - `590 passed`
  - `pytest tests/ -x -q`
    - first cold run hit an e2e app-server startup timeout
    - second warm run passed: `4146 passed, 21 skipped`
- Final clean-worktree verification from commit `5e88a87`:
  - `pytest rhodesli_ml/tests/ -x -q`
    - `588 passed, 2 skipped`
  - `pytest tests/ -x -q`
    - `4146 passed, 21 skipped`
- PR #10 GitHub `test` check passed for commit `5e88a87`.

### Important Working-Tree Note
- `data/identities.json` is dirty from live archive work and must stay out of the Session 100 commit.
- Merge-quality verification should happen in a clean worktree after committing the code/test/docs changes.
