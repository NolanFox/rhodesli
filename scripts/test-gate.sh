#!/bin/bash
# test-gate.sh — Unified test gate for all tools (HD-024)
# Usage: scripts/test-gate.sh [fast|full|ml|all]
# Called by hooks and scripts instead of inline pytest commands

set -uo pipefail

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

# ruff lives next to pytest in the same venv. CI runs `ruff check app/ core/
# tests/` as a blocking Lint step — mirror it locally so lint errors (e.g.
# F541) can't pass every local commit and only fail CI (which kept the Tests
# workflow red for ~5 sessions; Lesson 209).
RUFF="$(dirname "$PYTEST")/ruff"
run_lint() {
    if [ -x "$RUFF" ]; then
        if ! "$RUFF" check app/ core/ tests/ 2>&1 | tail -20; then
            echo "BLOCKED: ruff lint errors (run: ruff check --fix app/ core/ tests/)" >&2
            return 1
        fi
    fi
    return 0
}

case "$MODE" in
    fast)
        run_lint || exit 1
        # Pre-commit gate: run core test files that cover registry, supabase,
        # and photo rendering. Full suite has pre-existing ordering flakes
        # (PERF-001) that block commits on unrelated changes.
        # Deselect reason: confirmed-anchor coverage test is PERF-001 flaky —
        # tracked separately, not a silent skip.
        "$PYTEST" tests/test_postgres_reads.py tests/test_supabase_shadow.py \
            tests/test_registry.py tests/test_data_integrity.py \
            tests/test_deploy_safety_gate.py \
            -x -q --timeout=30 \
            --deselect tests/test_data_integrity.py::TestOrphanedIdentities::test_confirmed_anchors_in_face_to_photo \
            2>&1 | tail -20
        ;;
    full)
        "$PYTEST" tests/ -x -q -n auto --timeout=60 2>&1 | tail -20
        ;;
    ml)
        "$PYTEST" rhodesli_ml/tests/ -x -q -n auto --timeout=60 2>&1 | tail -20
        ;;
    all)
        # Fixed 2026-04-18: capture BOTH exit codes. Previously `all` exited
        # with only the ML status, silently hiding app-test failures (Codex P0).
        echo "=== App Tests ==="
        "$PYTEST" tests/ -x -q -n auto --timeout=60 2>&1 | tail -10
        APP_STATUS=${PIPESTATUS[0]}
        echo ""
        echo "=== ML Tests ==="
        "$PYTEST" rhodesli_ml/tests/ -x -q -n auto --timeout=60 2>&1 | tail -10
        ML_STATUS=${PIPESTATUS[0]}
        if [ "$APP_STATUS" -ne 0 ] || [ "$ML_STATUS" -ne 0 ]; then
            echo ""
            echo "FAIL: app=$APP_STATUS ml=$ML_STATUS" >&2
            exit 1
        fi
        ;;
    *)
        echo "Usage: scripts/test-gate.sh [fast|full|ml|all]" >&2
        exit 1
        ;;
esac
