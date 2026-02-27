#!/bin/bash
# Safely merges multiple worktree branches into main
# Usage: ./scripts/merge_tracks.sh track-c track-a track-b
# (order matters — merge docs-first, then independent features, then shared-dependency tracks last)

set -e

echo "=== Merge Gatekeeper ==="
git checkout main
git pull origin main

for TRACK in "$@"; do
  BRANCH="session-*/${TRACK}*"
  ACTUAL_BRANCH=$(git branch --list "$BRANCH" | head -1 | tr -d ' *')

  if [ -z "$ACTUAL_BRANCH" ]; then
    echo "WARNING: No branch matching pattern '$BRANCH' found. Skipping."
    continue
  fi

  echo ""
  echo "--- Merging: $ACTUAL_BRANCH ---"

  # Check for uncommitted work in worktree
  WORKTREE_PATH=$(git worktree list | grep "$ACTUAL_BRANCH" | awk '{print $1}')
  if [ -n "$WORKTREE_PATH" ]; then
    UNCOMMITTED=$(git -C "$WORKTREE_PATH" status --porcelain)
    if [ -n "$UNCOMMITTED" ]; then
      echo "WARNING: Uncommitted files in $WORKTREE_PATH:"
      echo "$UNCOMMITTED"
      echo "Auto-committing..."
      git -C "$WORKTREE_PATH" add -A
      git -C "$WORKTREE_PATH" commit -m "fix: auto-commit uncommitted files (merge gatekeeper)"
    fi
  fi

  # Merge
  git merge "$ACTUAL_BRANCH" --no-ff -m "merge: $ACTUAL_BRANCH into main"

  # Test
  echo "Running tests after merge..."
  source venv/bin/activate && pytest tests/ -x -q
  if [ $? -ne 0 ]; then
    echo "TESTS FAILED after merging $ACTUAL_BRANCH. Fix before continuing."
    exit 1
  fi

  echo "✓ $ACTUAL_BRANCH merged and tests pass"
done

echo ""
echo "=== All tracks merged. Run final verification: ==="
echo "  pytest tests/ -x -q"
echo "  git push origin main"
