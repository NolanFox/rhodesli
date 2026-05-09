# Session 158 Assessment

**Date**: 2026-05-09
**Mode**: implementation
**Predecessor**: Session 157b
**Successor**: Session 158b (continuation; redesigned Phase 158-2 + cutover)
**Outcome**: PARTIAL — Phases 158-0, 158-1, and Codex 157b audit shipped. **Phase 158-2 historical backfill DEFERRED** due to Supabase pooler instability today. All downstream cutover phases (158-4 RENAME, 158-6 DROP+VACUUM, 158-7 verify, 158-8 Track E, 158-9 final) gated on 158-2 → all DEFERRED to 158b.

## Honest summary

This session was supposed to cut over from v1 to v2 GEDCOM tables and DROP v1.
Today the Supabase pooler (us-west-2) refused long server-side cursor reads
across the 196K-row `gedcom_individuals` table — first attempt failed mid-stream,
second attempt 9/10 chunks succeeded but the 10th (NULL version_id) failed all
3 retries, third attempt (paginated NULL + 5 retries) failed even on the
`SELECT id, version_number FROM gedcom_versions` query (pooler degraded). REST
API works (verified live), but a REST-based variant ran for 45+ minutes and
plateaued at 951 MB resident memory before being terminated.

The cutover gates exist for a reason. Phase 158-2 must complete (and the result
must satisfy the user's "maintain change over time" requirement) before any
DROP. So we end the session honestly with the irreversible work deferred.

## Shipped

- **Phase 158-0** carry verification (commit `75dc10e0`):
  - v2 row counts unchanged from 157b end (21,998 / 6,741 / 9)
  - v1 still intact (196,645 individuals; 174,647 historical)
  - Harry Fox + Belle Isle Conservatory state verified
  - R2 archive at `gedcom-version-snapshots/2026-05-08-session-156/` verified — 42 files, 277 MB, v9 head_object readable

- **Phase 158-1** change-history reality check (commit `35c9dad6`) — **the user's central question is answered**:
  - **96.3% of v1 individuals (21,174 of 21,998) have a 2-state change history** (v1-v7 share one payload_hash, v8/v9 introduced a new state)
  - 95.2% of v1 families (6,417 of 6,741) likewise
  - ZERO individuals/families have ≥3 distinct states (one correction wave only — likely a v8 GEDCOM correction batch)
  - 21,809 individual rows have NULL payload_hash (legacy pre-hash data, 11.1%)
  - Post-Option-A backfill estimate: ~64K individuals + ~13K families = ~77K v2 rows (vs v1's 230K — still 3x reduction)
  - Albert Fox deep dive: visible columns identical across the 2 states; the change is in JSONB columns (events, citations, names, notes)
  - User chose **Option A** (full historical backfill) via AskUserQuestion

- **Codex 157b audit** (commit `ddfbdf35`) — first independent audit of 157b's 17 commits (157b's own A1.3 only audited Session 156):
  - 0 P0, **2 P1**, 3 P2, 2 P3
  - **P1.1**: B2 dual-read NOT safe under concurrent writes — v2 unique by payload_hash, helper queried by gedcom_id with `.limit(1)` and no ORDER BY. Post-historical-backfill (multiple v2 rows per gedcom_id), would return arbitrary state. **FIXED in commit 8bdc497a**.
  - **P1.2**: B2 masked v2 failures — caught all exceptions and silently fell back to v1, hiding schema drift / RLS / server errors. **FIXED in commit 8bdc497a**.
  - P2 + P3: BACKLOG candidates (B1 boundary `>` vs `>=`, B1 family field set, B3 sample size disclosure, B3 fallback timing not measured)

- **Dual-read helper hardening** (commit `8bdc497a`):
  - `app/gedcom_dual_read.py`:
    - Codex P1.1 fix: v2 reads now `.order("last_seen_version", desc=True).order("first_seen_version", desc=True).order("payload_hash", desc=False)` — guarantees latest state when multiple v2 rows exist per gedcom_id (post-historical-backfill)
    - Codex P1.2 fix: narrow `_is_v2_unavailable()` check — only PGRST205 / "relation X does not exist" falls back to v1; schema drift, RLS errors, bad columns now surface (don't silently serve v1)
    - **NEW**: `get_individual_history(gedcom_id) -> list[dict]` — returns all v2 historical states sorted by `first_seen_version` ASC; satisfies the user's "maintain change over time" requirement once the backfill lands in 158b
  - `tests/test_dual_read_helper.py`: 23 tests pass (was 13, **added 10**):
    - TestV2OrderedRead (2): verifies `.order(last_seen_version, desc=True)` is in the v2 query chain (individual + family)
    - TestV2FailClosed (3): non-PGRST raises, PGRST205 falls back, "relation does not exist" falls back
    - TestGetIndividualHistory (5): single state, multi-state, unknown id, empty id, PGRST205 returns []

- **Phase 158-2 WIP** (commit `dd1f7f59`):
  - `scripts/session158_historical_backfill_gedcom_v2.py`: chunked-by-version with per-chunk fresh connections + 5-retry. Robust enough for 9/10 chunks but the NULL chunk consistently fails today.
  - `scripts/session158_historical_backfill_rest.py`: REST-based variant. Reads work but loading 196K full-payload rows into memory exhausts process. Needs chunked-write redesign for 158b.

## Deferred to 158b (with reason)

| Phase | What | Reason |
|---|---|---|
| 158-2 | Historical backfill v1 → v2 (Option A) | Pooler unstable today; REST script needs chunked-write redesign to bound memory |
| 158-3 | Pre-flight backups (R2 + pg_dump) | Gated on 158-2 |
| 158-4 | Cutover RENAME v1 tables + v2 view + bulk-loader rewire | Gated on 158-2 |
| 158-5 | Wait period + sustained validation | Gated on 158-4 |
| 158-6 | DROP v1 + VACUUM FULL | Gated on 158-2 + 158-3 + 158-4 + 158-5 |
| 158-7 | Post-cutover query timing + browser verify | Gated on 158-6 |
| 158-8 | Track E GEDCOM upload UAT | Gated on 158-6 (v2-aware importer needs cutover) |
| 158-9 | Final verification | Gated on 158-7 + 158-8 |

## Red flags

| # | Severity | Description | Fix |
|---|---|---|---|
| 1 | P1 | Codex P1.1 + P1.2 helper changes shipped to production WITHOUT yet exercising the multi-state code path (since historical backfill didn't complete). The ORDER BY is a no-op against current v2 (every gedcom_id has 1 row from 156's backfill). | Will be exercised in 158b after the historical backfill lands. |
| 2 | P2 | Pooler instability today blocks any 196K-row read job. If 158b also hits this, we need to switch to chunked-write or use Supabase REST with bounded memory. | 158b prompt explicitly mandates chunked-write (write each chunk's aggregate immediately to v2, never accumulate full dataset in memory). |
| 3 | P2 | The historical backfill was the user's central deliverable from this session. Carrying it forward is a real lost-day, not a "minor deferral." | Plain-language note in 158b prompt: "this is the lost work from 158, please prioritize." |
| 4 | P2 | `scripts/session158_historical_backfill_rest.py` (committed) has the memory bug (loads all rows into one list before writing). The script will fail the same way next session unless redesigned. | 158b first action: redesign the script with chunked-write before running execute. |
| 5 | P3 | Codex P2 findings on 157b (B1 boundary `>` vs `>=`, B1 family field set, B3 sample size) not addressed. | BACKLOG: GEDCOM-CATCHUP-BOUNDARY-001, GEDCOM-CATCHUP-FAMILY-FIELDS-001, GEDCOM-TIMING-SAMPLE-DISCLOSURE-001. |

## AI Tool Usage (mandatory section per .claude/rules/ai-tool-audit.md)

- **Tool**: Codex CLI v0.130.0 (gpt-5.5, xhigh)
- **Agent type**: Independent (fresh context)
- **Task**: Audit Session 157b commits 7e11642d..c553644c (the predecessor session that was never independently audited)
- **Findings**: 0 P0, **2 P1**, 3 P2, 2 P3
- **Acted on**: P1.1 + P1.2 fixed immediately in commit `8bdc497a` BEFORE the historical backfill would have made the helper bug observable
- **Deferred**: P2 findings to BACKLOG (not blocking cutover); P3 findings noted in session log
- **Discarded**: 0
- **Value assessment**: **STRONG** — Codex caught a concurrency bug that would have surfaced as silent stale reads after the historical backfill. Without this audit, we'd have shipped the cutover with the helper returning arbitrary v2 rows for every gedcom_id with multiple states. We'd have caught it eventually via user-visible "wrong birth_place / wrong death_date" reports — but probably weeks later.
- **Would we have found this ourselves?** Unlikely until users reported wrong data. The bug is silent — `.limit(1)` returns SOME row, just not deterministically the right one.
- **Comparison note**: The retroactive /session-review on 157b also flagged this gap (independently from Codex), but at a higher abstraction level ("change-history question partially punted to 158") rather than the exact concurrency bug. Both lenses were valuable.

- **Tool**: general-purpose subagent (Claude Opus 4.7)
- **Agent type**: Independent (fresh context)
- **Task**: Retroactive /session-review on Session 157b (since 157b skipped the skill in its own closeout)
- **Findings**: 3 top concerns:
  1. SF-1 (P1): Browser verify via curl, not Chrome MCP — prompt required Chrome MCP
  2. C-1 (P1): Track B2 wired into `_load_gedcom_individual` instead of prompt-named `_load_gedcom_face_links`
  3. §6: B4's PROCEED partially punts the change-history question to 158
- **Acted on**: Phase 158-1 was the change-history continuity verification the review recommended; user opted in to Chrome MCP for 158 (not exercised today since cutover didn't proceed)
- **Deferred**: Adding `BROWSER-VERIFY-METHOD-001` and `TEST-MARKER-AUDIT-001` to BACKLOG (158b can carry)
- **Value assessment**: **MODERATE** — confirmed the change-history question was real (which was already on the 158 plan via Phase 158-1) and surfaced the curl-vs-Chrome-MCP gap which informed the user's decision to use Chrome MCP for 158.

## What 158b should verify FIRST

1. **Pooler health**: try a basic `SELECT count(*) FROM gedcom_individuals` and `SELECT id, version_number FROM gedcom_versions` via psycopg2. If the pooler is unhealthy AGAIN today, do not retry the heavy reads — switch immediately to chunked-write REST.
2. **Re-verify Phase 158-0 carry**: row counts, Harry/Belle Isle, R2 archive readability.
3. **Re-run Phase 158-1 query** for Albert Fox: confirm the 2-state history pattern is unchanged (no concurrent imports between 158 and 158b).
4. **Test the dual-read helper P1.1 fix live**: query a gedcom_id, confirm the ORDER BY is in flight via captured query log.

## Push status

`git push origin main` to be done as part of closeout.

## Browser verify status

DEFERRED. The shipped code changes (dual_read helper P1.1 + P1.2 + new history function) are backward-compatible no-ops against the current single-row-per-gedcom_id v2 state. There are no UI changes. Will verify via Chrome MCP in 158b after the cutover work resumes.
