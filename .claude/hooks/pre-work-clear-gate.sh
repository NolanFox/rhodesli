#!/bin/bash
# pre-work-clear-gate.sh — Block work when conversation context is heavy
#
# Called as PreToolUse hook on Edit|Write. Reads the transcript file
# (via transcript_path from stdin JSON) and counts lines as a proxy
# for context usage. The transcript is written by Claude Code and
# cannot be modified by the agent — this is an ungameable signal.
#
# Thresholds (tightened 2026-04-18 for Opus 4.7):
#   600+ lines — BLOCK (exit 2): context is heavy, /clear recommended
#   300+ lines — WARN (exit 0): advisory message, no block
#
# Why tightened: Opus 4.7 MRCR v2 recall drops to 32.2% (vs 4.6's 78.3%)
# and 4.7's tokenizer uses 1x-1.35x more tokens for the same text.
# Aggressive /clear is MORE important on 4.7, not less.
#
# Session modes:
#   implementation — Multi-phase session. Enforce /clear between phases.
#   interactive    — Ad-hoc work, triage, exploration. No /clear enforcement.
#   continuation   — Writing a continuation prompt. No enforcement at all.
#
# See: HD-032, Session 143 hooks research, Session 149 harness upgrade

set -uo pipefail

SESSION_MODE=$(cat .claude/session_mode.txt 2>/dev/null || echo "implementation")

# Interactive and continuation sessions skip the /clear gate.
if [ "$SESSION_MODE" = "interactive" ] || [ "$SESSION_MODE" = "continuation" ]; then
    exit 0
fi

# Fail CLOSED on missing python3 — the hook is enforcement, not advisory.
if ! command -v python3 >/dev/null 2>&1; then
    echo "BLOCKED: python3 not available for hook input parsing." >&2
    echo "Install python3 or set SESSION_MODE=interactive to bypass." >&2
    exit 2
fi

# Read hook input JSON from stdin
INPUT=$(cat)

# Extract file path. Parse failures fail CLOSED (exit 2) since this is a
# security-relevant gate (Codex audit P0, 2026-04-18).
FILE=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin).get('tool_input', {})
print(d.get('file_path', d.get('path', '')))
" 2>&1) || {
    echo "BLOCKED: Could not parse hook input JSON." >&2
    echo "$FILE" >&2
    exit 2
}

# Canonicalize FILE path to prevent bypass via ../ or embedded keywords
# (Codex audit P0, 2026-04-18: 'docs/session_context/../../app/main.py'
# previously bypassed the edit block). Uses Python for portable realpath
# since BSD realpath on macOS doesn't support -m.
REPO=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [ -n "$FILE" ] && [ -n "$REPO" ]; then
    CANONICAL=$(REPO="$REPO" FILE="$FILE" python3 -c "
import os, sys
repo = os.environ['REPO']
f = os.environ['FILE']
abs_path = f if os.path.isabs(f) else os.path.join(repo, f)
print(os.path.realpath(abs_path))
" 2>/dev/null)
    # Only exempt if canonical path is anchored to repo root AND in an allowed directory
    case "$CANONICAL" in
        "$REPO"/docs/assessments/*|\
        "$REPO"/docs/session_logs/*|\
        "$REPO"/docs/session_context/*|\
        "$REPO"/docs/feedback/*|\
        "$REPO"/CHANGELOG.md|\
        "$REPO"/ROADMAP.md|\
        "$REPO"/BACKLOG.md|\
        "$REPO"/SESSION_LOG.md|\
        "$REPO"/.claude/*)
            exit 0
            ;;
    esac
fi

# Extract transcript_path from hook input (same fail-closed policy)
TRANSCRIPT=$(echo "$INPUT" | python3 -c "
import sys, json
print(json.load(sys.stdin).get('transcript_path', ''))
" 2>&1) || {
    echo "BLOCKED: Could not parse hook input for transcript_path." >&2
    exit 2
}

# If no transcript path, allow (first-turn edits have no transcript yet).
if [ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ]; then
    exit 0
fi

# Count transcript lines — fast, ungameable proxy for context usage
LINES=$(wc -l < "$TRANSCRIPT" 2>/dev/null | tr -d ' ')
LINES=${LINES:-0}

# Block at 600+ lines (tightened from 800 for Opus 4.7)
if [ "$LINES" -ge 600 ]; then
    echo "BLOCKED: Transcript is $LINES lines — context is heavy." >&2
    echo "Run /clear before editing more code files." >&2
    echo "(Session docs like assessments/logs/CHANGELOG are still allowed)" >&2
    exit 2
fi

# Warn at 300+ lines (advisory, does not block)
if [ "$LINES" -ge 300 ]; then
    echo ""
    echo "=== Context advisory: $LINES transcript lines ==="
    echo "Consider /clear before starting the next phase."
    echo "(Opus 4.7 recall drops sharply past this point.)"
    echo "================================================"
    echo ""
fi

exit 0
