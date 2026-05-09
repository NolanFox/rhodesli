**Auditor**: Codex CLI (gpt-5.5, xhigh)
**Subject**: Session 157b commits 7e11642d..c553644c
**Date**: 2026-05-09
**Agent type**: Independent fresh context

# Independent Audit of Session 157b

Scope note: the requested command, `git log --oneline 7e11642d..c553644c`, returns 17 commits in this checkout (15 non-merge plus 2 merge commits), not 22. I reviewed the full returned range, with `git show` on code-changing commits: `f1f674d4`, `f1a8fe16`, `ed7949c8`, `385e7888`, `8047dbc8`, `52eaed38`, and `a8fa858a`.

## P0

None found. I did not find SQL injection reachable from request input, path traversal, hardcoded database passwords/API keys, or missing auth checks in data-modifying web routes.

## P1

1. **B2 dual-read is not safe under concurrent GEDCOM writes.** `gedcom_individuals_v2` and `gedcom_families_v2` are unique by `payload_hash`, not by GEDCOM id (`scripts/migrations/gedcom_v2_schema.sql:54`, `scripts/migrations/gedcom_v2_schema.sql:62`, `scripts/migrations/gedcom_v2_schema.sql:99`, `scripts/migrations/gedcom_v2_schema.sql:107`). The helper then queries v2 by `gedcom_id`/`family_gedcom_id` with `.limit(1)` and no `order()` (`app/gedcom_dual_read.py:53`, `app/gedcom_dual_read.py:57`, `app/gedcom_dual_read.py:132`, `app/gedcom_dual_read.py:135`). If a concurrent import creates a newer payload for the same id, v2 can contain both old and new payload rows; the helper may return the old row and never check v1 because any v2 row wins (`app/gedcom_dual_read.py:120`). This recreates the lesson-pattern family of local/production split-brain and schema drift: readers can silently prefer stale mirror data. Fix before cutover: read from a deterministic current-v2 view or order by `last_seen_version DESC, first_seen_version DESC, payload_hash`.

2. **B2 masks v2 failures, so cutover confidence can be false-green.** `get_individual()` catches all v2 exceptions, logs a warning, then falls back to v1 (`app/gedcom_dual_read.py:115`, `app/gedcom_dual_read.py:118`); family does the same (`app/gedcom_dual_read.py:177`, `app/gedcom_dual_read.py:180`). Only "relation missing" should be fallback-safe. Schema drift, permission/RLS failures, bad select columns, and server errors should be surfaced during the dual-read confidence window; otherwise production keeps working on v1 until Session 158 drops/renames it. The tests only assert PGRST205 fallback (`tests/test_dual_read_helper.py:110`) and do not cover fatal v2 errors.

## P2

1. **B1 catch-up can miss exact-boundary rows.** The script uses a strict `created_at > CUTOVER_TS` predicate (`scripts/session157_full_backfill_gedcom_v2.py:57`, `scripts/session157_full_backfill_gedcom_v2.py:140`). Because the initial Session 156 backfill timestamp was captured before the source SELECT (`scripts/session156_backfill_gedcom_v2.py:518`, `scripts/session156_backfill_gedcom_v2.py:544`), an import row committed at the same timestamp boundary can be excluded by both phases. The safer idempotent predicate is `>=` plus `ON CONFLICT`, or a high-watermark based on version id/version number.

2. **B1 family catch-up drops rich family fields for any future delta.** Initial Session 156 family backfill mapped `children_xrefs_json`, `marriage_event_json`, `events_json`, `notes_json`, and `citations_json` into v2 (`scripts/session156_backfill_gedcom_v2.py:341`, `scripts/session156_backfill_gedcom_v2.py:379`). The 157b catch-up only includes `family_gedcom_id`, spouses, `children_xrefs_json`, and maybe a non-schema `events_family_json` (`scripts/session157_full_backfill_gedcom_v2.py:306`, `scripts/session157_full_backfill_gedcom_v2.py:308`, `scripts/session157_full_backfill_gedcom_v2.py:315`). If post-cutover family rows appear, v2 receives default-empty marriage/events/notes/citations, a schema-drift data-loss risk hidden by the 0-row dry run.

3. **B3 timing evidence is weaker than the report claims.** The report header says 100 iterations per backend (`scripts/session157b_query_timing.py:227`), but bulk load and is-current paths run `max(iterations // 4, 10)`, which is 25 at the default (`scripts/session157b_query_timing.py:134`, `scripts/session157b_query_timing.py:190`), and the helper path runs 50 (`scripts/session157b_query_timing.py:380`). The p95 formula itself has no obvious off-by-one bug for 100 samples (`scripts/session157b_query_timing.py:78`), but p95 from 25 samples is high-variance and not a sound basis for GREEN cutover confidence. It is acceptable as smoke timing, not as statistical proof.

## P3

1. **B3 does not time the fallback path it relies on.** The helper benchmark uses ids sampled from v2 and documents that every call is a v2 hit (`scripts/session157b_query_timing.py:209`, `scripts/session157b_query_timing.py:221`). It does not measure v2-miss/v1-fallback latency or failure behavior, which is the path that matters if the mirror is incomplete.

2. **Dual-read tests miss production-shaped edge cases.** There is no test for duplicate v2 rows for the same `gedcom_id` with different `last_seen_version`, and no test that non-PGRST v2 errors fail closed instead of silently falling back. The field-selection test is also weak: it inspects `sb.table.return_value.select`, but the mock uses `sb.table.side_effect` to return per-table chain objects, so the assertion can pass without proving the actual select string (`tests/test_dual_read_helper.py:33`, `tests/test_dual_read_helper.py:42`, `tests/test_dual_read_helper.py:137`).

## Required Grades

- **B2 dual-read helper**: Not safe under concurrent writes; silent-failure paths present. Use ordered current-v2 reads and narrow fallback to expected "v2 unavailable" cases.
- **B1 catch-up backfill**: The stated no-op result is believable for 157b, but the strict boundary and family-field mapping make the script unsafe as the reusable catch-up tool it claims to be.
- **B3 query timing**: Good smoke check, not statistically strong. Actual sample sizes are 25/50 for several paths; p95 calculation is not the main bug, sample size/reporting is.
