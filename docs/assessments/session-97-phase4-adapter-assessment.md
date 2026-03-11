# Session 97 Phase 4 Assessment

**Date:** 2026-03-11  
**Scope:** Experiment-only embedding-adapter harness on frozen embeddings  
**Status:** Implemented, evaluated, not approved for rollout

## Outputs

- `rhodesli_ml/embedding_adapter_experiment.py`
- `scripts/run_embedding_adapter_experiment.py`
- `docs/assessments/session-97-phase4-adapter-report.json`

## What Landed

- Residual adapter experiment that stays in embedding space
- Identity-held-out and family-held-out experiment splits
- Slice reporting for:
  - same-family false positives
  - year-gap >= 20 recall when available
  - dominant vs tail positive recall
- Artifact-save guard: no experiment artifact is promoted by default when gates fail

## Live Result

`python scripts/run_embedding_adapter_experiment.py --dry-run --output docs/assessments/session-97-phase4-adapter-report.json`

Current report:

- identity holdout:
  - baseline AUC `0.9715`
  - adapter AUC `0.9720`
- family holdout:
  - baseline AUC `0.9985`
  - adapter AUC `0.9987`
  - same-family false positive rate improved from `0.0339` to `0.0169`
- year-gap `>= 20` recall:
  - unavailable in both splits on this current pair construction
- gate:
  - `passes: false`
  - reason: no year-gap slice improvement evidence yet

## Decision

Keep the harness, keep rollout off.

Reason:

- the experiment path is now real and reproducible
- slice-aware family holdouts are in place
- the current live snapshot does not show the hard-slice win required to justify further rollout work

## Why This Is Not LoRA

The harness intentionally stops at a frozen-embedding adapter.

- It is a real experiment path on today’s repo.
- It avoids premature PEFT plumbing around a backbone that is not yet the right target.
- It gives the next session a measurable plateau test before any re-embedding or LoRA work is attempted.
