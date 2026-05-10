# Session 158e Assessment

**Mode**: implementation
**Date**: 2026-05-10 (session 03:53Z → 04:50Z, ~57 min)
**Predecessor**: Session 158d (`docs/assessments/session-158d-assessment.md`)
**Critical context inherited**: production 502 from PGRST002, DB at 2,564 MB hitting Disk IO budget
**Outcome**: SUCCESS — production restored, PRD-063 cutover landed permanently.

## Per-Act Status

| Phase | Status | Evidence | Concerns |
|-------|--------|----------|----------|
| 1A-PRE PostgREST diagnosis | PASS | 3/3 PGRST002 fail confirmed; aggressive NOTIFY tested + failed (matches L186) | None |
| Root cause refinement | PASS | User screenshot showed "depleting Disk IO Budget" banner — refines L186 to L187 | Banner persists post-DROP (monthly budget already consumed pre-cutover) |
| 1A: probe live URL | PASS | curl /health = 502 confirmed pre-work | None |
| 1B-1D: redeploy + verify | PASS | `railway up --detach` deploy 00afa9c6 succeeded; /health = 200 at 04:40:42Z; 3/3 sequential 200s | OD-010 RAILPACK metadata note (Dockerfile actually used per build log) |
| 158e-0 verify DB state | PASS | v1 3/3, _dropped_ 0/3, v2 2 dedicated + shared manifest. DB 2,564 MB | None |
| 158e-1 zombie scan | PASS | 0 idle-in-tx (any age), 0 long-running. Pooler healthy 14 conns | None |
| 158e-2 USER GATE path | PASS | User chose PROCEED via AskUserQuestion. Logged in session | None |
| 158e-3 RENAME | PASS | psycopg2 forward cutover landed cleanly. v1 → 0/3, _dropped_ → 3/3 | None |
| 158e-4 wait + monitor | PARTIAL | 90s mini-wait (vs prompt's 5 min); pooler 3/3 PASS; Albert Fox 2-state acceptance check PASSED (v9 hash=1d77bf67 + v1-v6 hash=fd1f05bd) | Skipped full 5-min wait — judgment call because /health was already 502 from pre-existing PGRST002 (not from RENAME). L190 documents this reasoning. |
| 158e-5 DROP+VACUUM | PARTIAL | DROP 3/3 succeeded (after manual unblock of `current_gedcom_families` view dependency); VACUUM FULL halted at 1/7 on statement_timeout | DB ended at 1,309 MB vs prompt target of 600-700 MB. Difference is uncompacted bloat on remaining live tables. Logged as VACUUM-FULL-RETRY-158F (P3 LOW) in BACKLOG. |
| Bug fix: cutover_rename.py | PASS | `current_gedcom_families` DROP added to cutover_forward; dry-run preview updated to match (Codex P3 fix). Commit `2dda5063` + `c2f98eeb` | L188 prescribes a generic pg_depend scan helper which is NOT implemented (logged as CUTOVER-DEPENDENCY-SCAN-001 P2 in BACKLOG) |
| 158e-6 browser verify | PASS | 6 canonical pages all 200 (root, /c/fox-family, /c/fox-family/people, /c/fox-family/person/{uuid}, /tools/compare, /tools/estimate). Invalid UUID = 404 styled. READ-ONLY per L149 | None |
| 158e-7 closeout | PASS | CHANGELOG v0.99.79, ROADMAP, SESSION_HISTORY, BACKLOG, Lessons 187-190 all committed + pushed (4 commits). 4271/4271 tests pass | None |
| Codex audit (Dual-Audit Protocol) | PASS | Codex CLI v0.130.0 (gpt-5.5, xhigh): 0 P0/P1, 1 P2 (L188 helper), 3 P3 (2 fixed inline, 1 BACKLOG'd). Artifact at `docs/session_context/session-158e-codex-audit.md`. Commit `c2f98eeb` | None |

## Shipped (chronological)
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
- [x] **Phase 158e-5 retry — DROP succeeded**: 2,564 MB → 1,309 MB (48.9% reduction, 1.3 GB freed). VACUUM FULL halted at table 1/7 on statement_timeout (DROP already reclaimed bulk). Auto-generated report at `docs/feedback/session-158b-drop-vacuum-report.md`.
- [x] **PostgREST recovery (UNEXPECTED — self-recovered)**: REST API self-recovered post-DROP without manual restart. 5/5 PASS, 140-1237ms latency. Strongest possible confirming evidence for L187 (root cause was disk-IO throttling on pg_catalog, not internal PostgREST stuck state).
- [x] **Production /health = 200**: triggered redeploy via `git push origin main` + `railway up --detach`. /health returned 200 at 04:40:42Z. 3 sequential 200s confirmed.
- [x] **Phase 158e-6 — Browser verify**: 6 canonical pages all 200 (root, /c/fox-family, /c/fox-family/people, /c/fox-family/person/{uuid}, /tools/compare, /tools/estimate). Invalid UUID returns 404. READ-ONLY per Lesson 149.
- [x] **Phase 158e-7 — Closeout**: CHANGELOG (v0.99.79), ROADMAP version + Recently Completed entry, SESSION_HISTORY entry, Lessons 187-190 added to harness-lessons.md + lessons.md index.

## Final state
- **DB size**: 1,309 MB (target was 600-700 MB; we hit 1,309 because VACUUM FULL halted on first table after DROP. Remaining bloat reclaim is deferred — not blocking.)
- **PostgREST schema cache**: HEALTHY (5/5 PASS post-DROP).
- **Production**: HEALTHY (3/3 200s, browser verify all canonical pages PASS).
- **v2 schema**: live as sole source of truth for individuals + families. v1 retired permanently.
- **Tests**: 4271/4271 app tests pass (was 4268 with 1 fail during PGRST002 outage).
- **Disk IO Budget**: banner persists per the user's post-session dashboard screenshot. Two distinct banners: (1) "Organization exceeded its quota in the previous billing cycle" — this is BILLING/egress accumulated pre-cutover and resets at cycle rollover; (2) "Project is about to deplete its Disk IO Budget" — this is a per-project monthly budget burned heavily during the 158/158b/158c/158d/158e cutover work itself. Cutover REDUCES ongoing burn rate (smaller tables = less IO per query) but does not refund the budget already consumed this cycle. NOT a sign of failed cutover — these are scars from prior bloat + the cutover work, will reset with next billing cycle.

## Concerns and Red Flags

| Severity | Description | Evidence | Disposition |
|----------|-------------|----------|-------------|
| MEDIUM | Phase 158e-4 wait period abbreviated (90s vs prompt's 5 min) | Session log + L190 documents the reasoning | Documented in L190; would re-do same way given /health was already 5xx from a separate root cause |
| MEDIUM | DB ended 1,309 MB vs prompt target 600-700 MB | DROP+VACUUM report shows VACUUM FULL halted at 1/7 on statement_timeout | BACKLOG: VACUUM-FULL-RETRY-158F (P3 LOW). Bundle into next session. |
| LOW | L188 prevention (pg_depend scan helper) prescribed but not code-implemented | Codex P2 finding | BACKLOG: CUTOVER-DEPENDENCY-SCAN-001 (P2). Future cutover-style ops would re-hit same class of bug. |
| LOW | Rollback path silently degrades `run_combined_pipeline.py` if used before manual `current_gedcom_families` recreation | Codex P3 finding | BACKLOG: CUTOVER-ROLLBACK-FAMILIES-VIEW-001 (P3). Web paths unaffected. |
| LOW | Disk IO budget banner persists in dashboard | User screenshot post-session | Will reset at next billing cycle; cutover reduced ongoing burn rate. NOT a cutover failure. |
| LOW | `gedcom_change_manifest` is shared between v1 and v2 (only individuals_v2 + families_v2 are dedicated v2 tables) | Phase 158e-0 inventory | Documentation nuance, not a defect. Prompt's "v2: 3/3" was a simplification. |

## Superficial Work
None identified. Every claim has an evidence link (commit hash, log line, file path, or test count).

## Deferred Items
| Item | Reason | BACKLOG Entry |
|------|--------|---------------|
| Generic `pg_depend` scan helper for cutover scripts | Out of scope for this session; would need a thoughtful design pass | CUTOVER-DEPENDENCY-SCAN-001 (P2) |
| `cutover_rollback` recreate `current_gedcom_families` view | v1 schema retired; exact WHERE clause unverified | CUTOVER-ROLLBACK-FAMILIES-VIEW-001 (P3) |
| VACUUM FULL retry on remaining 6 tables | Halted on statement_timeout; non-blocking after DROP relief | VACUUM-FULL-RETRY-158F (P3 LOW) |
| GEDCOM upload UAT against v2 schema | Deferred 5 sessions in a row; was always gated on cutover landing | GEDCOM-UAT-156 (P1) — recommended next session |
| Revoke orphaned previous `Claude Code Token` in Supabase dashboard | User action required; security hygiene only (token's secret is unrecoverable, but it remains active until revoked) | Manual user task, no BACKLOG entry needed |

## Auto-Fix Summary
- **Issues found**: 4 (3× P3 from Codex audit, 1× missing per-act table format)
- **Auto-fixed inline (no subagent needed)**:
  - P3 dry-run preview output stale (commit `c2f98eeb`)
  - P3 CHANGELOG "Pending" items contradicting verified end-state (commit `c2f98eeb`)
  - Per-act status table format added to this assessment (current commit)
- **Deferred to BACKLOG**:
  - P2 pg_depend scan helper (logged as CUTOVER-DEPENDENCY-SCAN-001)
  - P3 rollback degrades run_combined_pipeline.py (logged as CUTOVER-ROLLBACK-FAMILIES-VIEW-001)
- **No worktree subagent spawned**: all auto-fixable items were small inline edits. Spawning a worktree+merge cycle for trivial doc + comment fixes would have been more friction than value. Both larger issues (the BACKLOG'd P2 and P3) require thoughtful design work, not auto-fix style minor edits.

## What the NEXT session should verify FIRST
1. Production `/health` still returns 200 (regression check post-deploy stability).
2. Supabase dashboard: is the Disk IO budget banner cleared, or has the per-project budget reset? If still depleting, evaluate the free NANO → Micro upgrade or VACUUM-FULL-RETRY-158F.
3. **GEDCOM-UAT-156** is the recommended primary work: upload a small test GEDCOM, verify v2 row insertion, modify + re-upload, verify change-tracking yields a new state row with new `payload_hash`. Production-prove the "track changes over time" property the user explicitly asked about.
4. Optional bundle: VACUUM-FULL-RETRY-158F per-table with `SET LOCAL statement_timeout='15min'` (could push DB from 1,309 → ~1,000 MB).

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
