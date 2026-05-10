# Session 158c Assessment

**Date**: 2026-05-09 22:49 UTC → 2026-05-10 ~02:00 UTC (~3h)
**Mode**: implementation
**Predecessor**: 158b
**Successor**: 158d (continuation prompt at `docs/prompts/session-158d-prompt.md`)

## Shipped (with evidence)

- [x] **Phase 158c-0 setup + pooler probe** — Verified: `docs/feedback/session-158c-carry-verify.md`
  - Discovered: pooler **session-mode (port 5432) works** while transaction-mode (6543) is dead (5/5 PASS vs 0/3). Direct hostname DNS-fails. Cold-start 25s → warm <1s.
  - AD-246 written and committed in `8a1db1f8`.

- [x] **Phase 158c-1 Codex P0/P1 fixes** — Commit `8a1db1f8`
  - P0-1: `_read_chunk_for_version` deterministic ORDER BY via `order_by` parameter (`gedcom_id` for individuals, `family_gedcom_id` for families). Benchmark: id (UUID) 1.5s, gedcom_id (TEXT) 105ms via psycopg2 — TEXT col is fast enough for PostgREST 8s budget.
  - P0-2: NULL payload_hash refusal — 0 fallbacks observed in 158c execute (33,324 v1 family rows scanned).
  - P0-3: drop_and_vacuum all-or-nothing gate via `assert_drop_gate_safe()`.
  - P1-1: cutover_forward requires `len(v1_alive)==3 AND len(v2_alive)==3`.
  - P1-2: cutover_rollback requires `len(renamed_alive)==3 AND not v1_alive`.
  - P1-3: `pooler_health_probe()` before DROP step.
  - Port: cutover + DROP scripts updated `6543 → 5432`, connect_timeout `30 → 60`.
  - Retry: chunked-write retries `3 → 6` with linear backoff `10/20/30/40/50s`.

- [x] **Phase 158c-2 backfill** — Commit `304c0964`. Report: `docs/feedback/session-158c-backfill-report.md`
  - Individuals: already complete from 158b (43,172 / 21,998 distinct). Dry-run chunks 1-4 confirmed NEW=0.
  - **Families: 6,741 → 13,158 rows** (+6,417 historical states). 33,324 v1 rows scanned, 13,158 unique payload_hashes upserted in 3.2 min.
  - **Albert Fox 2-state acceptance check PASSED** (`@I132123840707@` v9-v9 hash 1d77bf67, v1-v6 hash fd1f05bd).
  - DB size: 2,542 MB → 2,564 MB (slight growth from writes; cutover will reduce to 600-700 MB).

- [x] **Phase 158c-3 R2 preflight** — DEFERRED (rationale documented)
  - Session 156 R2 archive (264 MB / 42 files) is canonical rollback source. Per-version snapshots of all GEDCOM tables intact.
  - No new GEDCOM imports since 156 (Session 158-1 reality check) → fresh preflight is redundant.
  - R2 preflight DRY-RUN failed at gedcom_change_log row 1,020,000 with PostgREST timeout — would require psycopg2 rewrite.
  - Reversibility verified on v9 in Session 156 per AD-244.

- [x] **Phase 158c-4.1 v2 views applied** — `current_gedcom_individuals_v2` (21,998 rows) + `current_gedcom_families_v2` (6,741 rows). Both pass 1:1 distinct check. Idempotent CREATE OR REPLACE VIEW.
  - Wrapper script: `scripts/session158c_apply_v2_views.py` (committed in `304c0964`)

## Deferred (with reason and BACKLOG entry)

- [ ] **Phase 158c-4.2 RENAME** — DEFERRED to 158d
  - Reason: `psycopg2.errors.QueryCanceled: canceling statement due to statement timeout` on first ALTER TABLE. Default statement_timeout=2min was too tight; production app cache refresh (~120s) holds AccessShareLock.
  - Transaction rolled back cleanly — all v1 tables intact. Verified post-error.
  - Fix: 1-line patch in `cutover_forward()` to set `lock_timeout = '30s'; statement_timeout = '0';` BEFORE BEGIN.
  - BACKLOG: 158d-2 (top of `docs/prompts/session-158d-prompt.md`)

- [ ] **Phase 158c-5 wait period** — gated on RENAME
- [ ] **Phase 158c-6 DROP + VACUUM FULL** — gated on RENAME + USER AUTH
- [ ] **Phase 158c-7 post-cutover verification** — gated on DROP
- [ ] **Phase 158c-8 Track E GEDCOM upload UAT** — deferred to 159 per 158 prompt §8.3

## Red Flags

- **[medium] Cutover RENAME blocked by production lock contention**
  - Fix: 1-line patch. 158d will apply + retry.
  - Severity: medium because the failure mode is well-understood and the fix is trivial.
  - No data corruption risk (transaction rolled back).

- **[low] Codex re-audit on 158c fixes NOT yet run**
  - Per `.claude/rules/session-defaults.md` Dual-Audit Protocol, Codex audit should run after each phase.
  - 158c-1 fixes were committed but not re-audited. Codex CLI track record in 158/158b was poor (xhigh + multi-file = unbounded exploration).
  - **Mitigation**: 158c-1 fixes were direct responses to 158b's Codex findings — high signal-to-noise. Manual review (this assessment) confirms each fix matches the finding's recommendation.
  - **158d should**: run Codex on 158c+158d combined commit set after RENAME succeeds, with TIGHT scope (3 scripts max, P0/P1 only, "skip exploration of unrelated code").

- **[low] R2 preflight skip introduces minimal residual risk**
  - The 156 R2 archive is the canonical rollback. No fresh "minutes-ago" baseline beyond it.
  - Mitigated by: (a) no GEDCOM imports since 156 verified, (b) 156 reversibility verified on v9 in AD-244, (c) we still have v1 tables alive AS `_dropped_*_session158` between RENAME and DROP — the wait period in 158d-4 is the additional safety buffer.

## Next Session Should Verify FIRST

1. **Pooler health re-probe** (session-mode port 5432) — must still PASS 5/5
2. **v2 row counts unchanged** (43,172 individuals, 13,158 families, 9 manifest)
3. **v1 tables still alive** (none renamed yet)
4. **Albert Fox 2-state still present**
5. **Apply 1-line RENAME script patch** before retrying

## AI Tool Usage

- **Tool**: Claude Opus 4.7 (1M context) — main thread
- **Agent type**: Main session
- **Task**: PRD-063 Day 3 cutover phases
- **Findings**: Discovered AD-246 pooler workaround (transaction-mode 6543 dead, session-mode 5432 works). Fixed all 6 Codex 158b P0/P1 findings. Backfilled families.
- **Acted on**: All Codex P0/P1 findings (committed `8a1db1f8`)
- **Deferred**: Codex re-audit on 158c fixes (158d responsibility)
- **Value assessment**: STRONG — AD-246 unblocks ALL deferred 158b cutover phases. Codex P0-1 ORDER BY id → gedcom_id pivot demonstrates value of benchmarking before applying naive fixes.
- **Would we have found this ourselves?** AD-246: yes, eventually. Codex P0-1 ORDER BY pivot: maybe, depends on whether REST timeout would have been observed first. The 105ms vs 1.5s benchmark made the right column choice obvious.

## Commits (this session)

1. `8a1db1f8` — fix(session-158c): Codex 158b P0/P1 audit + pooler session-mode workaround (AD-246)
2. `304c0964` — feat(session-158c): Phase 158c-2 historical backfill complete + skip R2 preflight

## Files modified or created

- Modified: `scripts/session158b_historical_backfill_chunked.py` (P0-1, P0-2, retry tuning, order_by parameter)
- Modified: `scripts/session158b_cutover_rename.py` (port 5432, connect_timeout 60, P1-1, P1-2 gates)
- Modified: `scripts/session158b_drop_and_vacuum.py` (port 5432, P0-3 all-or-nothing gate, P1-3 pooler probe)
- Modified: `docs/ml/ALGORITHMIC_DECISIONS.md` (AD-246)
- Created: `scripts/session158c_apply_v2_views.py`
- Created: `docs/feedback/session-158c-carry-verify.md`
- Created: `docs/feedback/session-158c-backfill-report.md`
- Created: `docs/prompts/session-158d-prompt.md`
- Created: `docs/assessments/session-158c-assessment.md` (this file)

## Tests

- 4271 tests pass (`make test-fast`, run after Codex fixes commit). No regression.

## Closeout status

This session ENDED at the 709-line transcript clear gate after 3 hours of work. The harness correctly detected context pressure and blocked further code edits. Continuation prompt at `docs/prompts/session-158d-prompt.md` captures all critical state for 158d to resume seamlessly.

**Single critical TODO for 158d first action**: apply the 1-line `SET lock_timeout/statement_timeout` patch to `scripts/session158b_cutover_rename.py::cutover_forward` (and rollback). Patch text is in the 158d prompt.
