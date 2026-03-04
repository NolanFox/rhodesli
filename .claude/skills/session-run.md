---
description: "Framework for overnight/autonomous Claude Code sessions. Use when executing a multi-phase session prompt."
---
# Overnight Session Execution

## Protocol
1. Read CLAUDE.md, then the session prompt, then referenced context files
2. Execute phases sequentially — ONE deliverable per phase
3. Commit after every phase with descriptive message
4. Print context % after every phase
5. If context < 40%: /clear and re-read CLAUDE.md + prompt
6. If context < 20%: STOP. Log progress to SESSION_HISTORY.md
7. NEVER use /compact — it's lossy. Use /clear + re-read from disk

## Commit Discipline
- Atomic commits: one logical change per commit
- Run tests before commit: `scripts/test-gate.sh fast`
- Format: `feat|fix|docs(scope): description`

## Post-Implementation Quality Gate
After each implementation phase (not docs-only phases):
1. Run /simplify to review changed code for reuse, quality, and efficiency
2. Fix any issues found by /simplify before committing
3. This catches debug prints, dead code, and quality regressions early

## Verification Gate (end of every track)
- Re-read the original prompt
- Check each phase: completed/skipped/partial
- List any deviations with reasoning
- Run `scripts/test-gate.sh all` (both app + ML tests)
- Log results to session history
