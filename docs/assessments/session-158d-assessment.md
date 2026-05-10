# Session 158d Assessment

**Date**: 2026-05-10
**Mode**: implementation
**Predecessor**: 158c (`docs/assessments/session-158c-assessment.md`)
**Outcome**: PARTIAL — RENAME landed once, rollback executed per safety rule, app 502 persisted at session end

## Shipped

- [x] **Phase 158d-1**: cutover_rename / drop_and_vacuum / apply_v2_views patches
  - `SET LOCAL lock_timeout='30s'` + `statement_timeout='0'` inside `BEGIN` for
    cutover_forward, cutover_rollback, drop_renamed_tables (Codex 158c P1 form)
  - apply_v2_views.py: commit AFTER sanity checks (Codex 158c P1)
  - drop_and_vacuum.vacuum_full: re-raise on first failure (Codex 158c P2),
    write PARTIAL FAILURE banner to forensic report, exit non-zero
  - Commit `1cabf2d5`, dry-run gate verified
- [x] **Phase 158d-2**: RENAME executed (REVERSIBLE state)
  - 4 lock_timeout failures led to discovery of 16 zombie `idle in transaction`
    Supavisor backends from 158b cursor backfill, idle 17–22h
  - `pg_terminate_backend` cleared all 16 → next RENAME succeeded instantly
  - State after: v1 alive 0/3, `_dropped_*_session158` 3/3, v2 3/3
  - Commit `b2a5583e`, doc `docs/feedback/session-158d-cutover-rename.md`
- [x] **Phase 158d-3 (partial)**: Smoke + browser verify
  - `make test-fast`: 4269/4269 pass (one flaky REST-timeout test passed on retry)
  - Production smoke test: 11/11 routes returned 502 with `x-railway-fallback: true`
  - Per prompt rule ("ANY 5xx → ROLLBACK"), executed `--rollback`
  - DB state restored cleanly (verified at 02:37Z)
  - Doc `docs/feedback/session-158d-rollback.md`

## Deferred (correctly, per safety rule)

- **Phase 158d-4 (wait period)** — NOT executed (rollback path took precedence)
- **Phase 158d-5 (DROP + VACUUM FULL)** — NOT executed (irreversible step never
  authorized; rollback restored v1 names so no `_dropped_*` to drop)
- **Phase 158d-6 (post-cutover verification)** — NOT executed (no cutover state
  to verify after rollback)

## Red Flags

- **CRITICAL**: Production app returning 502 with `x-railway-fallback: true` for
  ~10 minutes after rollback. Cause hypothesis: `pg_terminate_backend` of 16
  zombie connections crashed the production app's connection pool (workers
  held dead references to those backends). Railway redeploy should self-heal
  via the pushed commits at 02:32Z. **If app does not recover within 15 min
  of session end, manual Railway dashboard restart required.** DB is safe.
- **HIGH**: 158b's failed cursor backfill left 16 zombie `idle in transaction`
  backends that survived 22h. This is a pattern across 158b/158c/158d — chunked
  cursor scripts that die mid-stream do not clean up server-side. Lesson 184
  (canonical) and Lesson 185 (NEW: `pg_terminate_backend` cascade).
- **MEDIUM**: The 158d FIRST ACTION patch (lock_timeout/statement_timeout SET
  LOCAL) was necessary but NOT sufficient. Required `pg_terminate_backend`
  cleanup as the actual unblocker. The patch is still correct (defends
  against future short-lived contention) but the runbook needs the zombie
  cleanup as a pre-requisite step.

## Next Session Should Verify FIRST

1. **Production health**: `curl https://rhodesli.nolanandrewfox.com/health` →
   must return 200 before doing ANY further DB work. If still 502, check
   Railway dashboard, restart manually if needed.
2. **DB state intact**: `psycopg2.connect(...)`, query
   `information_schema.tables` for `gedcom_*` — must show v1 alive 3/3,
   `_dropped_*_session158` 0/3.
3. **Pooler health**: 3 sequential `SELECT 1` connections via session-mode
   port 5432. If degraded, wait for stability before retrying cutover.
4. **No new zombies**: query `pg_stat_activity` for `state = 'idle in
   transaction' AND state_change < NOW() - INTERVAL '1 hour'`. Terminate
   any found ONLY AFTER the production app is freshly deployed (never on
   a hot pool).

## AI Tool Usage

- **Tool**: None this session — Codex audit deferred to 158e (no new
  irreversible changes shipped that would warrant a fresh audit).
- **Predecessor**: 158c Codex audit (`docs/session_context/session-158c-codex-audit.md`)
  P1/P2 findings ALL addressed in 158d Phase 1 patch.

## Path forward — Session 158e

Required for clean cutover retry:

1. **Pre-flight**: production must be freshly deployed (worker pool fresh).
2. **Maintenance window** (recommended) OR feature-flag the app's gedcom TTL
   cache to skip refresh during cutover.
3. Re-run RENAME → 5-min wait → DROP + VACUUM → verify.
4. Continuation prompt: `docs/prompts/session-158e-prompt.md`.

Do NOT retry RENAME without first ensuring no zombie backends exist AND no
hot connections aliased to terminated backends. The 158d pattern (RENAME +
zombie kill on a hot pool → app cascade) MUST NOT repeat.
