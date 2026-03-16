# Session 109b Context: Cross-Batch Clustering Gap Closure

**Predecessor:** Session 109 (core implementation shipped, gaps remain)
**PRD:** docs/prds/049_cross_batch_clustering.md
**Assessment:** docs/assessments/session-109-assessment.md

## What Session 109 Shipped
- `core/cross_batch_matching.py` — core matching function with 16 tests
- Upload pipeline wiring (`app/upload_routes.py`)
- Recluster endpoint wiring (`app/sync_routes.py`)
- Post-confirm re-matching (`app/identity_routes.py`)
- CI test fix (`test_people_link_to_person_pages`)
- Deploy SUCCESS, 1355 dry-run matches on production

## Gap Analysis (109 Prompt vs Delivered)

### G1: Recluster does NOT write to Supabase ml_proposals
- **109 Prompt Phase 3**: "Write to ml_proposals table"
- **Delivered**: Recluster writes proposals.json only. Upload path writes Supabase. Inconsistency.
- **Fix**: Add ml_runs + ml_proposals writes to recluster endpoint (same pattern as upload).

### G2: Missing tests for upload and confirm wiring
- **109 Prompt Phase 2**: "Test: Mock upload → verify cross-batch proposals generated"
- **109 Prompt Phase 4**: "Test: Confirm an identity → verify proposals regenerated"
- **Delivered**: Neither test written.
- **Fix**: Write both tests with proper mocks.

### G3: match_type column not verified on Supabase
- **109 Assessment**: "may need Supabase migration if column doesn't exist"
- **Risk**: Upload pipeline silently fails if column missing. Recluster has no Supabase writes at all.
- **Fix**: Query Supabase schema, add column if missing, or remove from insert if not needed.

### G4: James Fields specific identity validation never done
- **109 Prompt Phase 5**: "Verify Person 3474 appears as proposal for Person 28fa8bfa"
- **Delivered**: Only verified total count (1355). Never looked up specific identities.
- **Fix**: Find actual James Fields identity IDs on production, verify cross-batch matches them.

### G5: No browser verification of proposals sidebar
- **109 Prompt Phase 7**: "Verify proposals appear in Proposals sidebar"
- **Delivered**: Never opened proposals page in browser.
- **Fix**: Run recluster with dry_run=false, navigate to Proposals, screenshot.

### G6: dry_run=false never executed
- **Impact**: Cross-batch proposals exist as code but zero proposals are persisted on production.
- **Fix**: Execute recluster with dry_run=false to actually write proposals.

### G7: No screenshots taken
- **109 Prompt Phase 7**: "Screenshot James Fields proposals"
- **Fix**: Take screenshots during browser verification.

## Implementation Plan
1. Fix G1: Add Supabase writes to recluster endpoint
2. Fix G3: Verify match_type column, handle gracefully
3. Fix G2: Write missing tests (upload mock, confirm mock)
4. Fix G6: Run recluster dry_run=false on production
5. Fix G4+G5+G7: Browser verify James Fields + proposals sidebar + screenshots

## Key Files
| File | Change |
|------|--------|
| `app/sync_routes.py` | Add ml_runs/ml_proposals Supabase writes to recluster |
| `tests/test_cross_batch.py` | Add upload mock + confirm mock tests |
| `core/cross_batch_matching.py` | No changes expected |
