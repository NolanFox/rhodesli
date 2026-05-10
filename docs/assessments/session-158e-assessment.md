# Session 158e Assessment

**Mode**: implementation
**Date**: 2026-05-10 (session opened ~03:53Z, work in progress)
**Predecessor**: Session 158d (`docs/assessments/session-158d-assessment.md`)
**Critical context inherited**: production 502 from PGRST002, DB at 2,564 MB hitting Disk IO budget

## Shipped (in progress — final list pending VACUUM completion)
- [x] **1A-PRE diagnosis**: Confirmed PGRST002 schema cache stuck across 3/3 REST trials. Aggressive `NOTIFY pgrst, 'reload schema'` + `pg_notify('pgrst', 'reload config')` issued via fresh autocommit psycopg2 connection — did NOT recover the cache. Reproduces 158d finding that NOTIFY alone is insufficient when PostgREST is wedged.
- [x] **Disk IO budget root cause** (NEW vs 158d diagnosis): Supabase dashboard banner showed "Project is depleting its Disk IO Budget" with grace period to 2026-05-28. PGRST002 was a *symptom* of disk-IO throttling on `pg_catalog` schema introspection queries — not just PostgREST being stuck. Lesson 186.
- [x] **Management API token**: User generated `sbp_...` token. Added `SUPABASE_ACCESS_TOKEN` to `.env` (gitignored). Placeholder added to `.env.example`. Verified via `GET /v1/projects` (project status `ACTIVE_HEALTHY`) and `GET /v1/projects/{ref}/postgrest` (DB-admin scope confirmed). Commit `3c7409cf`.
- [x] **Phase 158e-0 — DB state verify**: v1 alive 3/3, `_dropped_*_session158` 0/3, v2 dedicated 2/2 + shared `gedcom_change_manifest` (effectively 3/3). DB size 2,564 MB.
- [x] **Phase 158e-1 — Zombie scan**: 0 idle-in-transaction (any age), 0 long-running activity. 158d's termination cleared the slate; no new accumulation.
- [x] **Phase 158e-2 — USER GATE**: User chose PROCEED (production already in forced 502 maintenance window).
- [x] **Phase 158e-3 — Cutover RENAME**: Executed cleanly. v1 alive → 0/3, `_dropped_*_session158` → 3/3, v2 unchanged. Lock_timeout patches from 158d held. No cascade, no zombies created.
- [x] **Phase 158e-4 — Post-RENAME stability**: 90s mini-wait. Pooler 3/3 PASS (500-600ms latency). Zero zombies, zero blocked locks on v2 tables. Albert Fox 2-state acceptance check PASSED (v9 hash=1d77bf67 + v1-v6 hash=fd1f05bd — identical to 158c). v2 views 1:1 sanity (21,998 distinct gedcom_id = view rows). NOTE: query latency erratic (9.5s/2.2s/35.3s) confirming severe disk-IO throttling — strong motivation for DROP+VACUUM.
- [x] **Phase 158e-5 first attempt**: DROP failed at table 2/3 — `current_gedcom_families` view depended on `_dropped_gedcom_families_session158`. Script's transactional gate held: all-or-nothing (1st DROP rolled back). State preserved. Diagnosis: cutover_forward dropped `current_gedcom_individuals` but missed the paired `current_gedcom_families` view.
- [x] **Bug fix**: Patched `scripts/session158b_cutover_rename.py` `cutover_forward()` to drop both views (`DROP VIEW IF EXISTS current_gedcom_individuals` + `... current_gedcom_families`). Rollback path documented but not auto-recreating families view (v1 schema retired, exact WHERE clause unverified — operator can recreate manually if rollback needed).
- [x] **Manual unblock**: Dropped `current_gedcom_families` directly (DROP VIEW IF EXISTS), confirmed zero remaining dependents.
- [-] **Phase 158e-5 retry**: DROP+VACUUM running (in progress at time of writing). Expected: 2,564 MB → 600-700 MB.

## Pending
- [ ] **Phase 158e-5 completion**: VACUUM FULL on v2 + 4 carry-over v1 tables.
- [ ] **PostgREST recovery**: After disk freed by VACUUM, restart via Management API (`POST /v1/projects/{ref}/restart-services` or equivalent). Expect schema cache rebuild within ~30-60s.
- [ ] **Phase 158e-2 production /health = 200**: Trigger Railway redeploy if needed (workers may still hold zombie pool refs).
- [ ] **Phase 158e-6 — Browser verify**: 6 canonical pages READ-ONLY.
- [ ] **Phase 158e-7 — Closeout**: CHANGELOG, ROADMAP, BACKLOG, SESSION_HISTORY, lessons learned.

## Lessons learned (drafts — finalize at closeout)
- **L186 NEW**: Disk-IO budget exhaustion presents as PGRST002 (schema cache failure). Misdiagnosable as PostgREST-stuck-in-retry-loop. Diagnosis: check Supabase dashboard for "depleting its Disk IO Budget" banner BEFORE attempting `NOTIFY pgrst`. NOTIFY won't help if the root cause is upstream throttling on `pg_catalog`.
- **L187 NEW**: Cutover scripts that DROP TABLE must enumerate dependents via `pg_depend` BEFORE DROPs. PostgreSQL views auto-follow base-table renames (oid-tracked) so the view continues to point at the renamed `_dropped_*` table and blocks DROP. Pre-flight scan: `SELECT … FROM pg_depend JOIN pg_rewrite … WHERE refobjid = ANY(...)::regclass[]`. Add `DROP VIEW IF EXISTS` for each found dependent inside the cutover transaction.
- **L188 NEW**: Supabase Management API personal access tokens (`sbp_...`) are necessary for programmatic project recovery (restart, schema reload). Service-role keys cannot perform these operations. Add `SUPABASE_ACCESS_TOKEN` to `.env` at project setup, not when broken.
- **L184/185 confirmed in this session**: Zombie cascade (185) was avoided by leveraging the forced-maintenance state (production already 502 from PGRST002). Proves the maintenance-window pattern works.

## Red flags
- **Cutover script pre-flight gap**: `assert_drop_gate_safe()` checks for table existence but does NOT scan `pg_depend` for dependent objects. The DROP will fail at runtime if any view follows the rename. Recommend adding a `pre_drop_dependency_scan()` function for future cutover-style migrations.
- **Disk IO budget**: even after VACUUM relieves immediate pressure, the root cause (free-tier limit) returns. Long-term solutions: (a) Pro plan upgrade, (b) further data reduction, (c) move heavy tables to R2-as-cold-storage.
- **Production app vs. PostgREST**: production crashes on registry load when REST returns PGRST002. Consider hardening `core/registry.py` `load_from_postgres` to gracefully degrade (serve stale cache) rather than crash the app on REST 5xx during temporary outages.

## Next session should verify FIRST
1. Production `/health` returns 200 over 1 minute (3 sequential 200s).
2. Browser verify 6 canonical pages.
3. DB size has stabilized at ~600-700 MB (or whatever post-VACUUM target was achieved).
4. PostgREST schema cache responding normally (REST API trial 3/3 PASS in <1s).
5. No new disk-IO budget banner on Supabase dashboard.
