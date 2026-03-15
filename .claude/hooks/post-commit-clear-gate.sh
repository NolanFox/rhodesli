#!/bin/bash
# post-commit-clear-gate.sh — Track commits for /clear enforcement
#
# Called as PostToolUse hook on Bash. After a git commit succeeds,
# increments a counter. The PreToolUse hook (pre-work-clear-gate.sh)
# blocks further work until /clear resets the conversation.
#
# For overnight sessions via run_session.sh, this is irrelevant because
# each phase already gets a separate `claude -p` invocation.
# This hook only matters for interactive sessions.
#
# See: HD-025

INPUT=$(cat)
CMD=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    # PostToolUse gets tool_result, not tool_input
    # Check the tool_input from the invocation
    cmd = d.get('tool_input', {}).get('command', '')
    print(cmd)
except:
    print('')
" 2>/dev/null)

# Detect successful git commit
if echo "$CMD" | grep -qE '\bgit commit\b'; then
    # Check if the commit actually succeeded (exit code 0 from the tool)
    COUNTER_FILE=".claude/commits_since_clear.txt"
    CURRENT=$(cat "$COUNTER_FILE" 2>/dev/null || echo "0")
    NEW=$((CURRENT + 1))
    echo "$NEW" > "$COUNTER_FILE"

    if [ "$NEW" -ge 1 ]; then
        echo ""
        echo "=== COMMIT #${NEW} SINCE LAST /clear ==="
        echo "You MUST /clear before starting the next phase."
        echo "Run /clear NOW. Do not read the next phase first."
        echo "After /clear, re-read the prompt file for the next phase."
        echo "============================================"
        echo ""
    fi
fi

exit 0
