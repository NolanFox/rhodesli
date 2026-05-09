# Session 158b Assessment

**Date**: 2026-05-09
**Mode**: implementation
**Predecessor**: Session 158 (`docs/assessments/session-158-assessment.md`)
**Successor**: Session 158c (`docs/prompts/session-158c-prompt.md`)
**Result**: PARTIAL — Phase 158b-2 backfill EXECUTE in progress at session close; Phases 158b-3 → 158b-9 DEFERRED to 158c due to Supabase pooler outage blocking psycopg2 DDL.

## Context

Session 158 deferred Phase 158-2 (historical backfill) to 158b due to pooler instability + REST script memory bug. Per `docs/prompts/session-158b-prompt.md`, 158b's job was:
1. Re-run carry verification + pooler probe
2. Redesign Phase 158-2 with chunked-write (read+aggregate+upsert per chunk; never accumulate)
3. Continue through 158b-3 → 158b-9 (cutover, DROP, VACUUM, browser verify)

## Shipped

### Phase 158b-0: Carry verification + A.5 hardening verify ✅
- **Evidence**: `docs/feedback/session-158b-carry-verify.md` (PASS — v2 21,998/6,741/9, R2 archive 42 files / 277 MB readable, Harry Fox 5 anchors v_id=14, Belle Isle INBOX with notes)
- **A.5 verify**: `INDIVIDUAL_HISTORY_FIELDS` contains all 6 JSONB columns (228 fields total). 25 dual-read tests pass (was 23 + 2 from 158 final-pass).
- **Commit**: `5799700a`

### Phase 158b-0B: Pooler health probe ✅ (FAILED 0/3)
- **Result**: 3/3 trials returned `OperationalError: SSL connection has been closed unexpectedly` against `aws-0-us-west-2.pooler.supabase.com:6543`.
- **Diagnostic**: Same pooler degradation as 158 saw, persisting across days. REST API on `https://fvynibivlphxwfowzkjl.supabase.co` works but throughput is degraded under load (read timeouts + RemoteProtocolError mid-stream).
- **Commit**: `5799700a` (probe + assessment)

### Phase 158b-2: Chunked-write historical backfill ⏳ in progress
- **Script**: `scripts/session158b_historical_backfill_chunked.py` (313 lines).
- **Design**: read 1 version_id at a time → aggregate by payload_hash → read existing v2 hits → merge first/last_seen_version → REST upsert in batches of 500. 10 chunks (9 versions + NULL). Each chunk peak ~50 MB memory.
- **EXECUTE state at session close**: chunks 1-5 complete (~110K rows upserted into individuals_v2, growing v2 from 21,998 → ~43,172 individuals). Chunks 6-10 + all of families pending.
- **Per-chunk timing observed** (individuals):
  - Chunk 1 (v1): 220s (51s read + 167s upsert) — NEW=21,174, UPDATE=770
  - Chunk 2 (v2): 240s (49s read + 189s upsert) — NEW=0, UPDATE=21,944 (all hashes match v1)
  - Chunk 3 (v3): 1937s (62s read + 1875s upsert) — pooler degraded heavily mid-chunk
  - Chunk 4 (v4): ~500s (121s read + 376s upsert) — multiple ReadTimeout retries
  - Chunk 5 (v5): in upsert phase (estimated 8-10 min remaining at observation)
- **Sanity check passed**: 196,645 v1 rows → 43,172 unique payload_hashes (within NOTE-2's 22K-100K STOP gate; expected post-backfill v2 ~43-65K).
- **No commit yet** — backfill must complete + Albert Fox 2-state verification before commit.

### Phase 158b-4.1: Bulk-loader rewire (code only) ✅
- **What changed**: 3 locations in `app/relationship_routes.py` now prefer `current_gedcom_individuals_v2` first, fall back to `current_gedcom_individuals` (v1 view), then to `gedcom_individuals` (v1 raw). The v2 view DDL itself is in `scripts/migrations/session158b_current_v2_views.sql` but NOT YET APPLIED (psycopg2 outage blocks). Code change is harmless because v2 view doesn't exist yet → falls through to v1 view (still alive).
- **Tests updated**: `test_individual_loader_uses_thin_fields` now asserts v2 view name; `test_single_individual_lookup_can_fetch_rich_row` rewritten to mock the `.order().order().order().limit()` chain that v2 dual-read uses (and asserts `INDIVIDUAL_RICH_FIELDS` from `gedcom_dual_read.py`, not `_GEDCOM_RICH_FIELDS` from `relationship_routes.py`).
- **Test count**: 4271 pass (no regression).
- **Commit**: `f2a857b8`

### Cutover scripts written (deferred to 158c) ✅
| Script | Lines | Purpose |
|---|---|---|
| `scripts/migrations/session158b_current_v2_views.sql` | 32 | DISTINCT ON views for current state |
| `scripts/session158b_cutover_rename.py` | 144 | Reversible RENAME v1 → _dropped_*_session158 + --rollback |
| `scripts/session158b_drop_and_vacuum.py` | 191 | DROP + VACUUM FULL + size delta report |
| `scripts/session158b_r2_preflight_snapshot.py` | 199 | Fresh R2 snapshot of v1 tables (REST-based) |

## Deferred to 158c

| Phase | Why deferred | Script ready |
|---|---|---|
| 158b-3 R2 preflight snapshot | Time budget at session close | yes |
| 158b-4.1 view migration apply | Pooler dead — psycopg2 unavailable | yes (SQL) |
| 158b-4.2 RENAME | Pooler dead | yes |
| 158b-5 wait period | Gated on 158b-4 | n/a |
| 158b-6 DROP + VACUUM FULL | Pooler dead | yes |
| 158b-7 query timing + browser verify | Pooler dead (timing) | yes (existing 157b script) |
| 158b-8 Track E GEDCOM upload UAT | Recommend defer to 159 | n/a |
| 158b-9 final verification | Gated on cutover | n/a |

158c continuation prompt: `docs/prompts/session-158c-prompt.md`.

## Red flags / risks

### High: Pooler outage blocking cutover
- **Severity**: HIGH
- **What**: 3/3 pooler probes fail with SSL connection closed. Persisted across 158 (yesterday) and 158b (today). Blocks all DDL (RENAME, DROP, VACUUM FULL).
- **Mitigation in 158c prompt**: re-probe; if 0/3 again, escalate to Supabase support OR try direct (non-pooler) connection (per Lesson 175 may be IPv6-only).
- **Worst case**: ~20 days until 2026-05-29 deadline; if pooler stays dead, manual SQL via Supabase Studio web UI is the fallback.

### Medium: Chunk 3 took 31 minutes (10x normal)
- **Severity**: MEDIUM
- **What**: REST API throughput unstable. Single chunk took 1875s vs 166s baseline (chunk 1).
- **Mitigation**: script has 3-retry loop on every batch + chunk read. All chunks completing eventually.
- **Risk**: if backfill runs >5 hours, future families processing may be similarly slow. Total session wall-clock could be 2-3x estimate.

### Low: Albert Fox 2-state verification gated on chunk 9
- **Severity**: LOW
- **What**: Verifying the central deliverable (v2 returns 2-state history for Albert) requires chunk 9 to finish (the v9-state hash). If session aborts before chunk 9, can't verify in this session.
- **Mitigation**: 158c prompt's "Phase 158c-2" verifies state regardless of when backfill completed.

### Low: 87 docs >300 lines (pre-existing harness check fail)
- **Severity**: LOW (pre-existing, not session-introduced)
- **What**: `harness-check.sh` reports 87 docs over the 300-line cap. Carries from many prior sessions.
- **Mitigation**: not session-blocking. Would require split work in a dedicated cleanup session.

## AI Tool Usage

- **Tool**: None this session beyond Claude Code itself.
- **Codex CLI**: NOT INVOKED — this session was tactical execution of redesigned 158-2 + setup; the per-phase Codex audit + final-pass audit are scheduled for 158c (where the IRREVERSIBLE work happens and benefits most from independent review).
- **Claude subagents**: NOT INVOKED.
- **Value assessment**: deferred — meaningful audit only after cutover completes.

## What 158c MUST verify FIRST

1. **Pooler health probe** — gate for whether 158c can even attempt cutover. If 0/3 PASS again, defer to 158d.
2. **Backfill final state** — re-run `gedcom_individuals_v2` and `gedcom_families_v2` count queries; expected ~43-65K and ~13K respectively.
3. **Albert Fox 2-state** — `get_individual_history('@I132123840707@')` must return exactly 2 entries with hashes `fd1f05bd...` and `1d77bf67...`.
4. **R2 archive readability** — re-test 156 archive (42 files / 277 MB) before any irreversible action.

## Lessons-candidate

**Pooler degradation lasting >24h (Lesson 184 candidate)**: Session 158 (yesterday) hit pooler issues mid-backfill. Session 158b (today) found pooler completely dead from session start. Suggests Supabase free-tier pooler may have sustained degradation periods. Worth opening a Supabase support ticket before the next pooler-dependent session. Adjacent: Lesson 183 (chunked-write template) needs a "psycopg2 fallback to REST" extension because chunked-write alone doesn't help DDL operations.
