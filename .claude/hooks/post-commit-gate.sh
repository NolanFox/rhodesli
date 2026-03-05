#!/bin/bash
# post-commit-gate.sh — /clear enforcement after git commit/merge
# Lesson 89: violated in Sessions 80 AND 89. Behavioral reminders failed.
# This hook now tracks commits-since-clear and ESCALATES warnings.

INPUT=$(cat)
CMD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null)

if echo "$CMD" | grep -qE "git commit|git merge"; then
    REPO=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
    S=$(cat "$REPO/.claude/current_session.txt" 2>/dev/null | tr -d '[:space:]' || echo "unknown")
    TRACKER="$REPO/.claude/commits_since_clear.txt"

    # Increment commit counter
    COUNT=0
    if [ -f "$TRACKER" ]; then
        COUNT=$(cat "$TRACKER" | tr -d '[:space:]')
        if ! [[ "$COUNT" =~ ^[0-9]+$ ]]; then COUNT=0; fi
    fi
    COUNT=$((COUNT + 1))
    echo "$COUNT" > "$TRACKER"

    if [ "$COUNT" -ge 3 ]; then
        echo "" >&2
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" >&2
        echo "CRITICAL: $COUNT COMMITS WITHOUT /clear" >&2
        echo "This is EXACTLY how Sessions 80, 89, and 89-cont failed." >&2
        echo "NEXT PROMPT WILL BE HARD-BLOCKED." >&2
        echo "NEXT GIT COMMIT WILL BE HARD-BLOCKED (at 4+)." >&2
        echo "You MUST /clear NOW. There is NO workaround." >&2
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" >&2
        echo "" >&2
    elif [ "$COUNT" -ge 2 ]; then
        echo "" >&2
        echo "WARNING: $COUNT commits without /clear." >&2
        echo "You are approaching the danger zone." >&2
        echo "/clear NOW before the next act." >&2
        echo "" >&2
    fi

    echo "=============================================="
    echo "SESSION ${S}: /clear GATE (commit #${COUNT})"
    echo "=============================================="
    echo "You just committed. You MUST now:"
    echo "  1. Run /clear (NOT /compact)"
    echo "  2. Re-read ONLY next act from prompt"
    echo "  3. Consider running /simplify if this was implementation"
    echo "=============================================="
    echo "REMINDER: Run make test-fast before proceeding."
fi

exit 0
