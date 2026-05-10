# Session 158d Phase 158d-3 — Rollback Triggered, App 502 Persists

**Date**: 2026-05-10T02:30:44Z (rollback) → 02:40:13Z (last 502 confirmed)
**Status**: Rollback successful at DB layer; production app 502 persists ~10 min after.

## What happened

1. **02:23Z** — RENAME succeeded after 5 attempts (4 failed at lock_timeout). Path
   to success: 16 zombie `idle in transaction` Supavisor backends from 158b's
   failed cursor backfill were terminated via `pg_terminate_backend`. Once those
   AccessShareLocks released, RENAME landed instantly. See
   `docs/feedback/session-158d-cutover-rename.md`.

2. **02:23-02:30Z** — Smoke / browser verify phase. `make test-fast` passed
   (4269/4269; one transient REST-timeout retest). Production smoke test
   returned 502 on ALL 11 routes with `x-railway-fallback: true`.

3. **02:30:44Z** — Per the prompt's hard rule ("ANY 5xx → ROLLBACK and end
   session"), executed `python scripts/session158b_cutover_rename.py --rollback`.
   First two attempts hit pooler `ECHECKOUTTIMEOUT` / `EDBHANDLEREXITED` (pool
   was thrashing). Third attempt succeeded. State restored:
   - v1 alive: `['gedcom_individuals', 'gedcom_families', 'gedcom_change_log']`
   - `_dropped_*_session158`: empty
   - v2 alive: 3/3 unchanged
   - `current_gedcom_individuals` view recreated

4. **02:30-02:40Z** — Production health checked every 15-20s for ~10 minutes.
   Every probe: `code=502` with `x-railway-fallback: true`. Pushed both 158d
   commits to main during this window; redeploy should have triggered.

5. DB state verified directly via pooler at 02:37Z: 16 gedcom-* tables present,
   v1 alive, no `_dropped_*` left over. Rollback is complete at the DB layer.

## Hypothesis on why production stayed 502

The `pg_terminate_backend` of 16 connections was the likely cascade trigger:

- Pre-cutover, the production app held some of those zombie connections in its
  effective working set (the connections were `idle in transaction` for ~22 hours
  — likely the production app's own old workers from 158b execution time).
- When we killed the backends, the production app's connection-pool slots
  pointed at terminated server-side connections. Subsequent queries got
  `connection has been terminated` errors.
- The app's startup or health-check code path may not have re-acquired
  connections cleanly — workers crashed, were restarted by Railway, repeated
  the same cycle, eventually Railway gave up and showed `x-railway-fallback`.

The rollback restored DB schema but did NOT restore the production app worker
state. A clean Railway deploy (which should have been triggered by the
`git push` at 02:32Z) is the recovery path. By 02:40Z it had not yet landed
(or the build is still running). Either way, the app must come up clean once
Railway completes the redeploy — DB is healthy.

## What was NOT executed (correctly)

- **DROP TABLE _dropped_gedcom_*_session158** — never executed (rollback restored
  the original v1 names, so there is nothing to drop)
- **VACUUM FULL** — never executed
- **DB size delta** — unchanged from 158c close (~2,564 MB)

The `--execute` path of `scripts/session158b_drop_and_vacuum.py` was NOT run.

## Lessons (candidates)

### Lesson 184 (carried from 158d cutover doc): zombie idle-in-transaction backends

Long-lived `idle in transaction` Supavisor backends from failed cursor scripts
can survive client disconnects indefinitely. Pre-DDL gate must check
`pg_stat_activity` for old idle-in-transaction sessions.

### Lesson 185 (NEW): `pg_terminate_backend` on zombies cascades into app pool

Terminating backends that the production app's pool holds (or holds dead
references to) crashes worker processes when they next try to use those slots.
After termination:
- App workers see `connection has been terminated` errors
- Workers crash, Railway restarts them, they re-fail the same way
- Eventually the runtime hits a max-restart threshold and goes 502

**Mitigation for Session 158e**:
1. Before `pg_terminate_backend`, **redeploy the production app** to give it
   a fresh pool. The zombies are leftover from old worker generations — a
   fresh deploy on a quiet pool will shed them naturally.
2. OR: declare a brief maintenance window. Take production offline (Railway
   service stop), run `pg_terminate_backend` + RENAME + verify, then
   service start.
3. Crucially, do NOT `pg_terminate_backend` connections WHILE the production
   app is hot. The app's own connection pool entries aliased to those backends
   become invalid.

## Path forward — Session 158e

Required for clean cutover retry:

1. **Pre-flight**: Verify production is healthy AND has been freshly deployed
   within the last 15 minutes (so its connection pool is not full of zombies).
2. **Maintenance window** (recommended): briefly take Railway service offline
   for ~5 min, do RENAME with fresh pool, bring back online.
3. **Or app-coordinated path**: short-circuit the app's TTL caches to NOT
   query gedcom_individuals during the cutover window. Could be a feature
   flag or a temporary route disable.
4. Re-run RENAME → wait → DROP + VACUUM → verify.

## Production check at session end

App returning 502 from Railway edge with `x-railway-fallback: true` as of
02:40:13Z. Latest 2 commits (`1cabf2d5`, `b2a5583e`) pushed to main at ~02:32Z
should have triggered a redeploy. If Railway redeploy completes successfully,
production should self-heal (DB is in good state). If redeploy also crashes,
manual intervention via Railway dashboard required.
