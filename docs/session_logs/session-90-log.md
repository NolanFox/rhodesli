# Session 90 Log
Started: 2026-03-05
Prompt: docs/prompts/session-90-prompt.md

## Phase Checklist
- [ ] Act 1: Orient + Immediate Cleanup + Upload Fix
- [ ] Act 2: Upload Date Backfill
- [ ] Act 3: Railway Volume Backup Script
- [ ] Act 4: Test Suite Audit + Prune
- [ ] Act 5: Data Migration PRD
- [ ] Act 6: Assessment + Docs

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed

## User Feedback (Nolan) — Captured During Session
1. **Testing slows us down** — Tests take too long, blocking every commit. Test pruning is high priority.
2. **Duplicate URLs on prod** — `/photo/a75e6b54b0eb6c50` and `/photo/inbox_0c57277a_0_unknown` both exist. Must not break either link. RESOLVED: both survive deploy via alias mechanism.
3. **Upload keeps erroring** — `claude_benatar_purim_followup_netanel_646766885...` fails with "0 faces extracted". ROOT CAUSE: InsightFace can't detect extreme close-crop faces. FIX: AD-204 padding fallback.
4. **Photos being lost is a data issue** — Upload showing green checkmark for 0 faces is misleading. FIX: amber warning UX.
5. **main.py partial refactor** — The 25K-line main.py causes test speed issues and blocks parallel worktrees. Should this be in scope? DECISION: Defer to Session 91 as dedicated effort. Related to test speed.
6. **Close-crop fallback** — "Can't imagine this will be the only one like this." DONE: AD-204 adds 40% padding retry for both hybrid and non-hybrid detection paths.
7. **Parallelize where possible** — Fix everything, run in parallel.
8. **Record all feedback** — Capture questions/feedback in session log for context preservation.

## Questions to Discuss (from prompt)
- Should we start Supabase shadow writes for identities/photos now, or just do R2 backups? → Deferred to PRD (Act 5)
- Should we prune the test suite (3700→~2500) now or defer? → Yes, do it (Act 4)
- Should we add an admin endpoint for backfill, or do sync-run-push? → Doing local backfill + push

## Act 1 Notes
- Phantom photo `a75e6b54b0eb6c50` not in local data, exists on production — will be cleaned on deploy
- Person 877 is real (Benatar face from inbox photo) — NOT a phantom identity
- Benatar photo metadata fixed: "Unknown" → "Claude Benatar upload"
- CHANGELOG updated for 89e (v0.92.2)
- AD-204: Close-crop padding fallback — tested locally, detects the Benatar face (0.822 confidence)
- Upload UX: 0 faces now shows amber warning instead of green checkmark
