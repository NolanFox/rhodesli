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
# State files (session_mode.txt, current_session.txt) are always excluded
# from the dirty check — they're ephemeral session state.
#
# See: HD-025

MODE=$(cat .claude/session_mode.txt 2>/dev/null || echo "implementation")
S=$(cat .claude/current_session.txt 2>/dev/null || echo "unknown")

# --- Continuation mode: never block ---
# The whole point is to write a prompt file and leave.
if [ "$MODE" = "continuation" ]; then
    echo "Continuation mode — no stop checks required."
    # Reset ephemeral state for next conversation (HD-026)
    echo "interactive" > .claude/session_mode.txt
    exit 0
fi

# --- Interactive mode: only check clean git ---
# No assessment or session log required for triage/exploration.
if [ "$MODE" = "interactive" ]; then
    DIRTY=$(git status --porcelain \
        -- ':!.claude/session_mode.txt' \
           ':!.claude/current_session.txt' \
           ':!data/identities.json')
    if [ -n "$DIRTY" ]; then
        echo "BLOCKED: Uncommitted files (commit or restore before ending)" >&2
        echo "$DIRTY" >&2
        exit 2
    fi
    # Reset ephemeral state for next conversation (HD-026)
    echo "interactive" > .claude/session_mode.txt
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

# Check codex audit file exists (HD-030 — mechanical enforcement added Session 141)
# Behavioral instructions failed: Session 141 skipped codex audit despite MANDATORY rule.
# Exception: if codex is unavailable (rate-limited, down, etc.), the audit file must
# still exist but can document the reason codex was skipped. Check for the file,
# not the codex output — this way the engineer must consciously document the skip.
if [ ! -f "docs/session_context/session-${S}-codex-audit.md" ]; then
    echo "BLOCKED: Codex audit file missing for session ${S}" >&2
    echo "Create: docs/session_context/session-${S}-codex-audit.md" >&2
    echo "Either run: codex exec --full-auto 'Audit [changed files]. P0/P1/P2/P3.'" >&2
    echo "Or document why codex was unavailable (rate limit, outage, etc.)" >&2
    exit 2
fi

# Check for uncommitted files (exclude ephemeral state + production-origin data)
# data/identities.json drifts from Supabase runtime syncs — never commit it (Lesson 141)
DIRTY=$(git status --porcelain \
    -- ':!.claude/session_mode.txt' \
       ':!.claude/current_session.txt' \
       ':!data/identities.json')
if [ -n "$DIRTY" ]; then
    echo "BLOCKED: Uncommitted files (commit before ending session)" >&2
    echo "$DIRTY" >&2
    exit 2
fi

# Check SESSION_HISTORY.md was updated with this session (advisory, not blocking)
if ! grep -q "Session ${S}" docs/roadmap/SESSION_HISTORY.md 2>/dev/null; then
    echo "WARNING: Session ${S} not found in docs/roadmap/SESSION_HISTORY.md — update before ending." >&2
fi

# Session 108 (Lesson 148): Warn if commits haven't been pushed to remote.
# Don't block (might be intentional for worktree/parallel sessions), but warn clearly.
AHEAD=$(git log origin/main..HEAD --oneline 2>/dev/null | wc -l | tr -d ' ')
if [ "$AHEAD" -gt 0 ]; then
    echo "WARNING: $AHEAD commit(s) ahead of origin/main — run 'git push origin main' before ending." >&2
fi

# Reset ephemeral state for next conversation (HD-026)
echo "interactive" > .claude/session_mode.txt
exit 0
