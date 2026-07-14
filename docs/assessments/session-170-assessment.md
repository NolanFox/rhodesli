# Session 170 Assessment — The Research Desk Replan (2026-07-13)

**Session type:** Strategy/planning (interactive mode; docs-only, no code/data/prod mutation).
**Original ask (owner, verbatim intent):** engagement collapsed because the roadmap stopped serving
the two core loves (Rhodes history documentation; identifying family in photos); go deep with
Fable + the new gpt-5.6-sol, generate every idea that could work, iterate until both models agree
on an ambitious plan, write it up + a multi-model session prompt, research model settings, log
everything into the harness, run the meta-analysis.

## Shipped

- [x] **Research fleet (4 parallel workstreams)** — Evidence:
  `docs/strategy/2026-07-reengagement/{engagement-evidence,tech-state,model-settings-research}.md`
  + Sol pass-1. Engagement mining (what energizes/drains, direct quotes), technical inventory
  (4 domains + leverage points), model-settings research (Sol GA 7/9, effort tiers, Terra/Luna,
  Fable-vs-Opus economics, community orchestration patterns).
- [x] **Two independent architect drafts, same brief** — `fable-pass1.md` (Fable) +
  `sol-pass1.md` (gpt-5.6-sol xhigh, 21 ideas, cited to file/line, own web research incl. the
  source-rights landscape). Sol given a first-class chance to shine, and it did.
- [x] **Adversarial iteration to convergence (3 rounds)** — `adjudication-round1.md` →
  `sol-critique.md` (AGREE-WITH-CHANGES + 5 failure modes with arithmetic + first-2-weeks
  sequence + 6 both-missed items) → `sol-signoff.md` (**CO-SIGN-WITH-NITS**, nits folded in).
- [x] **THE deliverable:** `docs/strategy/2026-07-reengagement/RESEARCH_DESK_PLAN.md` — the
  Morning Mystery with sealed verdicts; 4 lanes, WIP 1+1; consent-first evidence supply;
  Retrieval 2.0; kill list; 30-day pilot bar; model-orchestration table; operating rules.
- [x] **Next-session prompt:** `docs/prompts/session-171-prompt.md` (W1-S1+S2 + security riders
  R1-R3), with explicit multi-model operating instructions (Opus orchestrate · Sol medium-code/
  xhigh-audit · Fable ≤2 dispatches · budget stop rule · canary rule).
- [x] **Harness wiring:** codex pin → gpt-5.6-sol (tiered efforts) in
  `.claude/rules/codex-model-pin.txt` + `ai-tool-audit.md`; session-170 growth prompt marked
  SUPERSEDED; ROADMAP ★NOW section; BACKLOG Research Desk section + deprioritizations;
  CHANGELOG v0.99.91; project memory (`project_research_desk_pivot` + supersession note on the
  growth-eval memory) + MEMORY.md index; shared memory (parallel-idea-generation → VALIDATED ×2,
  new `multimodel_sol_effort_tiering`).
- [x] **Meta-analysis:** `docs/strategy/2026-07-reengagement/meta-log.md` (what worked/didn't,
  cost, fixes for next time).

## Deferred

- Session 171 execution (the first Morning Mystery) — deliberately: the plan's own WIP rule.
- Old Phase-A growth items beyond Riders R1-R3 — deprioritized per plan kill list (BACKLOG).
- Terra/Luna bulk-model pilot — noted in pin file + shared memory as unpiloted.

## Red flags

- [P2] Lesson-182 canary skipped when launching 3 research agents simultaneously (no harm done;
  logged in meta-log; follow the canary rule in 171).
- [P2] Sol's residual risk stands: a trust-breaking first artifact could sour the whole program —
  mitigated structurally (W1-S1 hand-builds the artifact before automation) but it's the thing
  to watch.
- [P3] `engagement-evidence.md` is 306 lines (6 over the doc cap) — research artifact, not a
  living doc; acceptable, noted.

## AI Tool Usage (per ai-tool-audit.md)

- **Tool:** Codex CLI v0.144.3 (gpt-5.6-sol) — 3 runs: ideation (xhigh), critique (xhigh),
  sign-off (high, via `-c model_reasoning_effort`). All `codex exec ... </dev/null`, zero stalls.
- **Agent type:** Independent (fresh context each run; round 2-3 read prior artifacts from disk).
- **Findings:** pass-1: 21 ideas, 2 repo discoveries (investigations table, stale gemini-2.0-flash);
  critique: 5 failure modes w/ arithmetic, 6 both-missed items, source-rights table; sign-off: 3 nits.
- **Acted on:** plan restructured around the critique (WIP limit, $2 cap, ≤3 decisions, revised
  30-day bar, sealed-verdict autonomy answer); all 3 sign-off nits folded in.
- **Value assessment: STRONG** — the arithmetic critique and the rights table are things we would
  not have produced alone; the autonomy-boundary catch reshaped the core product.
- **Claude side:** 3 subagents (haiku web-research ~110k tok; 2× sonnet repo-mining ~211k/~181k tok).
  Fable main loop as architect/orchestrator.

## Next session should verify FIRST

1. `RESEARCH_DESK_PLAN.md` + `session-171-prompt.md` exist on main and CI is green.
2. Rider R1 (tree-leak P0) lands before any Desk work — it's the only live privacy leak.
3. The Belle Isle case evidence is still as described (identity `ef39908e-...`, 2 anchors,
   GEDCOM candidate at 0.3) before building the packet.
