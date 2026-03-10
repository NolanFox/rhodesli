# Session 96e-cont2 Assessment

## Shipped
- [x] **Complete-linkage grouping** — Replaced single-linkage union-find with complete-linkage agglomerative clustering. Prevents transitive snowball clusters (252-face garbage cluster reduced to max 44-face cluster with avg intra-group distance 0.756). All 3 grouping functions fixed. Evidence: `core/grouping.py`, 15 grouping tests pass.
- [x] **Re-ran grouping** — 294 groups, 582 merges (vs 813 with single-linkage), 14 co-occurrence blocks. Largest cluster: 44 faces. Evidence: commit 800d4ac.
- [x] **Proposals regenerated at threshold 1.05** — 17 proposals (vs 2115 at 1.3). Only Medium+ confidence. Evidence: `data/proposals.json`.
- [x] **Sort control community prefix** — Sort links now include `/c/{slug}/` prefix via `nav_prefix` parameter. Evidence: `_sort_control()` in main.py.
- [x] **Name truncation fix** — "Unidentified Person NNNN" now shows "Person NNNN" on cards. Evidence: `identity_card()` in main.py.
- [x] **Upload Review: Grouped Identities section** — New section showing multi-face INBOX clusters sorted by face count, with thumbnails and links. Evidence: `cluster_review_routes.py`.
- [x] **Upload Review: Proposal confidence filter** — Only Medium+ confidence proposals shown (distance < 1.05). Evidence: `cluster_review_routes.py`.

## Deferred
- Match view Up Next carousel — needs separate implementation
- Match view ordering by strongest matches — needs proposal-aware sorting
- Duplicate face detection dedup — pre-existing issue from face detection pipeline, not grouping. 4 photos have duplicate detections. BACKLOG item needed.
- Face card consistency across all views — partial fix (name truncation), full consistency needs more work

## Red Flags
- [LOW] 4 pre-existing test failures (test_data_integrity Netanel Menashe orphans, test_error_handling, test_estimate_route) — not caused by this session
- [LOW] Compaction violation in previous continuation (Lesson 89)

## Lessons
- **Lesson 115**: Single-linkage union-find creates transitive snowball clusters. Complete-linkage (ALL inter-group distances must be below threshold) is mandatory for face grouping. A↔B close + B↔C close does NOT mean A↔C close.

## Next Session Should Verify
1. Fox Family browse view shows proper clusters (max 44 faces, not 252)
2. Upload Review shows Grouped Identities section with reasonable clusters
3. Sort links work from community context (don't redirect to Rhodes)
4. Investigate duplicate face detections (Dist: 0.00 entries in Similar)
5. Match view improvements (Up Next, ordering)
