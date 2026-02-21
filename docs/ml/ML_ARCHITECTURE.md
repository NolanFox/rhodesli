# Rhodesli ML Architecture

**Last updated:** 2026-02-21 (Session 55b)

Single source of truth for how ML works in Rhodesli. For individual decisions, see ALGORITHMIC_DECISIONS.md. For the ML roadmap, see docs/roadmap/ML_ROADMAP.md.

---

## Overview

Rhodesli uses ML for three capabilities:

| Capability | Model | Status | Serving |
|-----------|-------|--------|---------|
| Face detection + embedding | InsightFace buffalo_sc | Production | Railway (ONNX) |
| Similarity scoring | Siamese MLP calibration | Production | Railway (ONNX) |
| Date estimation | CORAL ordinal regression | Planned (Session 57) | Will use ONNX |

---

## Serving Path Contract (AD-110)

**Railway (production web):** Lightweight inference only.
- InsightFace buffalo_sc for face detection + embedding
- ONNX Runtime for calibration model (15MB dependency)
- Gemini API for date estimation and photo analysis
- User-facing latency target: <30s (ideally <10s)

**Local Mac:** Heavy ML processing.
- Model training (PyTorch)
- Full clustering pipeline
- Re-embedding with larger models (buffalo_l)
- Experiment tracking (MLflow)
- ONNX export for production deployment

**Why:** Railway has limited compute. Training would block web requests.

---

## Component Detail

### 1. Face Detection + Embedding (InsightFace)

- **Railway model:** buffalo_sc (compact) — det_500m detector + w600k_r50 recognizer
- **Local model:** buffalo_l (full) — det_10g detector + w600k_r50 recognizer
- **Output:** 512-dim PFE embedding per detected face
- **Storage:** embeddings.npy (NumPy array of dicts with filename, bbox, embeddings, det_score)
- **Performance:** buffalo_sc + 640px resize = 10.5s for 2-face photo (AD-119, Session 54F)
- **Integration:** app/main.py compare/estimate uploads → InsightFace → embeddings

### 2. Similarity Calibration (Session 55, AD-123-128)

- **Architecture:** Siamese MLP, 33K params, 129KB ONNX artifact
  - Input: Two 512-dim face embeddings
  - Features: |a-b| and a*b (1024-dim interaction features)
  - Hidden: Linear(1024→32) → ReLU → Dropout(0.5) → Linear(32→1) → Sigmoid
  - Output: P(same_person) in [0, 1]
- **Training data:** 46 confirmed identities, 175 faces, 959 positive pairs
  - Hard negative mining: cross-identity pairs within distance < 1.2
  - Train/eval split: identity-level stratification (37 train / 9 eval)
- **Results at threshold 0.5:**
  - F1: 0.13 → 0.60 (4.8x improvement over raw Euclidean)
  - Recall: 0.07 → 0.44 (6.4x improvement)
  - Precision: 1.00 → 0.98 (virtually unchanged)
  - AUC: 0.9493 → 0.9391 (within noise, SE=0.0146)
- **Serving:** ONNX Runtime in production, PyTorch locally (AD-128)
  - Fallback chain: ONNX → PyTorch → raw Euclidean
  - Integration: core/neighbors.py `find_similar_faces()` → inference.py
- **Artifacts:** rhodesli_ml/artifacts/calibration_v1.{pt,onnx}
- **MLflow:** Experiment logged in mlruns/ (local only)

### 3. Date Estimation — CORAL (Planned, Session 57)

- **Approach:** Ordinal regression on EfficientNet-B0 backbone
- **Ground truth:** 28 accepted birth years + 250 Gemini-labeled photos
- **Current state:** Gemini API provides baseline estimates (AD-101)
- **Serving:** Will follow ONNX pattern from calibration
- **Decision refs:** AD-039–045 (original), AD-101 (Gemini baseline)

### 4. Clustering Pipeline (Local Only)

- **Purpose:** Group face embeddings into identity clusters
- **Algorithm:** Hierarchical clustering on InsightFace embeddings
- **Uses calibration:** Can use calibrated scores for better clustering
- **Output:** Cluster assignments → proposals.json → gatekeeper review
- **Never runs on Railway:** Too compute-intensive

---

## Feature Touchpoints

| Feature | ML Components |
|---------|--------------|
| /compare upload | InsightFace (detect+embed) → Calibration (score) |
| "Also appears in" | Calibration (score against archive) |
| /estimate upload | InsightFace (detect) → Gemini API (date) |
| Person suggestions | Clustering (local) → Gatekeeper (web) |
| Birth year review | CORAL predictions (future) |
| Face overlays | InsightFace bounding boxes |

---

## Active Learning Loop

```
Community uploads photo → InsightFace detects faces
    ↓
Compare against archive → Calibration scores matches
    ↓
Show results to user → User confirms/rejects
    ↓
Admin reviews via Gatekeeper → Accept/Reject
    ↓
Accepted matches → New ground truth (identities.json)
    ↓
Retrain calibration model (periodic, local Mac)
    ↓
Export to ONNX → git push → Railway auto-deploy
    ↓
Better scores → Better suggestions → More confirmations
```

---

## Model Artifact Management

| Step | Tool | Location |
|------|------|----------|
| Training | PyTorch | Local Mac |
| Export | torch.onnx.export() | rhodesli_ml/calibration/export_onnx.py |
| Storage | Git (<5MB) or R2 (>5MB) | rhodesli_ml/artifacts/ |
| Deployment | git push → Railway | Dockerfile COPYs artifacts/ |
| Versioning | calibration_v1.onnx, v2, etc. | Same directory |

---

## Key Decisions

| AD# | Decision | Summary |
|-----|----------|---------|
| AD-001 | Multi-anchor matching | Retain all embeddings, not centroids |
| AD-002 | Embeddings once | Never regenerate unless model change |
| AD-110 | Serving Path Contract | Web = lightweight, local = heavy ML |
| AD-114 | Hybrid detection | det_500m + w600k_r50 for uploads |
| AD-119 | Compare perf fix | buffalo_sc in Docker, 51s→10.5s |
| AD-120 | Silent fallbacks are bugs | Log every model load |
| AD-123-126 | Calibration architecture | Siamese MLP, 33K params, F1 4.8x |
| AD-127 | Results interpretation | AUC drop is noise, F1 is signal |
| AD-128 | ONNX production serving | 15MB vs 500MB, exact accuracy |

---

## Files

| File | Purpose |
|------|---------|
| rhodesli_ml/calibration/model.py | CalibrationModel (Siamese MLP) |
| rhodesli_ml/calibration/train.py | Training with MLflow |
| rhodesli_ml/calibration/evaluate.py | Baseline vs calibrated comparison |
| rhodesli_ml/calibration/inference.py | Production API (ONNX→PyTorch→None) |
| rhodesli_ml/calibration/inference_onnx.py | ONNX Runtime inference |
| rhodesli_ml/calibration/export_onnx.py | PyTorch → ONNX export |
| rhodesli_ml/calibration/data.py | Pair generation, train/eval split |
| rhodesli_ml/artifacts/ | Model artifacts (.pt, .onnx) |
| core/neighbors.py | find_similar_faces() integration |
| docs/ml/ALGORITHMIC_DECISIONS.md | All ML decisions (AD-001 to AD-128) |
| docs/roadmap/ML_ROADMAP.md | ML task tracking |

---

## Future ML Work (Ordered)

1. **CORAL date estimation** (Session 57) — PyTorch portfolio piece
2. **MLflow dashboard** (Session 58) — experiment comparison UI
3. **Active learning pipeline** — automated retrain trigger
4. **Calibration v2** — retrain with more ground truth from gatekeeper
5. **LoRA fine-tuning** — only if calibration plateaus (AD-115 notes)
6. **KIN-001** — leverage 19 GEDCOM relationships for kinship scoring
