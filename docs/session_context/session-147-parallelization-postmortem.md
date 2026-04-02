# Session 147 Parallelization Postmortem

**Date:** 2026-03-31
**Session:** 147
**Scope:** 4 parallel worktree agents (Tracks A-D)

## What Happened

### Failure 1: Git lock contention on worktree creation
When 3 worktree agents launched simultaneously, the 3rd agent received:
```
error: could not lock config file .git/config: File exists
```
Track C failed completely and had to be relaunched manually.

### Failure 2: Agents did not commit their work
All 4 worktree agents completed code changes and tests but left changes uncommitted. The orchestrator had to manually run `git add && git commit` in each worktree directory. This wasted ~10 minutes and created risk of lost work if the worktrees were cleaned up.

### Failure 3: Uncommitted changes leaked to main
Track C's uncommitted changes appeared as modifications in the main working directory. Required `git checkout --` to clean main before merging. Root cause: worktrees share the git object database and uncommitted state can bleed through.

### Failure 4: Worktree branches created from stale base
All worktree branches were created from the base commit (pre-Session 147), not from current main HEAD. This meant `git diff main..branch` showed session docs as "deleted" rather than showing only the actual code changes. Merges succeeded because changes were to disjoint files, but the diff review was misleading.

## Root Causes

1. **Git lock contention**: `git worktree add` acquires a lock on `.git/config`. Multiple simultaneous calls compete for this lock. Git does not retry on lock failure.

2. **Missing commit enforcement**: Subagent prompts included "commit with conventional commit" but agents either couldn't commit or chose not to. No verification step checked for clean worktree state before the agent returned.

3. **Stale branch base**: Worktrees were created from the commit at session start, not from the latest main HEAD after session docs were committed.

## Fixes Applied

1. **Lessons 166-167** added to `tasks/lessons/harness-lessons.md` with Mistake/Rule/Prevention.
2. **Worktree enforcement rule** updated (`.claude/rules/worktree-enforcement.md`) with sections on commit discipline, lock contention, and branch base.
3. **Lessons index** updated in `tasks/lessons.md`.

## Remaining Risks

1. **No mechanical enforcement of agent commits**: The rule is still behavioral. A future improvement could add a post-agent hook that checks `git status --porcelain` and blocks merge if non-empty.

2. **merge.sh does not verify worktree cleanliness**: The canonical merge script (`scripts/merge.sh`) checks for uncommitted files but only in the main directory, not in worktree directories before merge.

3. **No retry logic for git lock errors**: Agents that hit lock contention fail immediately. A wrapper script with exponential backoff (e.g., 100ms, 200ms, 400ms) would handle transient lock contention gracefully.

## Recommended Improvements (Future Session)

- **Pre-dispatch worktree creation**: Orchestrator creates all worktrees sequentially, then dispatches agents to existing worktrees (eliminates lock contention entirely).
- **Post-agent verification**: Orchestrator runs `git -C <worktree> status --porcelain` after each agent returns; if non-empty, auto-commits or raises error.
- **merge.sh enhancement**: Add `--verify-worktrees` flag that checks all worktree branches for clean state before merging.

## Lessons
- Lesson 166: Worktree agents must commit before returning
- Lesson 167: Git lock contention when launching 3+ worktree agents simultaneously
- See also: Lesson 87 (subagent commit discipline, Session 69 — same pattern)
