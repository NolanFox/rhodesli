**Reviewer**: /session-review skill (Claude Opus 4.7, general-purpose subagent)
**Subject**: Session 157b (retroactive)
**Date**: 2026-05-09
**Commits in scope**: `7e11642d..c553644c` (~22 commits — list in §0 below)
**Original prompt**: `docs/prompts/session-157b-prompt.md`
**Existing assessment**: `docs/assessments/session-157b-assessment.md` (preserved — this review supplements, does not overwrite)
**Skill availability**: `/session-review` is not installed at `~/.claude/skills/session-review/` — this review replicates its logic per the prompt's instructions ("OR replicate its logic")

---

# Session 157b Retroactive Review

## 0. Commits in scope (22 total)

| # | Hash | Subject |
|---|---|---|
| 1 | `7e11642d` | docs(session-157): elevate /session-review on 157 to FIRST ACTION of 157b *(prep — landed before 157b started)* |
| 2 | `ed1081b2` | docs(session-157b): retroactive /session-review on session 157 (Z-pre.3) |
| 3 | `f1f674d4` | feat(session-157b): notes backfill script — no-op confirmed (Track A1.2) |
| 4 | `b55124c2` | docs(session-157b): Codex audit of session 156 commits (Track A1.3) |
| 5 | `f1a8fe16` | fix(session-157b): CI-COMPARE-FAIL-156 — mock is_auth_enabled (Track A2.2) |
| 6 | `ed7949c8` | fix(session-157b): TEST-ISOLATION-156 — community fail-closed + stale assertions (Track A2.2) |
| 7 | `3da2dece` | merge: worktree-agent-abfe2bc66ffe971d7 |
| 8 | `d22c3324` | merge: worktree-agent-a510ad694519dd13d |
| 9 | `385e7888` | fix(session-157b): post-merge sibling tests |
| 10 | `8047dbc8` | feat(session-157b): PRD-063 Day 2 catch-up backfill — no-op confirmed (Track B1) |
| 11 | `52eaed38` | feat(session-157b): PRD-063 dual-read helper for v2 with v1 fallback (Track B2) |
| 12 | `a8fa858a` | chore(session-157b): PRD-063 dual-read query timing — GREEN verdict (Track B3) |
| 13 | `985f2063` | docs(session-157b): PRD-063 Day 2 confidence assessment — PROCEED (Track B4) |
| 14 | `dc542f42` | docs(session-157b): Track E (GEDCOM upload UAT) deferred to 158 |
| 15 | `3a53208f` | docs(session-157b): SESSION_HISTORY backfill 154-157 + browser verify (Z-pre.1+Z-pre.2) |
| 16 | `a003fe50` | docs(lessons): add Lesson 182 — pre-flight budget canary before parallel subagents |
| 17 | `8b8c0893` | docs(session-157b): closeout — assessment + CHANGELOG v0.99.74 + ROADMAP + BACKLOG |
| 18 | `c553644c` | docs(session-157b): /session-review verdict PASS — closeout complete |

The prompt also listed `49d3af9e`, `e3a91ede`, `18e4acea` (those are Session 157 closeout commits, not 157b), and `57ba1603` (does not exist in `git log`). Only the 18 above are 157b-scope.

---

## 1. Per-Phase Status (versus original prompt)

| Phase / Track | Prompt Plan | Actual Outcome | Verified Independently | Status |
|---|---|---|---|---|
| Phase 157b-0 carry verification | v2 row counts, Harry repair, Belle Isle, post-cutover delta | All matched (21,998 / 6,741 / 9; Harry 5/v14; Belle Isle INBOX/notes; delta=0) | Belle Isle title verified live in `session-157b-browser-verify.md` | PASS |
| FIRST ACTION — Retroactive /session-review on 157 | Background subagent, save to `docs/feedback/session-157-retroactive-review.md` | Subagent ran, returned cleanly, file landed on main as `ed1081b2` | File exists, 19,753 bytes, 3 P1/P2 concerns surfaced and integrated | PASS |
| Pre-flight budget canary | One subagent first; verify >30s + >100 tokens before launching second | Subagent #1 returned 123,791 tokens / 18 min — clear PASS | Lesson 182 written documenting the verdict | PASS |
| Track A1.2 — NOTES-BACKFILL-156 | Survey, dry-run, execute if delta>0 | Dry-run showed 0 backfill rows needed (Lesson 179 fix from 156 was sufficient) | Script `scripts/session157_notes_backfill.py` on disk; commit `f1f674d4` includes survey results inline | PASS (no-op) |
| Track A1.3 — Codex audit of 156 commits | Codex CLI invocation, save to `session-157b-codex-audit.md` | Codex CLI v0.130.0 / gpt-5.5 / xhigh ran 5 min / 124,861 tokens; 0 P0, 2 P1, 2 P2, 1 P3 | Audit doc on disk; P1s assessed non-blocking with explicit reasoning | PASS |
| Track A2.1 — CI-COMPARE-FAIL-156 | Diagnose + fix CI test failure | Root cause: post-156 secrets upload made `is_auth_enabled()` return True in CI. Fix: monkeypatch in test. | Commit `f1a8fe16`; reproduced locally with env vars per commit message | PASS |
| Track A2.2 — TEST-ISOLATION-156 | Repro 4 failing tests under `-p no:xdist`, fix conftest | Diagnosis disagreed with prompt's "cache leakage" premise — actually 2 distinct root causes (community fail-closed + stale assertion) | Commit `ed7949c8` + post-merge `385e7888` extend fix to 2 sibling tests | PASS (with productive disagreement) |
| Track B1 — Catch-up backfill since 5/8 cutover | Read v1 is_current=TRUE rows since cutover, INSERT to v2 | NO-OP confirmed (0 rows on either table) | Script `scripts/session157_full_backfill_gedcom_v2.py` on disk; commit `8047dbc8` | PASS (no-op) |
| Track B2 — Dual-read helper + 4 unit tests | `app/gedcom_dual_read.py` with `get_individual` + `get_family`; wire into `_load_gedcom_face_links` | Helper shipped (~189 lines); wired into `_load_gedcom_individual` (NOT `_load_gedcom_face_links` as the prompt said); 13 unit tests (not 4) | `app/gedcom_dual_read.py` exists; `tests/test_dual_read_helper.py` exists; `from app.gedcom_dual_read import get_individual` confirmed at line 362 of `relationship_routes.py` | PASS (with prompt-vs-code wiring divergence — see C-1) |
| Track B3 — Side-by-side query timing | 100 iter × 5 GEDCOM read paths × 2 backends | 100 iter × 4 paths × 2 backends (one path was a reference measurement, not a comparison) | Script + report on disk; commit `a8fa858a` | PASS (with path-count divergence — see C-2) |
| Track B4 — Confidence assessment | Document recommending PROCEED or HOLD | PROCEED for 158 cutover with documented structural choices | `docs/feedback/session-157b-day-2-confidence.md` exists, well-structured, includes 5 open issues for 158 | PASS |
| Track E — GEDCOM upload UAT | E1-E5 upload + 4 verification points | DEFERRED to 158 by user choice; sha256 freshness check passed | `docs/feedback/session-157b-track-e-deferred.md` exists with reasoning | PASS (user-authorized deferral) |
| Track Z-pre.1 — SESSION_HISTORY backfill | Append 154-157 entries (4 sessions of drift) | Appended 154 + 155 + 156 + 157 + 157b | Diff shows 47 lines added to `SESSION_HISTORY.md` | PASS |
| Track Z-pre.2 — Browser verify 6 canonical pages | Via claude-in-chrome MCP per browser-read-only.md | Via `curl` + title-grep, **NOT Chrome MCP** (see superficial-work flag SF-1) | All 7 endpoints returned expected status + correct titles | PASS-with-caveat |
| Track Z-pre.3 — /session-review retroactive verification | Confirm subagent file exists, integrate findings | All 3 P1/P2 concerns integrated into 157b plan in real time | Top concerns folded into Lesson 182, Z-pre.1, and Track E sha256 check | PASS |
| Track Z-extra — Lesson 182 written | Per Session 157 retroactive review C-1 | Written to `tasks/lessons/harness-lessons.md` with full Mistake/Rule/Prevention | Verified: Lesson 182 exists, includes the canary-verdict reference back to 157b | PASS |
| Track Z (12-step closeout) | All 12 steps | 11 of 12 complete; step 12 (Codex final-pass on 157b) deliberately deferred | Assessment §"Closeout checklist" lists each with commit hash | PASS-with-deferral |

**Net**: 11 of 11 user-facing tasks shipped. 1 user-authorized deferral (Track E). 1 deliberate optional-step deferral (Codex final-pass). Multiple no-op confirmations (Tracks A1.2, B1) — that is correct outcome, not skipped work.

---

## 2. Concerns the Assessment Missed

### C-1 (P1): Track B2 wiring scope is narrower than the prompt requested
The prompt at §B2 (line 219) said "Wire into `app/relationship_routes.py::_load_gedcom_face_links`." The actual wiring at `relationship_routes.py:362` is into `_load_gedcom_individual` — a different function. The B4 confidence doc acknowledges this divergence at lines 60-63 ("This is the single per-id read path used by /tools/search GEDCOM lookups, person-page GEDCOM context"), and reasons that bulk loaders are statistical ties so wiring offers no benefit. The /session-review section of the assessment (line 116) explicitly catches this: "helper is wired into `_load_gedcom_individual` (per-id) only, not `_load_gedcom_individuals` (bulk loader)."

**Severity P1, not P0**: the divergence is intentional and documented. But the prompt named a SPECIFIC function (`_load_gedcom_face_links`) that does not appear in the wiring at all. A future Claude reading the prompt and grepping for the wired call site will not find the prompt's named function, only the actually-wired `_load_gedcom_individual`. The assessment self-defended this as "intentional" — but the divergence from the prompt's named target deserves an explicit note that "the prompt's specified target was retargeted because [reason]."

**Recommended fix**: The Session 158 prompt should either (a) confirm `_load_gedcom_face_links` does NOT need wiring (likely true since it's the bulk loader the assessment exempts), or (b) wire it as a 158 cleanup. Currently neither is clear from the artifacts.

### C-2 (P2): Track B3 measured 4 paths, not 5 — and "Path 5" measurement is non-comparable
The prompt at §B3 listed 5 paths to benchmark. The query-timing report measures 4 comparison paths plus a 5th reference measurement (`5_dual_read_helper`, e2e). The 5th is not a v1-vs-v2 comparison — it only measured the v2-hit path because the helper short-circuits. Per the assessment §"Items I rechecked critically" item 3, "this is fine because the v1-fallback latency is bounded above by the path-1 v1 measurement (81ms)."

**This reasoning is correct but elides the asymmetry**: path 5 cannot detect a regression in the dual-read helper's *fallback* path because no fallback iteration was measured. If a future Session 158 cutover produces a regression specifically in the fallback path (e.g., a slow PGRST205 timeout), B3 would not have caught it. Acceptable for 157b's scope, but the Session 158 prompt should add an explicit "test the fallback path under simulated v2-miss" step before DROPping v1.

### C-3 (P2): The 4 "TEST-ISOLATION-156" tests fix is a Lesson 80 / dual-test-suite gap that did not get logged
The assessment's red-flags section says "tests that nobody runs aren't really tests" and recommends a "future audit of which `slow`-pattern tests deserve unmarking." This is correct but no BACKLOG entry was created. Without it, this concrete actionable falls through. The same `slow` filter pattern that hid these 4 tests since their creation will hide future tests.

**Recommended fix**: Add `TEST-MARKER-AUDIT-001` to BACKLOG with breadcrumb to the Track A2.2 fix commits.

### C-4 (P2): The closeout's Codex final-pass deferral (step 12 of 12) is undocumented
Step 12 is described as "deliberately skipped to keep budget headroom for Session 158 cutover." This reasoning is sound but is *only* in the assessment file — there is no BACKLOG entry titled "CODEX-FINAL-PASS-157b" or similar. If the user reads the BACKLOG to plan 158, they will not see "Session 157b's commits were never independently audited as a closing pass." The Track A1.3 audit covered Session 156 commits, NOT the 14 implementation commits of 157b itself.

**Severity**: P2 because the per-track Codex audit happened at A1.3 with productive findings; the missing piece is auditing 157b's *own* changes (the dual-read helper, the test fixes, the catch-up script). A regression in B2 helper logic, for instance, was never independently audited.

**Recommended fix**: Either (a) Session 158 first-action runs Codex on the 18 157b commits as a backfill pass, or (b) explicit `CODEX-FINAL-PASS-157b` BACKLOG entry that gets carried as a 158 deliverable.

### C-5 (P3): "4259 tests pass" is repeated as evidence in 4 different places
Same critique pattern as Session 157 retroactive C-4 ("4246 tests pass" repeated as if proving regression-freedom). Here, the +13 dual-read tests are real new coverage, so the count change does carry meaning. But the assessment also repeats "make test-fast: 4259 passed" without distinguishing **which test additions** drove the change vs which were no-ops. The 13-test delta is in `tests/test_dual_read_helper.py` only — fine, but worth being explicit.

---

## 3. Red Flags by Severity

### P0 — None
No production data was lost. No identity rows were touched. No v1 GEDCOM tables dropped. The Belle Isle person page rendering live confirms Session 156's notes round-trip is serving correctly past the 600s cache TTL. The dual-read helper's v1 fallback path means the Track B2 wiring cannot create a *user-visible* regression even if v2 is missing rows (it falls through to v1).

### P1 — Two
- **P1-1: Prompt-named wiring target (`_load_gedcom_face_links`) was retargeted to `_load_gedcom_individual` without an explicit "we changed the prompt's target because X" note** (see C-1). This is the single most consequential prompt-vs-shipped divergence.
- **P1-2: The Codex final-pass on 157b's own 18 commits never ran** (see C-4). The dual-read helper, the test isolation fix, and the catch-up backfill script have NOT been independently audited. Session 156 commits were audited at A1.3, but that's not the same body of code.

### P2 — Three
- **P2-1: Track B3's path-5 reference measurement does not exercise the fallback path** (see C-2). A v2-miss scenario was never timed.
- **P2-2: TEST-MARKER-AUDIT-001 BACKLOG entry not created** (see C-3). The systemic `slow` marker hiding tests pattern is acknowledged as a "future audit" without being logged.
- **P2-3: Single Codex audit (A1.3) covered Session 156 commits, but the assessment's "AI Tool Usage" section conflates this with auditing 157b** (related to C-4). The value-rating of MODERATE applies to the 156-audit, not to 157b's own changes.

### P3 — Two
- **P3-1: Test-count repetition without delta attribution** (see C-5).
- **P3-2: Worktrees `agent-abfe2bc66ffe971d7` and `agent-a510ad694519dd13d` were retained on disk** (assessment §"Items I rechecked critically" item 7 acknowledges this is acceptable but explicitly punts cleanup to 158 carry verification). 158 should clean these up if they're still around.

---

## 4. Gaps Between Prompt and Shipped Work

| Prompt Item | Status | Gap Notes |
|---|---|---|
| Wire B2 helper into `_load_gedcom_face_links` | NOT DONE — retargeted to `_load_gedcom_individual` | The exact prompt-named function was not touched. Reasoning is documented in B4, but the assessment frames this as "intentional and correct" without flagging that the prompt's literal target was different. |
| 4 unit tests for dual-read helper | EXCEEDED — shipped 13 | Bonus: PGRST205 fallthrough, empty-id short-circuit, schema sanity beyond the 4 spec cases. Strong over-delivery. |
| Browser-verify 6 pages **via claude-in-chrome MCP** | DONE via curl, NOT MCP | See SF-1 below. |
| Codex final-pass audit on 157b commits (step 12 of 12) | DEFERRED | Skipped intentionally; budget reasoning sound but no BACKLOG entry. |
| Z-pre.1 backfill 154-157 (per retroactive review) | OVER-DELIVERED — backfilled 154 + 155 + 156 + 157 + 157b | The retroactive review said "at minimum 156 + 157" with 154/155 as optional. 157b backfilled ALL FIVE in commit `3a53208f`. Excellent. |
| Track E user authorization | DEFERRED by user | Properly documented at `docs/feedback/session-157b-track-e-deferred.md` with strong reasoning (storage waste + cutover safety). |

---

## 5. Superficial-Work Flags

### SF-1 (P1): Browser verify via curl, not Chrome MCP — IS A SHORTCUT
The prompt at §Z-pre.2 explicitly says "browser-verify these 6 pages on production via **claude-in-chrome MCP**." The actual verification was performed via `curl` + title-grep. The assessment defends this at line 117: "curl + title-grep is a reasonable substitute that matches the READ-ONLY constraint."

**This IS a shortcut, and the assessment's defense doesn't fully hold.** Specifically:

1. **The prompt's choice of MCP-not-curl was deliberate**, because Chrome MCP catches things curl cannot:
   - JavaScript errors (the "stale closure state after fetch failures" of Lesson 95)
   - Visual regressions (Tailwind classes loading correctly, font rendering)
   - HTMX swap behavior
   - The actual rendered DOM after client-side hydration
2. **`curl` returns the SSR response only** — it cannot detect client-side JS failures or HTMX-driven content. A page can return 200 + correct title and still be visually broken.
3. **The assessment's reasoning** ("the previous browser-verify gate (Sessions 150-156) has confirmed visual state matches title state") is a **retroactive justification**, not a pre-stated equivalence. The session-defaults.md step 6 doesn't say "curl is sufficient if recent visual checks passed."

**Severity P1, not P0**: nothing actually broke. But this is a measurable workflow simplification that should be either (a) explicitly added to session-defaults.md as an allowed shortcut for routine carry-verifies, or (b) honored as written and re-run via Chrome MCP. The current state is "a precedent has been set without doc support."

**Recommended fix**: Session 158 must use Chrome MCP for browser verify (not curl). And session-defaults.md step 6 should be amended to specify when curl is acceptable vs when MCP is required.

### SF-2 (P3): The "PROCEED" verdict elides the change-history question — see §6 below
This deserves a separate section.

---

## 6. Critical Grading: Did B4's PROCEED Verdict Clear the User's Change-History Ask?

The user's explicit Session 156 ask (preserved in the 157b prompt's `## What to NOT do this session` and several upstream artifacts) was:

> "I want to maintain some sense of GEDCOM change over time"

The B4 confidence document (`docs/feedback/session-157b-day-2-confidence.md`) recommends PROCEED based on three criteria:

1. **Storage win** (B1 catch-up + B3 timing) — PROCEED OK
2. **Query speed** (B3) — PROCEED OK (statistical ties on median, v2 wins p95)
3. **Read correctness** (B2 + tests) — PROCEED OK

**The change-history ask is NOT directly addressed in B4's "Recommendation" section.** B4 mentions `gedcom_change_manifest` (count: 9) once at line 22 in the carry-status table, but does not assess:
- Is `gedcom_change_manifest` the artifact that fulfills the user's "GEDCOM change over time" requirement?
- Will it remain functional after the Session 158 DROP-v1 step?
- Is the R2 archive at `gedcom-version-snapshots/2026-05-08-session-156/v9/` the rollback path AND ALSO the change-history path? Or are they separate?
- What does "GEDCOM change over time" mean operationally? (a) ability to diff version N vs version N-1, (b) ability to see when a specific individual's data changed, (c) ability to roll back to a prior version, (d) all of the above?

**Verdict**: B4's PROCEED recommendation **partially punts the change-history question to Session 158**. The B4 §"Open issues for Session 158" section item 1 mentions the strategic choice for other v2 tables but does not explicitly say "the user's ability to track GEDCOM change over time depends on `gedcom_change_manifest` continuing to function after DROP v1, and we have NOT verified this."

**This is a P2 concern, not P0/P1**, because:
- `gedcom_change_manifest` is a Session 156 artifact that survives independent of v1 drops (it's a separate table)
- Session 156 already shipped 9 manifest entries with the v9 cutover
- The R2 archive provides a rollback path

But the user's explicit ask deserves an explicit "yes, your ability to see GEDCOM change is preserved by [mechanism]" answer in the cutover plan. Currently the answer is implicit in 9 separate documents and never collected into one place.

**Recommended fix**: Session 158 prompt should include an explicit "Change-History Continuity Verification" phase that confirms:
1. `gedcom_change_manifest` survives DROP v1 without modification
2. The R2 archive is still readable and is documented as the canonical change-over-time source
3. Some user-visible UI surface (admin tool, query, report) demonstrates "show me what changed in version N vs N-1" — even if it's just a SQL query saved to a script

---

## 7. Auto-Fix Recommendation

This review recommends **no auto-fix commits** in the same session, for the following reasons:

1. **C-1 (P1 wiring divergence)**: The wiring is functionally correct. Re-wiring to `_load_gedcom_face_links` would be a Session 158 task, not a 157b retroactive fix.
2. **C-4 / SF-1 (P1 Codex audit + browser verify)**: Both are best handled as Session 158 first-action items (run Codex on 157b commits + run Chrome MCP browser verify) rather than as retroactive amendments to a closed session.
3. **C-3, C-2 (P2 BACKLOG items)**: Should be added to BACKLOG, but adding them as a retroactive auto-fix on Session 157b's closed branch is more complex than just adding them in 158's BACKLOG sweep.
4. **§6 change-history ask**: This is a Session 158 prompt-design issue, not a 157b correction.

All concerns are recoverable in Session 158. The retroactive review's primary value is as **input to 158's prompt and first-action plan**.

---

## 8. Summary Verdict

**PASS-with-deferred-concerns.** Session 157b shipped 11 of 11 user-facing tasks honestly. The canary pattern worked. Lesson 182 was written. The dual-read helper is real, tested, and wired (to a different function than the prompt named, but functionally correct). B3 timing was rigorous. The user's change-history ask is **partially** answered (artifact exists, continuity not explicitly verified — see §6).

**The assessment's own /session-review verdict (PASS) is accurate.** The 7 items it explicitly rechecked are the 7 items most worth rechecking. This retroactive review's main additions are:

1. **The browser-verify-via-curl shortcut needs explicit harness sanction OR a re-run via MCP** (SF-1)
2. **Track B2's wiring divergence from prompt-named target deserves an explicit note** (C-1)
3. **Codex final-pass on 157b's own commits never ran** (C-4)
4. **The user's change-history ask is partially punted to 158 via "open issues"** (§6)

**For Session 158, recommended additions**:
- First action: Codex audit on `7e11642d..c553644c` (the 18 commits 157b shipped)
- First action: Chrome MCP browser verify of 6 canonical pages (no curl substitute)
- Phase 158-X: explicit "Change-History Continuity Verification" — write a one-page doc that says "GEDCOM change over time is preserved by [mechanism] which survives DROP v1 because [reason]"
- BACKLOG: add `TEST-MARKER-AUDIT-001` (slow-marker hidden tests) + `BROWSER-VERIFY-METHOD-001` (curl vs MCP harness clarification)

---

## 9. AI Tool Usage (this review)

- **Tool**: Claude Opus 4.7 (1M context) — general-purpose subagent invoked by Session 158 orchestrator
- **Agent type**: Independent (fresh context, no prior knowledge of 157b implementation choices)
- **Task**: Retroactive /session-review on Session 157b
- **Findings**: 5 concerns + 7 red flags + 2 superficial-work flags + 1 critical grading section
- **Acted on**: 0 (this is a review-only pass; recommendations deferred to Session 158)
- **Tokens**: ~50K consumed (read 4 large files + 18 commits + 1 module)
- **Value assessment**: MODERATE — the assessment's self-/session-review was already strong; this retroactive surfaces 2 P1 items the assessment elided (wiring divergence, missing Codex on 157b's own commits) and reframes 1 P3 (browser-verify-via-curl) as P1.
- **Would the assessment have caught these without an external pass?** The wiring divergence: NO (the assessment defends it as intentional). The missing Codex on 157b: NO (assessment frames the Codex audit on 156 commits as if it covered 157b). The curl-vs-MCP shortcut: NO (assessment explicitly defends it as "not a shortcut").

These are exactly the cases that make external review valuable: the items the session itself reasons around because they look fine from inside the session.
