# SDD-038: Longitudinal Face Modeling — Implementation Plan

**Parent PRD**: [docs/prds/038_longitudinal_face_modeling.md](038_longitudinal_face_modeling.md)
**Status**: Ready for Review
**Date**: 2026-03-11
**Goal**: Improve cross-decade identity matching without destabilizing the app or overfitting to a few families.

---

## Decision Summary

1. Start with **measurement repair and scorer unification**, not model tuning.
2. Keep **recalibration local-only** and production hooks write-only.
3. Ship a **frozen-embedding longitudinal reranker** before any adapter training.
4. Treat LoRA / PEFT as a **gated experiment**, not the first milestone.
5. Build the later implementation prompt from the outputs of Phase 0 and Phase 1.

---

## Current-State Audit

1. **The matching path is split.**
   - `core/auto_cluster.py` is the shipped batch upload path.
   - `scripts/cluster_new_faces.py` is still used for proposal generation and some upload flows.
   - `app/upload_routes.py` still calls `cluster_new_faces.py`, so improving only one path will create inconsistent behavior.

2. **The calibration story is inconsistent.**
   - `rhodesli_ml/similarity_calibration.py` is a scalar isotonic wrapper over `similarity_score`.
   - `rhodesli_ml/calibration/` contains a newer pairwise MLP pipeline.
   - Repo docs still describe multiple incompatible "current" systems.

3. **The eval harness is stale.**
   - `scripts/evaluate_golden_set.py` and `scripts/evaluate_mls_vs_euclidean.py` currently fail on mixed embedding schemas (`mu` vs `embeddings`).
   - `data/golden_set.json` still has 125 mappings / 23 identities even though the repo now has many more confirmed identities.

4. **The local data snapshot is much stronger than the current PRD assumes.**
   - 84 confirmed identities
   - 28 confirmed identities with 2+ faces
   - about 1,453 same-identity pairs from confirmed faces
   - 271 / 271 date labels with year estimates
   - 32 confirmed identities with birth-year estimate records

5. **Longitudinal signal already exists.**
   - 331 same-identity pairs have photo-year coverage
   - 54 have year gaps >= 20
   - 13 have year gaps >= 30
   - max observed identity span in current local data is 57 years

6. **The pair-count bottleneck has changed shape.**
   - Absolute pair count is no longer the main blocker for adapter work.
   - Pair concentration is the blocker: current positive-pair Gini is about 0.788, with Roland Fox and Big Leon dominating the signal.

7. **The current baseline is strong enough that "improvement" must be slice-specific.**
   - On the existing golden set, a schema-aware local check gives Euclidean AUC about 0.978.
   - Straight MLS underperforms that baseline at about 0.953 on the same asset.
   - The Euclidean threshold that reaches about 90% precision is about 1.196 on the stale golden set.

---

## Where I Agree With The Existing PRD

- Local-only recalibration is the right operational choice for now.
- Active learning is the right way to turn admin effort into reusable signal.
- Quality and temporal signals should be exploited before changing the base embedding model.
- Retroactive improvement must stay additive-only and admin-reviewed.
- A formal eval gate is mandatory before any matcher change ships.

---

## Where I Diverge

1. **Evaluation repair comes before all five workstreams.**
   - The current repo cannot reliably measure improvement on the live schema.

2. **The primary target is `core/auto_cluster.py`, not only `scripts/cluster_new_faces.py`.**
   - That is the production batch path.
   - `cluster_new_faces.py` should become a thin wrapper around shared scoring code.

3. **"Best face per decade" is too brittle as the main longitudinal abstraction.**
   - Use a small prototype bank per identity instead: 3-5 medoid-style anchors chosen for temporal spread and quality.

4. **Metadata should feed a reranker, not the legacy isotonic module.**
   - Scalar isotonic calibration cannot absorb mixed feature sets cleanly.
   - The right target is a multifeature offline ranker with optional post-hoc calibration.

5. **LoRA readiness should be decided by slice gates, not raw pair count.**
   - The repo now has enough pairs to experiment, but the representation skew is still severe.

---

## Target Architecture

### Shared Offline Scoring Stack

1. **Retriever**
   - Fast Euclidean top-K candidate retrieval on frozen `mu` embeddings.
   - `core/auto_cluster.py` is the source of truth for offline batch matching.
   - `scripts/cluster_new_faces.py` should become a thin CLI wrapper over the shared scorer.

2. **Prototype Bank**
   - New per-identity cache of 3-5 representative anchors.
   - Selection rule:
     - maximize temporal spread when dates exist
     - enforce a tunable minimum era gap where metadata allows
     - only then prefer high-quality faces
     - avoid near-duplicate anchors from the same era

3. **Longitudinal Feature Builder**
   - Query-to-identity features, not just query-to-anchor features.
   - Core features:
     - top-1 / top-3 distance stats
     - top-1 to top-2 margin
     - query quality and matched-anchor quality
     - identity prototype dispersion
     - photo-year gap to nearest prototype
     - gap to identity year span
     - age compatibility when birth-year estimate exists
     - GEDCOM / surname / family-risk features
     - kinship-risk feature family for same-era close-relative collisions
     - same-community / cross-community flag

4. **Offline Reranker**
   - First choice: `HistGradientBoostingClassifier` on compact numeric features.
   - Reason:
     - local-only
     - handles missing values
     - easier feature importances and ablations than an MLP
   - Optional final step: isotonic calibration on reranker output if probability labels are exposed in UI.

5. **Decision Policy**
   - Tier thresholds remain policy, not model weights.
   - The model produces ranking scores; tiering maps those scores into:
     - no action
     - discovery suggestion
     - auto-add as candidate, still human-reviewed

---

## Implementation Phases

## Phase 0: Measurement And Path Unification

**Why first**: everything else is blind without it.

**Scope**
- Fix the embedding loaders used by eval scripts so mixed `mu` / `embeddings` files are supported.
- Rebuild the golden set from current confirmed identities.
- Add identity-level CV plus slice reports.
- Extract a shared scorer interface used by:
  - `core/auto_cluster.py`
  - `scripts/cluster_new_faces.py`
  - upload proposal generation paths

**Deliverables**
- `scripts/evaluate_longitudinal.py`
- versioned `golden_set_v2.json`
- baseline JSON report checked into docs or evaluation artifacts
- skew report for the rebuilt training / evaluation assets
- dominant vs tail identity slice report
- shared face/metadata loader module

## Phase 1: Recalibration Hygiene And Label Taxonomy

**Scope**
- Keep production hooks to pair insertion only.
- Add `scripts/recalibrate.py` and a status check.
- Record label provenance explicitly:
  - explicit_positive
  - explicit_negative
  - implicit_negative
  - discovery_confirmed
- Revisit implicit negatives so they stay weak-weighted and auditable.

**Deliverables**
- local recalibration CLI
- calibration status endpoint / status report
- label schema update and tests
- reverted-label exclusion and logical-consistency checks before recalibration export

## Phase 2: Frozen-Embedding Longitudinal Reranker

**Scope**
- Build prototype-bank generation.
- Compute longitudinal features.
- Train and compare reranker in shadow mode.
- Wire it behind a feature flag into the shared offline scorer.

**Success condition**
- beats current policy on age-gap slices without worsening kin false positives
- does not show dominant-identity bias toward the most overrepresented families
- preserves tail-identity recall

## Phase 3: Active Learning Inside Review UX

**Scope**
- Fold active learning into the existing review surfaces rather than shipping a disconnected widget.
- Query strategy:
  - uncertainty
  - diversity
  - underrepresented identities
  - age-gap and kinship slices
- Support one-click same / different actions plus batch review.
- Include a reversible audit path so recent active-learning labels can be inspected and undone before recalibration.

**Why**
- AD-215 is right: fixing errors must be easier than making them.

## Phase 4: Adapter / LoRA Experiment Track

**Scope**
- Run only after Phase 2 plateaus.
- Use balanced sampling, family holdouts, and quality-aware training.
- Prefer PEFT over broad full fine-tuning.
- Evaluate against slice gates, not only overall AUC.

**Default stance**
- Experimental until it clearly improves age-gap retrieval without damaging family-confusion rates.

---

## Eval Gates

1. **Core retrieval**
   - Rank-1 and Rank-3 on identity-held-out evaluation may not regress by more than 1 point.

2. **Longitudinal slice**
   - Recall on year-gap >= 20 pairs must improve by at least 5 points before rollout.

3. **Kinship safety**
   - Same-family false positive rate must stay flat or improve.

4. **Community safety**
   - No new cross-community leakage without proposal badges and review state.

5. **Shadow review**
   - Manually inspect the top 50 changed proposals before enabling the new scorer in batch mode.

6. **Rollback**
   - Every scorer version must be reversible with a config switch and artifact pin.

---

## Scale-Aware Architecture Path

1. **Now: local-only training and shadow evaluation**
   - Keep recalibration, reranker training, and any adapter experiments local.
   - Keep the web app on the current AD-110 contract: no heavy ML on requests.

2. **Design now for extraction later**
   - All new scorer steps should be callable through a narrow offline job interface:
     - load artifact version
     - score a face batch
     - emit proposals and eval reports
   - That keeps laptop execution and future cloud workers behaviorally identical.

3. **First cloud move: queued offline workers**
   - Do not jump straight to online inference.
   - The first cloud extraction should be:
     - queued batch scoring
     - scheduled recalibration / reranking
     - artifact storage and pinned rollback
   - This aligns with the existing ML service draft and async-serving research.

4. **Cutover triggers**
   - Move PRD-038 offline jobs off the laptop when any of these become true:
     - end-to-end batch scoring or shadow replay routinely exceeds 45 minutes
     - new-face volume is consistently above about 100 faces per day
     - identity scale reaches about 10k identities or 100k embeddings
     - retraining / backfill cadence is missed because local execution becomes operationally fragile
     - multiple admins need the same ML queue without Nolan's machine being online

5. **Later cloud move: interactive serving**
   - Real-time or batched online inference only becomes necessary when product scope changes:
     - live compare tools
     - self-serve archive onboarding at materially higher volume
     - same-day SLA expectations for large community uploads

---

## Prompt-Prep Outputs

The planning pass already packages the later execution bundle:
- `docs/prompts/session-97-prompt.md`
- `docs/session_context/session-97-context.md`
- `docs/assessments/session-97-prep-assessment.md`
- `docs/session_logs/session-97-log-stub.md`

Phase 0 and Phase 1 should then produce the exact runtime assets that Session 97 needs:

1. A stable file map for the real scoring path
2. A working eval CLI and baseline report
3. A feature dictionary for the reranker
4. A label taxonomy and recalibration workflow
5. A shortlist of open questions that actually block coding

Those outputs are what the future implementation prompt should reference, not just the original PRD prose.
