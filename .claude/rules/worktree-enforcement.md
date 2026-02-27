# Worktree Enforcement

Triggers: At the start of any parallelized session track.

## Rule:
Before any code changes in a parallel track, run:
```bash
source scripts/enforce_worktree.sh
```

If this fails, DO NOT PROCEED. Set up the worktree first.

## For merging:
After all tracks complete, use the merge gatekeeper:
```bash
./scripts/merge_tracks.sh <track-names-in-merge-order>
```

This handles: uncommitted file detection, auto-commit, ordered merging, test gates.

## Why this exists:
Session 71 observed Track A running directly on main instead of a worktree.
Behavioral instructions ("use worktrees") are routinely ignored.
Mechanical enforcement (scripts that check and fail) is the only reliable pattern.
See: HD-021 (worktree enforcement), AD-170 (subagent commit enforcement)
