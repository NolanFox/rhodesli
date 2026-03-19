# Session 120 Log — ML Comparison Script + UX Fix Sprint
Started: 2026-03-19
Prompt: docs/prompts/session-120-prompt.md

## Baseline
- Tests: 3234 passed, 1 flaky (test_photo_og_image_is_absolute_url — passes alone), 9 skipped
- Time: 32s
- Mode: implementation

## Phase Checklist
- [x] Phase 0: Orient — session log created, baseline verified
- [x] Phase 1: ML Embedding Comparison Script — 19 tests, scripts/compare_ml_embeddings.py (worktree)
- [x] Phase 2: Sentry Alert Investigation + Fix — root cause: grouping loaded from Supabase instead of JSON, 3 tests
- [x] Phase 3: FB-009 — Confirm Button Fix — disabled for unidentified in 3 surfaces, 9 tests (worktree)
- [x] Phase 4: FB-008 — Cross-Batch Match Notifications — notification after upload, 3 tests
- [x] Phase 5: FB-001 — Merge Search in Focus View — always-visible search box, 2 tests (worktree)
- [x] Phase 6: FB-011 — Community Filter on Similar Identities — same-community-first sort + dropdown, 7 tests (worktree)
- [x] Phase 7: Harness Outputs

## Verification Gate
- [x] All phases re-checked against original prompt
- [x] Feature Reality Contract passed
- [x] Assessment exists
- [ ] `git log origin/main..HEAD` empty

## Execution
- 4 parallel worktrees (Phases 1, 3, 5, 6) + sequential on main (Phases 2, 4)
- All merges clean (no conflicts)
- Final test count: 3278 passed (44 new tests)

## Phase Details

### Phase 0: Orient
- Session 120 set in current_session.txt
- Mode: implementation

### Phase 1: ML Embedding Comparison Script (Worktree)
- Created scripts/compare_ml_embeddings.py
- Local InsightFace via extract_faces() → mu key
- ML service via MLServiceClient.detect_and_embed() → embedding key
- Face matching by detection order + IoU fallback
- Cosine similarity (dot product of L2-normed vectors)
- Exit code 0 if all >= 0.999, 1 otherwise
- --local-only flag for local-only mode
- 19 tests across 6 classes

### Phase 2: Sentry Alert Fix
- Root cause: grouping step at upload_routes.py:998 used load_registry() which reads from Supabase
- process_directory() writes new faces to JSON; Supabase doesn't have them yet
- If grouping merges, save_registry() overwrites JSON with stale Supabase data
- Fix: Load from JSON directly (IdentityRegistry.load + PhotoRegistry.load)
- Also fixed cross-batch matching photo_reg to load from JSON
- Demoted POST-SYNC VALIDATION from error to warning
- 3 structural tests

### Phase 3: FB-009 Confirm Button Fix (Worktree)
- Disabled confirm button for unidentified persons in 3 surfaces:
  1. Photo modal quick-action (page_routes.py)
  2. Person detail page (person_routes.py)
  3. Review action buttons (main.py)
- Gray button with tooltip "Name this person first"
- 9 tests

### Phase 4: FB-008 Cross-Batch Match Notifications
- After find_cross_batch_matches(), create notification via _create_notification()
- Type: "upload_matches"
- Body: "Upload complete: N faces detected, M potential matches found. Top match: [name] (distance X.XX)"
- Uses existing notification infrastructure (Supabase table, bell badge)
- 3 tests

### Phase 5: FB-001 Merge Search in Focus View (Worktree)
- Added always-visible "Search to Merge" section to identity_card_expanded
- Search input with typeahead (300ms debounce) hitting /api/identity/{id}/search
- Admin-only, data_testid="focus-merge-search" for testing
- 2 tests (admin has search, non-admin doesn't)

### Phase 6: FB-011 Community Filter on Similar Identities (Worktree)
- Post-processes neighbors results to sort same-community first
- Added community filter dropdown (Same community / All communities / specific)
- HTMX dropdown re-fetches panel with ?community_filter param
- Does NOT modify frozen core/neighbors.py
- 7 tests

### Gap Review + Fix
- **FB-009 Focus view gap found**: Browser verification revealed confirm button still green/active in Focus view. Root cause: `identity_card_expanded()` has its own confirm button at main.py:5678, separate from `review_action_buttons()`. Fixed + 2 new tests.
- **BACKLOG gap**: Session 119 feedback items (FB-001 through FB-011) never added to BACKLOG. IDs UX-131-140 were taken. Added as UX-206 through UX-215 with correct statuses.
- **Browser verification**: All 4 features verified on production (FB-009 via JS inspection, FB-001/FB-011 via screenshots, FB-008 code-only — can't upload on production)
