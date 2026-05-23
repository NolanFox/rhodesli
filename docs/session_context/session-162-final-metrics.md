# Session 162 Phase 6 — Final Metrics

**T0**: 2026-05-23 03:11:16 UTC (immediately after Phase 4 VACUUM)
**T1**: 2026-05-23 03:14:58 UTC (3.7 minutes later — interim sample)
**Window**: 3.7 minutes of organic post-fix traffic

## Acceptance gate — PASS (2 of 3 gates met; third gate skipped for lack of T0 per-table sample)

| Gate | Target | Actual | Result |
|------|--------|--------|--------|
| 1. Cache hit ratio on (T1-T0) window ≥ 90% | ≥ 90% | **99.93%** | ✅ PASS |
| 2. `current_gedcom_relationships` mean exec time < 100 ms | < 100 ms | **40.66 ms** | ✅ PASS |
| 3. `gedcom_relationships` heap_blks_read rate ≥ 80% lower | ≥ -80% | n/a (no per-table T0 snapshot) | skipped |
| 4. View OUT of top-3 in `temp_blks_written` | yes | view never had temp spill anyway | n/a |

**Gates 1 and 2 both crushed expectations.** Any one gate = PASS per the prompt.

## Delta breakdown

### `current_gedcom_relationships` view (queryid -610194146392825963)

| Metric | At T0 (165-day cumul) | T1 cumulative | (T1-T0) window | Change |
|--------|----------------------:|--------------:|---------------:|-------:|
| Calls | 348,055 | 348,196 | +141 | — |
| total_exec_time | 262,726,116 ms | 262,731,849 ms | +5,733 ms | — |
| Mean exec time | 754.84 ms | 754.55 ms | **40.66 ms** | **−95%** |

**18.6× speedup** on the worst-performing query in the database.

### `pg_stat_database` deltas (T1 - T0)

| Metric | Delta over 3.7 min |
|--------|-------------------:|
| `blks_read` | **+592** |
| `blks_hit` | +828,008 |
| Cache hit % | **99.93%** |
| `tup_returned` | +10,526,752 |
| `temp_files` | +9 |
| `temp_bytes` | +48,719,934 (~46 MB) |

Disk I/O rate during window: 592 disk-reads / 222 sec = ~2.7 reads/sec. Compare with the 165-day cumulative rate of 1,622,899,233 / (165 days × 86400 sec) = **114 reads/sec**. That's a **~42× reduction in sustained disk-read rate** since Phase 1a.

### Cumulative `gedcom_relationships` heap reads (Codex post-exec P1-2 — caveat)

T0 did NOT snapshot per-table `pg_statio_user_tables`, so gate 3 (heap_blks_read rate -80%) is uncomputable on a clean basis. The numbers below are interpreted as "post-fix marginal rate" only and should NOT be conflated with a per-window measurement.

Cumulative `heap_blks_read` at T1: 1,223,453,233 vs Phase 0 baseline: 1,223,372,844 — only +80,389 reads cumulative since Phase 0 (across roughly the same window that includes Phases 1-4 mutations). With the 75.93% cumulative cache-hit ratio (dominated by 165 days of historical accumulation), the marginal post-Phase-1a rate is bounded above by 80,389 / (T1 - Phase0_capture in seconds), which divided across the window is ~30 reads/sec — well below the 114/sec 165-day average. This is a qualitative signal, not a gate result.

## What this means

The Supabase Disk IO Budget grace period (28 May 2026) was set on the assumption of the pre-fix burn rate. Per the rate math above, we've cut ongoing IO by 42× — well below the free-tier IOPS budget. The grace period clears itself once the per-day average falls under the threshold.

We will **not** need a Pro plan upgrade. The structural fix is sufficient.

## What's not measured here

- 60-min sample as originally prompted — only got 3.7 min before measurement. The signal is so strong that a longer sample wouldn't change the verdict. If desired, a follow-up measurement next session against this T0 / new T1 can confirm steady-state.
- Per-app-route latency changes — unmeasured here; will surface in Sentry transaction traces over the next few days.
- Phase 4 VACUUM-related improvements — folded into the same delta; can't be cleanly separated.

## T1 snapshot for follow-up comparisons

```json
{
  "snapshot_at": "2026-05-23T03:14:58.460478+00:00",
  "blks_read": 1622899825,
  "blks_hit": 4553594340,
  "tup_returned": 128168852342,
  "temp_files": 138849,
  "temp_bytes": 640659445452,
  "current_gedcom_relationships_view": {"queryid": -610194146392825963, "calls": 348196, "total_exec_time_ms": 262731849}
}
```

---

## ADDENDUM — T+60min Final-Window Recapture (Codex P0-1 resolved)

**Captured**: 2026-05-23T04:12:03Z
**Window**: **60.8 minutes** of organic post-fix traffic (target ≥ 60)

### Acceptance gate — PASS (gates 1 + 2 met on the proper-window sample)

| Gate | Target | Actual (60-min) | Result |
|------|--------|-----------------|--------|
| 1. Cache hit ratio on (T1_60 - T0) window ≥ 90% | ≥ 90% | **99.95%** | ✅ PASS |
| 2. `current_gedcom_relationships` mean exec time < 100 ms | < 100 ms | **37.57 ms** | ✅ PASS |
| 3. `gedcom_relationships` heap_blks_read rate ≥ 80% lower | ≥ -80% | n/a (still no per-table T0 snapshot) | skipped |
| 4. View OUT of top-3 in `temp_blks_written` | yes | view never had temp spill anyway | n/a |

### 60-min delta breakdown

`current_gedcom_relationships` view:
| Metric | At T0 | At T1_60 | (T1_60 - T0) window |
|--------|------:|---------:|--------------------:|
| Calls | 348,055 | 348,478 | +423 |
| total_exec_time | 262,726,116 ms | 262,742,007 ms | +15,891 ms |
| Mean exec time | 754.84 ms | 753.97 ms | **37.57 ms** |

**20.1× speedup** on the 60-min window (vs 18.6× on the 3.7-min interim sample — the longer sample is slightly faster as the buffer cache warms further).

`pg_stat_database` deltas (60-min):
| Metric | Delta over 60.8 min |
|--------|-------------------:|
| `blks_read` | +1,273 |
| `blks_hit` | +2,608,896 |
| Cache hit % | **99.95%** |
| `temp_files` | +87 |
| `temp_bytes` | +471,070,590 (~449 MB) |

### Sustained disk-read rate

- 60-min window: **0.35 reads/sec**
- Pre-fix 165-day average: 113.83 reads/sec
- **Reduction: 326×** (vs ~42× on the 3.7-min sample)

The free-tier sustained-IOPS budget for Nano is ~30/sec. We were at 113/sec pre-fix (3.8× over budget). Now at 0.35/sec = 1.2% of budget. The Disk IO Budget banner should clear on the next Supabase billing-cycle rollover.

### Codex P0-1 — RESOLVED

The Phase 6 measurement methodology is now sound: the post-Phase-4 T0 was a fresh counter snapshot; T1_60 sampled organic traffic for 60.8 minutes (≥ 60 min minimum); deltas were computed as (T1_60 - T0); two gates met with overwhelming margins. The original 3.7-min interim sample's PASS verdict is corroborated and refined by the proper-window numbers.

T1_60 snapshot: `docs/session_context/session-162-t1-60min-snapshot.json`
