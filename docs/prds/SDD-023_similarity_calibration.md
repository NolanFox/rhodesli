# SDD-023: Similarity Calibration — System Design

## Architecture

### Training Pipeline (runs local on Mac)
```
data/identities.json + data/embeddings.npy
    ↓
Pair Generator (same-person + hard negatives)
    ↓
PyTorch DataLoader (batched pairs)
    ↓
Siamese MLP (CalibrationModel)
    ↓
Training Loop (PyTorch + MLflow)
    ↓
Model Export (.pt artifact)
```

### Inference Pipeline (runs on Railway)
```
Upload Photo → InsightFace → Raw Embedding (512-dim)
    ↓
Load CalibrationModel (.pt, <50MB)
    ↓
Calibrated P(same_person) score
    ↓
Threshold → Tier Classification
```

## Data Preparation

### Pair Generation Strategy (AD-123)

**Positive pairs:** All (face_i, face_j) where both belong to the same confirmed identity. For identity with N faces → N*(N-1)/2 pairs. Total: 959 pairs from 18 multi-face identities.

**Hard negatives:** Cross-identity pairs where Euclidean distance < 1.2 (within the "possible match" zone). These are the cases the model must learn to reject — faces that look similar but belong to different people.

**Easy negatives:** Random cross-identity pairs. Sampled to achieve target positive:negative ratio.

**Ratio:** 1:3 positive:negative (tunable hyperparameter). With 959 positives, that's ~2,877 negatives (mix of hard and easy).

### Train/Eval Split (AD-125)

Split by identity, never by face. No identity's faces appear in both train and eval. This prevents data leakage — a model that memorizes individual faces would cheat on eval if faces from the same identity were in both sets.

- Train: 80% of identities (~37 identities)
- Eval: 20% of identities (~9 identities)
- Stratify: ensure eval set includes at least 4 multi-face identities

## Model Architecture (AD-124)

### Siamese MLP (chosen)

Input: For embedding pair (a, b), compute 4 interaction features:
- `concat(a, b)` → 1024-dim (raw pair)
- `|a - b|` → 512-dim (absolute difference)
- `a * b` → 512-dim (element-wise product)
- Total input: 2048-dim

Architecture:
```
Input (2048) → Linear(2048, 256) → ReLU → Dropout(0.3)
            → Linear(256, 64) → ReLU → Dropout(0.2)
            → Linear(64, 1) → Sigmoid
```

Output: P(same_person) ∈ [0, 1]
Loss: Binary Cross-Entropy

### Why Siamese MLP over Metric Learning Head

With 46 identities (18 multi-face), we have limited data to learn a new embedding space. The Siamese MLP directly models the comparison task — "given these two embeddings, are they the same person?" — which is more sample-efficient than learning a transformation that makes same-person embeddings cluster. Metric learning (contrastive/triplet loss) would need more identities to generalize.

## Training Configuration

| Parameter | Default | Sweep Range |
|-----------|---------|-------------|
| Learning rate | 1e-3 | [1e-4, 5e-4, 1e-3, 5e-3] |
| Batch size | 64 | [32, 64, 128] |
| Negative ratio | 3 | [2, 3, 5] |
| Dropout | 0.3/0.2 | Fixed |
| Epochs | 100 | Fixed (early stopping) |
| Early stopping patience | 10 | Fixed |

- Optimizer: Adam
- Hardware: CPU (Mac M-series), no GPU required
- Time target: <10 minutes per run

## Evaluation

### Metrics
- **Primary:** Precision and Recall at thresholds [0.3, 0.4, 0.5, 0.6, 0.7]
- **Secondary:** ROC-AUC, PR-AUC
- **Baseline:** Raw Euclidean distance with sigmoid approximation (current `_compute_confidence_pct`)

### Threshold Sweep
For each threshold t ∈ [0.3, 0.4, 0.5, 0.6, 0.7]:
- Predict "same person" if model output > t
- Compute precision = TP / (TP + FP)
- Compute recall = TP / (TP + FN)
- Select optimal threshold maximizing F1

### MLflow Logging
```python
mlflow.log_params({"lr": lr, "batch_size": bs, "neg_ratio": nr, "model": "siamese_mlp"})
mlflow.log_metrics({"precision_0.5": p, "recall_0.5": r, "roc_auc": auc, "best_threshold": t})
mlflow.pytorch.log_model(model, "calibration_model")
```

## Integration with Compare Pipeline

1. Load model artifact on first use (lazy, cached)
2. If `USE_CALIBRATION_MODEL=true` and model file exists: use calibrated scores
3. If model unavailable: fall back to raw Euclidean (graceful degradation)
4. Replace `_compute_confidence_pct()` sigmoid heuristic with learned probabilities
5. Threshold tiers may need recalibration based on model output distribution

### Code Changes
- `core/neighbors.py`: Add `calibrated_similarity()` function
- `core/neighbors.py`: Update `find_similar_faces()` to use calibrated scores when available
- New: `rhodesli_ml/calibration/inference.py` for model loading + prediction

## File Structure
```
rhodesli_ml/
├── calibration/
│   ├── __init__.py
│   ├── data.py          # Pair generation, DataLoader
│   ├── model.py         # CalibrationModel (PyTorch)
│   ├── train.py         # Training script + MLflow
│   ├── evaluate.py      # Evaluation against baseline
│   └── inference.py     # Model loading for production
├── tests/
│   ├── test_calibration_data.py
│   ├── test_calibration_model.py
│   ├── test_calibration_train.py
│   └── test_calibration_evaluate.py
└── artifacts/
    └── (calibration model .pt files — gitignored, tracked in MLflow)
```

## Test Plan
1. Pair generator produces correct positive/negative counts
2. No identity leaks between train/eval splits
3. Model forward pass produces valid probabilities [0, 1]
4. Training loop completes without error on small synthetic data
5. MLflow run is created with expected keys
6. Evaluation metrics computed correctly against known pairs
7. Model export/load roundtrip preserves outputs
8. Compare pipeline gracefully degrades without model file
9. Compare pipeline uses calibrated scores when model present
10. Known same-person pair scores higher than known different-person pair
