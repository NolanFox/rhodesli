# Session 109 — Cross-Batch Clustering & Match Notifications

## PRD
@docs/prds/049_cross_batch_clustering.md

## Context
@docs/session_context/session-109-context.md
@docs/session_context/session-108-clustering-analysis.md

## Pre-Requisites
- Read PRD-049 and the clustering analysis in full
- Read `core/identity_scoring.py` (reference implementation for matching)
- Read `core/grouping.py` (reference implementation for within-batch grouping)
- Read `app/upload_routes.py` `_background_ingest()` (where cross-batch hooks in)

## Phase 0: Orient (5 min)

1. Verify 108b deploy is live: `curl https://rhodesli.nolanandrewfox.com/health`
2. Read PRD-049
3. Read existing matching code: `core/identity_scoring.py:find_candidate_matches()`
4. Set session files: current_session=109, session_mode=implementation

## Phase 1: Cross-Batch Matching Core (30 min)

Create `core/cross_batch_matching.py`:

```python
def find_cross_batch_matches(
    new_face_ids: list[str],
    identities: dict,
    face_data: dict,
    photo_registry,
    threshold: float = 1.05,
    community_id: str = None,
) -> list[dict]:
```

Requirements:
- Compare `new_face_ids` against ALL existing identities (INBOX, PROPOSED, CONFIRMED)
- Community-scoped: only match within same community
- Respect co-occurrence blocks (skip if faces share a photo)
- Return sorted by distance with confidence tier
- Deduplicate against existing proposals
- Use best-linkage (min distance across all face embeddings in identity)

Tests in `tests/test_cross_batch.py`:
- Test: matches found against INBOX identity
- Test: matches found against CONFIRMED identity
- Test: co-occurrence faces skipped
- Test: different community faces skipped
- Test: results sorted by distance
- Test: confidence tiers correctly assigned
- Test: empty new_face_ids returns empty
- Test: empty identities returns empty

## Phase 2: Wire Into Upload Pipeline (20 min)

In `app/upload_routes.py` `_background_ingest()`, after the existing grouping step (line ~1003):

1. Call `find_cross_batch_matches()` with the new face IDs
2. Write results to `ml_proposals` Supabase table with `match_type="cross_batch"`
3. Write results to `proposals.json` (append, don't overwrite existing)
4. Log to `ml_runs` table
5. Create notification if matches found (simple log for now, full notification system later)

Test: Mock upload → verify cross-batch proposals generated

## Phase 3: Wire Into Admin Recluster (15 min)

Update `/api/admin/recluster` in `app/sync_routes.py`:

1. After existing grouping step, run cross-batch matching for ALL INBOX faces
2. Return cross_batch_matches count in response
3. Write to ml_proposals table

Test: Hit recluster endpoint → verify cross-batch matches returned

## Phase 4: Wire Into Confirm Identity (15 min)

In the confirm identity handler (`app/identity_routes.py`):

After `registry.confirm_identity()`:
1. In a background thread, re-run `find_candidate_matches()` (existing function)
2. Write new proposals for the newly confirmed identity
3. This leverages existing code — just needs to be triggered

Test: Confirm an identity → verify proposals regenerated

## Phase 5: James Fields Validation (15 min)

1. Trigger `/api/admin/recluster` on production (dry_run=true first)
2. Verify Person 3474 (distance 0.87) appears as cross-batch proposal for Person 28fa8bfa
3. Verify Person 3650 (distance 1.20) appears as moderate proposal
4. Verify Charles Fox ↔ Roland Fox are NOT auto-merged (proposal only)
5. Document results in session log

## Phase 6: Fix CI Test Failure (10 min)

Pre-existing flaky test: `test_people_link_to_person_pages` in `tests/test_public_browsing.py`.

The test asserts `/person/` links exist on the People page, but the test fixture has no confirmed identities with person pages. Fix by either:
- Creating a confirmed identity in the test fixture
- Adjusting the assertion to handle empty state
- Skipping in CI with `@pytest.mark.skipif`

This has been failing intermittently across multiple sessions. Fix it permanently.

## Phase 7: Deploy + Browser Verify (10 min)

1. `git push origin main`
2. `railway up` (if GitHub deploy uses RAILPACK)
3. Verify health endpoint
4. Trigger recluster on production
5. Verify proposals appear in Proposals sidebar
6. Screenshot James Fields proposals

## Phase 8: Harness Outputs (10 min)

1. Assessment: `docs/assessments/session-109-assessment.md`
2. Session log: `docs/session_logs/session-109-log.md`
3. AD-226: Cross-batch threshold decision in ALGORITHMIC_DECISIONS.md
4. Update ROADMAP, CHANGELOG (v0.99.14), BACKLOG
5. Verify all breadcrumbs

## Verification Checklist

- [ ] All tests pass (including new cross-batch tests)
- [ ] CI passes (flaky test fixed)
- [ ] James Fields Person 3474 appears as proposal
- [ ] Charles Fox ↔ Roland Fox NOT auto-merged
- [ ] Recluster endpoint includes cross-batch results
- [ ] Upload pipeline includes cross-batch step
- [ ] Confirm identity triggers re-matching
- [ ] All events logged to Supabase (ml_runs, ml_proposals)
- [ ] `git log origin/main..HEAD` is empty

## Parallelization

Per docs/architecture/PARALLEL_AGENT_STRATEGY.md:
- Phase 1 (core module) and Phase 6 (CI fix) can run in parallel worktrees
- Phases 2-4 are sequential (each depends on Phase 1)
- Phase 5 requires Phase 3 (recluster endpoint)
