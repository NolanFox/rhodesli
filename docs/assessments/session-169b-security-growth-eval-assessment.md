# Session 169b Assessment — Security Investigation + Multi-Rhodesli Growth Evaluation

**Date:** 2026-07-05 · **Mode:** interactive investigation → evaluation (no implementation)
**Models:** Opus (orchestrate+verify) · Codex gpt-5.5/xhigh (security audit + eval draft + brief
audit-gate) · Fable 5 (live-site architect/evaluator, read-only).
**Trigger:** owner found 51 anonymous "Compare Upload" pending entries; feared key exposure/breach,
and asked for a full evaluation + roadmap to make rhodesli valuable for other Rhodes families
without being spammy.

## Shipped (evidence)
- [x] Security verdict — `SECURITY_VERDICT.md` + independent `codex-security.md`. NO breach, NO
  browser-reachable key exposure; root cause traced to `app/compare_routes.py:1571-1700` and verified.
- [x] Two real limited findings, verified against code: committed `ML_SERVICE_TOKEN`
  (`docs/session_logs/session-116-log.md:50`); missing `/photos` path-traversal guard
  (`app/main.py:1439`). Both → user action / implementation sprint.
- [x] Two-draft → audit-gate → Fable dispatch loop (fable-full-eval): `opus-draft.md` +
  `codex-draft.md` → `FABLE_EVAL_PROMPT.md` → `codex-audit.md` (SHIP-WITH-FIXES, all P1/P2/P3 applied).
- [x] Fable live-site eval: `UX_NEWCOMER_AUDIT.md` (11 findings, 17 screenshots, desktop+mobile),
  `SPAM_BOUNDARY_DESIGN.md`, `MULTITENANT_READINESS.md`, `GROWTH_ROADMAP.md` (28 items + pilot
  playbook + outreach-ethics), `EVALS.md`. All in `docs/fable-eval/2026-07-05-security-growth/`.
- [x] NEW P0 (both code drafts missed; Fable caught by loading the page): cross-community tree leak,
  verified in code (`app/page_routes.py:10950`).

## Deferred (with reason)
- Implementation of ALL findings — deliberately a SEPARATE gated sprint (Session 170 = Phase A).
  This session was evaluation-only by design (fable-full-eval exclusion list).
- Map/Timeline/Connect surfaces unaudited (likely same tree-leak class) — flagged for Session 170.
- Help-Identify submit UX described from code only (prod-browser mutation ban).

## Red flags / self-critical notes
- **[medium] Two P0 UX findings from Fable were initially false positives** (zero-stats + blank face
  circles = lazy-load); Fable correctly self-caught them before reporting. Good discipline, but a
  reminder that live-site findings need the same verify gate as code findings — which is why the
  orchestrator re-verified the tree P0 in code before surfacing it.
- **[low] The 51-count and Help-Identify submit path were not independently re-verified** (auth-gated;
  browser was kept read-only + unauthenticated). Carried forward, not "verified."
- **[low] Did NOT push to origin during the session** — all commits local until closeout. Fine for a
  docs-only eval, but noted.
- **Honest scope:** this produced a strong PLAN, not a fix. The value is entirely in the next
  session executing Phase A; an eval that isn't acted on is theater (the exact fable-full-eval risk).

## What worked (keep doing)
- The independent-audit-of-the-brief gate (Codex) tightened prod-browser safety (P1) before Fable
  touched the live site — earned its keep.
- Fable's live-site pass produced the single highest-value finding (tree leak) that neither code-only
  reviewer found → validated cross-repo meta-lesson (`shared-memory/fable_vision_delta_catches_pageload_bugs.md`).

## Next session should verify FIRST
1. The tree cross-community leak still reproduces (`/c/rhodes/tree` shows Fox GEDCOM) — it's Phase A/C.
2. `ML_SERVICE_TOKEN` rotation status (user action) before treating it as closed.
3. Read `GROWTH_ROADMAP.md` + confirm Phase A scope with the owner before coding.

## AI Tool Usage
- **Codex CLI v0.142.5 (gpt-5.5, xhigh)** — 3 independent runs: security audit (STRONG — confirmed
  no-breach + found real path-traversal + committed-token findings the orchestrator would have taken
  longer to surface), eval draft (STRONG — concrete file:line multi-tenant gaps), brief audit-gate
  (MODERATE-STRONG — caught a real prod-browser-safety P1 loophole). Agent type: independent, fresh context.
- **Fable 5** — live-site evaluator. Value: STRONG. Found the P0 tree leak by loading the page; ran
  read-only; self-caught 2 false positives. Would a code-only review have found the tree leak? No —
  both independent code drafts missed it (real comparator).
