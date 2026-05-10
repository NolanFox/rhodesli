# Session 158d Phase 158d-2 — Cutover RENAME (REVERSIBLE)

**Date**: 2026-05-10T02:23:13Z
**Status**: COMPLETE — v1 → _dropped_*_session158
**Reversible**: yes via `python scripts/session158b_cutover_rename.py --rollback` (until DROP in 158d-5)

## Outcome

Before:
- v1 alive: `['gedcom_individuals', 'gedcom_families', 'gedcom_change_log']`
- _dropped_*_session158 alive: `[]`
- v2 alive: `['gedcom_individuals_v2', 'gedcom_families_v2', 'gedcom_change_manifest']`

After:
- v1 alive: `[]`
- _dropped_*_session158 alive: `['_dropped_gedcom_individuals_session158', '_dropped_gedcom_families_session158', '_dropped_gedcom_change_log_session158']`
- v2 alive: `['gedcom_individuals_v2', 'gedcom_families_v2', 'gedcom_change_manifest']`

## Path to success: zombie backend cleanup

158c hit `statement_timeout` after 2 min on the first ALTER TABLE; 158d's
`SET LOCAL lock_timeout='30s' / statement_timeout='0'` patch alone was NOT
sufficient — 4 EXECUTE attempts all failed at `lock_timeout`. Diagnosis via
`pg_stat_activity` revealed the real blocker:

**16 zombie `idle in transaction` Supavisor backends from Session 158b's
failed cursor-based historical backfill**, idle for 17–22 hours, all
holding `AccessShareLock` on `gedcom_individuals`. The chunked-write
backfill in 158b that died mid-stream left these cursors open:

```
backfill_gedcom_individuals_v2_4cfd51e3 (idle 79,721s ≈ 22h)
backfill_gedcom_individuals_v2_494861ce (idle 79,134s ≈ 22h)
+ 14 SELECT * FROM gedcom_individuals WHERE version_id = '...' (idle 17–22h each)
```

These were not blocked by `lock_timeout=30s` because they're stable holders
— each held lock continuously, never releasing it.

Cleanup: `pg_terminate_backend(pid)` on all 16 — 16/16 returned `True`. With
the locks freed, the next `ALTER TABLE RENAME` succeeded immediately.

## Lesson candidate (Lesson 184)

**Long-lived `idle in transaction` Supavisor backends from failed cursor
scripts can survive client disconnects indefinitely.** Before any
DDL session that needs `AccessExclusiveLock`, check
`pg_stat_activity` for orphan transactions older than 1 hour. If found,
`pg_terminate_backend` them — the cursor backfill pattern from Lesson 183
(chunked-write) is fundamentally vulnerable to leaving zombies when the
client side dies. Future chunked scripts should set
`SET idle_in_transaction_session_timeout = '5min'` at session start.

## App impact

The legacy `current_gedcom_individuals` view was dropped as part of the
cutover. Code paths that read v1 GEDCOM tables now hit PGRST205 errors,
which `app/gedcom_dual_read.py` and `app/relationship_routes.py` v2-first
fallback chains handle by reading from `current_gedcom_individuals_v2` /
`current_gedcom_families_v2` instead.

## Next phases

- 158d-3: smoke + browser verify
- 158d-4: 5-min wait
- 158d-5: USER GATE → DROP + VACUUM FULL (irreversible)
- 158d-6: post-cutover verification
- 158d-7: closeout
