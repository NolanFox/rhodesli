---
description: "Framework for overnight/autonomous Claude Code sessions. Use when executing a multi-phase session prompt."
---
# Overnight Session Execution

## Preferred: Use the Runner Script

For multi-phase prompts, use `run_session.sh` — it gives each phase a **separate `claude -p` invocation** with true context isolation:

```bash
./scripts/run_session.sh docs/prompts/session-NNN-prompt.md
```

This eliminates context stuffing entirely. Each phase runs fresh. No /clear needed.

### Prompt Format for Runner

Phases must use `## Phase N:` markers (case-insensitive). Each phase should be self-contained — include file paths, context file references, and goals. Don't assume prior phase context is available.

### Runner Features
- Phase-by-phase execution with checkpoint files between phases
- Auto-evaluation after all phases complete
- B-session generation if evaluator finds issues
- Commit detection per phase
- Commit counter reset between phases

## Fallback: Interactive Session Protocol

If running interactively (not via runner), these rules apply:

1. Execute phases sequentially — ONE deliverable per phase
2. Commit after every phase
3. /clear IMMEDIATELY after every commit — hooks enforce this:
   - PreToolUse: BLOCKS Edit/Write when transcript exceeds 800 lines
   - PostToolUse: advisory reminder after git commit
4. After /clear, re-read the prompt from disk
5. NEVER use /compact — it's lossy. Use /clear + re-read from disk

## Commit Discipline
- Atomic commits: one logical change per commit
- Run tests before commit: `scripts/test-gate.sh fast`
- Format: `feat|fix|docs(scope): description`

## Verification Gate (end of every track)
- Re-read the original prompt
- Check each phase: completed/skipped/partial
- List any deviations with reasoning
- Run `scripts/test-gate.sh all` (both app + ML tests)
- Log results to session history
