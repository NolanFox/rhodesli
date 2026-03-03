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
- [ ] Phase 3: PRD-025 Gap Closure (deferred — Claude downtime)
- [ ] Phase 4: Isaac Cohen E2E (deferred — depends on deploy)
- [ ] Phase 5: Session Docs (partial)

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

## Deferred Work
- **Phase 3: PRD-025 Gap Closure** — Reference context on shareable result page, merge/reject on result page. Session interrupted by Claude downtime.
- **Phase 4: Isaac Cohen E2E** — Browser verification. Depends on deployment.
- **Phase 5: Full session docs** — CHANGELOG, ROADMAP updates.

## Fixes
- Fixed `test_compare_status_starting` stale hardcoded timestamp → `datetime.now()`
- Fixed `_save_comparison_result` missing `result_id` and `created_at` fields
- Fixed test patching `find_nearest_neighbors` on wrong module

## Red Flags
- Pre-existing test failures in `test_skipped_focus.py` (~60) and `test_compare_intelligence.py` (2) — unrelated to this session
