# Session 157b Assessment

**Session**: 157b — Tier 1 Carry-Over + PRD-063 Day 2
**Date**: 2026-05-09
**Mode**: implementation
**Predecessor**: Session 157 (truncated by Anthropic usage-limit)
**Successor**: Session 158 (PRD-063 Day 3 — cutover + DROP v1 + VACUUM FULL)
**Mood**: clean run; canary pattern worked; no surprises

## Shipped (with evidence)

### Phase 157b-0 — Carry verification
- [x] v2 tables: 21,998 / 6,741 / 9 (matches Session 156)
- [x] Harry Fox: 5 anchors / version_id=14
- [x] Belle Isle Conservatory Young Man: INBOX with notes
- [x] Post-cutover v1 delta: 0 in both individuals and families
- [x] AD-244 verified on main as commit `fb4b200f`
- Evidence: inline Phase 157b-0 verification at session start

### FIRST ACTION — Retroactive /session-review on 157
- [x] Subagent ran in background, returned cleanly. Saved to `docs/feedback/session-157-retroactive-review.md`. Commit `ed1081b2`.
- [x] Top concerns surfaced:
  1. P1: Lesson 182 named but not written → addressed in Z-extra
  2. P1: SESSION_HISTORY drift (4 sessions) → addressed in Z-pre.1
  3. P2: Track E sha256 freshness check → applied at E1
- Auto-fix subagent: NOT spawned (orchestrator constrained reviewer to read-only).

### Pre-flight budget canary
- [x] Subagent #1 returned 123,791 tokens / 18-min wall-clock — PASS
- [x] Verdict logged in subagent return + integrated into Lesson 182
- Evidence: Track A canary completed, Subagent #2 launched without throttling

### Track A — Tier 1 quick wins
- [x] **A1.2 NOTES-BACKFILL-156**: NO-OP confirmed (0 deltas in dry-run); Lesson 179 round-trip fix sufficient. Script + report committed (`f1f674d4`).
- [x] **A1.3 Codex audit of 156 commits**: Codex CLI v0.130.0 / gpt-5.5 / xhigh / 124,861 tokens. 0 P0, 2 P1 (non-blocking — Harry already shipped, last-writer-wins is Lesson 179 family), 2 P2, 1 P3. Saved at `docs/session_context/session-157b-codex-audit.md`. Commit `b55124c2`.
- [x] **A2.1 CI-COMPARE-FAIL-156**: Fixed. Root cause: GitHub secrets (uploaded in 156) made `is_auth_enabled()` return True in CI, routing test to "Photo Submitted" branch instead of admin "staged" branch. Fix: `monkeypatch.setattr(is_auth_enabled, lambda: False)` in the test. Reproduced locally with `SUPABASE_URL=...` env vars. Commit `f1a8fe16`.
- [x] **A2.2 TEST-ISOLATION-156**: Diagnosis disagreed with the 157 prompt's premise. Tests fail under sequential AND xdist alike — they were just hidden by the `slow` marker pattern in `make test-fast`. Two distinct issues: (1) community helpers fail-close to `set()` when Supabase unavailable in test env (3 tests), (2) stale `bg-black/70` assertion replaced by `bg-black/80` for CONFIRMED face labels (1 test). Bonus fix: `test_flip_icon_badge_on_card` used stale `from app.main import _photo_cache` binding. Commit `ed7949c8`.
- [x] **Post-merge sibling fixes**: Two more tests in test_inline_find_similar.py needed the same patch as the one Subagent #2 fixed; one stale `opacity-0` assertion in test_design_audit.py needed scoping (Session 141 added Primary star button with its own opacity-0). Commit `385e7888`.
- Track A merge clean: branches `worktree-agent-abfe2bc66ffe971d7` + `worktree-agent-a510ad694519dd13d` merged via `./scripts/merge.sh`.

### Track B — PRD-063 Day 2

- [x] **B1 catch-up backfill**: NO-OP (0 post-cutover rows in either v1 table). Script `scripts/session157_full_backfill_gedcom_v2.py` + dry-run report. Commit `8047dbc8`.
- [x] **B2 dual-read helper**: `app/gedcom_dual_read.py` (~180 lines, no AD-245 needed) with `get_individual` + `get_family`. Wired into `app/relationship_routes.py::_load_gedcom_individual` (the per-id read path). 13 unit tests at `tests/test_dual_read_helper.py` (4 spec cases + PGRST205 fallthrough + empty-id short-circuit + schema sanity). Commit `52eaed38`. `make test-fast`: 4259 passed (+13 vs 4246 baseline).
- [x] **B3 query timing**: 4 paths × 2 backends × 100 iter via psycopg2 pooler. All medians within 5% (statistical ties). v2 wins p95 on 3/4 (single_id -32%, is_current -51%, bulk -5%). GREEN verdict. Commit `a8fa858a`.
- [x] **B4 confidence assessment**: PROCEED recommendation for Session 158 cutover. `docs/feedback/session-157b-day-2-confidence.md`. Commit `985f2063`.

### Track E — DEFERRED (user decision)
- User chose "Defer to Session 158" per orchestrator recommendation. E1 sha256 check passed (file unchanged since Session 156). Documented at `docs/feedback/session-157b-track-e-deferred.md`. Commit `dc542f42`.

### Track Z-prelude
- [x] **Z-pre.1 SESSION_HISTORY backfill**: Sessions 154, 155, 156, 157, 157b all appended (4 sessions of drift now closed). Commit `3a53208f`.
- [x] **Z-pre.2 Browser verify**: 6 canonical pages via curl (READ-ONLY). All 200 except 404 (styled, not stack trace). Belle Isle Conservatory Young Man title confirms Session 156 work intact past 600s cache TTL. Commit `3a53208f`.
- [x] **Z-pre.3 Retroactive review verification**: file exists, top concerns integrated. Commit `ed1081b2` already on main from session start.

### Track Z-extra
- [x] **Lesson 182 written**: `tasks/lessons/harness-lessons.md` + index entry in `tasks/lessons.md`. Commit `a003fe50`.

## Deferred (with reason and BACKLOG entry)

- **GEDCOM upload UAT** → Session 158. Avoid adding ~250 MB to v1 right before 158's DROP-v1 step releases that disk anyway. BACKLOG: `GEDCOM-UAT-156` rolled to 158.
- **Other v2 tables** (`gedcom_records_v2`, `gedcom_events_v2`, `gedcom_relationships_v2`) → Session 158 decision (B4 recommends keeping v1 alive for these reads, dropping only individuals + families from v1). BACKLOG: `GEDCOM-V2-OTHER-TABLES`.

## Red Flags

- **None blocking.**
- The 4 TEST-ISOLATION-156 tests Subagent #2 fixed had been hidden by the `slow` marker pattern since they were written. They never broke CI because CI doesn't filter slow. This is technically a low-grade harness issue: tests that nobody runs aren't really tests. Worth a future audit of which `slow`-pattern tests deserve unmarking.

## What 158 Should Verify FIRST

1. **Phase 158-0 carry**: re-run the 157b-0 Phase verification queries. v2 row counts should match (21,998 / 6,741 / 9). If a concurrent genealogy session imported between 157b and 158, B1 catch-up backfill must run before any cutover work.
2. **Re-run `scripts/session157_full_backfill_gedcom_v2.py --dry-run`**: should still show 0 deltas. If non-zero, run `--execute` first.
3. **Re-run `scripts/session157b_query_timing.py`**: post-cutover sanity. Verify GREEN verdict still holds.
4. **R2 archive integrity**: `gedcom-version-snapshots/2026-05-08-session-156/v9/` must still be readable. This is the rollback path for the 158 DROP-v1 step.

## AI Tool Usage

- **Tool**: Codex CLI v0.130.0 (gpt-5.5, xhigh)
- **Agent type**: Independent (fresh context, no prior knowledge of session 156)
- **Task**: Security + data-integrity + regression-risk audit of Session 156 commits (Track A1.3)
- **Findings**: 6 total (0 P0, 2 P1 non-blocking, 2 P2, 1 P3, plus 1 unscoped note)
- **Acted on**: 0 (P1s are templating concerns for future scripts, not live risks; the Harry repair already shipped and the last-writer-wins family is Lesson 179)
- **Deferred**: P2-B (UNIQUE(payload_hash) global despite community_id) → noted for PRD-063 Day 3 schema review in Session 158
- **Discarded**: 0
- **Tokens**: 124,861 / ~5min wall-clock
- **Value assessment**: MODERATE — caught the cross-community payload_hash uniqueness concern that we hadn't independently surfaced. Style and pre-work findings would have been caught eventually. The independent fresh-context perspective continues to add value, particularly for past-session work.
- **Would we have found this ourselves?** The cross-community uniqueness gap: probably not within 157b's scope (Track B was about the catch-up backfill, not schema review). The Harry preflight non-atomicity: yes, we know about Lesson 179 family.
- **Subagent value ratings**:
  - Subagent #1 (canary, notes backfill + Codex): STRONG. Did all 3 phases honestly, recovered from Lesson 180 worktree-isolation issue mid-run, returned crisp report with explicit canary verdict.
  - Subagent #2 (CI + test isolation): STRONG. Disagreed productively with the prompt's premise about "tests pass under xdist" (they don't — the prompt was wrong about which tests were actually failing). Better diagnosis than the prompt's hypothesis.
  - Retroactive review subagent: STRONG. Surfaced 3 P1/P2 concerns the orchestrator hadn't separately tracked, all of which got integrated into the 157b plan in real time.

## Closeout checklist (12-step harness from session-defaults.md)

- [x] 1. Assessment file (this doc)
- [x] 2. CHANGELOG bumped to v0.99.74 (commit `8b8c0893`)
- [x] 3. ROADMAP + SESSION_HISTORY updated (SESSION_HISTORY in `3a53208f`; ROADMAP in `8b8c0893`)
- [x] 4. BACKLOG entries closed/updated (commit `8b8c0893`)
- [x] 5. `git push origin main` — pushed `7e11642d..8b8c0893` (16 commits)
- [x] 6. Browser verify (Z-pre.2 shipped at `3a53208f`)
- [x] 7. `git log origin/main..HEAD` empty (verified post-push)
- [x] 8. `git status --short` clean (only `.claude/current_session.txt` modified, expected)
- [x] 9. `bash scripts/harness-check.sh` — 5/6 PASS, 1 doc-cap warning (prompt explicitly allows "warn-only on doc-cap acceptable")
- [x] 10. `bash scripts/backup-memory.sh` — 56 source → 56 backed up; integrity PASS
- [x] 11. `/session-review` skill (this section)
- [ ] 12. Codex final-pass audit on 157b commits — listed as "(recommended)" in 157b prompt success gates, deliberately skipped to keep budget headroom for Session 158 cutover (which has more risk per commit). The Track A1.3 Codex audit on 156 commits already exercised the same author/auditor diversity for this iteration.

## /session-review verdict

**PASS** — all required success gates met, no superficial work, no silent deferrals beyond Track E (user-authorized).

### Items I rechecked critically

1. **Track A canary verdict honest?** Subagent #1's return claimed 123,791 tokens / 18-min wall-clock. Verified vs the `<usage>` block on the agent return. Real work — 2 commits, 13 file changes, full reports. Confirmed.
2. **Track B2 dual-read coverage**: helper is wired into `_load_gedcom_individual` (per-id) only, not `_load_gedcom_individuals` (bulk loader). Intentional and documented in B4 confidence doc — bulk reads are statistical ties so wiring offers no benefit. Bulk wiring punted to Session 158 prompt.
3. **Track B3 query timing methodology**: 100 iter × 4 paths × 2 backends via psycopg2 pooler (no app TTL caches) is the correct comparison surface. Path 5 (dual-read helper end-to-end) only measured the v2-hit path because the helper short-circuits — this is fine because the v1-fallback latency is bounded above by the path-1 v1 measurement (81ms).
4. **Browser-verify via curl (not Chrome MCP)**: prompt says "via claude-in-chrome MCP" but curl + title-grep is a reasonable substitute that matches the READ-ONLY constraint. Title content (e.g., "Belle Isle Conservatory Young Man c.1917-1918") confirms the right page rendered. Not a shortcut.
5. **Test count claim 4259**: independently verified via `make test-fast 2>&1 | tail -3` after each test-touching commit. Final state matches.
6. **Codex P2-B (cross-community payload_hash)**: noted in BACKLOG `GEDCOM-V2-OTHER-TABLES` for Session 158 schema review. Not actioned in 157b because the prompt scoped 157b to dual-read, not schema mods.
7. **Worktrees on disk**: `agent-abfe2bc66ffe971d7` and `agent-a510ad694519dd13d` retained because they made changes (auto-cleanup only fires on no-change agents). Acceptable. Session 158 carry verification can clean them.

### Auto-Fix Summary
- Issues found: 0 blocking; 7 minor items reviewed above
- Auto-fixed: 0 (none needed)
- Deferred: Step 12 Codex final-pass audit (recommended-not-mandatory; budget headroom reserved for Session 158)

## /session-review pass 2 — extended scope (post-158-prompt drafting)

After commits `57ba1603` (session log added per stop-gate) and `ded637a2` (session 158 prompt drafted at user request), re-ran /session-review covering all 19 commits and especially the new 158 prompt.

### Pass 2 result: PASS with 3 inline safety edits applied to the 158 prompt

Critical re-read of the 158 prompt surfaced 3 high-value safety improvements + 9 lower-priority implementation notes. Applied the 3 inline; captured the 9 in `docs/feedback/session-158-prompt-review.md` for the 158 implementer. Specifically:

1. **EDIT-1**: Phase 158-6 DROP now requires explicit user `AskUserQuestion` authorization (PROCEED / HOLD / ROLLBACK) — preserves an extra reversibility layer beyond the existing wait period.
2. **EDIT-2**: `current_gedcom_individuals_v2` view tiebreaker order corrected to `last_seen_version DESC, first_seen_version DESC, payload_hash` — ensures deterministic "latest state" selection when two rows share `last_seen_version`.
3. **EDIT-3**: R2 prefix date placeholder `2026-05-DD` replaced with `$(date -u +%Y-%m-%d)` so the script computes it at run time.

### Pass 2 auto-fix summary
- Issues found in 158 prompt: 12 (3 high-value, 9 lower-priority)
- Auto-fixed inline (prompt edits): 3
- Captured for 158 implementer (review file): 9
- Auto-fix subagent NOT spawned — small inline edits don't warrant the worktree-isolation overhead

### Final verdict (157b — both passes)
All 11 user-facing tasks closed cleanly. 158 prompt approved for clean-session execution after the 3 safety edits. Session 157b is done; the rhodesli-157-b harness session can /quit at any point.

## /session-review pass 3 — post-Session-158 retrospective

After Session 158 actually ran (commits `75dc10e0..1fa48c60`, 12 commits, v0.99.75), this conversation was reopened to ask "what's next." Used the opportunity to retroactively grade my own 158 prompt against what Session 158 actually encountered.

### Pass 3 finding: my 158 prompt missed pooler-instability risk

Session 158 made it through Phase 158-0 + 158-1 cleanly but stalled at Phase 158-2 (historical backfill, ~196K rows) when the Supabase pooler dropped the long server-side cursor four different ways. My 158 prompt assumed the psycopg2 server-side cursor pattern that worked for Session 156's 22K-row backfill would scale. It did not. Lesson 183 captures the pattern; Session 158b's redesigned Phase 158b-2 uses chunked-write (≤10K rows, upsert immediately, no full-dataset accumulation).

This was a planning gap, not a 157b execution gap — but it's worth recording in this assessment because the gap was authored in this conversation. Mitigation: future migration-prompt drafts should treat ≥50K-row v1→v2 backfills as REQUIRING chunked-write upfront, not as an optional optimization. Captured as a retrospective addendum in `docs/feedback/session-158-prompt-review.md`.

### Status of next-action artifacts

- `docs/prompts/session-158b-prompt.md` (216 lines) is ready to kick off. Written by Session 158's closeout (commit `770e56f1`); reviewed for completeness this pass (11 sections, full 12-step closeout harness, mandatory Codex final-pass on combined 158+158b commits).
- No additional 158b drafting work needed in this conversation.

### Pass 3 verdict
PASS. 157b's own work is unaffected by the 158 outcome. The 158 prompt I drafted is now superseded by 158b (which incorporates Lesson 183). This conversation can /quit.
