#!/bin/bash
# post-commit-clear-gate.sh — Track commits for /clear enforcement
#
# Called as PostToolUse hook on Bash. After a git commit succeeds,
# increments a counter. The PreToolUse hook (pre-work-clear-gate.sh)
# blocks further EDITS until /clear resets the conversation.
#
# IMPORTANT: This hook exits 0 (warn only). Blocking happens at the
# pre-work gate. Exiting 2 here would make the commit tool call appear
# to fail even though git commit succeeded — confusing and causes the
# user to have to hit ESC.
#
# See: HD-025

INPUT=$(cat)
CMD=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    cmd = d.get('tool_input', {}).get('command', '')
    print(cmd)
except:
    print('')
" 2>/dev/null)

# Interactive and continuation sessions skip the /clear gate.
SESSION_MODE=$(cat .claude/session_mode.txt 2>/dev/null || echo "implementation")
if [ "$SESSION_MODE" = "interactive" ] || [ "$SESSION_MODE" = "continuation" ]; then
    exit 0
fi

# Detect successful git commit
if echo "$CMD" | grep -qE '\bgit commit\b'; then
    COUNTER_FILE=".claude/commits_since_clear.txt"
    CURRENT=$(cat "$COUNTER_FILE" 2>/dev/null || echo "0")
    NEW=$((CURRENT + 1))
    echo "$NEW" > "$COUNTER_FILE"

    # Warn (stdout, not stderr) — blocking happens at pre-work-clear-gate
    echo ""
    echo "=== COMMIT #${NEW} — /clear before next phase ==="
    echo "Run /clear before starting the next phase."
    echo "Document everything needed, commit docs, THEN /clear."
    echo "================================================"
    echo ""
fi

exit 0
