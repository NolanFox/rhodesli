#!/bin/bash
# Session self-evaluation helper
# Usage: bash scripts/session_assessment.sh <session-id> <prompt-file>

SESSION_ID=$1
PROMPT_FILE=$2

if [ -z "$SESSION_ID" ]; then
    echo "Usage: bash scripts/session_assessment.sh <session-id> [prompt-file]"
    echo "Example: bash scripts/session_assessment.sh 65c docs/prompts/session-65c-prompt.md"
    exit 1
fi

echo "=============================================="
echo "SESSION $SESSION_ID SELF-EVALUATION"
echo "=============================================="
echo ""

# Check mandatory outputs exist
echo "--- Mandatory Outputs ---"
[ -f "docs/assessments/session-${SESSION_ID}-assessment.md" ] && echo "  OK Assessment file" || echo "  MISSING Assessment file"
[ -f "SESSION_LOG.md" ] && echo "  OK Session log" || echo "  MISSING Session log"
[ -f "CHANGELOG.md" ] && echo "  OK CHANGELOG" || echo "  MISSING CHANGELOG"
[ -f "ROADMAP.md" ] && echo "  OK ROADMAP" || echo "  MISSING ROADMAP"
echo ""

# Check screenshots exist (if UX work was done)
SCREENSHOT_DIR="docs/screenshots/session-${SESSION_ID}"
if [ -d "$SCREENSHOT_DIR" ]; then
    COUNT=$(ls "$SCREENSHOT_DIR" 2>/dev/null | wc -l | tr -d ' ')
    echo "  OK Screenshots: $COUNT files in $SCREENSHOT_DIR"
else
    echo "  -- No screenshots directory (OK if no UX work)"
fi
echo ""

# Run tests
echo "--- Test Suites ---"
echo "App tests:"
source venv/bin/activate 2>/dev/null
pytest tests/ -x -q 2>&1 | tail -3
echo ""
echo "ML tests:"
pytest rhodesli_ml/tests/ -x -q 2>&1 | tail -3
echo ""

# Check recent commits
echo "--- Recent Commits ---"
git log --oneline -10
echo ""

# Check CLAUDE.md line count
CLAUDE_LINES=$(wc -l < CLAUDE.md | tr -d ' ')
echo "--- Doc Sizes ---"
echo "  CLAUDE.md: $CLAUDE_LINES lines (limit: 80)"
if [ "$CLAUDE_LINES" -gt 80 ]; then
    echo "  WARNING: CLAUDE.md exceeds 80 lines!"
fi
ROADMAP_LINES=$(wc -l < ROADMAP.md | tr -d ' ')
echo "  ROADMAP.md: $ROADMAP_LINES lines (limit: 150)"
echo ""

# Show prompt if provided
if [ -n "$PROMPT_FILE" ] && [ -f "$PROMPT_FILE" ]; then
    echo "--- Prompt Phases ---"
    grep -n "^## PHASE\|^### Phase" "$PROMPT_FILE"
    echo ""
fi

echo "=============================================="
echo "END EVALUATION"
echo "=============================================="
