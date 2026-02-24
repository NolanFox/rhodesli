#!/bin/bash
# Post-session evaluation hook — runs when Claude Code finishes.
# Checks mandatory session outputs and warns if anything is missing.

SESSION_ID=$(cat .claude/current_session.txt 2>/dev/null || echo "unknown")

if [ "$SESSION_ID" = "unknown" ]; then
    exit 0  # No session tracking active
fi

MISSING=0

# Check assessment file
if [ ! -f "docs/assessments/session-${SESSION_ID}-assessment.md" ]; then
    echo "WARNING: Assessment file missing! Run: bash scripts/session_assessment.sh $SESSION_ID" >&2
    MISSING=$((MISSING + 1))
fi

# Check SESSION_LOG.md was updated
if ! grep -q "Phase.*VERDICT" SESSION_LOG.md 2>/dev/null; then
    echo "WARNING: SESSION_LOG.md may not have phase verdicts" >&2
fi

# Check for /compact usage (red flag)
if git log --oneline -20 2>/dev/null | grep -qi "compact"; then
    echo "RED FLAG: /compact may have been used in this session" >&2
fi

# macOS notification
osascript -e "display notification \"Session $SESSION_ID completed. Missing outputs: $MISSING\" with title \"Rhodesli\"" 2>/dev/null

exit 0
