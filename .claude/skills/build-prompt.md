---
description: "Build a session prompt following Rhodesli best practices. Use when planning the next session."
disable-model-invocation: true
---
# Session Prompt Builder

## Inputs needed:
1. ROADMAP.md current priorities
2. BACKLOG.md open items
3. Last session assessment (from /skill:assess-session)
4. Any specific goals from Nolan

## Best practices to enforce:
- ONE deliverable per phase
- Total prompt under 3500 tokens per track
- /clear between phases (mandatory, explicit, repeated)
- Verification gate at end of each track
- Commit per phase
- Context file in docs/session_context/ with breadcrumbs
- Prompt file in docs/prompts/
- Small enough phases that context window doesn't fill up

## Template structure:
1. READ FIRST block (files to read in order)
2. SESSION RULES (non-negotiable constraints)
3. Phases grouped by track (if using worktrees)
4. Each phase: goal, steps, tests, commit message
5. Verification gate per track
6. Documentation updates (AD, ROADMAP, SESSION_HISTORY)

## Before finalizing:
- Diff ROADMAP.md — no items may be silently removed
- Diff BACKLOG.md — no items may be silently removed
- Check that all open concerns from last assessment have a phase
