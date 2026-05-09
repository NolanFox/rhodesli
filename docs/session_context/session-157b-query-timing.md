# Session 157b — PRD-063 Day 2 Query Timing Comparison

**Iterations**: 100 (per backend per path)
**Timestamp**: 2026-05-09 03:16:01 UTC
**Method**: psycopg2 direct connections via supabase pooler (`aws-0-us-west-2.pooler.supabase.com:6543`). No app TTL caches.
**Pricing**: lower median is better; p95 reveals tail latency.

## Summary

| Path | v1 median (ms) | v2 median (ms) | v2 speedup | v1 p95 | v2 p95 | Winner |
|---|---:|---:|---:|---:|---:|---|
| 1_single_id_lookup | 81.29 | 80.57 | 1.01× | 94.87 | 86.01 | **v2** |
| 2_bulk_thin_load | 100.4 | 100.63 | 1.00× | 406.19 | 194.73 | **v1** |
| 3_surname_search | 114.19 | 109.67 | 1.04× | 124.52 | 126.89 | **v2** |
| 4_is_current_vs_implicit | 83.88 | 82.77 | 1.01× | 276.31 | 117.64 | **v2** |

## Detail

### 1_single_id_lookup

**v1**

- iterations: 100
- median: 81.29 ms
- p95: 94.87 ms
- min/max: 78.31 / 176.92 ms
- total: 8346.31 ms

**v2**

- iterations: 100
- median: 80.57 ms
- p95: 86.01 ms
- min/max: 78.15 / 94.65 ms
- total: 8120.47 ms

### 2_bulk_thin_load

**v1**

- iterations: 25
- median: 100.4 ms
- p95: 406.19 ms
- min/max: 95.22 / 506.34 ms
- total: 2998.21 ms

**v2**

- iterations: 25
- median: 100.63 ms
- p95: 194.73 ms
- min/max: 95.17 / 197.53 ms
- total: 2707.92 ms

### 3_surname_search

**v1**

- iterations: 100
- median: 114.19 ms
- p95: 124.52 ms
- min/max: 94.33 / 137.71 ms
- total: 11482.08 ms

**v2**

- iterations: 100
- median: 109.67 ms
- p95: 126.89 ms
- min/max: 91.87 / 1228.12 ms
- total: 12364.22 ms

### 4_is_current_vs_implicit

**v1**

- iterations: 25
- median: 83.88 ms
- p95: 276.31 ms
- min/max: 80.33 / 356.34 ms
- total: 2366.48 ms

**v2**

- iterations: 25
- median: 82.77 ms
- p95: 117.64 ms
- min/max: 79.74 / 125.99 ms
- total: 2137.47 ms

### 5_dual_read_helper

- iterations: 50
- median: 101.54 ms
- p95: 263.53 ms
- min/max: 97.31 / 651.19 ms
- note: End-to-end via Supabase REST. v2 hit on every call (helper falls back to v1 only on miss).

## Verdict

  - `1_single_id_lookup`: v1 81.29ms / v2 80.57ms (-0.9% median, -9.3% p95) → **TIE**
  - `2_bulk_thin_load`: v1 100.4ms / v2 100.63ms (+0.2% median, -52.1% p95) → **TIE**
  - `3_surname_search`: v1 114.19ms / v2 109.67ms (-4.0% median, +1.9% p95) → **TIE**
  - `4_is_current_vs_implicit`: v1 83.88ms / v2 82.77ms (-1.3% median, -57.4% p95) → **TIE**

- Real v2 wins (>5% faster): 0
- Real v1 wins (>5% faster on median + p95): 0
- Ties (within 5% or noise): 4

**Recommendation**: dual-read confidence GREEN. No path is meaningfully slower on v2 (no >5% median + p95 regression). Network latency from the us-west-2 pooler floor (~80ms) dominates the actual query execution time, so the 18×/14× row reduction shows up more in p95 tail latency than in median. Session 158 cutover (read-from-v2-only + DROP v1) is safe from a query-speed perspective. Storage and operational wins remain the primary motivation.
