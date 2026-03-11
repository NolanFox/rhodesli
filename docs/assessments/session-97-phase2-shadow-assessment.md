# Session 97 Phase 2 Assessment

**Date:** 2026-03-11
**Scope:** Frozen-embedding longitudinal shadow reranker
**Status:** Implemented, evaluated, not approved for rollout

## Outputs

- `rhodesli_ml/longitudinal_reranker.py`
- `scripts/evaluate_longitudinal_shadow.py`
- `docs/assessments/session-97-phase2-shadow-report.json`
- `docs/assessments/session-97-phase2-prototype-bank.json`

## What Landed

- Quality-aware prototype-bank builder
- Runtime metadata loaders for:
  - photo year / collection
  - birth-year estimates
  - kinship graph from `relationships.json`
- Shadow reranker training harness using `HistGradientBoostingClassifier`
- Shared offline scorer hook for reranking shortlists behind an explicit flag
- Artifact-save guard: no reusable shadow artifact is emitted unless the Phase 2 gate passes or an operator forces it

## Live Result

The live dry-run report on current repo data shows:

- rerankable eval subset top-1 recall:
  - baseline: `0.9714`
  - reranker: `0.9714`
- year-gap `>= 20` top-1 recall:
  - baseline: `1.0`
  - reranker: `1.0`
- candidate-level AUC improved for the best shadow variant, but retrieval did not improve enough to justify rollout

## Decision

Do not enable the reranker for live proposal generation.

Reason:
- the gate in `docs/prds/038_longitudinal/EVALUATION_AND_SAFETY.md` is not met
- current evidence shows the harness works, but not that the new scorer beats the baseline where it matters

## Interpretation

This is still useful progress.

- The prototype-bank and reranker path now exists and is reproducible.
- The repo can measure whether richer temporal / kinship features help.
- The shared scorer can load a shadow reranker without changing default behavior.
- We now know the current rerankable eval subset is too easy for this model to earn rollout on top-1 retrieval alone.

## Next Iteration Targets

- enrich the eval subset with harder Fox-family and kinship-confusable examples
- add a harder retrieval benchmark where the true identity is present but not trivially rank-1 already
- revisit whether top-k shortlist size or candidate construction is the bigger bottleneck than reranking
- keep rollout off until the year-gap and tail-recall gates move materially
