# Session 142 Assessment

## Shipped

### Interactive Feedback Fixes (FB-001 through FB-012)
- [x] **FB-001** (P1): Similar Identities links → person page not review grid — FIXED
  - Evidence: test_neighbor_card_links_to_person_page passes, code change in cards.py
- [x] **FB-002** (P1): Compare "View Photo" missing community prefix — FIXED
  - Evidence: nav_prefix added to hx_get in compare_routes.py
- [x] **FB-003** (P1): Multi-merge from Focus mode returns redirect breaking layout — FIXED
  - Evidence: Focus mode now gets toast + OOB delete instead of HX-Redirect
- [x] **FB-004** (P0): "Confirm as [Name]" only confirmed, didn't merge — FIXED
  - Evidence: merge_target_id param added to both /confirm and /inbox/confirm routes
- [x] **FB-006** (P1): Bulk merge "already merged" shown as errors — FIXED
  - Evidence: Toast now separates already-merged from real failures
- [x] **FB-007** (P1): Similar panel shows stale merged identities — FIXED
  - Evidence: merged_into filter + 100-base fetch limit in neighbors endpoint
- [x] **FB-008** (P1): Esther "No similar identities" — FIXED
  - Evidence: Fetch limit increased from 20 to 100
- [x] **FB-010** (P1): Face overlay click doesn't navigate to person page — FIXED
  - Evidence: Hyperscript go-to-url now uses /person/{id}
- [x] **FB-011** (P2): No "Confirm Only" option when match suggested — FIXED
  - Evidence: "Confirm Only" button added alongside "Confirm as [Name]"
- [x] **FB-012** (P2): Similar panel persists after confirm — FIXED
  - Evidence: OOB innerHTML clear for expand-{id} div on confirm

### Codex Audit Fixes
- [x] **P1 CSRF**: `/inbox/{id}/confirm` missing `_check_origin()` — FIXED
- [x] **P1 Merge Side Effects**: Confirm+merge now runs `_merge_annotations()` + recalibration hook
- [x] **P2 Rematch Target**: Post-confirm rematching uses surviving target ID

### Batch Gemini Estimation
- [x] Script: `scripts/batch_gemini_for_person.py` — reads from Supabase, full preset, face coords, GEDCOM context
- [x] Test run: 2 photos successful with rich metadata (face analysis, ages, clothing, location)
- [-] Full batch: 14/277 photos complete, running overnight (~4.5h estimated)

### Documentation
- [x] PRD-059: Temporal Co-Occurrence Analysis
- [x] Session 140 prompt backfilled (harness gap)
- [x] Feedback log: docs/feedback/session-142-feedback.md
- [x] Codex audit: docs/session_context/session-142-codex-audit.md

## Deferred
- **FB-005** (P2): Merge from Similar panel toast — partially improved, needs OOB toast fix
- **FB-009** (P2): Speed Loop auto-suggestion — feature gap, not a bug. Needs proposal pipeline work.
- **P2 Batch JSON Safety**: Atomic writes for date_labels.json — BACKLOG
- **P2 Supabase Labels**: Batch script should also write to Supabase date labels — BACKLOG

## Red Flags
- **LOW**: Gemini batch GEDCOM loading is slow (~1 min per photo due to full tree pagination). Future optimization: cache GEDCOM data in-process across all photos.
- **LOW**: Supabase logging for batch Gemini calls failed due to schema mismatch (contract_valid, full_response_hash columns). Fixed in code but running batch still has old code. Non-fatal — data saved to JSON, Gemini API calls table has gaps for this batch.
- **NONE**: All 3815 tests pass throughout session.

## AI Tool Usage
- **Tool**: Codex CLI v0.115 (o4-mini)
- **Agent type**: Independent (fresh context)
- **Task**: Security + code quality audit of Session 142 changes
- **Findings**: 3 P1 (CSRF, merge side effects, label store), 2 P2 (rematch target, JSON safety)
- **Acted on**: All 3 P1s + 1 P2 fixed immediately
- **Deferred**: 2 P2s to BACKLOG (atomic writes, Supabase labels)
- **Value assessment**: STRONG — CSRF vulnerability on inbox confirm would not have been caught otherwise

## Next Session Should Verify
1. Gemini batch completed for all 279 photos
2. Date labels quality — spot-check 10 photos for accuracy
3. Deploy production and browser-verify FB-001/004/010 fixes
4. Begin PRD-059 Phase 2 (event grouping)
