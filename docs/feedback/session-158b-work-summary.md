# Session 158b — Comprehensive Work Summary

**Date**: 2026-05-09 (single-day session)
**Duration**: ~5 hours
**Final result**: PARTIAL — Phase 158b-2 backfill ran chunks 1-5/10 + chunk 6 partial, then died on httpx.ReadTimeout. All cutover phases (158b-3 → 158b-9) deferred to 158c due to sustained Supabase pooler outage blocking psycopg2 DDL.
**Continuation**: `docs/prompts/session-158c-prompt.md`
**Commits pushed**: 7 (`5799700a..f85ada8f`)

---

## What we set out to do

Per `docs/prompts/session-158b-prompt.md`:
1. Re-run carry verification + pooler health probe
2. Redesign Phase 158-2 historical backfill with chunked-write (read+aggregate+upsert per chunk; never accumulate full dataset in memory) — Lesson 183 template
3. Continue through Phases 158b-3 (R2 backups), 158b-4 (cutover RENAME + view), 158b-5 (wait period), 158b-6 (DROP + VACUUM FULL), 158b-7 (post-cutover verify + browser), 158b-8 (Track E GEDCOM upload UAT), 158b-9 (final verification)
4. Run Codex final-pass audit on combined 158 + 158b commits

---

## What actually happened — chronological

### Hour 1: setup + diagnosis
- Phase 158b-0 carry verification PASS (v2 21,998/6,741/9 intact, R2 archive 277 MB readable, Harry Fox + Belle Isle anchors unchanged)
- A.5 hardening verify: `INDIVIDUAL_HISTORY_FIELDS` has all 6 JSONB columns; 25 dual-read tests pass
- Phase 158b-0B pooler probe: **0/3 PASS** — `OperationalError: SSL connection has been closed unexpectedly` on every trial. Pooler at `aws-0-us-west-2.pooler.supabase.com:6543` completely dead today (same outage as Session 158 yesterday)
- Decision: switch all reads + writes to REST API; psycopg2 DDL phases deferred until pooler recovers

### Hour 2: redesigned backfill script + cutover scripts written
- `scripts/session158b_historical_backfill_chunked.py` (313 lines, NEW) — replaces Session 158's REST script that OOMed at 951 MB. Per-chunk peak memory ~50 MB.
- `scripts/session158b_cutover_rename.py` (144 lines, NEW) — reversible RENAME with `--rollback`
- `scripts/session158b_drop_and_vacuum.py` (191 lines, NEW) — IRREVERSIBLE DROP + VACUUM FULL with size delta report
- `scripts/session158b_r2_preflight_snapshot.py` (199 lines, NEW) — REST-based v1 snapshot to R2 before DROP
- `scripts/migrations/session158b_current_v2_views.sql` (32 lines, NEW) — DISTINCT ON views
- Sanity check: 196,645 v1 individual rows → **43,172 unique payload_hashes** (within NOTE-2's 22K-100K STOP gate; expected post-backfill ~43-65K)
- Pre-EXECUTE upsert API smoke test: PASS — single-row upsert with `on_conflict="payload_hash"` works
- **Commit `5799700a`**

### Hour 3: bulk-loader rewire (Phase 158b-4.1 code-only)
- 3 locations in `app/relationship_routes.py` updated to prefer `current_gedcom_individuals_v2` view first, fall back to `current_gedcom_individuals` (v1 view), then `gedcom_individuals` (v1 raw):
  - `_load_gedcom_individuals` bulk loader (line 326)
  - `_load_gedcom_individuals_by_ids` targeted loader (line 666)
  - GEDCOM search prefilter (line 952)
- 2 tests in `tests/test_gedcom_routes.py` updated:
  - `test_individual_loader_uses_thin_fields` — assertion now expects v2 view name
  - `test_single_individual_lookup_can_fetch_rich_row` — rewritten to mock the `.order().order().order().limit()` chain v2 dual-read uses; asserts `INDIVIDUAL_RICH_FIELDS` from `gedcom_dual_read.py`
- `make test-fast`: 4271 passed (no regression)
- **Commit `f2a857b8`**

### Hour 4: backfill EXECUTE — partial success then death
Per-chunk timing observed:

| Chunk | v_num | Read | Upsert | Total | NEW | UPDATE | Notes |
|---|---|---|---|---|---|---|---|
| 1 | v1 | 51s | 167s | 220s | 21,174 | 770 | Healthy — most rows are NEW |
| 2 | v2 | 49s | 189s | 240s | 0 | 21,944 | All v_num=2 hashes match v_num=1 — individuals didn't change |
| 3 | v3 | 62s | **1875s** | 1937s | 0 | 21,944 | Pooler/REST degraded; many retries |
| 4 | v4 | 121s | 376s | 500s | 0 | 21,944 | 3 batch retries (ReadTimeout, RemoteProtocolError) |
| 5 | v5 | 154s | **4230s** | 4384s | 0 | 21,944 | Many retries; pooler very unstable |
| 6 | v6 | 98s | DIED | n/a | 0 (read+merged) | 21,944 (computed) | `httpx.ReadTimeout` exhausted 3 retries on a single upsert batch |

Total wall-clock through chunk 5 + chunk 6 partial: ~3 hours.

State at backfill death:
- v2 individuals row count: ~110K rows (some redundant from updates; idempotent — re-running is safe)
- Chunks 7-10 (v7, v8, v9, NULL) NOT processed
- All families NOT processed
- Albert Fox 2-state verification: NOT YET POSSIBLE (chunk 9 needs to run for the v9 hash `1d77bf67`)

### Hour 5: closeout
- Progress checkpoint (`docs/feedback/session-158b-progress-checkpoint.md`) — **commit `182998d3`**
- 158c continuation prompt (`docs/prompts/session-158c-prompt.md`) — **commit `7d438807`**
- CHANGELOG v0.99.76 + ROADMAP + BACKLOG + assessment — **commit `1285eb87`**
- Pushed to main
- Session log + corrections after backfill died — **commit `33a4abab`**
- Codex audit attempted — ran ~28 min, produced 6571 lines of file exploration, **0 findings**, terminated by orchestrator. Manual self-audit by Claude written instead. — **commit `f85ada8f`**

---

## All artifacts produced this session

### Code (immutable once committed)
- `scripts/session158b_historical_backfill_chunked.py` — 313 lines, ran partially
- `scripts/session158b_cutover_rename.py` — 144 lines, NOT YET RUN
- `scripts/session158b_drop_and_vacuum.py` — 191 lines, NOT YET RUN (IRREVERSIBLE)
- `scripts/session158b_r2_preflight_snapshot.py` — 199 lines, NOT YET RUN
- `scripts/migrations/session158b_current_v2_views.sql` — 32 lines, NOT YET APPLIED

### Code edits
- `app/relationship_routes.py` — 3 locations rewired (v2 view preference)
- `tests/test_gedcom_routes.py` — 2 tests updated for v2 contract

### Documentation (everything 158c needs)
- `docs/assessments/session-158b-assessment.md` — full self-evaluation
- `docs/session_logs/session-158b-log.md` — phase checklist + commits
- `docs/feedback/session-158b-carry-verify.md` — Phase 158b-0 evidence
- `docs/feedback/session-158b-progress-checkpoint.md` — mid-session state snapshot
- `docs/feedback/session-158b-work-summary.md` — this file
- `docs/session_context/session-158b-codex-audit.md` — Codex run state + manual self-audit (4 P1s, 5 P2s, 3 P3s)
- `docs/prompts/session-158c-prompt.md` — continuation prompt for cutover phases
- `CHANGELOG.md` — v0.99.76 entry
- `ROADMAP.md` — Recently Completed entry
- `docs/BACKLOG.md` — deferred items rolled to 158c

### Live state on Supabase (not in git)
- `gedcom_individuals_v2`: ~110K rows (was 21,998) — partial backfill, includes some duplicates from chunk-6 partial
- `gedcom_families_v2`: 6,741 rows — UNCHANGED (families not yet processed)
- `gedcom_change_manifest`: 9 rows — unchanged
- v1 tables: ALIVE — `gedcom_individuals` 196,645, `gedcom_families` 33,324, `gedcom_change_log` ~1.65M

### R2 archive (canonical rollback)
- `gedcom-version-snapshots/2026-05-08-session-156/v9/` — 277 MB, 42 files, READABLE
- No fresh 158b R2 snapshot taken (Phase 158b-3 deferred)

---

## What 158c MUST do

Read `docs/prompts/session-158c-prompt.md` for the canonical continuation. High-level:

1. **Re-probe pooler health** — gate for whether 158c can attempt cutover at all
2. **Resume backfill** — re-run `session158b_historical_backfill_chunked.py --execute` (idempotent). Recommend tuning: bump `_upsert_v2` retry count 3→6, sleep 3s→10s with backoff
3. **Verify Albert Fox 2-state history** — `get_individual_history('@I132123840707@')` must return 2 entries with hashes `fd1f05bd...` and `1d77bf67...`
4. **R2 preflight snapshot** — `session158b_r2_preflight_snapshot.py --execute`
5. **Apply v2 views SQL** via psycopg2 (when pooler recovers) OR Supabase Studio web UI
6. **Run independent Codex audit on IRREVERSIBLE scripts** (drop_and_vacuum.py, cutover_rename.py) — non-negotiable gate per `docs/session_context/session-158b-codex-audit.md`
7. **Cutover RENAME** — `session158b_cutover_rename.py --execute` (reversible)
8. **Wait + sustained validation** — 5 min sleep, re-verify
9. **DROP + VACUUM FULL** — only after user authorization via AskUserQuestion
10. **Post-cutover verification** + Chrome MCP browser verify
11. **Track E GEDCOM upload UAT** — likely defer to 159
12. **Closeout**

---

## Lessons-candidate for `tasks/lessons.md`

- **Lesson 184 (proposed)**: Sustained Supabase pooler outage >24h needs Supabase support escalation. Two consecutive sessions saw 0/3 PASS with SSL connection closed. The pooler degradation is sustained, not transient — likely needs ticket-driven resolution, not retry-driven.
- **Lesson 185 (proposed)**: Codex CLI `xhigh` reasoning + multi-file scope produces unbounded exploration loops. For session-end audits, scope to ONE file or use `medium` reasoning effort. Hard wall-clock budget of 15 min is non-negotiable.
- **Lesson 186 (proposed, extends 183)**: REST upsert retry budget of 3 retries × 3s sleep is insufficient for sustained pooler/REST degradation. Bump to 6 retries with exponential backoff (3, 6, 12, 24, 48, 96s) for migration scripts. Include httpx-specific exception handling so non-transient errors (4xx) aren't retried.
