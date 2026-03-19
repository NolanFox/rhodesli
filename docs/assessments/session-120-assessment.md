# Session 120 Assessment — ML Comparison Script + UX Fix Sprint

## Per-Act Status
| Act | Status | Evidence | Concerns |
|-----|--------|----------|----------|
| Phase 0 | PASS | session log created, baseline 3234 tests | None |
| Phase 1 | PASS | scripts/compare_ml_embeddings.py + 19 tests pass | Not tested with real ML service (needs env vars) |
| Phase 2 | PASS | upload_routes.py fix + 3 structural tests | Fix addresses root cause; edge cases handled by orphan repair |
| Phase 3 | PASS | 4 surfaces fixed + 11 tests, browser verified | Initial fix missed Focus view button — caught in gap review, fixed |
| Phase 4 | PASS | notification code + 3 tests | Cannot browser-verify without production upload (READ-ONLY) |
| Phase 5 | PASS | search box in Focus view + 2 tests, browser verified | "Search to Merge" visible on production |
| Phase 6 | PASS | community filter/sort + 7 tests, browser verified | "Same community first" dropdown visible on production |
| Phase 7 | PASS | assessment, changelog, session log, BACKLOG | |

## Shipped
- [x] Phase 0: Orient — Evidence: session log, baseline tests
- [x] Phase 1: ML embedding comparison script — Evidence: 19 tests, scripts/compare_ml_embeddings.py
- [x] Phase 2: Sentry alert root cause fix — Evidence: 3 tests, grouping now loads from JSON
- [x] Phase 3: FB-009 confirm button disabled for unidentified — Evidence: 11 tests, browser JS confirmed disabled=true, bg-gray-400, title="Name this person first"
- [x] Phase 4: FB-008 cross-batch match notifications — Evidence: 3 tests
- [x] Phase 5: FB-001 merge search in Focus view — Evidence: 2 tests, browser screenshot shows "Search to Merge" box
- [x] Phase 6: FB-011 community filter on Similar Identities — Evidence: 7 tests, browser screenshot shows "Same community first" dropdown on Albert Fox person page

## Browser Verification (Production, READ-ONLY)
- **FB-009**: JS confirmed `disabled: true`, `bg-gray-400`, `cursor-not-allowed`, `title: "Name this person first"`, no hx-post. Verified for "Unidentified Person efb4d153" in Focus view.
- **FB-001**: "Search to Merge" section with "Search by name to merge..." input visible below Similar Identities in Focus view.
- **FB-011**: "Same community first" dropdown visible at top of Similar Identities panel on Albert Fox person page (/c/fox-family/person/85546ebf...). Fox Family matches shown first.
- **FB-008**: Notification bell exists, polls /api/notifications/count. Cannot verify notification content without uploading (READ-ONLY rule).
- **Gap found**: Initial FB-009 fix missed Focus view button (identity_card_expanded). Fixed in follow-up commit.

## Deferred
- None

## Red Flags
- **FIXED** FB-009 Focus view button was a separate code path from review_action_buttons() — caught during browser verification, fixed and pushed.
- **LOW** ML comparison script untested with real ML service — requires ML_SERVICE_URL env var. Will be verified in next upload session (AD-229 criterion).

## Auto-Fix Summary
- Issues found: 2 (Focus view confirm button, BACKLOG IDs)
- Auto-fixed: 2
- Deferred: 0

## Test Summary
- Baseline: 3234 passed
- Final: 3279 passed (+45 new tests)
- All pass in 28.2s

## Next Session Should Verify
1. Upload a photo and verify FB-008 notification appears in bell badge
2. Run scripts/compare_ml_embeddings.py with real ML service (AD-229 cosine criterion)
3. Check Sentry for any remaining POST-SYNC VALIDATION warnings after next upload
