# Session 111d — Remaining Work Parallelization Plan

## Worktree 1: `session-111d/focus-toast` (FB-057 + FB-028)
- Focus auto-advance + toast persistence
- Files: `app/main.py` (toast, focus card), `app/identity_routes.py` (confirm/skip/reject handlers)
- Fix toast OOB swap first, then verify focus auto-advance

## Worktree 2: `session-111d/neighbor-fixes` (FB-054/058 + FB-038)
- Thumbnail mismatch + checkbox preservation on Load More
- Files: `app/main.py` (neighbor_card, neighbors_sidebar)

## Worktree 3: `session-111d/cluster-search` (FB-030 + FB-051)
- Cluster count persistence + photo search community prefix
- Files: `app/cluster_review_routes.py`, `app/identity_routes.py`

## Merge Order: 3 → 2 → 1
