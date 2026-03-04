#!/bin/bash
# post-edit-format.sh — Auto-format Python files after Edit/Write
# Registered as PostToolUse hook for Edit|Write
# Inspired by everything-claude-code post-edit hooks (HD-024)

INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin).get('tool_input',{}); print(d.get('file_path',d.get('path','')))" 2>/dev/null)

# Only format Python files
if echo "$FILE" | grep -qE '\.py$'; then
    # Find ruff in the project venv (handle worktrees)
    REPO=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
    RUFF="${REPO}/venv/bin/ruff"
    if [ ! -f "$RUFF" ]; then
        COMMON=$(git rev-parse --git-common-dir 2>/dev/null)
        if [ -n "$COMMON" ] && [ "$COMMON" != ".git" ]; then
            RUFF="$(dirname "$COMMON")/venv/bin/ruff"
        fi
    fi

    if [ -f "$RUFF" ] && [ -f "$FILE" ]; then
        # Auto-format (non-blocking, always exit 0)
        "$RUFF" format "$FILE" 2>/dev/null
        "$RUFF" check --fix "$FILE" 2>/dev/null
    fi
fi

exit 0
