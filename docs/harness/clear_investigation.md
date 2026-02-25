# /clear Investigation — Context Isolation in Headless Mode

**Date:** 2026-02-25 | **Session:** 67

## Question
Does `/clear` work when running Claude Code with the `-p` (pipe) flag?

## Finding
**No. `/clear` is an interactive-mode slash command.** In `-p` mode:
- Claude Code runs a single prompt and exits
- Slash commands are not available
- There is no persistent session to clear

## Implication
Multi-phase sessions that need context isolation between phases cannot use
`/clear` in `-p` mode. Each phase must be a separate `claude -p` invocation.

## Solution: Phase-Splitting Session Runner

`scripts/run_session.sh` splits a session prompt into phases and runs each
as an independent `claude -p` call. Each invocation:
1. Gets a fresh context window (true isolation)
2. Reads the session prompt file and checkpoint from disk
3. Writes progress to a checkpoint file for the next phase
4. Commits after each phase

This gives REAL context isolation, not the fake isolation of `/clear` inside
an interactive session (which merely truncates the transcript but doesn't
release context window space).

## Limitation
Cannot test `claude -p` from within a Claude Code session (no nesting allowed).
The session runner script needs manual testing by the user:

```bash
./scripts/run_session.sh docs/prompts/session-68-prompt.md
```

## Recommendation
1. Continue using interactive mode with `/clear` between phases
2. For overnight/unattended runs, use `scripts/run_session.sh`
3. Each phase's `claude -p` call should re-read CLAUDE.md + session prompt
