#!/bin/bash
# post-commit-gate.sh — Dynamic /clear gate after git commit/merge
# Replaces hardcoded session-81 references with current session (HD-024)

INPUT=$(cat)
CMD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null)

if echo "$CMD" | grep -qE "git commit|git merge"; then
    REPO=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
    S=$(cat "$REPO/.claude/current_session.txt" 2>/dev/null | tr -d '[:space:]' || echo "unknown")

    echo "══════════════════════════════════════════════"
    echo "SESSION ${S}: /clear GATE"
    echo "══════════════════════════════════════════════"
    echo "You just committed. You MUST now:"
    echo "  1. Run /clear (NOT /compact)"
    echo "  2. Re-read ONLY next act from docs/prompts/session-${S}-prompt.md"
    echo "  3. Consider running /simplify if this was implementation work"
    echo "══════════════════════════════════════════════"
    echo "REMINDER: Run make test-fast before proceeding."
fi

exit 0
