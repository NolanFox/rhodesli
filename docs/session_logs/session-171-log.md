# Session 171 Log — Research Desk W1-S1+S2 + Security Riders

Started: 2026-07-13 · Prompt: `docs/prompts/session-171-prompt.md`
Plan: `docs/strategy/2026-07-reengagement/RESEARCH_DESK_PLAN.md`
Orchestrator: Opus 4.8 · Coder/Auditor: GPT-5.6-Sol · Investigators: Gemini 3.1 Pro + Sol · Architect: Fable 5

## Phase checklist
- [x] Phase 0a: init (session 171, mode implementation, venv, baseline test-fast **4638 passed**, harness-check)
- [x] Phase 0b: R1 tree scoping P0 — Sol coded (medium), 4 tests, commit `0c372aab`
- [ ] Phase 0c: R2 rotate ML_SERVICE_TOKEN — **USER ACTION** (Railway secret), surfaced to Nolan
- [x] Phase 1: first Morning Mystery (Belle Isle) — packet + 2 sealed verdicts + rubric + Fable review + delivery, commit `f4762898`
- [x] Phase 2: case/run contract (`investigation_runs`) — Sol coded (medium), 5 tests, migration applied + live-validated, commit `225b86da`
- [x] Phase 3: Sol xhigh audit + closeout docs + deploy + browser verify + CI

## Notes / deviations
- **R1 design fork resolved empirically:** the Fox GEDCOM is linked to identities across `rhodes` (53)
  and `fox-family` (9). Followed the approved acceptance criterion — Fox GEDCOM is `fox-family`-owned;
  rhodes/fader/bare-root get their own (near-empty) tree. Consequence flagged: the flagship root
  `/tree` now shows only Rhodes identities; the Fox tree lives at `/c/fox-family/tree`.
- **CHANGELOG version:** used **v0.99.92** (v0.99.91 was already taken by the Session 170 replan).
- **Belle Isle result:** both models ABSTAIN + DROP the Harry Isaackovitz candidate. The case still
  yields two concrete ledger deltas (drop a 36-year-old candidate; correct a stale NYC→Detroit
  location), which is why an abstention morning is still "worth opening."
- **Live contract validation:** real `create_run` for the Belle Isle case → run `edb28ae1`; idempotent
  re-run returned None; exactly 1 row for the idempotency key.

## Independent audit (Phase 3) — the gate earned its keep
Codex (gpt-5.6-sol, xhigh) ran the adversarial pass + live-tested, then stalled on final report → a
fresh-context Claude subagent completed + CONFIRMED it (`docs/session_context/session-171-codex-audit.md`).
**P1 (CONFIRMED, security):** R1 dropped Fox GEDCOM *nodes* but left kept nodes' `rels` +
`shared_photos` referencing dropped Fox nodes — leaking Fox UUIDs/`@xref`s/relationship structure.
Both the coder and my own review missed it; the original tests structurally couldn't catch it (stub
returned `rels: {}`). FIXED + regression test (`b5e83f7b`). P2 idempotency id-less-row + P3 TOCTOU
also FIXED. Auth-on-fox-family + key-delimiter DEFERRED → BACKLOG.

## CI-red caught + fixed (Lesson 208)
R1 made `test_tree_api.py` / `test_tree_navigation.py` (tree-building tests, synthetic ids) go red in
CI (Supabase present → rhodes scope fails closed → empty tree) while passing locally. Isolated those
building tests from R1 via a pass-through patch; R1 stays covered by `test_tree_community_scoping.py`.
68 tree tests pass; CI green (`806f7dcb`, run 29319931525 success).

## Verification gate — ALL PASS
- [x] All phases re-checked against original prompt
- [x] Zero writes to confirmed identity data (Phase 1 assembly read-only; Phase 2 module touches only investigation_runs)
- [x] Tests: R1 5/5, Phase 2 5/5, tree suite 68/68, full test-fast green (pre-commit on each commit)
- [x] Independent adversarial audit run; all P0/P1 fixed
- [x] Deploy verified on production (READ-ONLY): health 200, root 200, `/people` `/tools/estimate` `/tree` 200;
  **R1 confirmed live** — rhodes tree = 0 nodes / 0 Fox `@xref` (leak closed), fox-family tree = 15 nodes (Fox tree intact), fader = 0
- [x] CI green on the final push
- [x] `git log origin/main..HEAD` empty (all pushed)

## Outstanding (user action)
- **R2 — rotate `ML_SERVICE_TOKEN`** on Railway (Phase 0c). Not done autonomously.
- **R1 UX confirmation:** root `/tree` now Rhodes-scoped (empty on prod since rhodes identity-scope
  fails closed); Fox tree at `/c/fox-family/tree`. Confirm this is the desired UX.
- **TREE-AUTH-171 / RUN-KEY-171** in BACKLOG (deferred audit items).
