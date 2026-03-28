#!/bin/bash
# pre-work-clear-gate.sh — Block work if commits outstanding without /clear
#
# Called as PreToolUse hook on Edit|Write. If commits_since_clear > 0,
# BLOCKS the edit with exit 2, forcing Claude to /clear first.
#
# Session modes:
#   implementation — Multi-phase session. Enforce /clear between phases.
#   interactive    — Ad-hoc work, triage, exploration. No /clear enforcement.
#   continuation   — Writing a continuation prompt. No enforcement at all.
#
# The counter is reset to 0 by:
# - The user running: echo 0 > .claude/commits_since_clear.txt
# - Starting a new conversation (fresh context)
#
# See: HD-025

SESSION_MODE=$(cat .claude/session_mode.txt 2>/dev/null || echo "implementation")

# Interactive and continuation sessions skip the /clear gate.
if [ "$SESSION_MODE" = "interactive" ] || [ "$SESSION_MODE" = "continuation" ]; then
    exit 0
fi

# Session 133: Use git-aware path so worktree agents have their own counter
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
COUNTER_FILE="$REPO_ROOT/.claude/commits_since_clear.txt"
CURRENT=$(cat "$COUNTER_FILE" 2>/dev/null || echo "0")

# Block after 5+ commits without /clear (raised from 1 — Session 143 HD-032)
# Threshold 1 was too aggressive: forced counter reset after every commit,
# preventing autonomous work. 5 allows a full phase while still catching
# runaway context bloat.
# Exception: allow editing session docs (assessments, logs, session_context)
# so you can document before the final commit + /clear.
INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin).get('tool_input', {})
    print(d.get('file_path', d.get('path', '')))
except:
    print('')
" 2>/dev/null)

# Allow session documentation edits even after commits
if echo "$FILE" | grep -qE '(docs/assessments/|docs/session_logs/|docs/session_context/|docs/feedback/|CHANGELOG|ROADMAP|BACKLOG|SESSION_LOG|\.claude/)'; then
    exit 0
fi

if [ "$CURRENT" -ge 5 ]; then
    echo "BLOCKED: $CURRENT commits since last /clear." >&2
    echo "You MUST /clear before editing more code files." >&2
    echo "(Session docs like assessments/logs/CHANGELOG are still allowed)" >&2
    echo "After /clear, reset counter: echo 0 > .claude/commits_since_clear.txt" >&2
    exit 2
fi

exit 0
