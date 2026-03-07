# PRD-023: Similarity Calibration Strategy — Platt Scaling First, LoRA Later

**Author:** Nolan Fox
**Date:** 2026-02-22
**Status:** RESOLVED DIFFERENTLY — Isotonic regression shipped instead of LoRA (Session 63, AUC=0.9577, AD-149). LoRA deferred to ML-070
**Session:** 61B
**Depends on:** AD-123 (Siamese MLP calibration), AD-125 (ground truth pairs)

---

## Problem Statement

InsightFace's default embeddings are trained on modern, diverse faces (MS1MV3 / WebFace12M). Historical photos from 1900-1940 Rhodes have distinct characteristics: sepia tones, formal poses, limited lighting, period-specific grooming, and studio photography conventions. The embedding space may not optimally separate individuals from this era.

Session 55 built a Siamese MLP calibration layer (33K params) that improved F1@0.5 from 0.13 to 0.60 — a 4.8x improvement. But this model was trained on limited data and may not generalize well. The question: what's the next step on the calibration roadmap?

## Current State (Session 55-58)

| Component | Status | Metric |
|-----------|--------|--------|
| InsightFace embeddings | Frozen (512-dim, w600k_r50) | Baseline |
| Siamese MLP calibration | Deployed (ONNX, 129KB) | F1@0.5 = 0.60, precision@0.5 = 98% |
| ONNX serving | Production | 15MB runtime vs 500MB+ PyTorch |
| Fallback chain | ONNX → PyTorch → Euclidean | Graceful degradation |
| Ground truth pairs | 55 confirmed identities, ~230 anchor assignments | ~1200 positive pairs |

## Research Questions (Answered)

### 1. Does InsightFace support LoRA fine-tuning?
**Partial.** InsightFace uses ArcFace with ResNet or MobileFaceNet backbone. These are standard PyTorch/ONNX models that can be fine-tuned. LoRA (Low-Rank Adaptation) can be applied to the backbone's linear/conv layers. However: re-embedding all 550+ faces would be required after any backbone change, and the new embeddings would be in a different space than the originals.

### 2. How many labeled pairs do we need?
**Literature suggests 200-500 pairs minimum** for meaningful LoRA fine-tuning on a domain shift. We have ~1200 positive pairs from 55 confirmed identities. With negative mining, we can generate 10,000+ negative pairs. This is likely sufficient for calibration; borderline for LoRA.

### 3. Do we have enough confirmed identities?
**Yes for calibration, marginal for LoRA.** 55 confirmed identities with 2-8 photos each gives good coverage for score calibration. For LoRA, the diversity of subjects matters more than count — we need cross-age pairs (child → adult), cross-decade pairs, and diverse photo conditions. Our dataset is heavily skewed toward 1920s-1940s formal portraits.

### 4. What improvement is expected?
**Calibration (Platt scaling):** Literature suggests 3-8% accuracy improvement on domain-specific similarity tasks when properly calibrating an existing model's scores.
**LoRA fine-tuning:** Literature suggests 5-15% for significant domain shifts. Our domain shift (modern diverse → historical Sephardic) is moderate — formal poses and controlled studio lighting actually help recognition.

### 5. Is there a simpler approach first?
**Yes — Platt scaling and isotonic regression.** These fit a calibration curve to the raw similarity scores using confirmed match/non-match pairs as ground truth. No model retraining needed. Can be done with scikit-learn in 10 lines of code.

## Decision: Calibration Ladder

Progress through these stages, stopping when results are sufficient:

### Stage 1: Platt Scaling on Raw Scores (NEXT)
- Fit `sklearn.calibration.CalibratedClassifierCV` (Platt or isotonic) on raw Euclidean distances
- Input: distance between embedding pairs
- Output: calibrated probability of same-identity
- Ground truth: confirmed anchor pairs (positive) + random cross-identity pairs (negative)
- Expected: better threshold selection, more meaningful confidence scores
- Effort: ~1 session

### Stage 2: Siamese MLP Refinement (CURRENT — may be sufficient)
- The existing 33K param Siamese MLP (AD-123) already does this
- Next step: proper train/val/test split with held-out identities
- Retrain with more data (55 confirmed → more as community contributes)
- Add hard negative mining (closest non-matches)
- Effort: ~1 session

### Stage 3: LoRA Fine-Tuning (IF needed)
- Apply LoRA to InsightFace's w600k_r50 recognition backbone
- Train on heritage photo pairs with contrastive loss
- Requires re-embedding all 550+ faces with the fine-tuned model
- Requires careful validation — must not degrade modern-face performance
- Effort: ~2-3 sessions
- **Only pursue if Stage 1+2 combined F1 < 0.75**

## Out of Scope

- Training a face recognition model from scratch (insufficient data)
- Using generative AI for face augmentation (violates Rule 4)
- Multi-model ensemble at inference time (complexity not justified at scale)
- Real-time LoRA switching per-query (overkill for 550 faces)

## Success Criteria

1. Calibrated similarity scores are more meaningful (probability interpretation)
2. F1@0.5 improves from current 0.60 to 0.70+ (Stage 1+2 combined)
3. Precision@0.5 remains above 95% (false positives are worse than false negatives)
4. No regression on the 55 confirmed identities (all still correctly matched)
5. Calibration model deployable via ONNX (same pattern as AD-128)

## Breadcrumbs

- AD-123: Siamese similarity calibration architecture
- AD-124: Ground truth pair generation
- AD-125: InsightFace embedding analysis
- AD-126: Calibration integration
- AD-127: Calibration results interpretation
- AD-128: ONNX production serving
- AD-145: Similarity calibration strategy (this PRD's decision)
- ML-076: Similarity calibration (ROADMAP item, completed Session 55)
