# Session 90 Assessment (In Progress — mid-session update)

## Shipped
- [x] AD-204: Close-crop face detection padding fallback — DEPLOYED (94480af)
- [x] Upload date backfill for all 295 photos — DEPLOYED (b44ab66)
- [x] Benatar photo metadata "Unknown" -> "Claude Benatar upload" — DEPLOYED
- [x] CHANGELOG updated for session 89e (v0.92.2)
- [x] Photos without faces still added to archive — DEPLOYED (1617ef3)
- [x] UX: 0 faces shows info message not misleading green checkmark — DEPLOYED (1617ef3)

## Subagent Results
- [x] Track B: Test suite prune — COMPLETED (f092385, 245 tests removed)
- [x] Track C: Volume backup script to R2 — COMPLETED (3e4792c, AD-205)
- [x] Track D: Data migration PRD — COMPLETED (562f1b9, PRD-027)
- [ ] Track A: main.py route extraction — STALLED (no commits, likely failed)
- [ ] Merge all 3 completed branches — PENDING

## Not Yet Started
- Photo sorting by upload date and estimated date (ascending/descending)
- Harness hook cleanup (user reports errors)
- Browser verification of production
- Final assessment

## Red Flags
- [HIGH] **Auto-compacted — 4th occurrence** (Sessions 80, 89, 89-cont, 90). User trust issue. Root cause: orchestrator does too much in one context. Must /clear after EVERY commit.
- [MEDIUM] Commit 257de84 included backup script files from subagent — file leakage
- [MEDIUM] Hook over-engineering — adding complexity to hooks caused errors in subsequent sessions. User wants simplification.
- [LOW] Linter reverted changes during commit hook — had to re-apply edits 3x

## User Feedback Captured (15 items)
1. Testing slows us down — test pruning is high priority
2. Duplicate URLs on prod — both survive deploy via alias mechanism
3. Upload keeps erroring — AD-204 close-crop fallback fixes it
4. Photos being lost — photos without faces now registered in archive
5. main.py partial refactor — subagent launched (stalled)
6. Go big — fix tests, refactor main.py, Supabase migration, all outstanding issues
7. Photo sorting by upload date and estimated date — missing from Photos page
8. Use subagents, worktrees, hooks, follow harness — document everything
9. Close-crop photo should work after fix — needs production verification
10. Photos without faces should upload, just no face matching — UX should be clear
11. Don't lose subagents during clear/compaction — document state first
12. Auto-compacted AGAIN — "why do you keep doing this"
13. Hook errors from over-engineering — simplify, don't add more layers
14. Log everything and learn lessons — before clearing
15. Harness hooks broken — fix without making worse

## Lessons from Session 90
1. **Behavioral /clear enforcement failed a 4th time** — Must internalize: commit → /clear → NOTHING ELSE
2. **Subagent state must be documented before /clear** — Write branch+commit to session log
3. **Don't over-engineer hooks** — Each layer of enforcement adds its own failure modes
4. **Subagent file leakage is real** — Worktree files can appear in main if not careful with git add

## Next Context Should
1. Merge 3 branches (track-b, track-c, track-d)
2. Add photo sorting (upload date + estimated date, asc/desc)
3. Simplify harness hooks
4. Browser verify production
5. Write final assessment
