# Session 71 Log
Started: 2026-02-26
Theme: UX Dogfooding Fixes + GEDCOM Integration + Harness Enforcement
Prompt: docs/prompts/session-71-prompt.md
Context: docs/session_context/session-71-context.md
Predecessor: Session 70 (v0.75.0)

## Baseline
- Tests: 3133 app + 538 ML = 3671 total (all passing)
- Version: v0.75.0
- Commit: b877045

## Phase Checklist
- [x] Phase 0: Orient + verify production + setup
- [ ] Track A: UX fixes (face cards, enter key, Run Face Analysis, whitespace)
- [ ] Track B: GEDCOM integration (search ranking, pagination, People tab actions)
- [ ] Track C: Harness infrastructure (subagent enforcement, ML vocabulary AD, parallelization hook)
- [ ] Phase Final: Merge, deploy, browser verify

## Phase 0: Production Verification (Session 70 UX Fixes)

| Item | Expected | Actual | Result |
|------|----------|--------|--------|
| v0.75.0 deployed | Version visible | v0.75.0 in sidebar footer | PASS |
| Heritage Archive subtitle | Visible with contrast fix | Green text visible | PASS |
| Discoveries page | Badge count, confirm/reject buttons | 1 discovery, buttons functional | PASS |
| People page | Face cards render | 59 people, cards visible | PASS |
| Match vocabulary | "Possible match" etc. | "Possible match", "Moderate", "Medium", "Low" | PASS |
| Discovery card names | Not truncated (UX-110 fix) | Full names visible on discoveries | PASS |
| GEDCOM Family Tree Link | Search results | Results loading, Link buttons | PASS |
| Often appears with | Names shown | Truncated: "Rachel Ama...", "Rica Sharho..." | KNOWN ISSUE |

### Dogfooding Issues Confirmed
1. Face card photos ~120px (too small) — Track A
2. Quality score raw number "23.27" meaningless — Track A
3. "Often appears with" names truncated — Track A
4. GEDCOM search alphabetical, no ranking — Track B
5. No pagination for GEDCOM results — Track B
6. No GEDCOM link from People tab — Track B

## Track C: Harness Infrastructure (worktree-isolated)

### C1: Mechanical Subagent Commit Enforcement
- Created `scripts/merge-worktree.sh` with 4-step enforcement:
  1. Check `git status --porcelain` in worktree, auto-commit if uncommitted files found
  2. Run tests in worktree before merge
  3. Merge with `--no-ff` for clear merge history
  4. Run tests after merge to catch integration issues
- Supports `--dry-run` for preview
- Addresses Lesson 87 (sessions 64, 69 lost uncommitted files)

### C2: ML Banner Vocabulary AD Entry
- Added AD-170 documenting the Session 70 vocabulary change
- Old: `"ML Match: VERY HIGH/HIGH/MODERATE/LOW"`
- New: `"Strong match/Good match/Possible match/Weak match"` via `_CONFIDENCE_LABEL` dict
- Documented threshold mappings, risk assessment, and dual-vocabulary issue
- Note: proposal banner uses hardcoded 0.80/1.00/1.20 breakpoints vs calibrated config thresholds

### C3: Parallelization Skill Documentation
- Verified: UserPromptSubmit hook is wired in `.claude/settings.json` (line 40-48)
- Hook fires on every prompt with parallelization reminder text
- Parallelizer skill exists at `.claude/skills/prompt-parallelizer/SKILL.md`
- Parallel-optimizer agent at `.claude/agents/parallel-optimizer.md`
- Merge-resolver agent at `.claude/agents/merge-resolver.md`
- Status: FULLY WIRED. The hook + skill + agents form a complete pipeline.

### C4: Parallel Sessions Best Practices
- Created `docs/harness/PARALLEL_SESSIONS.md` (264 lines, under 300 limit)
- Covers: worktree setup, file ownership mapping, merge ceremony, when NOT to parallelize, recovery strategies
- Includes historical data from sessions 66/68/69/70/71

### C5: HD Entry
- Added HD-021 "Mechanical Subagent Commit Enforcement" to docs/HARNESS_DECISIONS.md
- Documents architecture, rationale, alternatives considered

### C6: Lessons Learned
- Added Lesson 88 to tasks/lessons.md index and tasks/lessons/harness-lessons.md
- "Monolithic app files prevent parallel worktree execution — Tracks touching app/main.py must be sequential"

## Execution Notes
- Monolithic app/main.py means Track A & B can't safely run in parallel worktrees
- Strategy: Track C in worktree (docs/scripts), Track A on main, Track B after A merges
