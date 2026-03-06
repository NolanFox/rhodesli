# Session 90 Assessment (In Progress)

## Shipped
- [x] AD-204: Close-crop face detection padding fallback — DEPLOYED (94480af)
- [x] Upload date backfill for all 295 photos — DEPLOYED (b44ab66)
- [x] Benatar photo metadata "Unknown" -> "Claude Benatar upload" — DEPLOYED
- [x] CHANGELOG updated for session 89e (v0.92.2)
- [ ] Photos without faces still added to archive — code ready, needs commit
- [ ] UX: 0 faces shows info message not misleading green checkmark — code ready, needs commit

## In Progress (Subagents)
- Track A: main.py route extraction (worktree)
- Track B: Test suite audit + prune (worktree)
- Track C: Volume backup script to R2 (worktree)
- Track D: Data migration PRD (worktree)

## Deferred
- Photo sorting by upload date and estimated date (ascending/descending) — user request, not yet started
- Supabase shadow writes — deferred to PRD recommendation

## User Feedback Captured
1. Testing slows us down — test pruning is high priority
2. Duplicate URLs on prod — both survive deploy via alias mechanism
3. Upload keeps erroring — AD-204 close-crop fallback fixes it
4. Photos being lost — photos without faces now registered in archive
5. main.py partial refactor — subagent launched
6. Go big — fix tests, refactor main.py, Supabase migration, all outstanding issues
7. Photo sorting by upload date and estimated date — missing from Photos page
8. Use subagents, worktrees, hooks, follow harness — document everything

## Red Flags
- [MEDIUM] Commit 257de84 accidentally included backup script files from subagent — subagent file leakage into main worktree
- [LOW] Linter reverted changes during commit hook — had to re-apply edits

## Next Session Should Verify
1. Close-crop photo upload works in production
2. Photos without faces appear in Photos section
3. Sorting options work on Photos page
4. Subagent work merged successfully
