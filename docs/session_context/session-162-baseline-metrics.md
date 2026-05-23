# Session 162 Phase 0 — Baseline Metrics

**Captured**: 2026-05-23T02:57:22Z (UTC)
**Database**: rhodesli (Supabase project fvynibivlphxwfowzkjl)
**Production /health**: 200 OK
**Counter window**: cumulative since `stats_reset = 2025-12-08 11:03:29 UTC` (≈166 days)

## Preflight summary

- ✅ No long-running queries (>30s, non-idle) in `pg_stat_activity`
- ✅ Partial index `idx_gedcom_relationships_current` exists with predicate `WHERE (is_current = true)`
- ✅ No NULL rows in `gedcom_relationships.is_current` (731,942 false + 140,796 true)
- ✅ DB size 1,309 MB (unchanged from Session 158e final state)

## Key takeaway

`current_gedcom_relationships` view = **#1 burner by ~10× margin**: 348,055 calls × 754 ms mean = 262,726 sec of CPU time across the 166-day window. heap reads on `gedcom_relationships` table: 1.22 BILLION blocks (75.93% cache hit). Fix in Phase 1a is expected to eliminate this.

`temp_blks_written` analysis (Codex P1.7): the 597 GB temp spill is dominated by **historical** queries — pre-158e legacy `gedcom_individuals` table reads + 158b backfill cursor fetches + cutover-time INSERTs. NOT ongoing request-path pressure. Temp spill will naturally fall over future sessions as the counters age out.

---

## Raw output

```
=== Session 162 Phase 0 Baseline — 2026-05-23T02:57:22.795295+00:00 ===

### Preflight: long-running queries (>30s, non-idle)
  NONE

### Preflight: idx_gedcom_relationships_current definition
  idx_gedcom_relationships_current: CREATE INDEX idx_gedcom_relationships_current ON public.gedcom_relationships USING btree (is_current) WHERE (is_current = true)
  ✓ predicate matches expected "WHERE (is_current = true)"

### Preflight: gedcom_relationships.is_current distribution
  is_current=False: 731,942
  is_current=True: 140,796

### DB size
  1309 MB (1,372,671,123 bytes)

### pg_stat_database (cumulative since 2025-12-08)
  stats_reset_at: 2025-12-08 11:03:29.274482+00:00
  blks_read=1,622,746,039  blks_hit=4,552,557,301  cache_hit%=73.72
  tup_returned=128,155,022,616  fetched=881,306,733
  temp_files=138,820  temp_bytes=597 GB

### pg_statio_user_tables top 12 by heap_blks_read
  table                                        heap_read       heap_hit     h%   idx_read     i%
  gedcom_relationships                     1,223,372,844  3,859,420,642 75.93%    186,422 99.44%
  gedcom_individuals_v2                        8,482,061    175,357,759 95.39%    100,460 97.68%
  gedcom_events                                2,275,781     14,694,557 86.59%     40,112 99.37%
  gedcom_records                                 788,280      1,764,040 69.12%     14,511 99.41%
  identities                                     209,787     22,997,994 99.10%      9,130 99.68%
  face_gemini_alignments                          82,417      1,440,932 94.59%      4,823 94.26%
  relationships                                   68,036      1,042,186 93.87%      3,067 99.32%
  audit_log                                       55,991      1,800,438 96.98%      5,018 97.09%
  date_labels                                     22,652        104,841 82.23%      1,041 95.17%
  photo_communities                               22,144        120,453 84.47%      1,474 88.82%
  ml_proposals                                    14,287         16,043 52.89%      2,087 76.30%
  photo_locations                                 13,226         37,978 74.17%        661 97.28%

### pg_stat_statements top 15 by total_exec_time
  calls= 348,055 total_ms=262,726,116 mean=  754.84 rows=  348,055 temp_w=         0
    WITH pgrst_source AS ( SELECT "public"."current_gedcom_relationships"."individual_gedcom_i
  calls=  52,081 total_ms=25,200,813 mean=  483.88 rows=   52,081 temp_w=         0
    WITH pgrst_source AS ( SELECT "public"."current_gedcom_individuals"."gedcom_id", "public".
  calls=   1,500 total_ms= 3,884,164 mean= 2589.44 rows=    1,500 temp_w=         0
    WITH pgrst_source AS ( SELECT "public"."gedcom_individuals".* FROM "public"."gedcom_indivi
  calls= 166,584 total_ms= 3,495,560 mean=   20.98 rows=  166,584 temp_w=         0
    WITH pgrst_source AS ( SELECT "public"."identities".* FROM "public"."identities"   LIMIT $
  calls=  29,888 total_ms= 2,132,464 mean=   71.35 rows=   29,888 temp_w=         0
    WITH pgrst_source AS ( SELECT "public"."face_gemini_alignments"."photo_id", "public"."face
  calls=   6,929 total_ms= 1,729,793 mean=  249.65 rows=    6,929 temp_w=         0
    WITH pgrst_source AS ( SELECT "public"."current_gedcom_individuals_v2"."gedcom_id", "publi
  calls=  34,439 total_ms= 1,479,872 mean=   42.97 rows=   34,439 temp_w=         0
    WITH pgrst_source AS ( SELECT "public"."identities"."identity_id", "public"."identities"."
  calls=1,417,155 total_ms= 1,453,432 mean=    1.03 rows=1,417,155 temp_w=         0
    select set_config('search_path', $1, true), set_config('role', $2, true), set_config('requ
  calls=     870 total_ms= 1,429,792 mean= 1643.44 rows=      870 temp_w=         0
    WITH pgrst_source AS ( SELECT "public"."current_gedcom_individuals".* FROM "public"."curre
  calls=      24 total_ms=   804,742 mean=33530.92 rows=  503,280 temp_w=         0
    SELECT * FROM gedcom_individuals WHERE version_id = $1
  calls= 163,509 total_ms=   798,807 mean=    4.89 rows=  163,509 temp_w=         0
    SELECT * FROM pgbouncer.get_auth($1)
  calls=  51,999 total_ms=   742,890 mean=   14.29 rows=   51,999 temp_w=         0
    WITH pgrst_source AS ( SELECT "public"."audit_log".* FROM "public"."audit_log"   LIMIT $1 
  calls=  18,158 total_ms=   577,906 mean=   31.83 rows=   18,158 temp_w=         0
    WITH pgrst_source AS ( SELECT "public"."identity_overrides"."identity_id", "public"."ident
  calls=     720 total_ms=   507,902 mean=  705.42 rows=      720 temp_w=         0
    WITH pgrst_source AS ( SELECT "public"."current_gedcom_individuals"."gedcom_id", "public".
  calls=   1,021 total_ms=   497,585 mean=  487.35 rows=    1,021 temp_w=         0
    WITH pgrst_source AS ( SELECT "public"."gedcom_change_log".* FROM "public"."gedcom_change_

### pg_stat_statements top 15 by temp_blks_written (spill)
  calls=     286 total_ms=   339,391 temp_w=   864,655 temp_r=   625,854
    WITH pgrst_source AS ( SELECT "public"."gedcom_individuals"."gedcom_id", "public"."gedcom_
  calls=     440 total_ms=   177,839 temp_w=   208,785 temp_r=    81,365
    WITH pgrst_source AS (INSERT INTO "public"."gedcom_individuals"("birth_date", "birth_event
  calls=     251 total_ms=   206,150 temp_w=    82,198 temp_r=    29,905
    WITH pgrst_source AS (INSERT INTO "public"."gedcom_individuals_v2"("birth_date", "birth_pl
  calls=     342 total_ms=    66,141 temp_w=    64,332 temp_r=         0
    insert into "gedcom_individuals" ("birth_date", "birth_event_json", "birth_place", "citati
  calls=      41 total_ms=     4,620 temp_w=    37,017 temp_r=         0
    FETCH FORWARD 5000 FROM "backfill_gedcom_individuals_v2_45bb9cca"
  calls=      66 total_ms=     2,970 temp_w=    28,785 temp_r=    21,333
    WITH pgrst_source AS ( SELECT "public"."gedcom_individuals".* FROM "public"."gedcom_indivi
  calls=      88 total_ms=    18,129 temp_w=    21,200 temp_r=         0
    WITH pgrst_source AS (UPDATE "public"."gedcom_individuals" SET "is_current" = "pgrst_body"
  calls=      12 total_ms=     2,705 temp_w=    13,656 temp_r=     1,536
    with f as (
      
-- CTE with sane arg_modes, arg_names, and arg_types.
-- All three are 
  calls=      39 total_ms=    14,933 temp_w=    11,092 temp_r=    10,295
    WITH pgrst_source AS ( SELECT "public"."gedcom_families"."family_gedcom_id", "public"."ged
  calls=      44 total_ms=    89,799 temp_w=    10,693 temp_r=     9,318
    WITH pgrst_source AS ( SELECT "public"."current_gedcom_individuals"."gedcom_id", "public".
  calls=      45 total_ms=     6,147 temp_w=     8,880 temp_r=     2,486
    WITH pgrst_source AS (INSERT INTO "public"."relationships"("data", "person_a", "person_b",
  calls=       9 total_ms=     2,090 temp_w=     6,394 temp_r=         0
    WITH pgrst_source AS (DELETE FROM "public"."relationships"  WHERE  "public"."relationships
  calls=       1 total_ms=     2,675 temp_w=     5,488 temp_r=     5,475
    SELECT gedcom_id,
                   COUNT(DISTINCT payload_hash) AS distinct_hashes,
    
  calls=       8 total_ms=       355 temp_w=     5,209 temp_r=         0
    FETCH FORWARD 5000 FROM "backfill_gedcom_families_v2_eb31d4dd"
  calls=      10 total_ms=     1,361 temp_w=     5,119 temp_r=         0
    FETCH FORWARD 5000 FROM "dump_gedcom_events_5a7a3bc3"

=== Phase 0 baseline collection complete ===
```
