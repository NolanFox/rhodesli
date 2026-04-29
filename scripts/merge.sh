#!/bin/bash
set -e
[ $# -eq 0 ] && echo "Usage: ./scripts/merge.sh branch1 [branch2...]" && exit 1

# Find repo root for venv
REPO_ROOT=$(git rev-parse --git-common-dir 2>/dev/null | xargs dirname)
PYTEST="${REPO_ROOT}/venv/bin/pytest"
[ ! -f "$PYTEST" ] && PYTEST="venv/bin/pytest"

# Pre-check: this script MUST run from the primary worktree, not a sub-worktree.
# A sub-worktree cannot checkout `main` because it's checked out in the primary.
# Without this guard, the merges silently land on the wrong branch (Lesson 176).
GIT_COMMON_DIR=$(git rev-parse --git-common-dir 2>/dev/null || echo "")
GIT_DIR=$(git rev-parse --git-dir 2>/dev/null || echo "")
if [ -z "$GIT_COMMON_DIR" ] || [ -z "$GIT_DIR" ]; then
    echo "ERROR: not inside a git repository" >&2
    exit 1
fi
if [ "$GIT_COMMON_DIR" != "$GIT_DIR" ] && [ "$GIT_COMMON_DIR" != ".git" ]; then
    echo "ERROR: scripts/merge.sh must run from the primary worktree (cwd=$(pwd))" >&2
    echo "       The primary worktree is at: $(dirname "$GIT_COMMON_DIR")" >&2
    echo "       Sub-worktrees can't checkout main because it's checked out elsewhere." >&2
    exit 1
fi

git checkout main
git pull origin main 2>/dev/null || true

for BRANCH in "$@"; do
  echo "=== Merging: $BRANCH ==="
  WT=$(git worktree list | grep "$BRANCH" | awk '{print $1}')
  [ -n "$WT" ] && [ "$WT" != "$(pwd)" ] && [ -n "$(git -C "$WT" status --porcelain)" ] && \
    git -C "$WT" add -A && git -C "$WT" commit -m "fix: auto-commit (merge script)"
  git merge "$BRANCH" --no-ff -m "merge: $BRANCH" || { echo "CONFLICT in $BRANCH — fix manually"; exit 1; }
  echo "=== Merged: $BRANCH ==="
done

echo "=== Running tests ==="
$PYTEST tests/ -x -q -n auto --timeout=60

echo "=== Done. Next: git push origin main ==="
