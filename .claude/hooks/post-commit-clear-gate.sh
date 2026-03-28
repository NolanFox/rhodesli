#!/bin/bash
# post-commit-clear-gate.sh — Advisory reminder after git commits
#
# Called as PostToolUse hook on Bash. After a git commit succeeds,
# prints a reminder to /clear between phases. Advisory only (exit 0).
#
# The actual enforcement is in pre-work-clear-gate.sh which uses
# transcript line count (ungameable) to detect heavy context.
#
# See: HD-032, Session 143 hooks research

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

# Interactive and continuation sessions skip the reminder.
SESSION_MODE=$(cat .claude/session_mode.txt 2>/dev/null || echo "implementation")
if [ "$SESSION_MODE" = "interactive" ] || [ "$SESSION_MODE" = "continuation" ]; then
    exit 0
fi

# Detect successful git commit — print advisory reminder
if echo "$CMD" | grep -qE '\bgit commit\b'; then
    echo ""
    echo "=== COMMIT DONE — /clear before next phase ==="
    echo "Document everything needed, commit docs, THEN /clear."
    echo "================================================"
    echo ""
fi

exit 0
