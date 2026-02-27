#!/bin/bash
# Verifies that the current session is NOT running on main
# Called at the start of each track in a parallelized session

CURRENT_BRANCH=$(git branch --show-current)

if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║  ERROR: Track is running on main branch!                    ║"
  echo "║  All tracks MUST run in a worktree.                         ║"
  echo "║                                                             ║"
  echo "║  Fix: git worktree add .claude/worktrees/<name> <branch>   ║"
  echo "╚══════════════════════════════════════════════════════════════╝"
  exit 1
fi

echo "✓ Running on branch: $CURRENT_BRANCH (not main — safe to proceed)"
