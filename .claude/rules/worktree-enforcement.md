# Worktree Enforcement

Triggers: At the start of any parallelized session track.

## Rule:
Parallel tracks MUST use worktrees (not work directly on main).
The Claude Code PreToolUse hook in `.claude/settings.json` blocks
commits to main when `.claude/parallel_session_active` exists.

## For merging:
After all tracks complete, use the canonical merge script:
```bash
./scripts/merge.sh branch1 [branch2...]
```

This handles: uncommitted file detection, ordered merging, test gates.

## Commit discipline (Lessons 87, 166):
Every worktree subagent MUST commit all changes before returning.
The orchestrator MUST verify each worktree is clean (`git status --porcelain`)
before proceeding to merge. Uncommitted worktree changes can leak to the
main working directory.

## Lock contention (Lesson 167):
Never launch 3+ `git worktree add` commands simultaneously — git lock
contention will cause failures. Preferred: create all worktree branches
sequentially in the orchestrator BEFORE dispatching parallel agents.

## Worktree base commit:
Always create worktree branches from current `main` HEAD, not an older
commit. Branches from stale bases cause `git diff main..branch` to show
unrelated deletions and complicate merge review.

## Why this exists:
Session 71 observed Track A running directly on main instead of a worktree.
Session 147: lock contention, uncommitted agents, file leaks to main.
Behavioral instructions ("use worktrees") are routinely ignored.
Mechanical enforcement (hooks + scripts that check and fail) is the only reliable pattern.
See: HD-021 (worktree enforcement), AD-171 (worktree enforcement)
