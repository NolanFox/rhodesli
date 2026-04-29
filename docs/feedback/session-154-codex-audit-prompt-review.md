**Auditor**: Codex CLI v0.125.0 (gpt-5.5, xhigh)
**Agent type**: Independent (fresh context, no prior session knowledge)
**Scope**: Pre-execution review of `docs/prompts/session-154-prompt.md` — Track E destructive-action gating, snapshot strategy, parallelization, closeout drift risk
**Date**: 2026-04-28 (run during session-153b → session-154 handoff)

## Summary

- P0: 0 findings
- P1: 2 findings — destructive-action authorization is gameable; E3 retention code introduces ungated recurring DELETE
- P2: 3 findings — snapshot under-specified for recovery; parallel file-ownership conflicts; closeout missing clean-worktree guard
- P3: 1 finding — SESSION_HISTORY verification gate too weak

## Findings

### P1 — Destructive authorization gate is not independent enough

`docs/prompts/session-154-prompt.md:212` (Phase D1 gate language) and lines 271-274 (Phase E2 gates) only require a one-line authorization file. The executing agent could create that file itself, so DELETE/VACUUM FULL could proceed without a fresh user approval after seeing the E1 plan.

**Required fix**: Require a post-E1 user message approving the exact plan commit, tables, DELETE predicates, snapshot paths, and VACUUM list; paste that verbatim into the auth doc. Remove "or similar" and "approved ahead of time" wording.

### P1 — E3 introduces recurring DELETE behavior outside E2's destructive gates

Lines 286-305 (Phase E3 retention policy) ask for code that archives then DELETEs weekly, but the strong gates are scoped to E2 at lines 269-284.

**Required fix**: Retention sweeps must be dry-run by default, `--execute` gated, per-table snapshotting, count/checksum verification, and no scheduler enablement without explicit user approval of OD-013.

### P2 — Snapshot strategy is directionally right but under-specified for recovery

Line 274 says every step snapshots first, and line 284 says revert from snapshot, but it does not require primary keys, row counts, checksum/re-read validation, or deleting by the snapshotted PK set.

**Required fix**: Snapshots must include primary keys, row counts, and checksums. Validate snapshot before mutation. Generate restore commands BEFORE VACUUM FULL. Use the snapshotted PK set for deletes (not predicates that could expand).

### P2 — Parallel file ownership has two missed conflict/registration risks

E3's `/api/admin/db-size` route at line 296 likely needs an import in `app/main.py:7953`, but Track E scope (line 313) only names a new route file. Also line 310 says E owns `*.json`, which collides ambiguously with Track A's shadow eval JSON at line 147.

**Required fix**: Clarify E owns only `session-154-supabase-*.json` (not all `*.json`). Coordinate any `app/main.py` import at merge.

### P2 — Closeout still lacks a clean-worktree guard

D2 checks pushed commits via lines 340-343, but `git log origin/main..HEAD` does not catch uncommitted files.

**Required fix**: Add `git status --short` must be empty AS A SEPARATE GATE, plus a final `bash scripts/harness-check.sh` after doc edits.

### P3 — SESSION_HISTORY order follows Lesson 77, but verification is weak

D2 step 5 correctly says backfill destination before trimming source. The success gate only greps "Session 143" at line 364.

**Required fix**: Require all sessions 143-153b present in SESSION_HISTORY before any ROADMAP trim.

## Disposition

P1s and P2s addressed inline in `docs/prompts/session-154-prompt.md` (Session 154 prep). P3 addressed in the same edit.

## Value assessment

**STRONG**. The destructive-action authorization weakness (P1 #1) is exactly the failure mode that produced 11 data integrity incidents in this codebase (Lessons 144-156, 168). Codex's catch is non-obvious — at first read the auth-file requirement looks robust, but it's gameable by the agent that's also doing the executing. Worth the audit time even if the rest of the findings were trivial.

## Would we have found this ourselves?

The P1s: probably not before execution. The P2s: maybe, after the fact in a postmortem. The P3: likely.
