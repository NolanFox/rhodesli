#!/bin/bash
# Session self-evaluation helper — enhanced for harness enforcement (HD-015)
# Usage: bash scripts/session_assessment.sh <session-id> [prompt-file]
# Returns non-zero exit code if critical items are missing.

SESSION_ID=$1
PROMPT_FILE=$2

if [ -z "$SESSION_ID" ]; then
    echo "Usage: bash scripts/session_assessment.sh <session-id> [prompt-file]"
    echo "Example: bash scripts/session_assessment.sh 65d docs/prompts/session-65d-prompt.md"
    exit 1
fi

CRITICAL_FAIL=0
WARN_COUNT=0

echo "=============================================="
echo "SESSION $SESSION_ID SELF-EVALUATION"
echo "=============================================="
echo ""

# 1. Mandatory outputs
echo "--- Mandatory Outputs ---"
check_file() {
    local path=$1 label=$2 critical=$3
    if [ -f "$path" ]; then
        echo "  [PASS] $label"
    elif [ "$critical" = "critical" ]; then
        echo "  [FAIL] $label — MISSING"
        CRITICAL_FAIL=$((CRITICAL_FAIL + 1))
    else
        echo "  [WARN] $label — missing"
        WARN_COUNT=$((WARN_COUNT + 1))
    fi
}

check_file "docs/assessments/session-${SESSION_ID}-assessment.md" "Assessment file" "critical"
check_file "SESSION_LOG.md" "Session log" "critical"
check_file "CHANGELOG.md" "CHANGELOG" "warn"
check_file "ROADMAP.md" "ROADMAP" "warn"
echo ""

# 2. Screenshots (if UX work was done)
echo "--- Screenshots ---"
SCREENSHOT_DIR="docs/screenshots/session-${SESSION_ID}"
if [ -d "$SCREENSHOT_DIR" ]; then
    COUNT=$(ls "$SCREENSHOT_DIR" 2>/dev/null | wc -l | tr -d ' ')
    echo "  [PASS] Screenshots: $COUNT files in $SCREENSHOT_DIR"
else
    echo "  [--] No screenshots directory (OK if no UX work)"
fi
echo ""

# 3. Context management checks
echo "--- Context Management ---"
# Check for /compact usage (red flag)
COMPACT_REFS=$(git log --oneline -20 2>/dev/null | grep -ci "compact" || true)
if [ "$COMPACT_REFS" -gt 0 ]; then
    echo "  [FLAG] /compact may have been used ($COMPACT_REFS refs in recent commits)"
    WARN_COUNT=$((WARN_COUNT + 1))
else
    echo "  [PASS] No /compact references in recent commits"
fi
# Check .claude/current_session.txt
if [ -f ".claude/current_session.txt" ]; then
    STORED_ID=$(cat .claude/current_session.txt)
    if [ "$STORED_ID" = "$SESSION_ID" ]; then
        echo "  [PASS] current_session.txt = $SESSION_ID"
    else
        echo "  [WARN] current_session.txt = $STORED_ID (expected $SESSION_ID)"
    fi
else
    echo "  [WARN] .claude/current_session.txt missing"
fi
echo ""

# 4. Test suites
echo "--- Test Suites ---"
if command -v pytest &>/dev/null; then
    echo "App tests:"
    source venv/bin/activate 2>/dev/null
    APP_RESULT=$(pytest tests/ -x -q 2>&1 | tail -3)
    echo "$APP_RESULT"
    if echo "$APP_RESULT" | grep -q "failed"; then
        echo "  [FAIL] App tests have failures"
        CRITICAL_FAIL=$((CRITICAL_FAIL + 1))
    fi
    echo ""
    echo "ML tests:"
    ML_RESULT=$(pytest rhodesli_ml/tests/ -x -q 2>&1 | tail -3)
    echo "$ML_RESULT"
    if echo "$ML_RESULT" | grep -q "failed"; then
        echo "  [FAIL] ML tests have failures"
        CRITICAL_FAIL=$((CRITICAL_FAIL + 1))
    fi
else
    echo "  [SKIP] pytest not found"
fi
echo ""

# 5. Recent commits
echo "--- Recent Commits (this session) ---"
git log --oneline -10
echo ""

# 6. Doc sizes
echo "--- Doc Sizes ---"
CLAUDE_LINES=$(wc -l < CLAUDE.md 2>/dev/null | tr -d ' ')
echo "  CLAUDE.md: $CLAUDE_LINES lines (limit: 80)"
if [ "$CLAUDE_LINES" -gt 80 ]; then
    echo "  [WARN] CLAUDE.md exceeds 80 lines!"
    WARN_COUNT=$((WARN_COUNT + 1))
fi
ROADMAP_LINES=$(wc -l < ROADMAP.md 2>/dev/null | tr -d ' ')
echo "  ROADMAP.md: $ROADMAP_LINES lines (limit: 150)"
if [ "$ROADMAP_LINES" -gt 150 ]; then
    echo "  [WARN] ROADMAP.md exceeds 150 lines!"
    WARN_COUNT=$((WARN_COUNT + 1))
fi
echo ""

# 7. AD entries check
echo "--- Algorithmic Decisions ---"
AD_COUNT=$(grep -c "^### AD-" docs/ml/ALGORITHMIC_DECISIONS.md 2>/dev/null || echo 0)
echo "  Total AD entries: $AD_COUNT"
LATEST_AD=$(grep "^### AD-" docs/ml/ALGORITHMIC_DECISIONS.md 2>/dev/null | tail -1)
echo "  Latest: $LATEST_AD"
echo ""

# 8. Prompt phases (if provided)
if [ -n "$PROMPT_FILE" ] && [ -f "$PROMPT_FILE" ]; then
    echo "--- Prompt Phases ---"
    grep -n "^## PHASE\|^### Phase" "$PROMPT_FILE"
    echo ""
fi

# Summary
echo "=============================================="
echo "SUMMARY: $CRITICAL_FAIL critical failures, $WARN_COUNT warnings"
if [ "$CRITICAL_FAIL" -gt 0 ]; then
    echo "ACTION REQUIRED: Fix critical failures before completing session"
fi
echo "=============================================="

exit $CRITICAL_FAIL
