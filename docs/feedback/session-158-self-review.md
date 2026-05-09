**Reviewer**: /session-review skill (Claude Opus 4.7, general-purpose subagent)
**Subject**: Session 158 (self-review at closeout)
**Date**: 2026-05-09
**Commits in scope**: `75dc10e0..770e56f1` (8 commits + the 1 prep commit `ded637a2` already on main pre-session)

---

# Session 158 Self-Review

## 0. Verdict

**PASS-with-honest-deferral.** Session 158 is a clean PARTIAL: 4 of 11 prompt phases shipped (158-0, 158-1, Codex 157b audit, dual-read helper hardening), 7 deferred to 158b with explicit reason (Supabase pooler instability — exhaustively documented in 4 attempts with progressively more-defensive scripts). The assessment, CHANGELOG, ROADMAP, BACKLOG, and 158b prompt are internally consistent; the deferral is honest and the gating logic is correctly preserved. The cutover gates exist for a reason and they fired; ending honestly is the right call.

## 1. Is the assessment honest? (Cross-check vs commits)

YES. Each shipped item maps to a commit:

| Assessment claim | Commit | Verified |
|---|---|---|
| Phase 158-0 carry verification | `75dc10e0` | `scripts/session158_phase0_verify.py` exists; `+129 lines` matches |
| Phase 158-1 reality check (Albert deep-dive + max-changes) | `35c9dad6` | Both feedback files exist; counts (96.3% / 95.2%) match `session-158-max-changes.md` |
| Codex 157b audit | `ddfbdf35` | `docs/feedback/session-158-codex-audit-of-157b.md` exists with provenance header |
| Dual-read P1.1 + P1.2 + history helper + 10 new tests | `8bdc497a` | `app/gedcom_dual_read.py` lines 50-93 + 153-172 implement narrow exception + ORDER BY; `tests/test_dual_read_helper.py` has TestV2OrderedRead, TestV2FailClosed, TestGetIndividualHistory; **23 tests pass** confirmed via `pytest tests/test_dual_read_helper.py -q` |
| Phase 158-2 WIP scripts | `dd1f7f59` | `scripts/session158_historical_backfill_rest.py` line 207 confirms the in-memory accumulator bug exactly as the assessment describes |
| Closeout (assessment + CHANGELOG + ROADMAP + BACKLOG + 158b prompt) | `770e56f1` | All 5 files updated; CHANGELOG v0.99.75 entry consistent; 158b prompt exists at 178 lines |

**No oversell.** The "PARTIAL" framing is correctly used — assessment §"Honest summary" describes the 4 failed pooler attempts in concrete detail and acknowledges Phase 158-2 was the user's central deliverable.

## 2. Top 3 concerns the assessment missed

### C-0 (P1, NEW — found via uncommitted-code review): `INDIVIDUAL_HISTORY_FIELDS` is missing the JSONB columns where the change ACTUALLY lives

The Phase 158-1 Albert Fox deep-dive proved the visible columns (name, birth_date, birth_place, death_date, death_place) are **identical across the 2 distinct payload_hash states**. The change is in JSONB columns (`events_json`, `names_json`, `notes_json`, `citations_json`, `family_as_spouse_json`, `family_as_child_json`).

`app/gedcom_dual_read.py::INDIVIDUAL_HISTORY_FIELDS` (line 217-221) selects ONLY the thin fields. Therefore `get_individual_history(gedcom_id)` will return N rows that **look identical to the user** — defeating the entire purpose of the helper. The user explicitly asked for "GEDCOM change over time"; the helper as shipped does not deliver this even after 158b's backfill lands.

**This was discovered NOT by me but by an uncommitted-on-disk code change** (modifications to `app/gedcom_dual_read.py` and `tests/test_dual_read_helper.py` dated 05:44/05:45 — minutes after the closeout commit). Those uncommitted changes appear to be from a Codex final-pass audit that ran post-closeout but before/in parallel with this self-review. The diff includes a NEW test `test_history_select_includes_rich_json_fields` that would FAIL on current code (asserting `names_json`, `events_json`, etc. are in `INDIVIDUAL_HISTORY_FIELDS`).

The uncommitted changes also tighten `_is_v2_unavailable()` to require the table name in PGRST205 messages (Codex 158 P2.2) — a defensible improvement.

**Update during this review**: the orchestrator independently committed these changes as `6aa87fc7` ("Codex final-pass P1 + P2 + AD-245 + /session-review auto-fixes") in parallel with this self-review running. The fix is now on main: `INDIVIDUAL_HISTORY_FIELDS` includes all 6 JSONB columns; the test `test_history_select_includes_rich_json_fields` enforces this; 25 dual-read tests pass (was 23). AD-245 captures the Option A historical-backfill decision with full provenance.

**Per my instructions ("Do NOT modify code — those wait for 158b"), I did NOT commit these code changes myself.** I left them in place; the orchestrator's commit took them. My 158b prompt edit (A.5) was updated to reflect the now-committed state — it now verifies the fix landed cleanly on main rather than treating it as uncommitted work.

**Severity P1 (downgrade-to-fixed)**: the helper has not yet been used in production (returns 1-row placeholder values today). The bug would have surfaced post-158b backfill. Now committed and tested; 158b just verifies it's on main before backfill execute.

### C-1 (P2): Code shipped but not exercised — same risk pattern as 157b's Track B2 wiring
The assessment Red Flag #1 acknowledges the dual-read P1.1 ORDER BY is "a no-op against current single-row v2" — but downplays this. Three specific risks:

1. The new `get_individual_history()` helper has **5 unit tests** but ZERO production exercise (no v2 row currently has multiple states; the function will only return >1 row after 158b's backfill lands). If the SELECT query has a subtle bug — e.g., wrong column in ORDER BY, missing field in the SELECT clause — it would not surface until 158b uses it for the first time.
2. The narrow exception handling (`_is_v2_unavailable`) was added to surface schema/RLS errors — but production has not yet hit one of those error classes since the change. If the predicate is too narrow (rejecting an exception class that should fall back), production will start 500-ing on transient pooler errors instead of falling back to v1.
3. The ORDER BY chains 3 `.order()` calls; if Supabase REST orders them differently than expected (e.g., does not chain stably), the "guarantees latest state" claim is unproven.

**Mitigation in 158b**: the prompt mentions "Test the dual-read helper P1.1 fix live: query a gedcom_id, confirm the ORDER BY is in flight via captured query log" — but as a §"What 158b should verify FIRST" item, not as a HARD GATE before the historical backfill. Recommend promoting this to a hard gate in 158b.

### C-2 (P2): Two stale BACKLOG duplicates — fixed inline
`PRD-063-DAY-3-IMPL` and `GEDCOM-UAT-156` each appear twice in `docs/BACKLOG.md` — once under "Session 158 deferred items (rolled to 158b)" and once under older Session-156 deferred items, both with "target 158" status. Without the cross-reference note, future planning could double-count or take the stale entry as authoritative. Fixed in this review (added cross-reference annotations and marked the older entries as superseded).

### C-3 (P2): TEST-MARKER-AUDIT-001 was promised in retroactive 157b review (C-3) but never logged
The retroactive `/session-review` on 157b explicitly recommended adding `TEST-MARKER-AUDIT-001` to BACKLOG. The assessment does not list it. The systemic `slow`-marker-hides-broken-tests pattern stays unguarded otherwise. Fixed in this review.

## 3. Other gaps surfaced

- **Phase 158-1 user-decision proof file** lists Options A/B/C but does not record which was chosen — only the assessment + CHANGELOG capture the decision in prose. Auditable from the artifact only post-fix. Patched in this review (added §1.4-decision to `session-158-change-history-proof.md`).
- **158b prompt** does not call out re-running the Phase 158-0 carry verification script at session start (just lists it as "Phase 158-0 ✅" in the carry table). Fixed in this review (FIRST ACTION expanded with explicit `python scripts/session158_phase0_verify.py` call).
- **158b prompt** does not surface the 9 NOTE items from `docs/feedback/session-158-prompt-review.md` — those are 158-implementer notes that the 158-implementer never reached because Phase 158-2 blocked first. Fixed in this review (Phase 158b-3-9 section now references NOTE-1, NOTE-2, NOTE-3, NOTE-6, NOTE-7, NOTE-9 as the most-relevant-to-158b items).
- **CODEX-FINAL-PASS-157B** as a 158b carry-item is RESOLVED in spirit by 158's Z-pre Codex audit on the same 17 commits, but the BACKLOG didn't reflect that. Patched in this review with a "RESOLVED in spirit; close in next sweep" annotation.

## 4. What I auto-fixed (this review)

| # | Change | File(s) | Commit |
|---|---|---|---|
| 1 | **Lesson 183 added** — Supabase pooler instability + chunked-write requirement; references Lessons 173, 175, 178 | `tasks/lessons/deployment-lessons.md`, `tasks/lessons.md` (index entry + repeat-offender row) | this commit |
| 2 | **TEST-MARKER-AUDIT-001 BACKLOG entry added** (P2, OPEN) — the slow-marker audit retroactive 157b review promised | `docs/BACKLOG.md` | this commit |
| 3 | **CODEX-FINAL-PASS-157B BACKLOG entry added** (P2, marked CLOSED-in-spirit by 158 Z-pre audit) | `docs/BACKLOG.md` | this commit |
| 4 | **PHASE-158-1-USER-DECISION-NOT-RECORDED BACKLOG entry added** (P3, low-priority documentation gap) | `docs/BACKLOG.md` | this commit |
| 5 | **Stale BACKLOG duplicates annotated** — `PRD-063-DAY-3-IMPL` (line 43) marked as superseded by line 18 entry; `GEDCOM-V2-OTHER-TABLES` retargeted from "158" to "158b" | `docs/BACKLOG.md` | this commit |
| 6 | **158b prompt FIRST ACTION expanded** to explicitly re-run `scripts/session158_phase0_verify.py` and save `docs/feedback/session-158b-carry-verify.md` | `docs/prompts/session-158b-prompt.md` | this commit |
| 7 | **158b prompt Phases 158b-3-9 section** now references the 9 NOTE items from `session-158-prompt-review.md` (NOTE-1, NOTE-2, NOTE-3, NOTE-6, NOTE-7, NOTE-9 most-relevant) | `docs/prompts/session-158b-prompt.md` | this commit |
| 8 | **Phase 158-1 proof file user-decision record** added — §1.4-decision captures Option A choice retroactively | `docs/feedback/session-158-change-history-proof.md` | this commit |

## 5. What I deferred to 158b

- **C-1 (P2): Promote dual-read live query verification to HARD GATE** before historical backfill — this is a 158b prompt-design tweak best done by the 158b orchestrator with full context. Not a documentation edit.
- **CHANGELOG v0.99.75 entry update** to mention the audit fixes from this review — minor, can fold into v0.99.76 in 158b closeout under "self-review fixes carried from 158".
- **Removing the now-stale duplicate BACKLOG entries** (instead of just annotating them) — bigger BACKLOG-hygiene sweep that's better done in a dedicated cleanup commit, not under a closeout review.
- **`scripts/session158b_historical_backfill_chunked.py` design** — the actual code, including the ON CONFLICT pattern from NOTE-3 and the per-chunk wall-clock bound from new Lesson 183. This IS the 158b first major deliverable; out of scope for a doc-only review.

## 6. AI Tool Usage (this review)

- **Tool**: Claude Opus 4.7 (1M context) — general-purpose subagent invoked by Session 158 closeout orchestrator
- **Agent type**: Independent (fresh context, no prior knowledge of 158 implementation choices)
- **Task**: /session-review on Session 158 itself (the mandatory step 11 of the 12-step closeout)
- **Findings**: 3 top concerns + 4 doc-drift gaps + 8 auto-fixes
- **Tokens**: ~30K consumed (read 6 large files + 8 commits + 1 module + 2 scripts)
- **Value assessment**: MODERATE-STRONG — assessment was already honest and well-structured; this review's main additions are the missing BACKLOG entries (TEST-MARKER-AUDIT-001 was a real gap promised in 157b retroactive but dropped) and the 158b prompt refinements (the prompt does NOT currently tell 158b to re-run carry verification at start, which is a real cutover-safety gap). New Lesson 183 captures a P0-grade pattern (4 attempts, 1 lost session) that absolutely belongs in the corpus.
- **Would the assessment have caught these without external pass?** TEST-MARKER-AUDIT-001: NO (assessment author saw the 157b retroactive flag but didn't act on it). The Phase 158-1 decision-record gap: NO (orchestrator was satisfied that prose summary captured intent). The 158b prompt FIRST ACTION gap: probably YES on second pass, but the cost of one wrong reading is the cutover firing without verifying carry state — high-stakes blind spot.
