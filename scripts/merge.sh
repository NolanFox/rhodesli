#!/bin/bash
set -e
[ $# -eq 0 ] && echo "Usage: ./scripts/merge.sh branch1 [branch2...]" && exit 1

# Find repo root for venv
REPO_ROOT=$(git rev-parse --git-common-dir 2>/dev/null | xargs dirname)
PYTEST="${REPO_ROOT}/venv/bin/pytest"
[ ! -f "$PYTEST" ] && PYTEST="venv/bin/pytest"

git checkout main && git pull origin main 2>/dev/null || true

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
