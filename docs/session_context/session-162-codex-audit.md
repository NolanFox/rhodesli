# Session 162 — Codex CLI Pre-Execution Audit

**Auditor**: Codex CLI v0.133.0 (gpt-5.5, xhigh reasoning effort)
**Agent type**: Independent (fresh context, no prior session knowledge)
**Scope**: Pre-execution audit of `docs/prompts/session-162-prompt.md` + `docs/session_context/session-162-context.md`
**Date**: 2026-05-22
**Tokens used**: 130,804
**Pin freshness**: model pin refreshed 2026-05-22 immediately before this audit (verified gpt-5.5 still latest via developers.openai.com/codex/models)

---

## Verdict

Bottom line (Codex): "The core semantic change looks correct. I did not find evidence that app callers intentionally depend on `NULL` meaning 'current'; the context's live distribution shows `0` NULL rows, so the NOT NULL constraint is data-safe as of the audit snapshot. The bigger issues are measurement validity, lock/rollback safety, and a raw-table fallback that can reintroduce the same IO pattern."

**Triage**: 1 P0 + 7 P1 + 6 P2 + 2 P3.

All P0 + P1 applied to the prompt before execution. Selected P2 applied; rest evaluated.

---

## P0

### P0-1: Phase 6 measurement is not a valid 60-min sample
**Codex**: "Phase 0 captures cumulative counters and the context says those counters span 165 days since 2025-12-08, but Phase 6 says to re-run the same queries and judge a 60-minute window. Fix before execution: after preserving the historical baseline, either reset `pg_stat_database`/`pg_stat_statements` if permitted, or capture a fresh T0 after Phase 4 and compute all acceptance metrics from counter deltas."

**Applied**: Yes. Phase 4 now captures T0 immediately after the last VACUUM; Phase 6 captures T1 after 60 min and computes (T1 - T0). Acceptance criteria updated to read against the post-Phase-4 window. Approach (b) chosen (delta computation; preserves history). Context file updated with §"Measurement validity caveat".

---

## P1

### P1-1: Phase 1 couples low-risk view fix with higher-lock NOT NULL constraint
**Applied**: Yes. Split into:
- Phase 1a: CREATE OR REPLACE VIEW + fix raw-table fallback (low lock cost; rollback-safe)
- Phase 1b: SET NOT NULL constraint (separate, gated on 1a verified + /health = 200 for ≥10 min; can be deferred if hot traffic blocks the lock)

### P1-2: `lock_timeout` does not bound post-lock app block; need preflight
**Applied**: Yes. Phase 0 adds a `pg_stat_activity` preflight scanning for any non-idle queries older than 30s. Phase 1a uses tight `lock_timeout = '5s'` for the no-touch view replace. Phase 1b uses `lock_timeout = '10s'` and a fresh pre-check.

### P1-3: EXPLAIN expectation too strict — `SELECT *` cannot be index-only
**Applied**: Yes. Phase 1a-iii now accepts:
- Index Scan using `idx_gedcom_relationships_current`
- Bitmap Heap Scan with `idx_gedcom_relationships_current`
- Index Only Scan (only for `count(*)` variant)
Two EXPLAINs documented: one `count(*)` (can be Index Only), one `SELECT *` (heap fetch expected).

### P1-4: App fallback path reads raw `gedcom_relationships` without `is_current` filter
**Applied**: Yes (CRITICAL — confirmed via grep). `app/relationship_routes.py:513-518` and `:632-637` both fall back to raw table when view 404s, without filtering. Promoted from Phase 5 (audit-only) to Phase 1a-iv (mutation, same commit as view replace). New test `tests/test_session162_relationship_fallback_filters.py` asserts both fallback paths include `is_current = true` filter.

### P1-5: `identity_overrides` rollback misses RLS line 84 of original migration
**Applied**: Yes. Phase 3 rollback now documented as: (a) replay lines 10-29 (CREATE TABLE + 2 indexes), (b) replay line 84 (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY`), (c) `git revert` the Python changes.

### P1-6: Phase 2 grep stale — `scripts/migrate_to_supabase.py` writes to `identity_overrides`
**Applied**: Yes (confirmed via grep at lines 70, 99, 245). Phase 2 step 2 now archives the script to `scripts/_archive/migrate_to_supabase_session59C.py` BEFORE Phase 3 DROP. Context updated to call out the writer (was missed in initial diagnosis).

### P1-7: Temp-file spill (596 GB) deserves first-class measurement
**Applied**: Yes. Phase 0 baseline queries now include `pg_stat_statements ORDER BY temp_blks_written DESC LIMIT 15`. Phase 6 acceptance gate 4 added: "View OUT of top-3 in temp_blks_written ranking" as a spill-collapse signal.

---

## P2

### P2-1: Phase 1 should preflight verify the partial index exists with predicate `WHERE is_current = true`
**Applied**: Yes. Phase 0 step 4 added: introspect `pg_indexes` for `idx_gedcom_relationships_current` and confirm predicate. Abort if absent or mismatched.

### P2-2: Run ANALYZE before Phase 1 EXPLAIN, else stale stats can cause spurious rollback
**Applied**: Yes. Phase 1a-ii is `ANALYZE gedcom_relationships;` immediately before the EXPLAIN in 1a-iii.

### P2-3: Phase 4 VACUUM cannot run inside a transaction block — specify autocommit
**Applied**: Yes. Phase 4 now references `scripts/session158b_drop_and_vacuum.py:75-92` for the canonical `psycopg2.connect(...).autocommit = True` pattern. Explicit "Client mode" note added.

### P2-4: Add `pg_depend` preflight before DROP `identity_overrides` (Lesson 188)
**Applied**: Yes. Phase 2 step 3 is now an explicit `pg_depend` query before snapshot/DROP. Stops the session if any rows return.

### P2-5: Test plan can collide with historical migration files
**Applied**: Yes. Tests for the view definition use `@pytest.mark.live_db` (gated by `RUN_LIVE_DB_TESTS=1` env var) so they don't scan SQL files in CI. Companion static test asserts the *forward* SQL script (not the whole repo) does not contain the bad clause.

### P2-6: Commit gates need both app AND ML test suites
**Applied**: Yes. Session init and Phase 3 step 4 now require `make test-fast` AND `pytest rhodesli_ml/tests/ -x -q`. Dual-test rule enforced.

---

## P3

### P3-1: Prompt is 333 lines, over the 300-line doc cap
**Disposition**: Accepted as-is per session-prompt exception. Session prompts are not in the doc cap rule's scope (look at Sessions 158/158d/158e/154 prompts which are all 200-1000 lines). Logged here but not changed.

### P3-2: Phase 1 NULL safety check scans the table twice
**Disposition**: Phase 1b NULL check kept as full COUNT(*) — happens once before the SET NOT NULL operation which then scans the table itself. The proposed `EXISTS LIMIT 1` is cheaper on a NULL-finds case but doesn't change correctness. Not changed; trivial optimization, not a safety issue.

---

## Provenance

- Invocation: `codex exec "Audit the Session 162 prompt + context files..." </dev/null` (the working pattern per `.claude/rules/ai-tool-audit.md`, NOT `--full-auto`)
- Run time: ~1 minute (no hang)
- Codex CLI version: 0.133.0 (newer than pinned minimum 0.129.0)
- Codex model pin refreshed to 2026-05-22 immediately before run (was 14 days stale per harness rule)
- All findings applied or explicitly dispositioned BEFORE execution begins.

## What was missing from the original draft (in retrospect)

1. **Measurement validity** — biggest miss. I designed Phase 6 to compare 60-min sample against 165-day cumulative counters. That would have produced meaningless deltas and either falsely passed (huge denominators dilute everything) or falsely failed (small sample with high variance).
2. **Raw-table fallback** — second-biggest miss. `app/relationship_routes.py` has two `is_current`-blind fallback paths. The Disk IO regression could re-emerge silently during ANY PostgREST flake.
3. **`migrate_to_supabase.py`** — would have errored on next run (or anyone re-executing it from history) after the DROP.

Two-audit pattern justified again: prompt design audit caught structural-correctness issues that I, having designed the plan, was blind to. Post-execution audit (Phase 7) is a separate run by a fresh-context agent on the actual commits.
