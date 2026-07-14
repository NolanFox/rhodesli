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

## Verification gate
- [x] All phases re-checked against original prompt
- [x] Zero writes to confirmed identity data (Phase 1 assembly is read-only; Phase 2 module touches only investigation_runs)
- [x] Tests: R1 4/4, Phase 2 5/5, baseline 4638 (pre-commit hooks ran full test-fast on each commit)
- [ ] Deploy + production browser verify (Phase 3, in progress)
