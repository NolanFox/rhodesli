# Session 49: Production Polish + Bug Fixes (Autonomous)

Read CLAUDE.md. Read .claude/rules/spec-driven-development.md.
Read .claude/rules/verification-gate.md.
Read .claude/rules/feature-reality-contract.md.
Read ROADMAP.md. Read BACKLOG.md (first 40 lines).
Read CHANGELOG.md (first 10 lines -- get current version).

## Session Identity
- **Previous session:** Session 48 (harness inflection)
- **Goal:** Fix known production bugs, verify Session 47/48
  deliverables in production, and polish UX for the interactive
  GEDCOM + birth year review session that follows.
- **Time budget:** ~30 min autonomous
- **Mode:** No human interaction needed. Fix what's broken,
  verify what was built, document what needs interactive review.

## CRITICAL CONSTRAINTS
- DO NOT modify identity data, photo_index.json, or ML data files
- DO NOT create persistent test data on production
- DO NOT build new features -- only fix existing issues
- Commit after every fix. Descriptive messages.
- Test before every commit: `pytest tests/ -x -q`

---

## PHASE 0: Orient + Save This Prompt (~2 min)

## PHASE 1: Production Route Health Check (~3 min)
Before fixing anything, document what's actually working.

## PHASE 2: Fix Version Display (if still broken) (~3 min)
Session 47 was supposed to fix the footer showing "v0.8.0" instead of the actual version.

## PHASE 3: Fix Collection Name Truncation (~5 min)
Bug: Collection names are truncated in admin view.

## PHASE 4: "Unmatched" Faces UX Clarity (~5 min)
The app shows "354 Unmatched" faces but doesn't explain what "unmatched" means.

## PHASE 5: Verify Session 47/48 Deliverables (~5 min)
Check that the work from the last two sessions actually landed.

## PHASE 6: Small Bug Sweep (~5 min)
Fix any other small issues found while checking the codebase.

## PHASE 7: Prepare for Interactive Session (~3 min)
Create a checklist file for the interactive session that follows.

## PHASE 8: Update BACKLOG with Next Sessions Plan (~3 min)

## PHASE 9: Verification Gate
