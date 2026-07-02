---
name: supabase-migration-safety
description: >
  Safety protocol for ANY bulk Supabase/Postgres operation in rhodesli: imports, backfills,
  migrations, cutovers (RENAME/DROP/VACUUM), schema changes, and ≥50K-row reads/writes. Distills
  the Sessions 154–164 GEDCOM saga (a non-atomic importer bloated the DB to 1.3 GB and took the
  site down) plus the Session 158/162 cutover+disk-IO incidents. Load BEFORE writing or running
  any migration/import/cutover script, adding a partial index, or debugging pooler/PostgREST
  failures. DO NOT USE FOR: single-row app writes, ordinary feature queries, or JSON-file work.
---

# Supabase Migration Safety — bulk-operation discipline

## Why this skill exists (the scar tissue)
A batch importer that committed per-batch left full duplicate datasets on every failed retry —
7 of 9 GEDCOM "versions" were garbage, ~900 MB of it, and the DB grew past the free-tier 500 MB
limit and took production DOWN (Lessons 199/200, Sessions 163–164). Separately: a cutover lost a
day to pooler failures (L183), 16 zombie backends blocked DDL (L184), terminating them crashed
production (L185), and one `OR is_current IS NULL` clause defeated a partial index and consumed
73.9% of ALL disk reads for 165 days (L198).

## Triggers — WHEN to load
- Writing or modifying anything in `scripts/` that does bulk DB reads/writes, DDL, or cutover
- Any import/backfill ≥ ~10K rows; any RENAME/DROP/VACUUM; any new index (especially partial)
- Debugging: pooler timeouts, `PGRST002`, `statement timeout`, `lock_timeout`, 402/NXDOMAIN
WHEN NOT: single-row upserts in app routes; local JSON work; read-only analytics under 10K rows.

## Required reading
1. `tasks/lessons/deployment-lessons.md` — Lessons 183, 184, 185, 186, 200, 203
2. `tasks/lessons/harness-lessons.md` — Lessons 187–190, 198, 199, 201, 202, 204
3. `docs/architecture/GEDCOM_HISTORY.md` — the shipped atomic-importer reference design
4. `scripts/import_gedcom_version.py` — canonical atomic import (lock→diff→verify-R2→apply→COMMIT)
5. `docs/ops/OPS_DECISIONS.md` — OD-014/OD-015 context if touching plan/size limits

## The invariants
1. **Bulk imports are ONE transaction.** Failure = ZERO rows. Allocate version numbers and
   dedup source-hashes INSIDE the txn under `pg_advisory_xact_lock`. Never write a test that
   asserts partial rows survive a failed import (a test once institutionalized the bug — L199).
2. **Chunked-write for ≥50K rows:** read + aggregate + upsert ONE chunk (≤10K rows) at a time;
   never accumulate the full dataset in memory; 3-retry per chunk (L183).
3. **Connection discipline:** use the pooler (`aws-0-<region>.pooler.supabase.com`), session
   mode port 5432 for DDL (transaction mode 6543 has died for days at a time — AD-246). Direct
   `db.<ref>.supabase.co` is IPv6-only and often unreachable (L175). Long cursor scripts set
   `idle_in_transaction_session_timeout='5min'` (L184). psycopg2 named cursors have
   `.description = None` until first fetch (L204).
4. **REST reads page at 1000 rows.** `.select().execute()` silently truncates; loop
   `.range(offset, offset+999)` for any table ≥1000 rows (L173).
5. **Pre-DDL checklist:** (a) scan `pg_stat_activity` for old idle-in-transaction backends —
   but NEVER `pg_terminate_backend` on a hot production pool (it cascades into worker crashes —
   L185; use a maintenance window or redeploy first); (b) scan `pg_depend` for view dependents
   before DROP/RENAME — views auto-follow renames by oid (L188); (c) inside BEGIN:
   `SET LOCAL lock_timeout='30s'; SET LOCAL statement_timeout='0'` (Session 158d form).
6. **Snapshot before destroy.** R2/content-addressed snapshot with sha256 BEFORE any DROP or
   prune; archive the EXACT imported bytes, and verify an archive's hash matches the recorded
   `source_hash` before trusting it (L203). Migrate history from PRODUCTION current-state, not a
   re-parsed archive.
7. **Partial indexes:** any `WHERE`/view/fallback touching the indexed column must match the
   index predicate exactly — `OR col IS NULL` silently forces full scans (L198). Prefer
   `SET NOT NULL` to structurally prevent re-introduction; audit ALL views + REST callers.
8. **Baseline before cutover; abort on the DELTA.** Capture `/health` first. If production is
   already 5xx from the problem the cutover fixes, rolling back on "still 5xx" locks in the
   failure (L190). PGRST002 after DDL: check the Supabase dashboard disk-IO banner FIRST — it is
   usually resource exhaustion, not a stuck schema cache (L187).

## Verification gates (ALL before any production run)
1. **Independent-model audit of the ACTUAL script** (Codex CLI per `.claude/rules/ai-tool-audit.md`,
   or a fresh-context subagent) — treat BLOCK as a hard stop; fix all P0/P1 and re-audit until
   SAFE TO RUN. This gate caught a lossy diff-base and an executable KeyError that would have
   shipped a broken history layer (L202).
2. Dry-run mode exists and was run; row-count deltas printed and sanity-checked.
3. Structural test: a deliberately-failed import leaves zero rows.
4. Rollback path proven: unwind/restore script exists and was exercised against the dry-run.
5. Post-run: verify counts via SQL AND the production page renders (a reader repointed to a
   dropped view fails closed to `None` — a silent quality regression, not an error; L205: grep
   every dropped table/view/column across `scripts/ app/ rhodesli_ml/` after schema changes).

## Anti-patterns (hard NOs)
- Per-batch commits in an import ("resume where it failed" = duplicate-row factory).
- `pg_terminate_backend` while the app is serving traffic.
- Trusting `--collect-only`, mocks, or local green for schema compatibility (L105/152/208 —
  run the real path on ONE production item and verify the side effect).
- VACUUM FULL through the app's live window (AccessExclusiveLock; Session 158e proved it).
- Reducing DB size and assuming a Fair-Use 402 lifts mid-cycle — it lifts only on upgrade or
  billing reset (L200). Free-tier has THREE independent limits: disk-IO, egress, DB size.

## Escalation (user-gated — never execute autonomously)
DROP of any production table, VACUUM FULL, plan upgrades/downgrades, `--execute` on any
migration, terminating backends, or anything irreversible without a verified snapshot.
