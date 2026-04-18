#!/bin/bash
# post-edit-format.sh — Auto-format Python files after Edit/Write
# Registered as PostToolUse hook for Edit|Write
# Inspired by everything-claude-code post-edit hooks (HD-024)

set -uo pipefail

INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin).get('tool_input',{}); print(d.get('file_path',d.get('path','')))" 2>/dev/null || echo "")

# Only format Python files
if echo "$FILE" | grep -qE '\.py$'; then
    # Resolve REPO; bail if not in a git checkout.
    REPO=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
    [ -z "$REPO" ] && exit 0

    # Canonicalize FILE against REPO to prevent formatting arbitrary paths
    # (Codex P1, 2026-04-18).
    CANONICAL=$(realpath -m -- "$FILE" 2>/dev/null || echo "")
    case "$CANONICAL" in
        "$REPO"/*) ;;  # inside repo — allowed
        *) exit 0 ;;    # outside repo — skip
    esac

    # Find ruff in the project venv (handle worktrees)
    RUFF="${REPO}/venv/bin/ruff"
    if [ ! -f "$RUFF" ]; then
        COMMON=$(git rev-parse --git-common-dir 2>/dev/null)
        if [ -n "$COMMON" ] && [ "$COMMON" != ".git" ]; then
            RUFF="$(dirname "$COMMON")/venv/bin/ruff"
        fi
    fi

    if [ -f "$RUFF" ] && [ -f "$CANONICAL" ]; then
        # Auto-format (non-blocking). Log ruff errors to stderr instead of
        # swallowing them silently (Codex P2, 2026-04-18).
        "$RUFF" format "$CANONICAL" 2>&1 >/dev/null | head -5 >&2 || true
        "$RUFF" check --fix "$CANONICAL" 2>&1 >/dev/null | head -5 >&2 || true
    fi
fi

exit 0
