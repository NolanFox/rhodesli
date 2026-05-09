**Auditor**: Codex CLI v0.130.0 (gpt-5.5, xhigh)
**Agent type**: Independent (fresh context)
**Scope**: Session 158b commits `5799700a..f85ada8f` (7 commits) — 2 audit runs (first timed out at exploration phase; second ran with tighter scope and produced findings)
**Date**: 2026-05-09

---

## Codex findings (Run 2 — focused 3-script scope, COMPLETED)

Run 2 invocation: `codex exec` against scripts `session158b_historical_backfill_chunked.py` + `session158b_cutover_rename.py` + `session158b_drop_and_vacuum.py` ONLY (lower-risk scripts skipped). Wall-clock ~5 min, 27,248 tokens used. ✅

### P0 — must-fix before 158c executes irreversible work

- **P0-1** `scripts/session158b_historical_backfill_chunked.py:117` (`_read_chunk_for_version`) — REST `.range()` pagination has NO deterministic `.order()`. Source rows can be silently skipped/duplicated across pages. **Implication for 158b**: chunks 1-5 + chunk 6 partial may be incomplete or contain duplicates. **Implication for 158c**: cannot trust the partial state; resume backfill must include `.order(...)` and re-process all chunks (idempotent ON CONFLICT means no harm in re-run). **Fix**: add `.order("id")` (or whatever has a unique index) to the SELECT in `_read_chunk_for_version` before `.range()`.
- **P0-2** `scripts/session158b_historical_backfill_chunked.py:137` (`_aggregate_chunk` fallback hash) — when `payload_hash` is NULL on v1 rows, fallback computes SHA256 only over `key_fields` (gedcom_id, name, given_name, surname, gender, birth/death). Two distinct rows with identical key fields but different events/citations/notes would collide and be incorrectly merged into a single v2 row. **Mitigation**: 0 fallback hashes were observed in chunks 1-5 (all v1 rows have payload_hash), so 158b output is likely uncorrupted. But the code path is still wrong. **Fix**: extend `key_fields` to include the full set of identifying + JSONB fields, OR raise on NULL payload_hash instead of falling back.
- **P0-3** `scripts/session158b_drop_and_vacuum.py:111` (`drop_renamed_tables`) — script drops whatever `_dropped_*_session158` tables EXIST and silently skips missing ones. There is no in-script all-or-nothing gate that asserts (a) all 3 renamed tables are present AND (b) the original v1 names are absent. **Implication**: if only 2 of 3 RENAMEs succeeded, this script would happily drop those 2 and leave the v1 namespace partially populated. **Fix**: add a pre-DROP assertion that all 3 `_dropped_*_session158` tables exist AND all 3 `gedcom_individuals/gedcom_families/gedcom_change_log` originals do NOT exist. Fail-fast otherwise.

### P1 — should-fix before 158c

- **P1-1** `scripts/session158b_cutover_rename.py:145` — cutover forward only checks `before["v1_alive"]` (any v1 table present) before RENAME. Should require ALL three v1 tables present AND ALL three v2 tables present. **Fix**: assert `len(before["v1_alive"]) == 3` AND `len(before["v2_alive"]) == 3`.
- **P1-2** `scripts/session158b_cutover_rename.py:139` (rollback path) — only checks any renamed table exists. Partial cutover states fail late inside the BEGIN/COMMIT transaction. **Fix**: pre-rollback assertion that all 3 renamed tables exist; or build per-table rollback that's idempotent.
- **P1-3** `scripts/session158b_drop_and_vacuum.py:165` (`get_conn`) — uses pooler psycopg2 for IRREVERSIBLE work despite today's known SSL instability. If pooler disconnects mid-DROP-COMMIT, transaction state is ambiguous; if mid-VACUUM (autocommit), partial vacuum on some tables. **Mitigation**: VACUUM partial-state is benign (re-run on remaining tables). DROP transaction is atomic — partial commit is impossible inside BEGIN/COMMIT. So this is a P1 in spirit, P2 in actual blast radius. **Fix**: add explicit pooler health probe before DROP step; consider direct (non-pooler) connection if pooler is degraded.

### P2/P3 — out of scope per prompt

Run 2 prompt explicitly skipped P2/P3. Manual self-audit (below) covers P2/P3 for completeness.

---

## Codex findings (Run 1 — full 7-file scope, TIMED OUT, no findings)

First Codex run was scoped to all 7 158b artifacts with `xhigh` reasoning. Ran ~28 min, 6571 lines of file exploration output, 0 P0/P1/P2/P3 entries reached. Terminated by orchestrator after exhausting session budget.

Lessons: xhigh + multi-file scope produces unbounded exploration. Run 2's tighter scope (3 files only, P0/P1 only, "skip exploration of unrelated code") completed in ~5 min with 27K tokens — ~50x faster.

---

## Original auditor preamble

## Codex CLI run state

- **Invocation**: `codex exec "<24-line audit prompt>" </dev/null` (per `.claude/rules/ai-tool-audit.md` working form)
- **CLI version**: codex-cli 0.130.0
- **Model**: gpt-5.5
- **Reasoning effort**: xhigh
- **Wall-clock at termination**: ~28 minutes
- **Output produced**: 6571 lines of exploration (file reads + grep results)
- **Findings produced**: 0 P0/P1/P2/P3 entries reached
- **Termination reason**: SIGTERM by orchestrator after 25+ minutes without findings phase. Codex was still in tool-call/exploration loop; CPU was 0% (waiting on OpenAI API responses) intermittently. Session budget exhausted; need to land closeout.

This is the **third** session this year where Codex CLI has been functionally unusable for closeout audits within reasonable budget:
- Session 152: `--full-auto` stdin hang (resolved in 155 — use `</dev/null` redirect)
- Session 154 Track E.4: subagent token-budget exhausted before reaching design phase
- Session 158b (this session): xhigh reasoning + thorough exploration runs >25 min without findings

**Lesson 178-adjacent**: Codex `xhigh` may need a hard wall-clock budget (e.g., 15 min) and a fallback to `medium` effort if findings haven't appeared. Or pre-prune the scope per audit (one file at a time vs 7 files at once).

The full Codex output (exploration logs, no findings) is preserved at `/tmp/codex_158b_audit.log` (6571 lines) for forensic review if useful. Not committed to repo (log is large + transient).

## Manual self-audit (by Claude main-thread, fresh re-read of the diffs)

Audit scope re-read:
- `scripts/session158b_historical_backfill_chunked.py` (313 lines, NEW, RAN partially)
- `scripts/session158b_cutover_rename.py` (144 lines, NEW, NOT YET RUN)
- `scripts/session158b_drop_and_vacuum.py` (191 lines, NEW, NOT YET RUN — IRREVERSIBLE)
- `scripts/session158b_r2_preflight_snapshot.py` (199 lines, NEW, NOT YET RUN)
- `scripts/migrations/session158b_current_v2_views.sql` (32 lines, NEW)
- `app/relationship_routes.py` (3 modified locations)
- `tests/test_gedcom_routes.py` (2 modified tests)

This is a self-audit and therefore not "independent." It's also not a substitute for the Codex findings that didn't land. **158c MUST run a fresh Codex audit on the IRREVERSIBLE scripts before they execute.** That is a non-negotiable gate.

### P0 — none identified by self-audit

(Self-audit cannot reliably surface P0s in the same code I just wrote. Codex independence matters most here. Flagged as a residual risk for 158c to address.)

### P1 — concerning items I want 158c-Codex to focus on

- **P1-A** `scripts/session158b_historical_backfill_chunked.py:181-191` (`_upsert_v2`) — retry count is 3 with fixed 3s sleep. Backfill DIED on chunk 6 because a single batch exhausted retries during pooler/REST instability. Recommend: increase to 6 retries with exponential backoff (3s, 6s, 12s, 24s, 48s, 96s) before raising. Also consider catching httpx-specific exceptions (ReadTimeout, RemoteProtocolError, ConnectError) explicitly so non-transient errors aren't retried.
- **P1-B** `scripts/session158b_drop_and_vacuum.py` — DROP step uses `BEGIN ... DROP TABLE ... COMMIT` for the three renamed tables. If pooler closes connection mid-DROP, transaction rolls back and we're back to renamed-but-alive state. That's actually safe behavior. BUT the VACUUM FULL step is in autocommit mode (required because VACUUM cannot run inside a transaction) — if pooler closes mid-VACUUM, we may end up with VACUUM on some tables but not others. That's also safe (can re-run on remaining tables). No immediate fix needed but worth flagging for 158c monitoring.
- **P1-C** `scripts/session158b_cutover_rename.py:54-66` — rollback path recreates `current_gedcom_individuals` view but does NOT restore any other dependent objects that may have been dropped. Need to verify there are no other views, indexes, foreign keys, or triggers depending on `gedcom_individuals` or `gedcom_families` that get implicitly dropped at RENAME time. Mitigation: add a pre-RENAME query that lists all objects depending on these tables; assert the only one is `current_gedcom_individuals` view.
- **P1-D** `app/relationship_routes.py` v2-view-first fallback chain — if `current_gedcom_individuals_v2` view returns ZERO ROWS (which it will until the view is created) we fall through? Re-reading the code: the fallback chain runs only when `.execute()` raises an exception. A successful query that returns empty data will NOT trigger fallback. So if the view exists but returns 0 rows (e.g., partial-state v2), the bulk loader returns []. This is actually correct behavior — but needs documentation. Mitigation: add a structural test that asserts post-cutover bulk-loader returns >=10K rows.

### P2 — quality/observability

- **P2-A** `_upsert_v2` doesn't log batch indexing on success (only on retry). For a 44-batch chunk (22K rows / 500 batch size), you can't tell from the log whether batches 1-43 succeeded. Add per-batch debug log: `print(f'  batch {i//UPSERT_BATCH+1}/{total_batches} OK in {elapsed:.1f}s')`.
- **P2-B** Backfill script lacks `--start-version` flag for resumability. Re-running from chunk 1 after a crash on chunk 6 means redoing 5 chunks of UPDATE-only work (~20+ min). Adding `--start-version v_num` to skip earlier chunks would save significant time on retries.
- **P2-C** `session158b_drop_and_vacuum.py` doesn't capture R2 archive prefix in the report header — only the date. If multiple 158b runs land different days, this loses provenance. Add `--r2-archive-prefix` arg or auto-derive from `gedcom-pre-drop-snapshots/<UTC-date>-session-158{b,c}/`.
- **P2-D** `session158b_cutover_rename.py:101` `verify_state` queries `information_schema.tables` for "all gedcom_*" tables but doesn't return them ordered or filter to only the relevant ones — output noise for debugging.
- **P2-E** R2 preflight script encodes JSONL to memory before upload. For a 196K-row table that's ~50-100 MB. Streaming upload (boto3 multipart) would reduce peak memory but probably not necessary at this scale.

### P3 — style/docs

- **P3-A** Backfill script's `_aggregate_chunk` mutates the input row dict via `{**r, ...}` — minor; produces a new dict, but it's worth a comment.
- **P3-B** Test rewrite for `test_single_individual_lookup_can_fetch_rich_row` carries a longer comment block explaining the v2 mock chain. Consider extracting a `_make_v2_mock(...)` helper for future tests that need this pattern.
- **P3-C** AD entries (AD-245, AD-246, AD-247) referenced in 158b prompt non-negotiable rules but NOT YET WRITTEN. Should land as part of 158c first commits.

## Provenance

Codex CLI run started but didn't produce findings within session budget. Self-audit by Claude is included as a stopgap. **158c MUST run an independent Codex audit on the IRREVERSIBLE scripts (drop_and_vacuum.py, cutover_rename.py) BEFORE they execute** — this is a non-negotiable gate per the prompt's "Codex final-pass audit on combined 158 + 158b commits" rule and per `.claude/rules/ai-tool-audit.md` "best-available model for audit work" principle.

To improve odds of completion in 158c:
1. Pre-prune scope to ONE file at a time (chunked-write script first, then drop+vacuum, then RENAME)
2. Set explicit wall-clock budget (15 min) and fall back to gpt-5.5 medium effort if no findings by then
3. Provide more focused prompts ("review IRREVERSIBLE DROP path for race conditions" vs "audit all 7 files")
