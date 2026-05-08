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

# cleanup_state — called before any exit path.
# - Resets session mode to interactive for next conversation (HD-026)
# - Clears parallel_session_active if it somehow survived (prevents stuck
#   commit-block on main if a parallel session crashed — 2026-04-18)
cleanup_state() {
    echo "interactive" > .claude/session_mode.txt
    # Only clear the parallel flag if no worktrees still active.
    if [ -f .claude/parallel_session_active ]; then
        local active_worktrees
        active_worktrees=$(git worktree list 2>/dev/null | grep -c agent- || echo 0)
        if [ "$active_worktrees" -eq 0 ]; then
            rm -f .claude/parallel_session_active
        fi
    fi
}

# --- Continuation mode: never block ---
# The whole point is to write a prompt file and leave.
if [ "$MODE" = "continuation" ]; then
    echo "Continuation mode — no stop checks required."
    cleanup_state
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
        # --- STOP_GATE_LOOP_BREAKER_INSTALLED (2026-05-07, fox-genealogy HD-005-derived) ---
        # Scoped loop-breaker: ONLY short-circuits the dirty-files block, not the whole hook.
        # Implementation-mode assessment/log/codex-audit requirements above are NOT bypassed.
        LB_STATE=".claude/.stop-gate-state"
        LB_HASH=$(echo "$DIRTY" | shasum -a 256 | cut -d' ' -f1)
        LB_NOW=$(date +%s)
        if [ -f "$LB_STATE" ]; then
            LB_LAST=$(tail -1 "$LB_STATE" 2>/dev/null || echo "")
            LB_LH=$(echo "$LB_LAST" | awk -F'|' '{print $1}')
            LB_LT=$(echo "$LB_LAST" | awk -F'|' '{print $2}')
            LB_LC=$(echo "$LB_LAST" | awk -F'|' '{print $3}')
            # Validate timestamp + count are numeric (defends against state corruption)
            if [ "$LB_LH" = "$LB_HASH" ] && [[ "$LB_LT" =~ ^[0-9]+$ ]] && [[ "$LB_LC" =~ ^[0-9]+$ ]]; then
                LB_AGE=$((LB_NOW - LB_LT))
                # Reject negative ages (clock skew or future-dated state)
                if [ "$LB_AGE" -ge 0 ] && [ "$LB_AGE" -le 60 ]; then
                    LB_NEW=$((LB_LC + 1))
                    echo "${LB_HASH}|${LB_NOW}|${LB_NEW}" > "$LB_STATE"
                    if [ "$LB_NEW" -ge 3 ]; then
                        echo "WARNING: stop-gate loop-breaker activated. Same dirty file set blocked $LB_NEW times in 60s." >&2
                        echo "Likely cause: concurrent Claude Code conversation with dirty files in this repo." >&2
                        echo "Bypassing dirty-files block ONLY. Other hook checks (assessment, log, codex audit) still enforced." >&2
                        echo "To re-enable strict checks: clean working tree or remove $LB_STATE." >&2
                        cleanup_state 2>/dev/null || true
                        exit 0
                    fi
                else
                    echo "${LB_HASH}|${LB_NOW}|1" > "$LB_STATE"
                fi
            else
                echo "${LB_HASH}|${LB_NOW}|1" > "$LB_STATE"
            fi
        else
            echo "${LB_HASH}|${LB_NOW}|1" > "$LB_STATE"
        fi
        # --- END STOP_GATE_LOOP_BREAKER ---
        exit 2
    fi
    cleanup_state
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
    echo "Either run: codex exec 'Audit [changed files]. P0/P1/P2/P3.'  # NOT --full-auto (stdin hang, see .claude/rules/ai-tool-audit.md)" >&2
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
        # --- STOP_GATE_LOOP_BREAKER_INSTALLED (2026-05-07, fox-genealogy HD-005-derived) ---
        # Scoped loop-breaker: ONLY short-circuits the dirty-files block, not the whole hook.
        # Implementation-mode assessment/log/codex-audit requirements above are NOT bypassed.
        LB_STATE=".claude/.stop-gate-state"
        LB_HASH=$(echo "$DIRTY" | shasum -a 256 | cut -d' ' -f1)
        LB_NOW=$(date +%s)
        if [ -f "$LB_STATE" ]; then
            LB_LAST=$(tail -1 "$LB_STATE" 2>/dev/null || echo "")
            LB_LH=$(echo "$LB_LAST" | awk -F'|' '{print $1}')
            LB_LT=$(echo "$LB_LAST" | awk -F'|' '{print $2}')
            LB_LC=$(echo "$LB_LAST" | awk -F'|' '{print $3}')
            # Validate timestamp + count are numeric (defends against state corruption)
            if [ "$LB_LH" = "$LB_HASH" ] && [[ "$LB_LT" =~ ^[0-9]+$ ]] && [[ "$LB_LC" =~ ^[0-9]+$ ]]; then
                LB_AGE=$((LB_NOW - LB_LT))
                # Reject negative ages (clock skew or future-dated state)
                if [ "$LB_AGE" -ge 0 ] && [ "$LB_AGE" -le 60 ]; then
                    LB_NEW=$((LB_LC + 1))
                    echo "${LB_HASH}|${LB_NOW}|${LB_NEW}" > "$LB_STATE"
                    if [ "$LB_NEW" -ge 3 ]; then
                        echo "WARNING: stop-gate loop-breaker activated. Same dirty file set blocked $LB_NEW times in 60s." >&2
                        echo "Likely cause: concurrent Claude Code conversation with dirty files in this repo." >&2
                        echo "Bypassing dirty-files block ONLY. Other hook checks (assessment, log, codex audit) still enforced." >&2
                        echo "To re-enable strict checks: clean working tree or remove $LB_STATE." >&2
                        cleanup_state 2>/dev/null || true
                        exit 0
                    fi
                else
                    echo "${LB_HASH}|${LB_NOW}|1" > "$LB_STATE"
                fi
            else
                echo "${LB_HASH}|${LB_NOW}|1" > "$LB_STATE"
            fi
        else
            echo "${LB_HASH}|${LB_NOW}|1" > "$LB_STATE"
        fi
        # --- END STOP_GATE_LOOP_BREAKER ---
        exit 2
fi

# Check SESSION_HISTORY.md was updated with this session (advisory, not blocking)
if ! grep -q "Session ${S}" docs/roadmap/SESSION_HISTORY.md 2>/dev/null; then
    echo "WARNING: Session ${S} not found in docs/roadmap/SESSION_HISTORY.md — update before ending." >&2
fi

# Session 108 (Lesson 148): Warn if commits haven't been pushed to remote.
# Don't block (might be intentional for worktree/parallel sessions), but warn clearly.
if git rev-parse --verify origin/main >/dev/null 2>&1; then
    AHEAD=$(git log origin/main..HEAD --oneline 2>/dev/null | wc -l | tr -d ' ')
    if [ "$AHEAD" -gt 0 ]; then
        echo "WARNING: $AHEAD commit(s) ahead of origin/main — run 'git push origin main' before ending." >&2
    fi
else
    echo "WARNING: Cannot verify origin/main (remote unavailable) — cannot confirm push status." >&2
fi

# Memory backup + integrity check (2026-04-18 — Lesson 169, Session 148).
# Non-blocking: advisory warning only. User's memory lives outside git so this
# is the last line of defense against accidental loss.
if [ -x scripts/backup-memory.sh ]; then
    if ! bash scripts/backup-memory.sh >/dev/null 2>&1; then
        echo "WARNING: Memory backup/integrity check failed — run scripts/backup-memory.sh manually." >&2
    fi
fi

cleanup_state
exit 0
