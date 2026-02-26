#!/usr/bin/env bash
# setup-worktree.sh — Set up dependencies for a new worktree or fresh clone.
# Usage: ./scripts/setup-worktree.sh
#
# Steps:
#   1. Creates Python venv if not present
#   2. Activates venv and installs requirements
#   3. Copies .env from main worktree if not present
#   4. Runs quick test verification
#
# See docs/HARNESS_DECISIONS.md HD-019 for context.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== Rhodesli Worktree Setup ==="
echo "Working directory: $REPO_ROOT"
echo ""

# --- 1. Create venv ---
if [[ ! -d venv ]]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    echo "  venv created"
else
    echo "  venv already exists"
fi

# --- 2. Activate and install ---
echo "Activating venv and installing dependencies..."
source venv/bin/activate
pip install -q --upgrade pip
if [[ -f requirements.txt ]]; then
    pip install -q -r requirements.txt
    echo "  requirements.txt installed"
else
    echo "  WARNING: requirements.txt not found"
fi

# --- 3. Copy .env from main worktree ---
if [[ ! -f .env ]]; then
    # Try to find .env in the main worktree (parent of .claude/worktrees/)
    MAIN_WORKTREE="$(git rev-parse --show-toplevel 2>/dev/null || echo "")"
    # If we're in a worktree, the main worktree's .env might be elsewhere
    MAIN_ENV=""
    if [[ -n "$MAIN_WORKTREE" ]]; then
        # Check commondir for the main worktree path
        COMMON_DIR="$(git rev-parse --git-common-dir 2>/dev/null || echo "")"
        if [[ -n "$COMMON_DIR" && "$COMMON_DIR" != ".git" ]]; then
            MAIN_ROOT="$(dirname "$COMMON_DIR")"
            if [[ -f "$MAIN_ROOT/.env" ]]; then
                MAIN_ENV="$MAIN_ROOT/.env"
            fi
        fi
    fi

    if [[ -n "$MAIN_ENV" ]]; then
        echo "Copying .env from main worktree: $MAIN_ENV"
        cp "$MAIN_ENV" .env
        echo "  .env copied"
    else
        echo "  WARNING: No .env found. Copy manually or create from .env.example"
    fi
else
    echo "  .env already exists"
fi

# --- 4. Quick test verification ---
echo ""
echo "Running quick test verification..."
source venv/bin/activate

# Run a small subset to verify setup works
if pytest tests/ -x -q --co 2>/dev/null | tail -1; then
    echo "  App test collection: OK"
else
    echo "  WARNING: App test collection failed — check requirements"
fi

if pytest rhodesli_ml/tests/ -x -q --co 2>/dev/null | tail -1; then
    echo "  ML test collection: OK"
else
    echo "  WARNING: ML test collection failed — check rhodesli_ml dependencies"
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "To run full tests:"
echo "  source venv/bin/activate"
echo "  pytest tests/ -x -q && pytest rhodesli_ml/tests/ -x -q"
