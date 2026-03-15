# PRD-045: Active Learning Feedback Loop

**Status:** Draft | **Author:** Session 102 | **Date:** 2026-03-15
**Depends on:** PRD-046 (ML Run Provenance)
**Builds on:** PRD-038 (Longitudinal Face Modeling, Session 97)

## Problem

Rhodesli has 95 confirmed identities with 262 confirmed face anchors. After each
triage session, Nolan confirms clusters and rejects mismatches. This feedback is
stored in the identity registry but never fed back into the ML pipeline. The
clustering runs with the same thresholds regardless of accumulated knowledge.

## Research Foundation

Academic literature strongly supports constrained clustering with user feedback:
- **Wagstaff et al. (2001)**: Must-link/cannot-link constraints dramatically improve clustering
- **Semi-supervised deep embedded clustering** (ScienceDirect 2023): Pairwise constraints in embedding space
- **Continuous learning for face clustering** (ResearchGate 2021): Active learning + self-paced learning
- **DC-SSDEC** (PMC 2025): Dual-constraint semi-supervised using soft constraints

See `docs/ml/ACTIVE_LEARNING_RESEARCH.md` for full references.

## What PRD-038 Already Built (Session 97)

1. **Prototype-bank reranker** (`rhodesli_ml/longitudinal_reranker.py`) — confirmed faces as reference centroids, shadow mode only
2. **Active learning module** (`rhodesli_ml/active_learning.py`) — selects most informative faces for review, wired to review UX
3. **Adapter experiment harness** (`rhodesli_ml/embedding_adapter_experiment.py`) — frozen-embedding fine-tuning track
4. **Calibration lineage** (`rhodesli_ml/calibration_lineage.py`) — reversible labels, pair tracking

All rollout gates are closed — not enough labels at the time. Now we have 95 confirmed identities.

## Solution

### Phase 1: Activate Prototype-Bank Reranker (1 session)

**Prerequisite:** PRD-046 tables exist.

1. Run `longitudinal_reranker.py` with current confirmed anchors
2. Compare shadow scores vs baseline scores on known-good pairs
3. If AUC improves or stays flat: enable for proposal generation
4. Log as ml_run with `pipeline_type=reranker_shadow`

### Phase 2: Re-cluster with Confirmed Anchors as Seeds (1 session)

1. Modify `cluster_new_faces.py` to use confirmed faces as must-link constraints
2. Modify rejection lists as cannot-link constraints
3. Run clustering, write to ml_proposals with new run_id
4. Use `compare_ml_runs.py` to diff against prior run
5. If net positive (more correct matches, fewer false positives): deploy

### Phase 3: Wire into Post-Triage Pipeline (1 session)

1. After each speed-run/triage session, automatically queue a re-clustering run
2. Run in background (not blocking request path — AD-110)
3. Show "New suggestions available" badge when run completes
4. Admin reviews diff before applying

### Phase 4: Measure and Iterate

1. Track precision@k and recall on confirmed pairs across runs
2. If constrained clustering outperforms baseline consistently: make it default
3. If adapter experiment shows promise: graduate from shadow mode

## Current Label Inventory

| Community | Confirmed Identities | Confirmed Faces | Named |
|-----------|---------------------|-----------------|-------|
| All | 95 | 262 | 90 |

262 confirmed faces provide ~34,000+ positive pairs and a much larger negative
pair set. This is sufficient for constrained clustering evaluation.

## Risk Scenarios

1. **Production-local divergence during ML re-runs**: Mitigated by PRD-046 run tracking + Supabase as source of truth
2. **Embedding version drift**: Current embeddings are frozen PFE vectors. No drift risk until embeddings are regenerated.
3. **Threshold changes without tracking**: PRD-046 config_json captures all thresholds per run
4. **Reranker degrades for rare faces**: Shadow mode comparison catches this before deployment
5. **Cost**: All computation is local/offline. No API costs. Only risk is local compute time.

## Out of Scope

- Online learning (updating embeddings in real-time)
- Multi-model ensemble (single PFE model for now)
- Automated threshold tuning (manual review of diffs)

## Acceptance Criteria

- [ ] Prototype-bank reranker running on current labels (shadow mode)
- [ ] At least one constrained clustering run with before/after comparison
- [ ] Post-triage re-clustering wired (background, non-blocking)
- [ ] Precision/recall metrics tracked per run in ml_runs.result_summary
- [ ] No regression on known-good confirmed pairs
