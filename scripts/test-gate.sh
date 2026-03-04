#!/bin/bash
# test-gate.sh — Unified test gate for all tools (HD-024)
# Usage: scripts/test-gate.sh [fast|full|ml|all]
# Called by hooks and scripts instead of inline pytest commands

set -euo pipefail

MODE=${1:-fast}
# Handle worktrees: git-common-dir points to main repo's .git
REPO=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
PYTEST="${REPO}/venv/bin/pytest"

# Worktree fallback: check main repo via git-common-dir
if [ ! -f "$PYTEST" ]; then
    COMMON=$(git rev-parse --git-common-dir 2>/dev/null)
    if [ -n "$COMMON" ] && [ "$COMMON" != ".git" ]; then
        MAIN_REPO=$(dirname "$COMMON")
        PYTEST="${MAIN_REPO}/venv/bin/pytest"
    fi
fi

if [ ! -f "$PYTEST" ]; then
    echo "ERROR: pytest not found" >&2
    exit 1
fi

case "$MODE" in
    fast)
        $PYTEST tests/ -x -q -n auto -m "not slow" --timeout=30 2>&1 | tail -20
        ;;
    full)
        $PYTEST tests/ -x -q -n auto --timeout=60 2>&1 | tail -20
        ;;
    ml)
        $PYTEST rhodesli_ml/tests/ -x -q -n auto --timeout=60 2>&1 | tail -20
        ;;
    all)
        echo "=== App Tests ==="
        $PYTEST tests/ -x -q -n auto --timeout=60 2>&1 | tail -10
        echo ""
        echo "=== ML Tests ==="
        $PYTEST rhodesli_ml/tests/ -x -q -n auto --timeout=60 2>&1 | tail -10
        ;;
    *)
        echo "Usage: scripts/test-gate.sh [fast|full|ml|all]" >&2
        exit 1
        ;;
esac
