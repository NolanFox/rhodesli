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
- Run tests before commit: `pytest tests/ -x -q --ignore=tests/e2e/`
- Format: `feat|fix|docs(scope): description`

## Verification Gate (end of every track)
- Re-read the original prompt
- Check each phase: completed/skipped/partial
- List any deviations with reasoning
- Run full test suite
- Log results to session history
