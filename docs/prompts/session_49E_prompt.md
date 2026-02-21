# RHODESLI — Session 49E: Stabilization, Verification & Feature Hardening

## ROLE
You are Lead Engineer for Rhodesli, a heritage photo archive with ML-powered face recognition for the Jewish community of Rhodes. Stack: FastHTML + HTMX + InsightFace + Supabase + Cloudflare R2 + Railway.

## SESSION GOALS (in priority order)
1. Investigate and resolve test count discrepancy (2520 expected vs 1293 reported)
2. Investigate the 127 pre-existing test failures from state pollution
3. Fix "Name These Faces" end-to-end (PRD-level planning → implementation → production verification)
4. Fix Compare/Estimate upload to SAVE photos through gatekeeper pipeline (PRD-level planning → implementation → production verification)
5. Production verification of ALL 49D fixes using Railway CLI + browser
6. Install compaction-resilient checkpoint system for this and future sessions

## NON-NEGOTIABLE RULES

### Execution Rules
1. Commit after EVERY completed phase
2. Run `pytest tests/ -x -q` AND `pytest rhodesli_ml/tests/ -x -q` before each commit. Both suites. Every time.
3. Deploy via `git push` (Railway auto-deploys). NEVER use Railway dashboard.
4. After every deploy, verify with Railway CLI: `railway logs --tail 50`
5. Use Claude in Chrome extension for browser verification. Playwright as fallback.
6. Do NOT declare any feature "done" without production browser verification.

### Documentation Rules (COMPACTION PROTECTION)
7. Update `docs/session_context/session_49E_checkpoint.md` after EVERY phase.
8. Update ALGORITHMIC_DECISIONS.md for any ML or architectural decisions.
9. Update HARNESS_DECISIONS.md for any process/tooling decisions.
10. No doc over 300 lines. CLAUDE.md under 80 lines.
11. Save the original prompt to disk immediately.

### Planning Rules
12. For Name These Faces (Phase 4) and Upload Pipeline (Phase 5): write a full PRD BEFORE writing any code.
13. Break complex phases into numbered sub-tasks.

## PHASES
- Phase 0: Orient + Install Checkpoint System
- Phase 1: Test Count Investigation
- Phase 2: Pre-existing Test Failures
- Phase 3: Production Verification of 49D Fixes
- Phase 4: Name These Faces Full Fix (PRD → implement → verify)
- Phase 5: Compare/Estimate Upload Save Pipeline (PRD → implement → verify)
- Phase 6: Verification Gate + Session Docs
- Phase 7: Harness Improvements

## CRITICAL REMINDERS (read if context was compacted)
1. You are in Session 49E. Read this file and docs/session_context/session_49E_checkpoint.md.
2. Two test suites: `pytest tests/` (app) AND `pytest rhodesli_ml/tests/` (ML). Run BOTH.
3. Deploy via git push. Verify with `railway logs --tail 50`.
4. Browser verify with Chrome extension / Playwright. Not curl.
5. Update checkpoint file after every phase.
6. Write PRDs before code for Phases 4 and 5.
7. Commit after every phase.
8. No doc over 300 lines. CLAUDE.md under 80.
