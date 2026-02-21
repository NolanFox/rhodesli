# Overnight Session Protocol

Applies when: Session runs autonomously, typically while human is
away. No human available for questions.

## Before Starting
Read these files in order:
1. CLAUDE.md (always)
2. .claude/rules/prompt-decomposition.md
3. .claude/rules/phase-execution.md
4. .claude/rules/verification-gate.md
5. Prompt file at docs/prompts/session_NN_prompt.md

## Core Rules

### No Human Available
- NEVER stop to ask — log and continue
- Blockers → session log + tasks/todo.md, skip to next phase
- Ambiguity → conservative option, document why

### Prompt Preservation
- First action: save prompt to docs/prompts/session_NN_prompt.md
- Parse phases: docs/prompts/session_NN_phases.json
- Re-read relevant phase before each phase (not memory)

### Context Management
- /compact at 60% context
- After compaction: re-read current phase from prompt file
- Commit after every phase

### Verification Gate (MANDATORY)
- Re-read original prompt from disk
- Check every deliverable against criteria
- Run pytest, deployment checks
- Log gate results

### Safety
- NO irreversible data mutations without explicit instruction
- NO pushing to production unless prompt says to
- Data scripts: --dry-run default

## Breadcrumbs
- docs/session_protocols/INDEX.md → this file
- .claude/rules/prompt-decomposition.md (HD-001)
- .claude/rules/phase-execution.md (HD-002)
- .claude/rules/verification-gate.md (HD-003, HD-004)
- HARNESS_DECISIONS.md → HD-015
