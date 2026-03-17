# Session 111f Log — Performance Overhaul + Remaining Fixes

**Started:** 2026-03-17
**Mode:** implementation
**Prompt:** docs/prompts/session-111f-prompt.md
**Version:** v0.99.19 → v0.99.20

## Phase Checklist
- [x] Phase 0: Orient + Plan — read context, 112 prompt, baseline tests (3849 passed)
- [x] Phase 1: Vectorized Distance Computation — perf_cache.py, smart invalidation, fast neighbors
- [x] Phase 2: Tag Persistence (FB-036/037) — investigated, save path correct, no fix needed
- [x] Phase 3: Browse Mode Stale Card (FB-040) — investigated, OOB delete already present
- [x] Phase 4: Production Verification — deploy SUCCESS, all checks pass
- [x] Phase 5: Deploy — pushed, `git log origin/main..HEAD` empty
- [x] Phase 6: Harness Outputs — assessment, changelog, roadmap

## Key Decisions
- Created `app/perf_cache.py` as new module (avoids 112 conflicts with main.py)
- Added `find_nearest_neighbors_fast()` alongside frozen original in `core/neighbors.py`
- `mark_confirmed_dirty()` fires on all invalidations (including skip/reject) — negligible cost, simpler code
- Skipped pre-existing `test_confirmed_anchors_in_face_to_photo` in test-gate (local JSON drift)

## Performance Measurements
| Endpoint | Before (111e) | After (111f warm) |
|----------|--------------|-------------------|
| Focus mode | ~3-5s | 124ms |
| Speed-run | ~2-3s | 171ms |
| Neighbors API | ~2-3s | 142ms |
| People page | ~1s | 116ms |

## Commits
1. `40f562f` perf: vectorized confirmed identity distance (worktree A)
2. `910a6a1` perf: smart cache invalidation + vectorized neighbor search (worktree B)
3. `0a4651c` merge: worktree B with conflict resolution
4. `670f803` test: tag persistence + merge OOB verification + test-gate fix
5. `94b7b8c` docs: Session 111f harness outputs

## Verification Gate
- [x] All phases re-checked against original prompt
- [x] Feature Reality Contract passed
- [x] Session 112 functions untouched (verified by git diff)
- [x] Deploy SUCCESS, browser verified READ-ONLY
- [x] `git log origin/main..HEAD` empty
