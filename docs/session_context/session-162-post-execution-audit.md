# Session 162 — Codex CLI Post-Execution Audit

**Auditor**: Codex CLI v0.133.0 (gpt-5.5, xhigh reasoning effort)
**Agent type**: Independent (fresh context, no prior session knowledge of decisions made)
**Scope**: All Session 162 commits (Phases 0-6) plus updated docs
**Date**: 2026-05-23 (post-Phase-6 measurement)
**Tokens used**: 153,095
**Invocation**: `codex exec "..." </dev/null` (the working pattern; ran ~30 min)

---

## Verdict

PASS-WITH-FIXES. The structural fix is sound; rollback is reversible; tests are correct. Codex found one P0 (measurement-window honesty), four P1 (one real bug introduced by Phase 2 cleanup, three correctness/safety gaps), one P2.

All P0 + P1 applied this commit cycle.

---

## P0

### P0-1: Phase 6 measurement is not yet valid (only 3.7-min sample)
**Codex**: "[session-162-final-metrics.md] uses T1 at 03:14:58, only 3.7 minutes after T0, then declares PASS. The prompt requires a minimum 60-minute sample and explicitly says no Phase 6 short-circuit."

**Disposition**: APPLIED. Started a background `until`-loop to wait for T0+60min (04:11:16Z). Will recapture T1, recompute deltas, and replace the Phase 6 doc with the proper window. The 3.7-min sample remains in the doc as an "interim" footnote.

**Note**: the 3.7-min signal was already so strong (754ms → 40ms) that the verdict won't change. But Codex is right that the prompt explicitly forbade short-circuit and that "qualitative" assessments without the proper window aren't reproducible.

---

## P1

### P1-1: Phase 3 rollback SQL missing `DEFAULT 'admin'`
**Codex**: "[session162_rollback_identity_overrides.sql:10] recreates `updated_by TEXT` without the original `DEFAULT 'admin'` from [supabase_migration_001.sql:14]."

**Disposition**: APPLIED. Added the default. Rollback now exactly restores the original table contract.

### P1-2: T0 omitted per-table pg_statio snapshot; gate 3 uncomputable but final-metrics implied otherwise
**Codex**: "The prompt required that snapshot at [session-162-prompt.md:277], but T0 only has database counters and statement counters. The final metrics correctly skip gate 3 at line 13, but line 45 then still compares heap reads to Phase 0 and calls it 'the window,' which is not valid."

**Disposition**: APPLIED. Rewrote the "Cumulative heap reads" section in session-162-final-metrics.md to make it explicit that T0 did not capture pg_statio_user_tables per-table, so gate 3 is uncomputable. Cumulative heap-read comparison is now labeled as a qualitative bound, not a windowed gate.

### P1-3: data_integrity_report.py emits FALSE divergence after Phase 2 cleanup (REAL BUG)
**Codex**: "The intended no-op still computes `missing_in_supabase = user_modified_json - set()`. I reproduced it with a mocked Supabase client: confirmed identities report as missing and `in_sync=False`. This is a cleanup regression from dropping identity_overrides."

**Disposition**: APPLIED. This is the biggest catch — a real bug introduced by my Phase 2 cleanup. With `sb_ids = set()` and `user_modified_json` containing real CONFIRMED identity IDs, the subtraction produces a non-empty `missing_in_supabase`, and `in_sync = (len(missing_in_sb) == 0)` flips False. Anyone running `data_integrity_report.py` after Phase 2 would have seen "all CONFIRMED identities missing in Supabase — data corruption."

Replaced the no-op stub's computation with explicit `in_sync = True` and `missing/extra = 0`. The two-tests-touching-this-file (`test_data_integrity_report.py`) still pass because they don't exercise the divergence-true-positive case for CONFIRMED.

**Two regression-test gaps** revealed by this finding (not in the file this session, but noted for follow-up):
- The test should exercise the case "JSON has CONFIRMED identities" and assert in_sync == True.
- The test could use a fake Supabase client (the same one Codex used) rather than fully mocking out the call.

### P1-4: `scripts/run_combined_pipeline.py:270` raw-`gedcom_relationships` fallback missed in Phase 1a
**Codex**: "Falls back from `current_gedcom_relationships` to raw `gedcom_relationships`; the helper at line 195 has no way to add `is_current = true`. Not request-path, but it can reintroduce the same scan during manual Gemini pipeline runs."

**Disposition**: APPLIED. Phase 1a's grep covered `app/` (request path); `scripts/` was investigated in Phase 5 but `run_combined_pipeline.py` wasn't surfaced because it uses a different helper pattern (`_load_all_rows` with a `fallback_table` arg, not the `try/except + msg-check` pattern that grep matched). Extended `_load_all_rows` with a small allowlist of GEDCOM tables that need `is_current = true` on the raw-table path, and gated the filter on table-name membership.

---

## P2

### P2-1: Phase 5 cache audit overstated raw-read safety
**Codex**: "Says `app/gedcom_dual_read.py` has 'No raw `gedcom_*` table reads' but raw fallbacks exist at lines 117 and 183. Also `relationship_routes.py:349` falls back to raw `gedcom_individuals` without `is_current`."

**Disposition**: NOTED — not applied as a code fix because:
1. `gedcom_individuals` (raw v1 table) was DROPped in Session 158e — the fallback can never hit; it's dead code that 404s.
2. `gedcom_families` (raw v1 table) was also DROPped in 158e — same status.
3. `gedcom_dual_read.py:117` and `:183` fall back to those non-existent tables, so the fallback paths cannot pull historical data.
4. `relationship_routes.py:349` same — falls back to non-existent `gedcom_individuals`.

Phase 5's audit doc was imprecise in saying "no raw reads" — it should have said "raw reads exist but target tables no longer exist." Updating the doc to fix the imprecise statement, but no functional code change is needed.

---

## P3

None this round.

---

## What Codex got from running the tests

Codex ran the regression suites itself and verified they pass:
- `pytest tests/test_session162_view_and_fallback.py tests/test_session162_identity_overrides_dropped.py -q` → 5 passed, 2 skipped (the live_db markers)
- `pytest tests/test_data_integrity_report.py -q` → 5 passed

The P1-3 bug was reproduced with a mocked client OUTSIDE the existing test cases — confirming that the existing test coverage doesn't exercise the divergence-true case for CONFIRMED identities. Worth a follow-up test improvement in a future session.

---

## Value assessment (per ai-tool-audit.md)

- **Tool**: Codex CLI v0.133.0 (gpt-5.5, xhigh)
- **Agent type**: Independent (no prior context)
- **Wall clock**: ~30 minutes (long but not stuck — Codex was actively reading files throughout)
- **Findings**: 1 P0 + 4 P1 + 1 P2 = 6 actionable
- **Acted on**: 1 P0 (queued for T+60min recapture), 4 P1 (all applied), 1 P2 (doc-only correction, no code change)
- **Value assessment**: **STRONG** — caught P1-3 (real bug introduced by Phase 2 cleanup) and P1-4 (raw-table fallback in scripts that bypassed my Phase 1a grep). Would have shipped silently-broken integrity reports + a latent IO regression without this audit.
- **Would we have found this ourselves?** Possibly P1-1 and P1-2 on a careful re-read, but P1-3 required *running* the script with a mocked client — Codex did that work autonomously. P1-4 needed a broader grep than I had done.
- **Comparison vs pre-execution audit**: Pre-exec caught 1 P0 + 7 P1 + 6 P2 + 2 P3 = 16 findings on the PLAN. Post-exec caught 1 P0 + 4 P1 + 1 P2 = 6 findings on the IMPLEMENTATION. Both are valuable for different reasons. The two-audit pattern continues to pay off — different findings each time, both critical.
