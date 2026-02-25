#!/bin/bash
# session-stop-gate.sh — Blocks session end until mandatory outputs exist
# Hook type: command (Stop event)
# Returns: {"decision": "block/approve", "reason": "..."}
#
# Checks:
# 1. Assessment file exists for current session
# 2. SESSION_LOG.md has phase verdicts
# 3. Screenshots without UX review are flagged
# 4. If failures exist, b-path prompt should exist

INPUT=$(cat)
STOP_ACTIVE=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('stop_hook_active','false'))" 2>/dev/null || echo "false")
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
SESSION_ID=$(cat "$PROJECT_DIR/.claude/current_session.txt" 2>/dev/null | tr -d '[:space:]')

# No active session tracking — allow
if [ -z "$SESSION_ID" ] || [ "$SESSION_ID" = "unknown" ]; then
    echo '{"decision": "approve", "reason": "No active session tracking"}'
    exit 0
fi

ASSESSMENT="$PROJECT_DIR/docs/assessments/session-${SESSION_ID}-assessment.md"
SESSION_LOG="$PROJECT_DIR/SESSION_LOG.md"

# If already blocked once, only check for the critical item (assessment)
if [ "$STOP_ACTIVE" = "True" ] || [ "$STOP_ACTIVE" = "true" ]; then
    if [ -f "$ASSESSMENT" ]; then
        echo '{"decision": "approve", "reason": "Assessment file now exists. Session complete."}'
    else
        echo "{\"decision\": \"block\", \"reason\": \"Assessment file STILL missing: docs/assessments/session-${SESSION_ID}-assessment.md — write it now before stopping.\"}"
    fi
    exit 0
fi

# Full checks on first stop attempt
MISSING=""

# Check 1: Assessment file
if [ ! -f "$ASSESSMENT" ]; then
    MISSING="${MISSING}Assessment file (docs/assessments/session-${SESSION_ID}-assessment.md). "
fi

# Check 2: Phase verdicts in SESSION_LOG.md
if [ -f "$SESSION_LOG" ]; then
    PHASE_COUNT=$(grep -cE "Phase.*COMPLETE|Phase.*PASS|Phase.*DONE|Phase.*SKIP" "$SESSION_LOG" 2>/dev/null || echo "0")
    if [ "$PHASE_COUNT" -lt 1 ]; then
        MISSING="${MISSING}Phase verdicts in SESSION_LOG.md (found $PHASE_COUNT phases marked). "
    fi
fi

# Check 3: Screenshots without UX review
SCREENSHOT_DIR="$PROJECT_DIR/docs/screenshots/session-${SESSION_ID}"
if [ -d "$SCREENSHOT_DIR" ]; then
    SCREENSHOT_COUNT=$(ls -1 "$SCREENSHOT_DIR" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$SCREENSHOT_COUNT" -gt 0 ]; then
        if ! grep -qi "ux.review\|ux-reviewer\|UX review" "$SESSION_LOG" 2>/dev/null; then
            MISSING="${MISSING}UX review: $SCREENSHOT_COUNT screenshots in docs/screenshots/session-${SESSION_ID}/ but no UX review logged. "
        fi
    fi
fi

# Check 4: If SESSION_LOG has phase FAIL verdicts (not just the word in test descriptions)
if grep -qE "Phase.*—.*FAIL|Phase.*FAIL$|VERDICT.*FAIL" "$SESSION_LOG" 2>/dev/null; then
    BPATH="$PROJECT_DIR/docs/prompts/session-${SESSION_ID}b-prompt.md"
    if [ ! -f "$BPATH" ]; then
        MISSING="${MISSING}B-path prompt: SESSION_LOG has FAIL but no docs/prompts/session-${SESSION_ID}b-prompt.md. "
    fi
fi

if [ -n "$MISSING" ]; then
    echo "{\"decision\": \"block\", \"reason\": \"Missing: ${MISSING}Complete these before stopping.\"}"
else
    echo "{\"decision\": \"approve\", \"reason\": \"Session ${SESSION_ID} outputs verified.\"}"
fi
exit 0
