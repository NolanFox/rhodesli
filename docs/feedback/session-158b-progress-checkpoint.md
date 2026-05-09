# Session 158b Progress Checkpoint

**Date**: 2026-05-09 (UTC).
**Mode**: implementation.
**Stop pressure**: pooler health degraded today (0/3 PASS on probe) and REST API throughput degraded under script load.

## Phases completed

| Phase | Status | Commit |
|---|---|---|
| 158b-0 carry verification + A.5 hardening verify | ✅ | `5799700a` (setup) |
| 158b-0B pooler health probe | ✅ FAIL (0/3 PASS — pooler dead) | same |
| 158b-2 chunked-write backfill — script written | ✅ | `5799700a` |
| 158b-2 chunked-write backfill — DRY-RUN | ✅ partial (chunks 1-3) | n/a |
| 158b-2 chunked-write backfill — EXECUTE | ⏳ in progress | n/a (running) |
| 158b-4.1 bulk-loader rewire to prefer v2 view | ✅ code only | `f2a857b8` |

## Phase 158b-2 EXECUTE timing observed

| Chunk | Rows | Read time | Upsert time | NEW | UPDATE | Notes |
|---|---|---|---|---|---|---|
| 1 (v1) | 21,944 | 51.5s | 166.6s | 21,174 | 770 | Healthy |
| 2 (v2) | 21,944 | 48.8s | 189.0s | 0 | 21,944 | All hashes match v1 |
| 3 (v3) | 21,944 | 61.5s | **1875.3s** | 0 | 21,944 | RemoteProtocolError retry; pooler degraded |
| 4 (v4) | 21,944 | 121.2s | in progress | TBD | TBD | ReadTimeout retry |
| 5-9 + NULL | TBD | TBD | TBD | TBD | TBD | Pending |

**Per-chunk wall-clock observed**: 220s → 240s → 1937s → ??? .
**Worst-case total**: 10 × 30 min = 5 hours (if pooler stays this slow).
**Best-case total**: 10 × 4 min = 40 min (if chunks 4-10 stabilize).

## Critical observations

1. **All v_num=2..N chunks show 0 NEW** so far (after chunk 1's 21,174 NEW). This means GEDCOM individuals haven't changed across versions for the rows tested so far. Albert Fox's 2-state history (v1-7 hash `fd1f05bd`, v9 hash `1d77bf67`) WILL show up — but those 2 distinct states are within the 21,174 + (TBD chunk 9) hashes, not in chunks 2-8 deltas.

2. **Estimated final v2 row count**: ~43K based on 196,645 v1 rows mapping to 43,172 unique payload_hashes. Within the 22K-100K STOP gate per NOTE-2.

3. **Pooler psycopg2 connections fail immediately** (SSL closed). This blocks:
   - View migration (need psycopg2)
   - Phase 158b-4.2 RENAME (DDL needs psycopg2)
   - Phase 158b-6 DROP + VACUUM FULL (DDL + non-transactional VACUUM needs psycopg2)
   - **Workaround**: apply via Supabase Studio (web UI) OR retry psycopg2 if pooler recovers

4. **REST API** still works for reads + upserts but with intermittent timeouts. Backfill continues with retries.

## Current decision tree

- If backfill **completes within 3h** AND **pooler recovers** for psycopg2 DDL: continue Phase 158b-3 → 158b-7 in this session
- If backfill **completes** but **pooler still dead**: defer Phase 158b-4 to 158c (need psycopg2 for cutover)
- If backfill **doesn't complete** (script hangs >1h between chunks): kill, write resume capability, defer to 158c

## Albert Fox 2-state verification (post-backfill gate)

```python
# Expected after Phase 158-2 EXECUTE completes:
from app.gedcom_dual_read import get_individual_history
hist = get_individual_history('@I132123840707@')
# Expected: 2 states
#   v_first=1, v_last=7, hash=fd1f05bd... (steady state v1-v7)
#   v_first=9, v_last=9, hash=1d77bf67... (changed in v9)
```

## What 158c (or 158b later) needs to do

1. Re-verify backfill completion
2. Apply view migration (when pooler recovers)
3. Phase 158b-4.2 RENAME via psycopg2
4. Phase 158b-5 wait period
5. Phase 158b-6 DROP + VACUUM FULL via psycopg2
6. Phase 158b-7 post-cutover verification
7. Phase 158b-8 GEDCOM upload UAT (Track E) — likely defer to 159
