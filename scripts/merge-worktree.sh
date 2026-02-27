#!/usr/bin/env bash
# merge-worktree.sh — Merge a subagent worktree branch back to main with commit enforcement.
#
# Usage: ./scripts/merge-worktree.sh <worktree-path> [--dry-run]
#
# Pre-merge verification:
#   1. Check for uncommitted files in the worktree (auto-commit if found)
#   2. Run tests in the worktree
#   3. Merge to current branch
#   4. Run tests after merge
#
# The commit enforcement gate (Step 1) prevents the recurring issue where
# subagents leave uncommitted files that are lost during merge (Lesson 87).
#
# See: docs/HARNESS_DECISIONS.md HD-021
# See: tasks/lessons/harness-lessons.md Lesson 87

set -euo pipefail

# --- Argument Parsing ---

WORKTREE_PATH="${1:?Usage: $0 <worktree-path> [--dry-run]}"
DRY_RUN=false
if [[ "${2:-}" == "--dry-run" ]]; then
    DRY_RUN=true
fi

if [[ ! -d "$WORKTREE_PATH" ]]; then
    echo "ERROR: Worktree path does not exist: $WORKTREE_PATH"
    exit 1
fi

# Resolve absolute path
WORKTREE_PATH="$(cd "$WORKTREE_PATH" && pwd)"

# Get the branch name from the worktree
WORKTREE_BRANCH=$(git -C "$WORKTREE_PATH" rev-parse --abbrev-ref HEAD 2>/dev/null)
if [[ -z "$WORKTREE_BRANCH" ]]; then
    echo "ERROR: Could not determine branch for worktree: $WORKTREE_PATH"
    exit 1
fi

echo "=== Merge Worktree ==="
echo "Worktree: $WORKTREE_PATH"
echo "Branch: $WORKTREE_BRANCH"
echo "Dry run: $DRY_RUN"
echo ""

# ============================================================
# STEP 1: Subagent Commit Enforcement Gate (Lesson 87, HD-021)
# ============================================================

echo "--- Step 1: Checking for uncommitted files ---"

UNCOMMITTED=$(git -C "$WORKTREE_PATH" status --porcelain)
if [ -n "$UNCOMMITTED" ]; then
    echo "WARNING: Subagent left uncommitted files:"
    echo "$UNCOMMITTED"
    echo ""

    if [[ "$DRY_RUN" == true ]]; then
        echo "[DRY RUN] Would auto-commit these files."
    else
        echo "Auto-committing uncommitted files..."
        git -C "$WORKTREE_PATH" add -A
        git -C "$WORKTREE_PATH" commit -m "fix: auto-commit uncommitted subagent files (enforcement gate)"
        echo "Auto-committed. Review these files in the merge."
    fi
else
    echo "  Working tree is clean. No uncommitted files."
fi

# ============================================================
# STEP 2: Run tests in the worktree
# ============================================================

echo ""
echo "--- Step 2: Running tests in worktree ---"

if [[ "$DRY_RUN" == true ]]; then
    echo "[DRY RUN] Would run: pytest tests/ -x -q in $WORKTREE_PATH"
else
    if [[ -f "$WORKTREE_PATH/venv/bin/activate" ]]; then
        echo "Running tests..."
        (
            cd "$WORKTREE_PATH"
            source venv/bin/activate
            pytest tests/ -x -q --tb=short 2>&1 | tail -5
        )
        WORKTREE_TEST_EXIT=$?
        if [[ $WORKTREE_TEST_EXIT -ne 0 ]]; then
            echo "ERROR: Tests failed in worktree. Fix before merging."
            exit 1
        fi
        echo "  Tests passed in worktree."
    else
        echo "  WARNING: No venv in worktree — skipping tests (verify manually)"
    fi
fi

# ============================================================
# STEP 3: Merge to current branch
# ============================================================

echo ""
echo "--- Step 3: Merging $WORKTREE_BRANCH ---"

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "  Current branch: $CURRENT_BRANCH"
echo "  Merging from: $WORKTREE_BRANCH"

if [[ "$DRY_RUN" == true ]]; then
    echo "[DRY RUN] Would run: git merge $WORKTREE_BRANCH --no-ff -m \"merge: $WORKTREE_BRANCH\""
    # Show what would be merged
    MERGE_BASE=$(git merge-base "$CURRENT_BRANCH" "$WORKTREE_BRANCH" 2>/dev/null || echo "")
    if [[ -n "$MERGE_BASE" ]]; then
        echo ""
        echo "Commits to merge:"
        git log --oneline "$MERGE_BASE".."$WORKTREE_BRANCH" 2>/dev/null || echo "  (could not determine)"
        echo ""
        echo "Files changed:"
        git diff --stat "$MERGE_BASE".."$WORKTREE_BRANCH" 2>/dev/null || echo "  (could not determine)"
    fi
else
    if git merge "$WORKTREE_BRANCH" --no-ff -m "merge: $WORKTREE_BRANCH"; then
        echo "  Merge successful."
    else
        echo "ERROR: Merge failed (conflicts). Resolve manually:"
        echo "  git status"
        echo "  # Fix conflicts, then:"
        echo "  git add -A && git commit"
        exit 1
    fi
fi

# ============================================================
# STEP 4: Run tests after merge
# ============================================================

echo ""
echo "--- Step 4: Running tests after merge ---"

if [[ "$DRY_RUN" == true ]]; then
    echo "[DRY RUN] Would run post-merge tests."
else
    REPO_ROOT="$(git rev-parse --show-toplevel)"
    if [[ -f "$REPO_ROOT/venv/bin/activate" ]]; then
        echo "Running tests on merged result..."
        (
            cd "$REPO_ROOT"
            source venv/bin/activate
            pytest tests/ -x -q --tb=short 2>&1 | tail -5
        )
        POST_MERGE_EXIT=$?
        if [[ $POST_MERGE_EXIT -ne 0 ]]; then
            echo ""
            echo "ERROR: Tests failed after merge! Consider reverting:"
            echo "  git reset --hard HEAD~1"
            exit 1
        fi
        echo "  Post-merge tests passed."
    else
        echo "  WARNING: No venv — skipping post-merge tests"
    fi
fi

echo ""
echo "=== Merge complete: $WORKTREE_BRANCH ==="
