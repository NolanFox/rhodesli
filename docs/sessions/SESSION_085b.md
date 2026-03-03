# Session 85b: Compare Navigation + PRD-025 Gap Closure

Started: 2026-03-03
Prompt: docs/prompts/session-85b-prompt.md
PRD: docs/prds/025_compare_functional_rebuild.md
Context: docs/session_context/session-85b-context.md
Predecessor: Session 85 (v0.87.0)

## Phase Checklist
- [x] Phase 0: Orient
- [x] Phase 1: Archive Photo → Compare
- [x] Phase 2: Navigation Links
- [x] Phase 3: PRD-025 Gap Closure
- [x] Phase 4: Isaac Cohen E2E + Browser Verification
- [x] Phase 5: Session Docs

## Phase 0: Orient
- Set `.claude/current_session.txt` to `85b`
- Read: tasks/lessons.md, PRD-025, session 85 assessment
- Created session log
- Confirmed session 85 deployment is live

## Phase 1: Archive Photo → Compare
- New `GET /api/compare/from-photo?photo_id=X&identity_id=Y` route
  - Loads photo faces from photo_index/embeddings
  - Computes per-face L2 distances against person's anchors
  - Calibrated confidence scores + tier classification
  - Merge/Not Same admin actions on each face
  - Reference person context (existing top archive matches)
  - Shareable result saved to comparison_results.json
- New `GET /api/compare/search-person-photo` for photo-scoped person search
  - Returns `<a>` links (bookmarkable URLs) instead of hx-post buttons
- `/compare?photo_id=X&person_id=Y` auto-loads comparison via HTMX lazy load
- `/compare?photo_id=X` shows photo faces + person search
- 8 new tests, all passing (30 total compare tests)
- Commit: 1cc6e43

## Phase 2: Navigation Links
- Photo page: "Compare faces" link in "People in this photo" section header
- Photo page: "Compare Faces" button in CTA area
- Person page: "Compare with a photo" link now passes `person_id` query param
- Tests: `test_photo_page_has_compare_link`, `test_person_page_has_compare_link` PASS
- Commit: 1cc6e43 (combined with Phase 1)

## Phase 3: PRD-025 Gap Closure
- Reference context section on shareable `/compare/result/{id}` page
  - Shows reference person's closest existing archive matches with distances
  - Shows comparison: "Your best match (X) scores distance Y"
- Merge/Not Same admin action buttons on each match card in result page
  - HTMX swap to update row after action
- 3 new tests: `test_compare_result_shows_reference_context`, `test_compare_result_merge_action`, `test_compare_result_not_same_action`
- Commit: 31f4624

## Phase 4: Isaac Cohen E2E + Browser Verification
- Isaac Cohen identity ID: `7a7effee-4372-4da4-af08-1feaa1a3beca`
- Photo ID: `f86fdef4cd4051da`
- Compare URL: `/compare?photo_id=f86fdef4cd4051da&person_id=7a7effee-4372-4da4-af08-1feaa1a3beca`
- **Shareable link: `https://rhodesli.nolanandrewfox.com/compare/result/edc67864978f`**

### Production Bugs Fixed
1. `find_nearest_neighbors` called with `None` as `photo_registry` → fixed to pass `load_photo_registry()` (commit e514375)
2. `registry.identities` (private attribute) → fixed to use `get_identity_for_face()` and `list_identities()` (commit 00a9876)
3. Railway volume disk-full → `_save_comparison_result` now catches OSError gracefully, added auto_backup pruning at startup (commit 0d67095)

### Browser Verification Results
- [x] Compare page with photo_id + person_id loads comparison: **PASS**
- [x] 5 faces scored against Isaac Cohen with confidence bars: **PASS**
- [x] Merge/Not Same admin buttons visible on each card: **PASS**
- [x] Reference context section shows Isaac Cohen's closest archive matches: **PASS**
- [x] "Share this comparison" link opens shareable result page: **PASS**
- [x] Shareable URL works without authentication (curl returns 200): **PASS**
- [x] Photo page shows "Compare Upload" link: **PASS**
- [x] Person page shows "Compare with a photo" button: **PASS**
- [x] Result page has response form ("Do you recognize anyone?"): **PASS**

## Fixes (across continuation sessions)
- Fixed stale compare upload tests for unified pipeline (commit e07b4a5)
- Fixed `test_compare_status_starting` stale hardcoded timestamp → `datetime.now()`
- Fixed `_save_comparison_result` missing `result_id` and `created_at` fields
- Fixed test patching `find_nearest_neighbors` on wrong module
- Fixed face_ids extraction to handle both `face_ids` (string list) and `faces` (dict list) formats
- Fixed photo URL to try both `filename` and `path` keys

## Commits
1. `1cc6e43` feat(compare): archive-to-compare navigation + photo/person page links
2. `e07b4a5` fix(tests): update stale compare upload tests for unified pipeline
3. `31f4624` feat(compare): reference context + merge/reject on shareable result page
4. `e514375` fix(compare): pass photo_registry to find_nearest_neighbors, fix face_ids extraction
5. `00a9876` fix(compare): use public registry API instead of private .identities attribute
6. `0d67095` fix(compare): handle disk-full errors gracefully in comparison save

## Red Flags
- **P1: Railway volume disk full** — All comparison saves fail with OSError. Fixed with graceful catch + startup cleanup, but root cause (volume space) needs attention in a future ops session.
- **P2: Pre-existing test failures** — `test_skipped_focus.py` (~60), `test_compare_intelligence.py` (2). Unrelated to this session.
