# Session 135b Assessment

**Date:** 2026-03-23
**Mode:** Interactive continuation
**Predecessor:** Session 135

## Shipped

### P0 Fixes
- [x] **FB-007 / Esther data repair** — Person 3779 shared all 8 face IDs with Esther Burd Fox. Ran `audit_multi_claimed_faces.py --execute`. Multi-claimed faces now at zero. Evidence: re-run audit shows 0 multi-claimed.
- [x] **FB-010 / Face strip limit** — Focus mode face strip limited to first 6 faces (`all_face_ids[:6]`), causing 8-face identities to show fewer thumbnails than Speed-run. Removed slice to show all faces. Evidence: code change in `app/main.py:6188`.

### P1 Performance
- [x] **FB-002 / Load More performance** — Precomputed global embedding matrix in `perf_cache.py` eliminates 100-200ms matrix construction per neighbors cache miss. New `get_all_neighbors()` function uses vectorized cosine distance. Wired into `/api/identity/{id}/neighbors`. `mark_global_dirty()` invalidation on all identity mutations. Evidence: 7 new tests pass, code in `app/perf_cache.py:207-369`.

## Deferred
- **FB-008**: Override button context — needs PRD for co-occurrence preview UX. BACKLOG: existing entry.
- **FB-009**: Compare modal active side indicator (P2) — BACKLOG: existing entry.
- **Speed-run vs Focus UX overlap**: Needs first-principles UX review. Not a code fix — design analysis required. BACKLOG: add entry.

## Test Results
- 3729 app tests pass (up from 3723 baseline)
- 7 new tests: `tests/test_session_135b_global_perf_cache.py`

## Red Flags
- None critical. The global matrix uses ~50MB RAM for 1864 identities × ~3K faces. Well within Railway 512MB limit (~10% overhead).
- The `get_all_neighbors()` lookup for identity_info is O(N) linear scan. Could be a dict lookup but N is small (~1864). Low priority.

## Next Session Should Verify
1. Load More on Similar Identities is noticeably faster on production
2. Person 3779 no longer appears in Fox Family triage
3. Focus mode shows all 8+ face thumbnails for Esther Burd Fox
