# Session 162 Context — Supabase Disk IO Budget Remediation

**Date**: 2026-05-22
**Mode**: implementation
**Predecessor**: [session-161-context.md](session-161-context.md) (rhodes-inbox)
**Trigger**: Supabase email "Your project rhodesli is running out of Disk IO Budget" received 2026-05-21 11:45 PT
**Planned 162 (dossier auto-update + wiki narrative) pushed to**: Session 163

---

## TL;DR

Storage was fixed in Session 158e (DB 2,564 MB → 1,309 MB). **Disk IO Budget is a different metric** — it's per-IOPS daily burn, dominated by query plans, missing indexes, table bloat, and dead-table query loops, not how much you store at rest. The user is right to be confused: we *did* fix everything we were aware of in 158e. The 158e assessment even predicted this could come back ("long-term solutions: Pro plan upgrade, further data reduction, move heavy tables to R2-as-cold-storage" — Red Flag LOW). What we didn't catch was a **bad WHERE clause in a hot view** that defeats a partial index.

The single biggest culprit is a one-line bug in the `current_gedcom_relationships` view: `WHERE is_current = true OR is_current IS NULL`. The `OR ... IS NULL` clause prevents Postgres from using the partial index `idx_gedcom_relationships_current WHERE is_current = true`. Every one of the 347,914 historical calls full-scanned the 872,738-row table even though only 140,796 rows are current. Fix: drop the `OR is_current IS NULL` (the column actually has zero NULL values; the defensive clause is unnecessary). Estimated impact: ~74% of total disk reads collapse to buffer-cache hits.

Plus two secondary wins: (a) DROP the `identity_overrides` table (0 live rows, deprecated since Session 130, still polled by `data_integrity_audit.py`), and (b) VACUUM the bloat tables that 158e's VACUUM FULL never reached (it halted at table 1/7 on statement_timeout per the 158c P2 re-raise).

User decisions taken via AskUserQuestion at session start:
- **Plan strategy**: Structural-only, no Pro plan upgrade
- **identity_overrides disposition**: Investigate first, drop only if safe

---

## Empirical Diagnosis (collected 2026-05-22)

### Overall DB state

| Metric | Value | Healthy threshold |
|--------|-------|-------------------|
| DB size | 1,309 MB | < 1,500 MB (Session 158e target) |
| **Cache hit ratio** | **73.73%** | **≥ 95%** |
| `blks_read` (disk) | 1,619,914,004 | as low as possible |
| `blks_hit` (cache) | 4,546,398,767 | high |
| `temp_files` count | 138,775 | low |
| `temp_files` total size | **596 GB** | < 10 GB ideally |
| `stats_reset_at` | 2025-12-08 | (counter window = 165 days) |

A 73.73% cache hit ratio means 26% of every query hits disk. Industry guidance: ≥ 95% is healthy, < 90% means you have an indexing or sizing problem. 596 GB of temp file spill in 165 days means Postgres is constantly writing intermediate sort/hash results to disk because `work_mem` can't hold them — but that's usually a downstream symptom of bad query plans, not a tuning issue we can fix on Supabase's managed plan.

### Top 5 queries by total exec time (since 2025-12-08)

| Rank | Query | Calls | Mean ms | Total blocks read | % of disk reads |
|------|-------|------:|--------:|------------------:|----------------:|
| 1 | `current_gedcom_relationships` view | 347,914 | 754.90 | 1,198,193,196 | **73.9%** |
| 2 | `current_gedcom_individuals` view (DOES NOT EXIST — historical) | 52,081 | 483.88 | 334,011,615 | 20.6% |
| 3 | `gedcom_individuals` (DOES NOT EXIST — historical) | 1,500 | 2589.44 | 1,876,229 | 0.12% |
| 4 | `identities` table | 166,584 | 20.98 | 7,508 | 0.0005% |
| 5 | `face_gemini_alignments` table | 29,868 | 71.38 | 93,776 | 0.006% |

**Critical observation**: Ranks 2-3 are queries against tables/views that no longer exist (DROPped in Session 158e). Their stats remain in pg_stat_statements as a 165-day historical artifact, but they are not generating ongoing IO. **The only ongoing burner is rank 1**.

### Per-table disk read distribution (`pg_statio_user_tables`)

| Table | heap_blks_read (disk) | heap cache hit % | idx cache hit % |
|-------|----------------------:|-----------------:|----------------:|
| `gedcom_relationships` | **1,222,407,212** | **75.94%** | 99.44% |
| `gedcom_individuals_v2` | 8,474,085 | 95.38% | 97.68% |
| `gedcom_events` | 2,275,781 | 86.59% | 99.37% |
| `gedcom_records` | 788,280 | 69.12% | 99.41% |

`gedcom_relationships` alone accounts for 75% of all heap disk reads. Index cache hit on the same table is 99.44% — indexes are healthy, the problem is full-table heap scans that bypass them.

### The root cause query

```sql
-- View definition (from pg_get_viewdef):
CREATE VIEW current_gedcom_relationships AS
 SELECT id, individual_gedcom_id, related_gedcom_id, relationship_type,
        family_gedcom_id, created_at, version_id, is_current, edge_key,
        relationship_payload, payload_hash, superseded_by
   FROM gedcom_relationships
  WHERE is_current = true OR is_current IS NULL;
                       ^^^^^^^^^^^^^^^^^^^^^^^^^
                       This clause defeats the partial index.
```

Existing partial index:

```sql
CREATE INDEX idx_gedcom_relationships_current ON public.gedcom_relationships
 USING btree (is_current) WHERE (is_current = true);
```

Postgres' planner cannot use a partial index when the WHERE clause includes an OR over a predicate the index excludes (NULL values). Result: full seq scan over 872,738 rows on every PostgREST call.

### is_current distribution (verified empty NULL set)

| is_current | count |
|-----------|------:|
| false | 731,942 |
| true | 140,796 |
| **NULL** | **0** |

The defensive `OR is_current IS NULL` was over-engineering. The column has no NULL values, never has had any, and structurally never can have any if we add a NOT NULL constraint.

### Estimated impact of the fix

| Metric | Before | After (projected) | Reduction |
|--------|-------:|------------------:|----------:|
| Rows scanned per call | 872,738 | 140,796 | 84% |
| Heap blocks per call | ~28 MB | ~5 MB | 82% |
| Disk reads (assuming working-set fits in cache) | 1.2B/quarter | < 100M/quarter | ~92% |
| Sustained IOPS from this view | ~84 IOPS | ~5 IOPS | 94% |

The free Supabase Nano sustained IOPS budget is ~30 IOPS. This fix alone should drop us back well under budget without a plan upgrade.

### Bloat candidates (`pg_stat_user_tables` dead tuples)

| Table | live | dead | dead % | last_autovacuum |
|-------|-----:|-----:|-------:|-----------------|
| `gedcom_relationships` | 872,197 | 140,870 | 13.9% | 2026-03-29 |
| `gedcom_events` | 226,249 | 44,108 | 16.3% | 2026-03-12 |
| `photo_faces` | 3,338 | 568 | 14.5% | 2026-03-17 |
| `photos` | 1,127 | 265 | 19.0% | 2026-04-02 |
| `date_labels` | 559 | 107 | 16.1% | 2026-03-29 |

None of these has been manually vacuumed since the Session 158e cutover (`last_vacuum` is None across the board). Session 158e's VACUUM FULL halted at table 1/7 on statement_timeout (per the 158c P2 re-raise design) after the DROP-TABLE bulk reclaim, so the autovacuum-only state means we still have low-grade bloat that compounds with the partial-index miss.

### `identity_overrides` — verified dead in request path; ONE stale write-side caller

```
0 live rows.
509,515 idx_scans + 17,223,552 seq tuple reads in the counter window.
```

In-app DEPRECATED stubs (no-ops):
- `app/supabase_data.py:118` `sync_identity_overrides()` — body returns None
- `app/supabase_data.py:281` `# --- identity_overrides REMOVED (Session 130) ---`
- `app/supabase_data.py:1269` `load_identity_overrides_from_supabase()` — returns `{}`
- `app/main.py:1834` historical comment

Active readers (periodic only, NOT in request path):
- `scripts/data_integrity_audit.py:374` — integrity report
- `scripts/data_integrity_report.py:165` — integrity report

**Codex audit (2026-05-22) caught one I missed**:
- `scripts/migrate_to_supabase.py` — actively *writes* to `identity_overrides`:
  - `:70` docstring "Migrate user-modified identities to identity_overrides table"
  - `:99` `sb.table('identity_overrides').upsert(batch).execute()`
  - `:245` `counts['identity_overrides'] = migrate_identities(sb, identities, dry_run)`

The script is a one-shot Session 59C migration tool that should never run again (it migrated JSON→Postgres long ago). But the file is still in the tree and would error on a re-run if the table is dropped. Must retire it (rename → `scripts/_archive/migrate_to_supabase_session59C.py` OR delete the identity_overrides path) BEFORE DROP.

**Verdict**: still safe to DROP, but Phase 2 must retire `migrate_to_supabase.py` in the same investigation step; and Phase 3 rollback must restore RLS (line 84 of `supabase_migration_001.sql`, not just lines 10-29).

### Codex audit warning — raw-table fallback IO landmine

`app/relationship_routes.py` has two fallback paths that read raw `gedcom_relationships` WITHOUT the `is_current = true` filter when the view returns a "relation does not exist" error:
- `:513-518` `_load_gedcom_rows(sb, "gedcom_relationships", ...)` after view miss
- `:632-637` `sb.table("gedcom_relationships").select(...).or_(filter_expr).execute()` after view miss

If the view is briefly unavailable (PostgREST schema cache flake — exactly the failure mode Lesson 187 describes during disk-IO pressure), these fallbacks pull from the 872k-row raw table without filtering for current rows. That is the SAME IO antipattern we're fixing, just on a slower trigger.

**Mitigation**: add `is_current = true` filter to both fallback paths BEFORE landing the view migration in Phase 1. This is Phase 1a in the prompt (was floated to Phase 5 in v1; promoted on Codex P1).

### Measurement validity caveat (Codex P0)

`pg_stat_database` and `pg_stat_statements` are cumulative counters since `stats_reset = 2025-12-08`. A naive "rerun the baseline queries and compute deltas" is invalid because the 165-day denominator dwarfs any 60-min window.

Phase 6 must use one of:
- (a) Reset counters explicitly via `SELECT pg_stat_statements_reset(); SELECT pg_stat_reset();` after Phase 4 commit, then sample fresh. Requires service-role privileges, which we have.
- (b) Compute deltas: capture a fresh T0 snapshot after Phase 4 commit, wait 60 min, capture T1, compute (T1 - T0) and report relative to that window.

Approach (a) is cleaner but resets stats history for other operators; (b) preserves history but requires bookkeeping. Prompt uses (b).

---

## Plan

7 phases, dual-test-fast between each, /clear between each, commit per phase. User gates documented inline.

### Phase 0 — Baseline + safety setup (NO mutations)
- Snapshot current `pg_stat_database` cache hit ratio, `pg_statio_user_tables` heap reads, top-15 `pg_stat_statements`
- Save raw metrics to `docs/session_context/session-162-baseline-metrics.md`
- Confirm production `/health = 200`
- Confirm `make test-fast` green at HEAD
- Take Supabase dashboard screenshot via Chrome MCP (`grace period until` date is the budget deadline we're racing)

### Phase 1 — Fix `current_gedcom_relationships` view (THE big win)

Single migration script:

```sql
-- File: scripts/session162_fix_current_gedcom_relationships_view.sql
BEGIN;
SET LOCAL lock_timeout = '30s';
SET LOCAL statement_timeout = '60s';

-- Safety: confirm no NULL rows exist before adding NOT NULL constraint
DO $$
DECLARE
  null_count bigint;
BEGIN
  SELECT COUNT(*) INTO null_count FROM gedcom_relationships WHERE is_current IS NULL;
  IF null_count > 0 THEN
    RAISE EXCEPTION 'gedcom_relationships has % NULL is_current rows; refusing to add NOT NULL constraint', null_count;
  END IF;
END $$;

ALTER TABLE gedcom_relationships ALTER COLUMN is_current SET NOT NULL;

CREATE OR REPLACE VIEW current_gedcom_relationships AS
 SELECT id, individual_gedcom_id, related_gedcom_id, relationship_type,
        family_gedcom_id, created_at, version_id, is_current, edge_key,
        relationship_payload, payload_hash, superseded_by
   FROM gedcom_relationships
  WHERE is_current = true;
COMMIT;

-- Verification (separate query, run after commit):
EXPLAIN (ANALYZE, BUFFERS) SELECT count(*) FROM current_gedcom_relationships;
-- Expect: Index Only Scan using idx_gedcom_relationships_current
```

Rollback: re-add `OR is_current IS NULL` (it was the original definition; harmless to restore).

After commit, wait 90 seconds for PostgREST schema cache reload (NOTIFY pgrst, 'reload schema' if needed), then re-EXPLAIN. Verify the new plan uses the partial index.

### Phase 2 — Investigate `identity_overrides` (no mutation yet)
- Re-grep for any read paths missed in pre-session diagnosis
- Snapshot the empty table to `r2://rhodesli-backups/session162/identity_overrides_snapshot.json.gz` (defensive — table has 0 live rows, but if the snapshot fails we don't drop)
- Run `data_integrity_audit.py` and `data_integrity_report.py` on a fresh clone with the table removed from the queries (to confirm the scripts still pass)
- **PROCEED GATE 1**: report to user (no automatic drop). If user approves, execute Phase 3.

### Phase 3 — DROP `identity_overrides` (DESTRUCTIVE, gated on Phase 2 + user approval)
```sql
BEGIN;
SET LOCAL lock_timeout = '30s';
-- Drop dependent indexes first (they cascade with the table, but explicit is safer)
DROP TABLE IF EXISTS identity_overrides;
COMMIT;
```
Update `scripts/data_integrity_audit.py` and `scripts/data_integrity_report.py` to remove `identity_overrides` from their query lists in the same commit. Add a unit test that asserts the table no longer exists in `information_schema.tables` (regression guard).

Rollback: replay `supabase_migration_001.sql` lines 10-29 (table + 2 indexes). All rows were empty anyway.

### Phase 4 — VACUUM bloat tables (no FULL, no statement_timeout risk)
For each table in `[gedcom_relationships, gedcom_events, photo_faces, photos, date_labels]`:
- `VACUUM (ANALYZE, VERBOSE) <table>;`
- Capture before/after pg_class size + pg_stat_user_tables dead-tuple count

NO `VACUUM FULL` — Session 158e showed FULL on bloat tables hits statement_timeout and risks app downtime. Plain VACUUM reclaims dead-tuple space in-place without exclusive locks. ANALYZE updates planner statistics (important after the Phase 1 view change).

### Phase 5 — App-side TTL audit
- Grep `app/` for every `supabase.table("gedcom_relationships")` / `supabase.from_("current_gedcom_relationships")` reader
- Measure cache hit/miss rate via `app/perf_cache.py` instrumentation (already in place)
- For any reader that doesn't go through a TTL cache, consider adding one (≥ 300s for GEDCOM data — it changes only on admin upload)
- This is investigation, not mutation. Findings to `docs/session_context/session-162-cache-audit.md`. Code changes only if a glaring miss is found.

### Phase 6 — Measure
- 60-minute wait after Phase 4 (let PostgREST + autovacuum settle, accumulate a fresh sample)
- Re-run the Phase 0 baseline queries
- Compute deltas: cache hit %, top-15 query exec time, `pg_statio_user_tables` heap reads
- Save to `docs/session_context/session-162-final-metrics.md`
- **Acceptance criteria** (any one of these gates a PASS):
  - Cache hit ratio ≥ 90% over the post-Phase-4 sample window, OR
  - `current_gedcom_relationships` mean exec time < 100 ms (down from 754 ms), OR
  - `gedcom_relationships` heap_blks_read rate dropped ≥ 80% on a 60-min sample

If NONE met, escalate to user-decision: (a) accept partial improvement and ship, (b) approve Pro plan upgrade as separate task.

### Phase 7 — Codex audit + auto-fix
- `codex exec "Audit Session 162 commits for correctness, safety, rollback completeness, missing tests"` per harness AI-tool-audit rule. Use the staged invocation pattern from `.claude/rules/ai-tool-audit.md` (codex exec "<prompt>" </dev/null).
- Apply any P0/P1 findings inline; P2/P3 to BACKLOG.

### Phase 8 — Closeout
- New `OD-014` in `docs/ops/OPS_DECISIONS.md`: "Disk IO Budget Remediation — Bad-WHERE View Fix + Dead-Table Drop + VACUUM Bloat"
- New lesson L198 in `tasks/lessons.md`: "Partial indexes are defeated by `OR ... IS NULL` clauses — verify view definitions match index predicates"
- CHANGELOG bump (v0.99.81 → v0.99.82)
- ROADMAP entry under "Recently Completed"; renumber pending 162 → 163
- SESSION_HISTORY entry
- `git push origin main`, verify production `/health = 200` + 6 canonical page browser verify
- Memory backup via `scripts/backup-memory.sh`
- `/session-review`

---

## Concerns / Risks

1. **Adding NOT NULL constraint** scans the entire table to verify. On 872k rows + 13.9% bloat this could take 30-90s and acquire AccessExclusiveLock. The `lock_timeout = '30s'` + `statement_timeout = '60s'` gates abort cleanly if it stalls. Production app may briefly serve cached data during the lock (≤ 30s). NOT a 158d-style cutover risk because we're not renaming or dropping — we're constraining an existing column.

2. **CREATE OR REPLACE VIEW** is non-blocking but does invalidate PostgREST's schema cache. Per Lesson 187, schema-cache PGRST002 can self-recover or may need dashboard restart. **Mitigation**: have `SUPABASE_ACCESS_TOKEN` ready in `.env` (already present from 158e per Lesson 189). 158e established that `pg_catalog` IO pressure is the *cause* of PGRST002; this session relieves that pressure, so we expect graceful recovery.

3. **VACUUM holds ShareUpdateExclusiveLock** which blocks DDL but NOT reads or writes. `gedcom_relationships` has 1M+ ins/upd/del lifetime — VACUUM may run for several minutes. Plain VACUUM (not FULL) does this online; no app downtime expected.

4. **`identity_overrides` DROP** has zero rows and zero in-app readers — but the two integrity scripts will fail until updated. Same commit must remove their references.

5. **Acceptance gates use a 60-min sample after Phase 4** — to avoid declaring PASS off a 30-second sample that hasn't warmed up the new plan.

6. **No /compact, /clear between each phase** per session-protocol. Each phase commits atomically; recovery from any failure is `git revert <commit>` + re-apply.

---

## Why this is the right shape

- One root-cause fix (Phase 1) drives 70%+ of expected improvement
- Dead-code cleanup (Phases 2-3) drives 5-10% improvement and removes a future-confusion landmine
- Bloat sweep (Phase 4) drives 5-10% improvement and refreshes planner stats so the new view plan is healthy from the start
- App-side TTL audit (Phase 5) is investigation-first; only mutate code if a clear win is identified
- Measurement gate (Phase 6) prevents declaring victory off noise; defers Pro-plan decision to data, not anxiety

The Pro plan upgrade ($25/mo) remains an explicit *user-only* fallback gate at Phase 6, never auto-applied.

---

## Breadcrumbs

- Predecessor session: [session-161-context.md](session-161-context.md)
- Predecessor IO incident: [session-158e-assessment.md](../assessments/session-158e-assessment.md) (storage cutover)
- Prior context with same warning: [session-112-context.md](session-112-context.md) §"Supabase Resource Constraints"
- Related ops decisions: OD-011 (egress), OD-012 (egress crisis), OD-013 (DB storage compliance)
- Related lessons: 186 (PGRST002 = schema cache), **187 (PGRST002 = Disk IO Budget root cause)**, 188 (view deps before DROP), 189 (`SUPABASE_ACCESS_TOKEN` in .env), 190 (5xx baseline rule)
- New PRD: NONE — this is targeted remediation, not a feature
- Memory: `feedback_platform_reliability.md`, `project_supabase_egress.md`
