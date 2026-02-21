# PRD-023: Similarity Calibration on Frozen InsightFace Embeddings

## Problem Statement

The compare tool uses raw Euclidean distance on InsightFace embeddings with hand-tuned thresholds (AD-013, AD-067). This produces false positives (unrelated people matched because faces happen to be close in embedding space) and false negatives (same person at different ages not matched because the distance exceeds the fixed threshold). The 46 confirmed identities with embeddings provide ground truth to train a calibration layer that improves match quality without retraining the base model.

## Ground Truth Data

| Metric | Count |
|--------|-------|
| Confirmed identities with embeddings | 46 |
| Multi-face identities (2+ faces) | 18 |
| Total faces with embeddings | 175 |
| Same-person positive pairs | 959 |
| Cross-identity pairs | 1,035 |

**Key identities (by face count):** Big Leon Capeluto (25), Moise Capeluto (18), Victoria Cukran Capeluto (17), Victoria Capuano Capeluto (15), Vida Capeluto (15), Betty Capeluto (12).

The data has a heavy class imbalance: 959 positive (same-person) pairs vs potentially 1,035+ negative pairs. The 18 multi-face identities provide all positive training signal; the 28 single-face identities only contribute to negative pairs.

## Success Metrics

| Metric | Target |
|--------|--------|
| Precision@0.5 | ≥10% improvement over raw Euclidean baseline |
| Recall@0.5 | Maintained or improved |
| Training time | <10 min on Mac M-series CPU |
| Model artifact size | <50MB (loadable on Railway) |
| ROC-AUC | Documented, compared to baseline |

## User Impact

- Compare tool returns fewer false matches for uploaded photos
- "Also appears in" suggestions on person pages are more accurate
- Confidence percentages reflect learned probabilities, not heuristic approximation
- Foundation for future active learning loop

## Non-Goals (This Session)

- LoRA fine-tuning of base model (future, only if calibration plateaus)
- Active learning UI for user feedback
- Real-time retraining on new identifications
- Integration with kinship detection (family resemblance remains unsolvable per AD-067)

## Acceptance Criteria

- [ ] Training pipeline runs end-to-end on CPU
- [ ] MLflow logs all experiments with metrics + hyperparameters
- [ ] Precision@0.5 improvement documented with exact numbers
- [ ] Model artifact saved and loadable
- [ ] Compare pipeline uses calibrated model when available
- [ ] All existing compare tests still pass
- [ ] 10+ new tests for calibration pipeline
- [ ] Graceful degradation: compare works without model file
