#!/bin/bash
# stop-gate.sh — Session end enforcement
#
# Called as Stop hook. Behavior depends on session mode:
#
# Session modes (set via: echo "MODE" > .claude/session_mode.txt):
#   implementation — Multi-phase session. Require assessment + logs + clean git.
#   interactive    — Ad-hoc work, triage, exploration. Only check clean git.
#                    No assessment or session log required.
#   continuation   — Writing a continuation prompt/handoff. Never block.
#
# State files (.claude/commits_since_clear.txt, session_mode.txt, current_session.txt)
# are always excluded from the dirty check — they're ephemeral session state.
#
# See: HD-025

MODE=$(cat .claude/session_mode.txt 2>/dev/null || echo "implementation")
S=$(cat .claude/current_session.txt 2>/dev/null || echo "unknown")

# --- Continuation mode: never block ---
# The whole point is to write a prompt file and leave.
if [ "$MODE" = "continuation" ]; then
    echo "Continuation mode — no stop checks required."
    exit 0
fi

# --- Interactive mode: only check clean git ---
# No assessment or session log required for triage/exploration.
if [ "$MODE" = "interactive" ]; then
    DIRTY=$(git status --porcelain \
        -- ':!.claude/commits_since_clear.txt' \
           ':!.claude/session_mode.txt' \
           ':!.claude/current_session.txt')
    if [ -n "$DIRTY" ]; then
        echo "BLOCKED: Uncommitted files (commit or restore before ending)" >&2
        echo "$DIRTY" >&2
        exit 2
    fi
    exit 0
fi

# --- Implementation mode: full checks ---

# Merge sessions skip assessment requirement
if echo "$S" | grep -qi merge; then
    echo "Merge session — assessment not required"
else
    if [ ! -f "docs/assessments/session-${S}-assessment.md" ]; then
        echo "BLOCKED: Assessment file missing for session ${S}" >&2
        echo "Create: docs/assessments/session-${S}-assessment.md" >&2
        exit 2
    fi
    if [ ! -f "docs/session_logs/session-${S}-log.md" ]; then
        echo "BLOCKED: Session log missing for session ${S}" >&2
        echo "Create: docs/session_logs/session-${S}-log.md" >&2
        exit 2
    fi
fi

# Check for uncommitted files (exclude ephemeral state files)
DIRTY=$(git status --porcelain \
    -- ':!.claude/commits_since_clear.txt' \
       ':!.claude/session_mode.txt' \
       ':!.claude/current_session.txt')
if [ -n "$DIRTY" ]; then
    echo "BLOCKED: Uncommitted files (commit before ending session)" >&2
    echo "$DIRTY" >&2
    exit 2
fi

exit 0
