# Session 109 Context: Cross-Batch Clustering Implementation

**Predecessor:** Session 108 (data integrity + clustering analysis), Session 108b (bug fixes)
**PRD:** docs/prds/049_cross_batch_clustering.md
**Analysis:** docs/session_context/session-108-clustering-analysis.md

## What We Learned in Session 108

1. The clustering pipeline only groups faces within a single upload batch, never across batches
2. Proposals only match INBOX against CONFIRMED — INBOX-to-INBOX matches are invisible
3. James Fields (9 faces, 2 photos) was never matched against 1652 existing Fox Family faces
4. Empirical analysis: Charles Fox ↔ Roland Fox at distance 0.50 means no auto-merge is safe
5. Design decision: human-in-loop for ALL cross-batch matches, auto-merge only within-batch

## What Session 108b Shipped

- FB-013: Compare button fixed on person page
- FB-014: "View Photo →" link in photo context modal
- FB-015: Sidebar search finds photos by filename
- Collage override NameError fix
- v0.99.13 deployed

## Implementation Plan for Session 109

**Phase 0:** Orient — verify 108b deploy, read PRD-049
**Phase 1:** Create `core/cross_batch_matching.py` with tests
**Phase 2:** Wire into upload pipeline (`app/upload_routes.py`)
**Phase 3:** Wire into admin recluster (`app/sync_routes.py`)
**Phase 4:** Wire into confirm identity (`app/identity_routes.py`)
**Phase 5:** Test with James Fields — run recluster, verify proposals appear
**Phase 6:** Fix CI test failure (test_people_link_to_person_pages)
**Phase 7:** Deploy + browser verify
**Phase 8:** Harness outputs

## Key Files

| File | Purpose |
|------|---------|
| `core/cross_batch_matching.py` | NEW — cross-batch matching function |
| `core/identity_scoring.py` | Reference — existing find_candidate_matches |
| `core/grouping.py` | Reference — existing within-batch grouping |
| `app/upload_routes.py` | Wire cross-batch into _background_ingest |
| `app/sync_routes.py` | Wire cross-batch into /api/admin/recluster |
| `app/identity_routes.py` | Wire post-confirm re-matching |
| `core/config.py` | Add CROSS_BATCH_THRESHOLD |

## Risks

1. **Performance**: Cross-batch matching against 2000+ faces could be slow. May need batch processing or embedding index.
2. **Proposal volume**: Could generate hundreds of proposals per upload. Need deduplication and prioritization.
3. **Notification spam**: If every upload triggers notifications, users may ignore them. Throttle or batch.

## James Fields Test Cases

After implementation, these should be true:
- Person 3474 (dist 0.87) appears as proposal for Person 28fa8bfa
- Person 3650 (dist 1.20) appears as lower-confidence proposal
- Charles Fox ↔ Roland Fox (dist 0.50) appears as proposal, NOT auto-merged
- Co-occurrence faces remain blocked unless Override used
