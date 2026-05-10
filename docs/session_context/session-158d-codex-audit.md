# Session 158d — Codex Audit

**Auditor**: Codex CLI v0.130.0 (gpt-5.5, xhigh per `~/.codex/config.toml`)
**Agent type**: Independent (fresh context, no prior session knowledge)
**Scope**: Session 158d script changes — `scripts/session158b_cutover_rename.py`, `scripts/session158b_drop_and_vacuum.py`, `scripts/session158c_apply_v2_views.py` (commit `1cabf2d5` only; docs commits not in audit scope)
**Date**: 2026-05-10
**Invocation**: `codex exec "..." </dev/null` (per `.claude/rules/ai-tool-audit.md`)

## Findings

### P0: none.

### P1: none.

### P2

- **`scripts/session158b_drop_and_vacuum.py:222`** — `vacuum_full()` records completed/failed table timings in a local dict, then re-raises at line 243. The caller's `timings` remains the `{}` initialized at line 287 because the assignment at line 291 never completes. Result: the `PARTIAL FAILURE` report writes an empty `VACUUM FULL timings` block at line 322, and the exception message is only printed, not persisted. Failure-path forensics are not complete.
  - **Fix**: pass a mutable timings dict into `vacuum_full` so partial state is captured by the caller, OR raise a custom exception carrying `timings + failed_table`, OR defer the raise until after the report has the populated dict.
  - **Disposition**: deferred to 158e first irreversible-script change. The Codex finding is correct — when a VACUUM fails partway, the report would currently say `PARTIAL FAILURE` with empty timings. Not a blocker for 158e cutover (DROP+VACUUM only runs after RENAME succeeds, and a VACUUM failure is informational not destructive), but should be fixed before next IRREVERSIBLE run.

### P3

- **`scripts/session158c_apply_v2_views.py:89`** — Sanity checks compare counts using separate READ COMMITTED snapshots: view count vs base distinct count at lines 89–92, and again at lines 103–106. If the v2 base tables are written concurrently, this can false-fail or validate mixed snapshots. Because commit is delayed until line 118, the script also holds the view DDL lock during all count scans.
  - **Fix**: prefer one SQL statement per table that returns both counts, OR `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ` before applying/sanity-checking.
  - **Disposition**: deferred to BACKLOG. The current cutover sequence freezes v2 writes during 158d/158e (no backfill running concurrently), so READ COMMITTED is sufficient for the Day 3 cutover window. Worth fixing before any future v2 schema work.

## Notes

- `SET LOCAL` placement: **no finding**. In the rename/drop helpers, `SET LOCAL lock_timeout` and `statement_timeout` after `BEGIN` is correct for PostgreSQL transaction scope. With psycopg2 default transactions, earlier verification `SELECT`s may already have opened a transaction before the helper `BEGIN`, but `SET LOCAL` still applies to the active transaction and the helper `COMMIT` closes it.
- 158d Codex 158c P1/P2 fixes (committed in `1cabf2d5`) all verified by this audit — no regressions found.

## Value assessment

**MODERATE** — Codex caught a real forensics gap (P2 vacuum timings) that I had not explicitly verified. The P3 isolation finding is technically correct but practically deferrable. Not the most impactful audit, but the verification of `SET LOCAL` placement provides confidence in the most safety-critical change in this session.

## Tokens used

45,002
