# Session 109b — Cross-Batch Clustering Gap Closure

## Context
@docs/session_context/session-109b-context.md
@docs/prds/049_cross_batch_clustering.md
@docs/assessments/session-109-assessment.md

## Phase 0: Orient (3 min)
1. Set session files: current_session=109b, session_mode=implementation
2. Read gap analysis in session-109b-context.md
3. Find James Fields identity IDs on production via browser

## Phase 1: Fix Recluster Supabase Writes (15 min)
Add ml_runs + ml_proposals Supabase writes to `/api/admin/recluster` in `app/sync_routes.py`.
Same pattern as upload pipeline. Must include match_type field.
Handle match_type column gracefully (try with, fallback without).

## Phase 2: Add Missing Tests (20 min)
In `tests/test_cross_batch.py`:
- Test: Mock upload pipeline → verify cross-batch proposals generated
- Test: Mock confirm identity → verify proposals regenerated
- Test: Recluster endpoint writes Supabase (mock)
- Test: James Fields-like scenario: 2 similar faces in different batches → proposal generated

## Phase 3: Production Validation (20 min)
1. Run recluster with dry_run=false on production
2. Find James Fields identity IDs via browser
3. Verify Person 3474 (or equivalent) appears as proposal
4. Verify Charles Fox ↔ Roland Fox NOT auto-merged
5. Verify proposals appear in Proposals sidebar
6. Screenshot everything

## Phase 4: Harness Outputs (10 min)
1. Assessment: docs/assessments/session-109b-assessment.md
2. Update session log
3. Update ROADMAP, CHANGELOG
4. All breadcrumbs verified
