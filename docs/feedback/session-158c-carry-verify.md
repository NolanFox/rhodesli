# Session 158c — Phase 158c-0 Carry Verify

**Date**: 2026-05-09 22:50 UTC
**Mode**: 158c (continuation of 158b)
**Method**: Direct psycopg2 via session-mode pooler (port 5432) — REST timed out on v1 count(*)

## Pooler Probe Results

| Mode | Port | Trial 1 | Trial 2 | Trial 3 | Trial 4 | Trial 5 | Verdict |
|---|---|---|---|---|---|---|---|
| Transaction (158b default) | 6543 | FAIL SSL | FAIL SSL | FAIL SSL | n/a | n/a | **0/3 — DEAD** |
| Session (158c discovery) | 5432 | PASS 25391ms | PASS 14665ms | PASS 4203ms | PASS 973ms | PASS 1018ms | **5/5 — WORKS** |
| Direct (db.<ref>) | 5432 | DNS FAIL | DNS FAIL | n/a | n/a | n/a | **0/2 — IPv6-only/unreachable** |

**Discovery**: Supabase pooler transaction-mode (6543) remains down (same outage as 158b),
but session-mode (5432) is healthy. First trial slow (cold start), then warm to <1s. This
unblocks all psycopg2-requiring DDL phases. Bumping `connect_timeout` 30s → 60s in cutover
scripts to absorb cold-start latency.

## v2 Row Counts (post-158b chunked-write partial)

| Table | Rows | Distinct gedcom_id |
|---|---|---|
| gedcom_individuals_v2 | **43,172** | 21,998 |
| gedcom_families_v2 | **6,741** | (column is `family_gedcom_id`) |
| gedcom_change_manifest | **9** | n/a |

**Interpretation**:
- Individuals: 43,172 rows / 21,998 distinct = **1.96 states per individual**.
  Per Session 158-1 finding: 96.3% of individuals have a 2-state history.
  → Backfill is essentially **complete** for individuals (chunks 6-10 will mostly no-op).
- Families: 6,741 rows = current state ONLY. **No historical compression yet.**
  → Need to run families backfill in 158c-2.

## v1 Still Intact

| Table | Total | is_current=TRUE | Historical |
|---|---|---|---|
| gedcom_individuals | 196,645 | 21,998 | 174,647 |
| gedcom_families | 33,324 | 6,741 | 26,583 |

## DB Size + Top Tables

- **DB size: 2,542 MB (2.48 GB)** — 2.3× over the 1.1 GB free-tier ceiling.
- Top tables (top 10 by total relation size):

```
TBD — query truncated due to verify script bug. Will re-run.
```

(Top tables query was in same script that errored on `gedcom_id` column for families_v2.
Re-running with corrected schema in next phase.)

## Summary

- **Pooler workaround**: session-mode port 5432 unblocks all DDL. Cutover phases CAN proceed.
- **v2 individuals**: complete (43,172 = 21,998 × 2 states avg per 158-1 finding).
- **v2 families**: needs historical backfill (only current state present).
- **DB at 2,542 MB**: cutover urgency confirmed. Free-tier deadline 2026-05-29 (20 days).

## Decision

**PROCEED with 158c phases via session-mode pooler (port 5432).**
Update cutover/drop scripts to use port 5432 + connect_timeout=60s.
