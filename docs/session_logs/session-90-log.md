# Session 90 Log
Started: 2026-03-05
Prompt: docs/prompts/session-90-prompt.md

## Phase Checklist
- [x] Act 1: Orient + Immediate Cleanup + Upload Fix (COMMITTED: 94480af, b44ab66)
- [ ] Act 1b: No-faces photo registration (STAGED, needs commit after /clear)
- [ ] Act 2: Upload Date Backfill (COMMITTED: b44ab66)
- [ ] Act 3: Railway Volume Backup Script (subagent Track C)
- [ ] Act 4: Test Suite Audit + Prune (subagent Track B)
- [ ] Act 5: Data Migration PRD (subagent Track D)
- [ ] Act A: main.py route extraction (subagent Track A)
- [ ] Act 6: Assessment + Docs

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed

## User Feedback (Nolan) — Captured During Session
1. **Testing slows us down** — Tests take too long, blocking every commit. Test pruning is high priority.
2. **Duplicate URLs on prod** — Both URLs survive deploy via alias mechanism. No links break.
3. **Upload keeps erroring** — ROOT CAUSE: InsightFace can't detect extreme close-crop faces. FIX: AD-204 padding fallback.
4. **Photos being lost is a data issue** — Upload showing green checkmark for 0 faces is misleading. FIX: UX updated.
5. **main.py partial refactor** — The 25K-line main.py causes test speed issues and blocks parallel worktrees. Subagent launched.
6. **Close-crop fallback** — DONE: AD-204 adds 40% padding retry.
7. **Parallelize where possible** — 4 subagents launched in worktrees.
8. **Record all feedback** — Capturing in this log.
9. **Go big** — Fix test issue, refactor main.py, Supabase migration, outstanding issues, backfill.
10. **Photo without faces should still upload** — Just shouldn't have face matching. UX should be clear. FIX: Photos now registered even with 0 faces.
11. **Use subagents, worktrees, hooks, follow harness** — Document everything.

## PENDING AFTER /clear
- 4 files staged for commit: core/ingest_inbox.py, core/photo_registry.py, app/main.py, tests/test_ingest_inbox.py
- Commit message: "fix(upload): photos without faces still added to archive"
- Also: app/upload_routes.py and docs/prds/027_data_migration.md are subagent spillover — don't commit these
- 4 subagents running in background worktrees (Tracks A, B, C, D)
- Deployed: close-crop fix + backfill (94480af, b44ab66)
- The previous commit 257de84 accidentally included backup script files from a subagent

## Commits So Far
1. 94480af — fix(upload): close-crop face detection fallback + UX warning (AD-204)
2. b44ab66 — feat(photos): backfill upload dates for all 295 photos
3. 257de84 — fix(upload): photos without faces still added to archive (BUT contained wrong files — backup scripts not my actual changes)
