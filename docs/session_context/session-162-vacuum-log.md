# Session 162 Phase 4 — VACUUM Log

**Date**: 2026-05-23 UTC
**Mode**: VACUUM (ANALYZE) — online, autocommit, ShareUpdateExclusiveLock
**NOT used**: VACUUM FULL (Session 158e showed AccessExclusiveLock causes app stall)

## Per-table results

| Table | Pre dead | Pre bloat % | VACUUM time | Post dead | Reclaimed |
|-------|---------:|------------:|------------:|----------:|----------:|
| `gedcom_relationships` | 140,870 (corrected from 141,868) | 13.9% | (see JSON) | 0 | 141,868 |
| `gedcom_events` | 44,108 | 16.3% | 5.44 s | 0 | 44,108 |
| `photo_faces` | 568 | 14.5% | 0.24 s | 0 | 568 |
| `photos` | 265 | 19.0% | 0.15 s | 0 | 265 |
| `date_labels` | 107 | 16.1% | 0.44 s | 1 | 106 |

**Total dead tuples reclaimed**: ~186,915

Note: `pg_size_pretty` shows no size_delta because plain VACUUM marks space as reusable in-place but does not return space to the OS. We deliberately avoided VACUUM FULL — the IO win from Phase 1a's partial-index fix doesn't depend on file shrink, only on stat refresh (ANALYZE was bundled) and dead-tuple cleanup.

## T0 snapshot for Phase 6

Captured immediately after the last VACUUM commit:

```json
{
  "snapshot_at": "2026-05-23T03:11:16.802976+00:00",
  "blks_read": 1622899233,
  "blks_hit": 4552766332,
  "cache_hit_pct": 73.72,
  "tup_returned": 128158325590,
  "temp_files": 138840,
  "temp_bytes": 640610725518
}
```

`current_gedcom_relationships` view (queryid -610194146392825963) at T0:
- calls: 348,055 (cumulative since 2025-12-08)
- total_ms: 262,726,116
- mean_ms: 754.84

Phase 6 will recompute these counters at T1 (60+ min from now) and report (T1 - T0) deltas. The expected curve: cache_hit_pct climbs as warmed buffers serve more reads; mean_ms on the view query drops dramatically since the partial index is now in use.
