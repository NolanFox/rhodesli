**Auditor**: Codex CLI v0.130.0 (gpt-5.5, xhigh) — RUN STARTED but TERMINATED without findings phase. Self-audit by Claude Opus 4.7 supplements.
**Agent type**: Independent (fresh context Codex) + main-thread Claude self-audit
**Scope**: Session 158b commits `5799700a..33a4abab` (6 commits)
**Date**: 2026-05-09

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
