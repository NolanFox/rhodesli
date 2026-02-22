# Session 58 Checkpoint — MLflow Model Registry + Promotion Pipeline

**Started:** 2026-02-21
**Prompt:** docs/prompts/session_58_prompt.md
**Planning Context:** docs/session_context/session_58_planning_context.md

## Phase Checklist
- [x] Phase 0: Orient + checkpoint
- [ ] Phase 0.5: Audit Session 57 deliverables
- [ ] Phase 1: Model Registry setup + register both models
- [ ] Phase 2: Promotion pipeline (promote_model.py)
- [ ] Phase 3: Backfill + docs + verification gate

## Phase 0 Findings

### Current MLflow State
- **MLflow version:** 3.9.0
- **Two tracking URIs:**
  - `rhodesli_ml/mlruns/` — date estimation (11 runs, 1 experiment)
  - `mlruns/` (top-level) — similarity calibration (1 run, 1 experiment)
- **Registered models:** 0 (neither model is in the registry)
- **ONNX artifacts:** date_estimation_v1.onnx, calibration_v1.onnx

### Date Estimation Runs (rhodesli_ml/mlruns/)
| Run ID (short) | Status | adj_accuracy | mae_decades | Notes |
|---|---|---|---|---|
| c122dd48 | RUNNING | 0.925 | 0.453 | Best metrics, epoch 29 |
| 040ea0f7 | FINISHED | 0.931 | 0.552 | Best adj, epoch 22 |
| 5a8209b2 | FINISHED | 0.782 | 0.764 | Latest FINISHED |
| af4d63ed | FINISHED | 0.857 | 0.714 | |

### Similarity Calibration Runs (mlruns/)
| Run ID | Status | best_f1 |
|---|---|---|
| f7113921 | FINISHED | 0.753 |

### Key Decision Needed
The two experiment directories need to be consolidated under one tracking URI.
Decision: Use `rhodesli_ml/mlruns` as the canonical URI. Move/register calibration runs there.

## Session 57 Audit
_(To be filled in Phase 0.5)_

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed
