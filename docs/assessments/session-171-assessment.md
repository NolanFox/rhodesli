# Session 171 Assessment — Research Desk W1-S1+S2 + Security Riders

**Date:** 2026-07-13/14 · **Mode:** implementation · **Plan:** `docs/strategy/2026-07-reengagement/RESEARCH_DESK_PLAN.md`
**Orchestrator:** Opus 4.8 · **Coder/Auditor:** GPT-5.6-Sol (medium/xhigh) · **Investigators:** Gemini 3.1 Pro + Sol · **Architect:** Fable 5

## Shipped
- [x] **Phase 0 / R1 — Tree scoping P0 (cross-community GEDCOM leak).** `/api/tree/data` +
  `/api/tree/expand` now scope to the viewing community; Fox GEDCOM is owned by `fox-family`, every
  other community sees only its own identities (fail-closed on unknown scope). Coder: Sol (medium).
  Evidence: commit `0c372aab`; 4 hermetic tests in `tests/test_tree_community_scoping.py`.
- [x] **Phase 1 / W1-S1 — First hand-built Morning Mystery (Belle Isle young man).** Immutable evidence
  packet (E1-E13, hashed manifest), TWO independent blind sealed verdicts (Gemini 3.1 Pro + Sol medium
  — both ABSTAIN + DROP the weak Harry Isaackovitz candidate), the binary "worth-opening" rubric, and
  a mobile-first interactive artifact delivered to Nolan. Fable reviewed the artifact vs. the rubric;
  its self-scoring-honesty fixes were applied. Evidence: commit `f4762898`; Gemini call logged to
  `gemini_api_calls` (experiment_id `manual-session171-belle-isle`); zero writes to confirmed data.
- [x] **Phase 2 / W1-S2 — Case/run contract.** New `investigation_runs` table (extends, doesn't
  replace, `identification_investigations`): immutable input manifest + hash, idempotency key, atomic
  single-upsert creation, status lifecycle, sealed-verdict envelope, ≤3-decisions CHECK, `rights_state`
  stub. 5 structural tests (atomicity / no-confirmed-writes / idempotency / decision-limit /
  transition-guard). Migration applied to Supabase (additive/idempotent); validated on the real Belle
  Isle run (`edb28ae1`, idempotent re-run → 1 row). Evidence: commit `225b86da`.

## Deferred / User action
- **R2 — Rotate `ML_SERVICE_TOKEN`** (Phase 0c): production-secret rotation on Railway. NOT done
  autonomously (requires Railway env access + ML-service redeploy + owner authorization). Surfaced to
  Nolan with exact steps. This is the one Phase-0 item outstanding.
- **R3 (ephemeral compare):** already cut by owner directive 2026-07-13 (consent items deprioritized);
  lives in BACKLOG only. Not in scope.

## Red flags / watch
- **R1 behavior change to the flagship surface:** the bare root `/tree` (defaults to `rhodes`) and
  `/c/rhodes/tree` now show only Rhodes identities — the Fox family tree lives at `/c/fox-family/tree`.
  This is the intended fix per the approved acceptance criterion, but it is a visible change to how
  Nolan reaches his own tree. **Next session / Nolan should confirm** this is the desired UX (browser
  verify at closeout).
- **Sealed-verdict token/cost not auto-captured:** the Gemini call logged with cost/tokens NULL; the
  artifact records an estimated $0.14. Capturing `usage_metadata` is a nightly-runner TODO.

## Next session should verify first
1. R1 on production (READ-ONLY): `/c/rhodes/tree` data contains no Fox GEDCOM individuals; `/c/fox-family/tree` still renders the Fox tree.
2. Whether Nolan wants the Fox tree reachable from the root or only under `/c/fox-family/`.
3. R2 token rotation status.

## AI Tool Usage
- **Sol (gpt-5.6-sol)** via `codex exec </dev/null`: R1 coder (medium, 47k tok), Phase 2 coder
  (medium, 40k tok), sealed verdict (medium, 12k tok), adversarial audit (xhigh — see codex-audit doc).
  Value: STRONG on code (both features implemented to spec with hermetic tests on the first pass).
- **Gemini 3.1 Pro:** sealed investigator verdict (multimodal, logged, ~$0.09).
- **Fable 5** (Agent, 1 dispatch, 135k tok): artifact-vs-rubric architect review. Value: STRONG —
  caught three self-scoring over-claims (unrecorded cost, a non-existent one-tap write-back, a
  misdescribed model divergence) and a real rubric gap (generic-lever degeneracy). All applied.
- **Opus 4.8:** orchestrate, evidence assembly, artifact authorship, de-slop, closeout.
- Full meta-analysis in `docs/strategy/2026-07-reengagement/meta-log.md`.

---

## Session-Review Pass (final gate)

### Per-deliverable status (re-verified on disk + live)
| Deliverable | Status | Evidence |
|---|---|---|
| R1 tree scoping (P0) | PASS | `test_tree_community_scoping.py` (5 tests) + prod: rhodes tree 0 Fox `@xref`, fox-family 15 nodes |
| R1 rels/shared_photos sub-leak (audit P1) | PASS | scrub in `_scope_tree_nodes_to_community` + regression test; commit `b5e83f7b` |
| Phase 1 Morning Mystery | PASS | PACKET/verdict-gemini/verdict-sol/manifest/MORNING_MYSTERY + rubric on disk; `gemini_api_calls`=1 (Belle Isle) |
| Phase 2 run contract | PASS | `investigation_runs.py` + migration + 5 tests; migration applied; `investigation_runs`=1 (live run `edb28ae1`) |
| W1-S3 assembler (overnight) | PASS | `packet_assembler.py` + 7 tests; live-validated on Belle Isle; sha256 seal stable across runs |
| Closeout docs | PASS | assessment, log, codex-audit, W1-S4 prompt, CONTINUATION, CHANGELOG v0.99.92, ROADMAP/BACKLOG, meta-log, AD-252 |
| Deploy + CI | PASS | prod all-200, R1 live; CI green on code push `a140499a`; 0 unpushed |

### Concerns / red flags
- None outstanding. Two independent audits ran IN-session (the R1 `rels` leak + the assembler
  non-reproducible-seal) and their P0/P1 fixes are committed + re-verified — the auto-fix role was
  served live, so no separate auto-fix worktree was spawned (nothing left to fix).
- Carried (not defects): R2 token rotation (user action), R1 UX confirmation (user decision),
  TREE-AUTH-171 / RUN-KEY-171 / PACKET-DECOUPLE-171 (BACKLOG).

### Novel-Discovery Audit
This was a tooling/product session, not a research session. The one investigation (Belle Isle)
produced an **honest double-ABSTENTION** — no identification claimed, decisive missing evidence named.
Tally — **genuine-novel: 0 · vault-catch-up: 0 · withdrawn: 0 · methodology: 1** (the assembler
mechanically reproduces the abstention signal). Per Lesson-50 spirit, 0 novel + honest classification
= WIN: no over-claiming; the models correctly refused to invent a name where no reference face exists.

### User-Feedback Absorb (feedback received this session)
1. **"Use Opus/Fable/Sol with varying effort + different roles."** (a) acknowledged; (b) applied
   throughout — Opus orchestrate, Sol code(medium)/audit(xhigh)/investigate, Gemini+Sol sealed
   verdicts, Fable architect/judge; (c) methodology: role-based (not model-name) division survives
   model churn; (d/e) already codified in `multimodel-sprint` skill — no new rule needed.
2. **"Keep going while I sleep — make as much progress as you can."** (a) acknowledged; (b) continued
   into W1-S3 (infra) but held the WIP line — did NOT generate new unreviewed cases (plan: review
   loop must survive human review first); (c) methodology: autonomous progress = advance the enabling
   task, not the risky/unvalidated frontier.
3. **"I'm confused what my next steps are — write a continuation prompt that explains what we've done
   and what's next."** (a) acknowledged my prior summaries were too technical; (b) wrote
   `docs/prompts/session-172-CONTINUATION.md` (plain-language, menu-style, written TO Nolan); (c)
   methodology lesson captured as durable memory `feedback_plain_language_orientation`; (d) rule:
   end sessions with plain-language what-we-did / your-decisions / pick-your-next-move, POINT to the
   technical detail rather than leading with it; (e) no Codex-audit-template change needed.
4. **"Close out everything including meta analysis."** (a) acknowledged; (b) meta-log has the
   multi-model performance analysis + 3 meta-lessons; shared-memory got 2 validated cross-repo lessons
   (independent-audit-gate reinforced; codex-xhigh report-stall + fallback); (c/d/e) captured.

### Auto-Fix Summary
- Issues found this pass: 0 (all in-session audit findings already fixed + committed + re-verified)
- Auto-fixed: 0 needed · Deferred: 0 (carried items are user-action/BACKLOG, not fixable here)
