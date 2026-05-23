# Session 162 Prompt — Supabase Disk IO Budget Remediation

**Date**: 2026-05-22
**Mode**: implementation
**Context**: [session-162-context.md](../session_context/session-162-context.md) — read FIRST
**Predecessor**: Session 161 (rhodes-inbox), v0.99.81
**Target version on close**: v0.99.82
**Pre-execution audit**: Codex CLI v0.133.0 (gpt-5.5/xhigh) — 1 P0 + 7 P1 + 6 P2 applied below.

**Trigger email** (received 2026-05-21 11:45 PT):
> Your project rhodesli is running out of Disk IO Budget. Response times can increase noticeably. CPU usage rises due to IO wait. Instance may become unresponsive.

**User decisions taken at session-prep** (via AskUserQuestion):
- Plan strategy: **Structural-only, no Pro plan upgrade**
- `identity_overrides` disposition: **Investigate first, drop only if safe**

**Key empirical finding**: The view `current_gedcom_relationships` has `WHERE is_current = true OR is_current IS NULL`. The `OR ... IS NULL` clause defeats the partial index `idx_gedcom_relationships_current WHERE is_current = true`. Every one of 347,914 historical calls seq-scans 872,738 rows even though only 140,796 are current. This view alone = **73.9% of all disk reads**. Column has 0 NULL values; defensive clause is unnecessary. Fix = drop `OR is_current IS NULL` from view AND fix two raw-table fallback paths in `app/relationship_routes.py` that bypass the view filter.

---

## Session init (MUST run before Phase 0)

```bash
echo "162" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast                       # baseline must be green
pytest rhodesli_ml/tests/ -x -q      # ML suite also green (dual-test rule)
bash scripts/harness-check.sh
```

Create `docs/session_logs/session-162-log.md` with phase checklist.

---

## Acceptance criteria (Phase 6 gate)

Phase 0 captures cumulative counters since `stats_reset = 2025-12-08` (165-day window). These are NOT directly comparable to a 60-min post-fix sample. Phase 6 must compute deltas from a fresh T0 snapshot taken AFTER Phase 4 commit, not against the cumulative baseline.

ANY ONE of these = PASS (computed on the (T1 - T0) post-Phase-4 60-min window):
1. Cache hit ratio on the (T1 - T0) window ≥ 90%
2. `current_gedcom_relationships` mean_exec_time over the window < 100 ms (baseline 754.90 ms)
3. `gedcom_relationships` heap_blks_read per-minute rate ≥ 80% lower than the 165-day cumulative rate
4. Top-15 `pg_stat_statements` by `temp_blks_written` shows the view is OUT of the top-3 (temp-spill collapse signal)

If NONE met: STOP, report numbers, user-decision gate (accept partial / Pro upgrade / Phase 6b).

---

## Phase 0 — Baseline + safety preflight (NO mutations)

Goal: capture pre-state for delta computation; verify environment.

1. Confirm production `/health = 200`.
2. Confirm `make test-fast` AND `pytest rhodesli_ml/tests/ -x -q` both green.
3. **Preflight lock check** (Codex P1.2): `SELECT pid, usename, state, query_start, wait_event_type, LEFT(query, 80) FROM pg_stat_activity WHERE datname=current_database() AND state != 'idle' AND query_start < now() - interval '30 seconds';` — log any long-running queries that could block Phase 1's ALTER. Abort Phase 1 if a long writer is active.
4. **Partial index preflight** (Codex P2.1): `SELECT indexname, indexdef FROM pg_indexes WHERE indexname='idx_gedcom_relationships_current';` — verify the predicate is `WHERE (is_current = true)` exactly. If absent or different, Phase 1 will not deliver the expected speedup; report and pause.
5. Connect via pooler: `host=aws-0-us-west-2.pooler.supabase.com port=5432 user=postgres.fvynibivlphxwfowzkjl password=$SUPABASE_DB_PASSWORD` (Lesson 175).
6. Run baseline queries → save full output to `docs/session_context/session-162-baseline-metrics.md`:
   - `pg_database_size`
   - `pg_stat_database` cache hit ratio + temp counters
   - `pg_statio_user_tables` top-12 by heap_blks_read
   - **Top-15 `pg_stat_statements` by `total_exec_time`**
   - **Top-15 `pg_stat_statements` by `temp_blks_written`** (Codex P1.7 — measure spill, not just exec time)
   - `is_current` distribution on `gedcom_relationships` (sanity check: still 0 NULL?)
7. Supabase dashboard screenshot via Chrome MCP (read-only — `.claude/rules/browser-read-only.md`). Capture the grace-period date.

**Commit**: `docs(session-162): Phase 0 — baseline IO metrics + preflight`
**/clear.**

---

## Phase 1a — Fix the view + fix raw-table fallback (LOW-LOCK, the big win)

Goal: fix the IO leak without taking AccessExclusiveLock on the table. NOT NULL constraint is split to Phase 1b (Codex P1.1).

### 1a-i — Replace the view (CREATE OR REPLACE only)

`scripts/session162a_replace_view.sql`:

```sql
-- Session 162 Phase 1a — replace current_gedcom_relationships to use partial index
-- CREATE OR REPLACE VIEW takes no exclusive lock on underlying table.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '15s';

CREATE OR REPLACE VIEW current_gedcom_relationships AS
 SELECT id, individual_gedcom_id, related_gedcom_id, relationship_type,
        family_gedcom_id, created_at, version_id, is_current, edge_key,
        relationship_payload, payload_hash, superseded_by
   FROM gedcom_relationships
  WHERE is_current = true;

COMMIT;
```

Rollback: `scripts/session162a_rollback_view.sql` restores `WHERE is_current = true OR is_current IS NULL`.

### 1a-ii — Refresh planner stats BEFORE EXPLAIN (Codex P2.2)

```sql
ANALYZE gedcom_relationships;
```

Otherwise the planner may still produce a Seq Scan from stale stats and we'd roll back unnecessarily.

### 1a-iii — Smoke + EXPLAIN

1. `NOTIFY pgrst, 'reload schema';` (best-effort)
2. Wait 90s.
3. `curl https://rhodesli.nolanandrewfox.com/health` → 200.
4. EXPLAIN — **note**: `SELECT *` cannot be index-only (needs heap columns); accept any of (Codex P1.3):
   - Index Scan using `idx_gedcom_relationships_current`
   - Bitmap Heap Scan with `idx_gedcom_relationships_current`
   - Index Only Scan (only if the test uses `count(*)`)
   ```sql
   EXPLAIN (ANALYZE, BUFFERS) SELECT count(*) FROM current_gedcom_relationships;
   EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM current_gedcom_relationships LIMIT 10;
   ```
   PASS if either uses the partial index; FAIL if both show Seq Scan.

### 1a-iv — Fix raw-table fallback paths (Codex P1.4 — promoted from Phase 5)

`app/relationship_routes.py` has two fallback branches that read raw `gedcom_relationships` if the view 404s. Both currently miss the `is_current` filter:

- Line 513-518 — `_load_gedcom_rows(sb, "gedcom_relationships", ...)` after view miss
- Line 632-637 — `sb.table("gedcom_relationships").select(...).or_(filter_expr).execute()`

Edit both to add an explicit `is_current = true` filter (Supabase REST: `.eq("is_current", True)` or include in select). Same commit as 1a.

Add `tests/test_session162_relationship_fallback_filters.py`:
- Mock the view to raise PGRST205
- Verify the fallback to raw table includes the `is_current = true` filter
- Verify no path can return historical (is_current=false) rows

### 1a — Regression test

`tests/test_session162_view_definition.py`:
- Use a live DB introspection (skipped in offline CI; runs in nightly): assert `pg_get_viewdef('current_gedcom_relationships'::regclass, true)` returns a string containing `WHERE is_current = true` AND NOT containing `OR is_current IS NULL`.
- Mark with `@pytest.mark.live_db` — runs when `RUN_LIVE_DB_TESTS=1`. Avoids Codex P2.5 collision with historical migration files.
- Also write a static test on the forward SQL: parse `scripts/session162a_replace_view.sql` and assert it does NOT contain `is_current IS NULL`.

**Commit**: `fix(db): Session 162 Phase 1a — replace view + fix raw-table fallback filters`
**/clear.**

---

## Phase 1b — Add NOT NULL constraint (DEFERRED to AFTER Phase 1a verified, separately rollbackable)

Goal: structurally prevent reintroducing NULLs that would re-defeat the partial index.

Pre-gate: Phase 1a EXPLAIN must show partial-index usage AND production /health = 200 for ≥ 10 min.

Pre-check live data again immediately before:
```sql
SELECT COUNT(*) FROM gedcom_relationships WHERE is_current IS NULL;  -- must be 0
SELECT pid, usename, state, query_start FROM pg_stat_activity
 WHERE datname=current_database() AND state != 'idle' AND query_start < now() - interval '10 seconds';
```

`scripts/session162b_set_not_null.sql`:

```sql
BEGIN;
SET LOCAL lock_timeout = '10s';     -- short — abort fast if app traffic is hot
SET LOCAL statement_timeout = '60s'; -- bounded scan time after lock acquired
DO $$
DECLARE n bigint;
BEGIN
  SELECT COUNT(*) INTO n FROM gedcom_relationships WHERE is_current IS NULL;
  IF n > 0 THEN RAISE EXCEPTION 'aborting: % NULL rows', n; END IF;
END $$;
ALTER TABLE gedcom_relationships ALTER COLUMN is_current SET NOT NULL;
COMMIT;
```

If the ALTER hangs on lock_timeout: that's the gate firing because app traffic is hot. Abort, retry during a quieter window, OR defer Phase 1b to a follow-up session. Phase 1a alone delivers the IO win; 1b is structural hygiene.

Rollback: `ALTER TABLE gedcom_relationships ALTER COLUMN is_current DROP NOT NULL;`

**Commit (only if applied successfully)**: `fix(db): Session 162 Phase 1b — gedcom_relationships.is_current SET NOT NULL`
If skipped/aborted: log to session log; defer to follow-up.
**/clear.**

---

## Phase 2 — Investigate `identity_overrides` (NO mutation, snapshot only)

Goal: confirm 100% safety before destroying anything.

1. Exhaustive grep `app/ core/ scripts/ tests/ rhodesli_ml/`:
   - `grep -rn "identity_overrides" --include="*.py"`
   - `grep -rn "identity_overrides" --include="*.sql"`
   - Cross-check expected refs (see context §"identity_overrides — verified dead").
2. **Retire `scripts/migrate_to_supabase.py`** (Codex P1.6): this script *writes* to `identity_overrides` at lines 70, 99, 245. It's a Session 59C one-shot tool. Move it to `scripts/_archive/migrate_to_supabase_session59C.py` and add a top-of-file banner `# ARCHIVED 2026-05-22 — Session 59C one-shot migration tool. identity_overrides is dropped.` This MUST happen before Phase 3 DROP.
3. **`pg_depend` preflight** (Codex P2.4, Lesson 188):
   ```sql
   SELECT n.nspname AS dependent_schema, c.relname AS dependent_obj, c.relkind
     FROM pg_depend d
     JOIN pg_class c ON c.oid = d.objid
     JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE d.refobjid = 'identity_overrides'::regclass AND d.deptype = 'n';
   ```
   If ANY rows return: stop, investigate, do not DROP.
4. Snapshot to R2 via `scripts/session162_snapshot_identity_overrides.py` — writes `r2://rhodesli-backups/session162/identity_overrides_snapshot.json.gz` with row count + schema dump + timestamp.
5. Run integrity scripts against a worktree where `identity_overrides` is stubbed-out:
   - `scripts/data_integrity_audit.py --dry-run`
   - `scripts/data_integrity_report.py`
   - Both must pass.
6. Findings → `docs/session_context/session-162-identity-overrides-investigation.md`.

**Commit**: `docs(session-162): Phase 2 — identity_overrides investigation + R2 snapshot + archive migrate script`
**/clear.**

**🛑 PROCEED GATE 1**: Report to user. Require explicit "drop confirmed" before Phase 3. If declined, defer Phase 3, skip to Phase 4.

---

## Phase 3 — DROP `identity_overrides` (DESTRUCTIVE, gated)

1. `scripts/session162_drop_identity_overrides.sql`:
   ```sql
   BEGIN;
   SET LOCAL lock_timeout = '30s';
   DROP TABLE IF EXISTS identity_overrides;
   COMMIT;
   ```
2. Remove `identity_overrides` references from `scripts/data_integrity_audit.py` (line ~374) and `scripts/data_integrity_report.py` (lines ~122, ~165). Update tests touching these scripts in the same commit.
3. `tests/test_session162_identity_overrides_dropped.py`:
   - `@pytest.mark.live_db`: asserts `identity_overrides` is absent from `information_schema.tables`
   - Static grep test: asserts no Python file outside `app/supabase_data.py` (deprecation stubs allowed) and outside `scripts/_archive/` references `identity_overrides`
4. Full test suite: `make test-fast` AND `pytest rhodesli_ml/tests/ -x -q` (Codex P2.6 — dual-test rule).

**Rollback** (Codex P1.5 — RLS line was missing in v1):
```sql
-- Replay scripts/supabase_migration_001.sql lines 10-29 (CREATE TABLE + 2 indexes)
-- THEN replay line 84:
ALTER TABLE identity_overrides ENABLE ROW LEVEL SECURITY;
-- Plus: git revert the Python changes
```
Empty table; data recoverable from R2 snapshot (was empty anyway).

**Commit**: `feat(db): Session 162 Phase 3 — DROP identity_overrides + cleanup`
**/clear.**

---

## Phase 4 — VACUUM bloat tables (online, NO FULL)

Goal: reclaim dead tuples; refresh planner stats; settle the new view plan.

**Client mode** (Codex P2.3): VACUUM cannot run inside a transaction block. Run each in autocommit mode — see `scripts/session158b_drop_and_vacuum.py:75-92` for the canonical `psycopg2.connect(...).autocommit = True` pattern.

```sql
-- One at a time, autocommit, with progress capture
VACUUM (ANALYZE, VERBOSE) gedcom_relationships;
VACUUM (ANALYZE, VERBOSE) gedcom_events;
VACUUM (ANALYZE, VERBOSE) photo_faces;
VACUUM (ANALYZE, VERBOSE) photos;
VACUUM (ANALYZE, VERBOSE) date_labels;
```

NO `VACUUM FULL` (Session 158e hit statement_timeout; AccessExclusiveLock is unacceptable on hot tables).

Per table: capture before/after `pg_class.reltuples` + `pg_stat_user_tables.n_dead_tup` → `docs/session_context/session-162-vacuum-log.md`.

If a VACUUM stalls > 10 min: Ctrl-C (safe; VACUUM is restartable), note + skip, move to next. Failure here does NOT block the session.

**T0 snapshot** for Phase 6 (capture IMMEDIATELY after the last VACUUM commits, before any wait period):

```sql
-- Save to docs/session_context/session-162-t0-snapshot.md
SELECT blks_read, blks_hit, tup_returned, temp_files, temp_bytes,
       (SELECT now()) AS snapshot_at
  FROM pg_stat_database WHERE datname=current_database();
SELECT relname, heap_blks_read, heap_blks_hit, idx_blks_read, idx_blks_hit
  FROM pg_statio_user_tables ORDER BY heap_blks_read DESC LIMIT 12;
SELECT queryid, calls, total_exec_time, temp_blks_written
  FROM pg_stat_statements
  WHERE query LIKE '%current_gedcom_relationships%' OR query LIKE '%gedcom_relationships%';
```

**Commit**: `chore(db): Session 162 Phase 4 — VACUUM 5 bloat tables + T0 snapshot`
**/clear.**

---

## Phase 5 — App-side TTL audit (investigation; mutation only if hot bug found)

Steps:
1. Grep all GEDCOM readers in `app/`:
   - `grep -rn "supabase.table[\"\']gedcom_" app/`
   - `grep -rn "supabase.from_[\"\']gedcom_" app/`
   - `grep -rn "current_gedcom_" app/`
2. For each, check TTL cache wrapping (`@ttl_cache` or manual `_cache_ttl_secs`). GEDCOM data changes only on admin upload — anything < 300s TTL is suspicious.
3. Use `app/perf_cache.py` to add miss-count instrumentation (no new caches without explicit user OK).
4. Findings → `docs/session_context/session-162-cache-audit.md`.

Mutation only if a clear hot-loop offender is found.

**Commit** (code change): `perf(cache): Session 162 Phase 5 — <fix description>`
**Commit** (audit only): `docs(session-162): Phase 5 — cache audit findings`
**/clear.**

---

## Phase 6 — Measure + acceptance gate

T0 was captured at the end of Phase 4. Wait at minimum 60 minutes of organic traffic. Run other work during the wait (Phase 5 audit, or take a break).

T1 snapshot (same queries as T0):

```sql
SELECT blks_read, blks_hit, tup_returned, temp_files, temp_bytes, (SELECT now()) AS snapshot_at
  FROM pg_stat_database WHERE datname=current_database();
SELECT relname, heap_blks_read, heap_blks_hit, idx_blks_read, idx_blks_hit
  FROM pg_statio_user_tables ORDER BY heap_blks_read DESC LIMIT 12;
SELECT queryid, calls, total_exec_time, temp_blks_written
  FROM pg_stat_statements
  WHERE query LIKE '%current_gedcom_relationships%' OR query LIKE '%gedcom_relationships%';
```

Compute (T1 - T0) deltas. Save to `docs/session_context/session-162-final-metrics.md`.

Acceptance (ANY ONE = PASS):
1. Cache hit ratio on (T1 - T0) window ≥ 90%
2. `current_gedcom_relationships` mean_exec_time over (T1 - T0) calls < 100 ms
3. `gedcom_relationships` heap_blks_read per-minute on (T1 - T0) ≥ 80% lower than the 165-day rate
4. View OUT of top-3 in `temp_blks_written` ranking

If NONE met: STOP. Report numbers. User-decision gate:
- (a) Accept partial improvement; ship; follow-up next session
- (b) Approve Pro plan upgrade ($25-50/mo); separate user task
- (c) Phase 6b: investigate new top offenders in `pg_stat_statements`

Do NOT proceed to Phase 7 with unresolved acceptance.

**Commit**: `docs(session-162): Phase 6 — final metrics + acceptance gate <PASS|FAIL>`
**/clear.**

---

## Phase 7 — Codex audit (post-execution)

```bash
codex exec "Audit Session 162 commits for: correctness, safety, rollback completeness, test coverage, missed root causes. P0/P1/P2/P3." </dev/null
```

Fallback to Claude general-purpose subagent if `codex exec` hangs (Sessions 152/153/154/161 pattern).

Save → `docs/session_context/session-162-post-execution-audit.md` with provenance header.

Apply P0/P1 inline; P2/P3 → BACKLOG.

**Commit (if fixes)**: `fix(session-162): Phase 7 — Codex audit fixes`
**/clear.**

---

## Phase 8 — Closeout

1. `OD-014` in `docs/ops/OPS_DECISIONS.md`: "Disk IO Budget Remediation — view fix + dead-table DROP + VACUUM" with before/after numbers.
2. Lesson L198 in `tasks/lessons.md`: "Partial indexes silently defeated by `OR <pred> IS NULL` — audit views against index predicates."
3. CHANGELOG v0.99.81 → v0.99.82.
4. ROADMAP: pending 162 → 163 already renumbered pre-session; add Recently Completed entry.
5. SESSION_HISTORY entry.
6. `docs/assessments/session-162-assessment.md`.
7. `git push origin main`.
8. `curl https://rhodesli.nolanandrewfox.com/health` → 200.
9. Browser verify 6 canonical pages (read-only, Lesson 149).
10. `bash scripts/backup-memory.sh`.
11. `/session-review`.

Closeout commits (atomic per file group):
- `docs(ops): Session 162 — OD-014 Disk IO Budget remediation`
- `docs(lessons): Session 162 — L198 partial-index + OR IS NULL pitfall`
- `chore(release): Session 162 — v0.99.82 CHANGELOG`
- `docs(session-162): closeout — assessment + SESSION_HISTORY`
- `chore(memory): backup Session 162 memory updates`

---

## Anti-goals

- ❌ NO `VACUUM FULL` anywhere
- ❌ NO touching `gedcom_individuals_v2` or `gedcom_families_v2`
- ❌ NO automatic Supabase plan upgrade
- ❌ NO new TTL caches in Phase 5 without user OK
- ❌ NO production browser clicks (Lesson 149)
- ❌ NO Phase 1b before Phase 1a verified
- ❌ NO Phase 6 short-circuit (60 min wait minimum)

---

## Concerns to flag

- ALTER hangs > lock_timeout: investigate via `pg_stat_activity`, do not retry blindly
- Post-Phase-1a EXPLAIN Seq Scan: try ANALYZE; if still Seq Scan, check Supabase dashboard for Disk IO banner (Lesson 187)
- VACUUM stall: Ctrl-C is safe; skip + move on
- PGRST002 post-view-replace: per Lesson 187 may need dashboard restart; `SUPABASE_ACCESS_TOKEN` is in .env per Lesson 189
- Phase 1a EXPLAIN must accept Index Scan / Bitmap Heap Scan / Index Only Scan with the partial index — `SELECT *` cannot be index-only (heap cols needed)

---

## Test expectations

- `make test-fast` AND `pytest rhodesli_ml/tests/ -x -q` green at every commit (dual-test rule)
- New tests:
  - `tests/test_session162_view_definition.py` (static + live_db marker)
  - `tests/test_session162_relationship_fallback_filters.py` (raw-table fallback filter)
  - `tests/test_session162_identity_overrides_dropped.py` (if Phase 3 runs)
- `RUN_LIVE_DB_TESTS=1` env var gates live introspection tests
- No e2e tests touched
- Expected test count: 4313 → ~4318 (+5)

---

## Breadcrumbs

- Context: `docs/session_context/session-162-context.md`
- Predecessor: Session 161 (rhodes-inbox), v0.99.81
- 158e: `docs/assessments/session-158e-assessment.md`
- Lessons: 175 (pooler), 180 (worktree paths), 187 (Disk IO ↔ PGRST002), 188 (view deps before DROP), 189 (SUPABASE_ACCESS_TOKEN), 190 (5xx baseline)
- Ops: OD-011, OD-012, OD-013
- Rules: `.claude/rules/browser-read-only.md`, `.claude/rules/ai-tool-audit.md`, `.claude/rules/session-protocol.md`, `.claude/rules/dual-test-suites.md`
- Pre-execution audit: `docs/session_context/session-162-codex-audit.md` (to be written from the Codex output above)
