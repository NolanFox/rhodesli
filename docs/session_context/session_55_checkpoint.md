# Session 55 — Live Checkpoint
Last updated: 2026-02-21T15:55:00
Current phase: 4 (Evaluate Against Baseline) — COMPLETING
Status: IN PROGRESS

## Completed Phases
- Phase 0: Orient + Checkpoint System
- Phase 1: Backlog/Roadmap Audit (BACKLOG trimmed 338→272 lines, 8 new items)
- Phase 2: PRD-023 + SDD-023 + AD-123/124/125
- Phase 3: Implementation (6 modules, 43 tests, 2942 total passing)
- Phase 4: Evaluate Against Baseline (AD-126, MLflow tracked)

## Key Findings

### Ground Truth Data
- 46 confirmed identities (18 multi-face, 28 single-face)
- 175 faces with embeddings, 959 same-person pairs
- Identity-level split: 37 train / 9 eval (AD-125)
- 3304 training pairs, 532 eval pairs (neg_ratio=3)

### Architecture Evolution
- Initial 540K param model: overfits catastrophically (train loss 0.003, eval loss increasing)
- Hyperparameter sweep (4 configs): all overfitting, all worse than baseline
- Final 33K param model (AD-126): |a-b| + a*b features only, hidden=32, dropout=0.5

### Final Results (MLflow Run 1)
| Metric | Baseline | Calibrated | Delta |
|--------|----------|------------|-------|
| F1@0.5 | 0.1268 | 0.6042 | +0.4774 (4.8x) |
| Precision@0.5 | 1.0000 | 0.9831 | -0.0169 |
| Recall@0.5 | 0.0677 | 0.4361 | +0.3684 (6.4x) |
| AUC | 0.9493 | 0.9391 | -0.0102 |
| Best F1 | 0.5304 | 0.7530 | +0.2226 |
| Best Threshold | 0.3 | 0.3 | — |

### Portfolio Sentence
"Trained a learned calibration layer on frozen InsightFace embeddings using 46 confirmed identities as ground truth, tracked with MLflow — improving F1 by 4.8x (0.13→0.60) while maintaining 98% precision."

## Next Phase
Phase 5: Integrate into Compare Pipeline

## Files Created This Session
- docs/prompts/session_55_prompt.md
- docs/session_context/session_55_checkpoint.md
- docs/prds/PRD-023_similarity_calibration.md
- docs/prds/SDD-023_similarity_calibration.md
- rhodesli_ml/calibration/__init__.py
- rhodesli_ml/calibration/data.py
- rhodesli_ml/calibration/model.py
- rhodesli_ml/calibration/train.py
- rhodesli_ml/calibration/evaluate.py
- rhodesli_ml/calibration/inference.py
- rhodesli_ml/tests/test_calibration_data.py
- rhodesli_ml/tests/test_calibration_model.py
- rhodesli_ml/tests/test_calibration_train.py
- rhodesli_ml/tests/test_calibration_evaluate.py
- rhodesli_ml/artifacts/calibration_v1.pt
- mlruns/ (MLflow experiment tracking)

## Files Modified This Session
- docs/BACKLOG.md (trimmed, 8 new items)
- ROADMAP.md (session numbering fix)
- docs/ml/ALGORITHMIC_DECISIONS.md (AD-123, AD-124, AD-125, AD-126)
- .claude/hooks/recovery-instructions.sh

## ML Experiment Tracking
- Training runs: 1 (MLflow tracked)
- Model: 33K params, 153 epochs, early stopping at patience=20
- Training time: 14.94s
- Best eval loss: 0.3249
- Artifact: rhodesli_ml/artifacts/calibration_v1.pt
