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

## Why this exists:
Session 71 observed Track A running directly on main instead of a worktree.
Behavioral instructions ("use worktrees") are routinely ignored.
Mechanical enforcement (hooks + scripts that check and fail) is the only reliable pattern.
See: HD-021 (worktree enforcement), AD-171 (worktree enforcement)
