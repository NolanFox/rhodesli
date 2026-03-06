# Session 90 Assessment

## Shipped
- [x] AD-204: Close-crop face detection padding fallback — DEPLOYED (94480af)
- [x] Upload date backfill for all 295 photos — DEPLOYED (b44ab66)
- [x] Benatar photo metadata "Unknown" -> "Claude Benatar upload" — DEPLOYED
- [x] Photos without faces registered in archive — DEPLOYED (1617ef3)
- [x] UX: 0 faces shows info message not misleading green checkmark — DEPLOYED
- [x] Track B: Test suite prune — 245 tests removed (merged from f092385)
- [x] Track C: Volume backup script to R2, AD-205 (merged from 3e4792c)
- [x] Track D: Data migration PRD-027 (merged from 562f1b9)
- [x] All 3 branches merged to main with conflict resolution
- [x] Hook simplification — Removed commit counter, PreCompact, recovery scripts. Kept test gate + ruff format (6206e5e)
- [x] Photo sorting — 7 sort options: Upload Date (Newest/Oldest), Estimated Date (Newest/Oldest), Filename (A-Z), Most Faces, By Source (625c793, e39e936)
- [x] Performance: loading="lazy" on images + CDN preconnects (c180c54)
- [x] Upload routes restored after merge loss (6093361, 95a8db1)

## Deferred
- main.py refactor (Track A stalled) — 34K lines, still monolithic — Needs dedicated session
- Full Supabase migration — PRD-027 written, shadow writes planned for Session 91+
- Test runtime target (<3 min) — Currently ~5 min. Removed 245 tests but xdist has flaky ordering issues
- Supabase sync background threading — Would save 2-10s startup time (perf research finding)
- No-faces UX on photo page — Photos register in archive but no special UI treatment

## Red Flags
- [HIGH] **Auto-compacted — 4th occurrence** (Sessions 80, 89, 89-cont, 90). Root cause: orchestrator does too much in one context.
- [MEDIUM] Upload routes lost TWICE during merges — fragile due to 34K line main.py. Refactor overdue.
- [MEDIUM] Hook over-engineering caused more problems than it solved — now simplified.
- [LOW] 21 flaky xdist tests — test isolation issues with parallel execution.
- [LOW] Subagent worktree coordination — agents sometimes edit main repo instead of worktree.

## User Feedback (15 items captured)
1. Testing slows us down
2. Upload keeps erroring -> AD-204 fix
3. Photos being lost -> now registered even with 0 faces
4. main.py refactor needed -> Track A stalled
5. Photo sorting missing -> DONE (7 sort options)
6. Hook errors -> DONE (simplified)
7. Don't lose subagents during clear -> documented in session log
8. Auto-compacted AGAIN -> 4th failure, hooks simplified
9. Go big, use subagents -> 7 subagents launched across session
10. Site loads slowly -> CDN preconnects + lazy loading applied

## Lessons
1. Behavioral /clear enforcement failed 4x — hooks simplified instead of adding more
2. Subagent state must be documented before /clear
3. Don't over-engineer hooks — each layer adds failure modes
4. Upload routes in monolithic main.py are fragile during merges — refactor urgently needed
5. Merge conflicts in 34K-line file are error-prone — sections get silently dropped

## Next Session Should Verify
1. Photo sorting works on production (7 sort options visible)
2. Upload page still works after route restoration
3. Lazy loading images render correctly
4. Hook simplification doesn't cause issues
