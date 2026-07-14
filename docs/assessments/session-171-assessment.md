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
