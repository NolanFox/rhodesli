# Session 52: ML Pipeline to Cloud + Fix Regressions

Read CLAUDE.md. Read .claude/rules/spec-driven-development.md.
Read .claude/rules/verification-gate.md.
Read .claude/rules/feature-reality-contract.md.
Read .claude/rules/harness-decisions.md.
Read .claude/rules/prompt-decomposition.md.
Read CHANGELOG.md (first 10 lines).
Read docs/ALGORITHMIC_DECISIONS.md (last 30 lines).
Read ROADMAP.md.
Read BACKLOG.md.

## Session Identity
- **Previous sessions:** 51 (Quick-Identify), 51B (bug fixes)
- **Goal:** Three critical tracks:
  1. FIX REGRESSIONS from Session 51 (face clicks broken, Name These
     Faces not appearing for admin)
  2. GET ML PIPELINE RUNNING ON RAILWAY so Compare and Estimate
     actually process uploads in real-time
  3. ENABLE NEW PHOTO PROCESSING so the full ingestion pipeline
     (face detection → embedding → similarity → clustering) runs
     in the cloud, not just on Nolan's local machine
- **Time budget:** ~60 min (large session, use phase isolation)
- **Priority:** P0 — Multiple shipped features don't work. The app's
  core value proposition (upload photo → find matches) is broken.

## Phase checklist:
- [ ] Phase 0: Deep audit — what actually works in production?
- [ ] Phase 1: Fix Session 51 regressions (face clicks + Name These Faces)
- [ ] Phase 2: Research — ML pipeline architecture + Railway capabilities
- [ ] Phase 3: Enable ML dependencies in Docker
- [ ] Phase 4: Wire Compare upload to real processing
- [ ] Phase 5: Wire Estimate upload to real processing
- [ ] Phase 6: New photo ingestion pipeline (cloud-ready)
- [ ] Phase 7: FUNCTIONAL end-to-end verification
- [ ] Phase 8: Docs, ROADMAP, BACKLOG, changelog
