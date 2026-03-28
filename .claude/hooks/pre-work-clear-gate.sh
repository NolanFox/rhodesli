#!/bin/bash
# pre-work-clear-gate.sh — Block work when conversation context is heavy
#
# Called as PreToolUse hook on Edit|Write. Reads the transcript file
# (via transcript_path from stdin JSON) and counts lines as a proxy
# for context usage. The transcript is written by Claude Code and
# cannot be modified by the agent — this is an ungameable signal.
#
# Thresholds:
#   800+ lines — BLOCK (exit 2): context is heavy, /clear recommended
#   400+ lines — WARN (exit 0): advisory message, no block
#
# Session modes:
#   implementation — Multi-phase session. Enforce /clear between phases.
#   interactive    — Ad-hoc work, triage, exploration. No /clear enforcement.
#   continuation   — Writing a continuation prompt. No enforcement at all.
#
# See: HD-032, Session 143 hooks research

SESSION_MODE=$(cat .claude/session_mode.txt 2>/dev/null || echo "implementation")

# Interactive and continuation sessions skip the /clear gate.
if [ "$SESSION_MODE" = "interactive" ] || [ "$SESSION_MODE" = "continuation" ]; then
    exit 0
fi

# Read hook input JSON from stdin
INPUT=$(cat)

# Extract file path to check for session doc exemptions
FILE=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin).get('tool_input', {})
    print(d.get('file_path', d.get('path', '')))
except:
    print('')
" 2>/dev/null)

# Allow session documentation edits regardless of context size
if echo "$FILE" | grep -qE '(docs/assessments/|docs/session_logs/|docs/session_context/|docs/feedback/|CHANGELOG|ROADMAP|BACKLOG|SESSION_LOG|\.claude/)'; then
    exit 0
fi

# Extract transcript_path from hook input
TRANSCRIPT=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    print(json.load(sys.stdin).get('transcript_path', ''))
except:
    print('')
" 2>/dev/null)

# If no transcript path or file doesn't exist, allow (graceful degradation)
if [ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ]; then
    exit 0
fi

# Count transcript lines — fast, ungameable proxy for context usage
LINES=$(wc -l < "$TRANSCRIPT" 2>/dev/null | tr -d ' ')

# Block at 800+ lines
if [ "$LINES" -ge 800 ]; then
    echo "BLOCKED: Transcript is $LINES lines — context is heavy." >&2
    echo "Run /clear before editing more code files." >&2
    echo "(Session docs like assessments/logs/CHANGELOG are still allowed)" >&2
    exit 2
fi

# Warn at 400+ lines (advisory, does not block)
if [ "$LINES" -ge 400 ]; then
    echo ""
    echo "=== Context advisory: $LINES transcript lines ==="
    echo "Consider /clear before starting the next phase."
    echo "================================================"
    echo ""
fi

exit 0
