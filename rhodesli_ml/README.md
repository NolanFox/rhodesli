# Rhodesli ML Pipeline

Machine learning components for the Rhodesli heritage photo archive.
**Separate from the web app** — these dependencies (PyTorch, Lightning, MLflow) are NOT deployed to Railway.

## Setup

```bash
cd rhodesli_ml
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

For Gemini date labeling, also install the optional dependency:
```bash
pip install -e ".[gemini]"
export GOOGLE_API_KEY=your-gemini-api-key
```

## Quick Start

### 1. Generate date labels (requires Gemini API key)
```bash
# Dry run (3 photos, no cost)
python -m rhodesli_ml.scripts.generate_date_labels --dry-run

# Full run with Gemini 3 Pro
python -m rhodesli_ml.scripts.generate_date_labels --model gemini-3-pro-preview --max-cost 5.00
```

### 2. Train date estimation model
```bash
# Dry run (2 epochs, 10 images — validates pipeline)
python -m rhodesli_ml.training.train_date --dry-run

# Full training
python -m rhodesli_ml.training.train_date

# Custom config
python -m rhodesli_ml.training.train_date --config rhodesli_ml/config/date_estimation.yaml
```

### 3. Evaluate model (regression gate)
```bash
python -m rhodesli_ml.scripts.run_evaluation \
  --model rhodesli_ml/checkpoints/best.ckpt \
  --data rhodesli_ml/data/date_labels.json \
  --photos-dir raw_photos
```

### 4. View experiment results
```bash
cd rhodesli_ml && mlflow ui --backend-store-uri mlruns
# Open http://localhost:5000
```

## Components

| Directory | Purpose |
|-----------|---------|
| `config/` | YAML configs for training hyperparams and paths |
| `data/` | Signal harvesting, date labels, augmentations, dataset classes |
| `models/` | PyTorch Lightning modules (date classifier with CORAL loss) |
| `evaluation/` | Regression gate with mandatory quality thresholds |
| `training/` | Training loops with MLflow logging |
| `scripts/` | CLI tools (label generation, evaluation, signal harvesting) |
| `tests/` | 53 tests covering all pipeline components |

## Date Estimation Pipeline

The date estimation model predicts the decade (1900s–2000s) of heritage photos using ordinal regression.

**Architecture** (see `docs/ml/DATE_ESTIMATION_DECISIONS.md` for full rationale):
- **Backbone**: EfficientNet-B0 (pretrained, early layers frozen)
- **Loss**: CORAL ordinal regression + KL divergence auxiliary loss for soft labels
- **Labels**: Gemini 3 Pro silver labels with evidence-first prompt architecture
- **Augmentations**: Heritage-specific (sepia, film grain, scanning artifacts, fading, JPEG compression)
- **Evaluation**: Regression gate — adjacent accuracy >= 0.70, MAE <= 1.5 decades

**Decision provenance**: AD-039 through AD-045 in `docs/ml/ALGORITHMIC_DECISIONS.md`

## Testing

```bash
cd rhodesli_ml
python -m pytest tests/ -v
```

53 tests covering: CORAL loss, ordinal probabilities, dataset creation, augmentations, model forward/backward, regression gate, label generation.

## Architecture Decisions

1. **No backbone fine-tuning yet.** InsightFace embeddings stay frozen.
2. **First intervention:** Learned similarity calibration (small MLP) on frozen embeddings.
3. **PyTorch entry point:** Date/era estimation via transfer learning (EfficientNet-B0).
4. **Framework:** PyTorch Lightning + MLflow from day 1.
5. **Evaluation gate mandatory** before any production changes.
6. **CORAL ordinal regression** — predicting 1940s when answer is 1950s is less wrong than 2000s.
7. **Soft label training** — Gemini's decade probability distributions used as auxiliary KL loss.
8. **Heritage augmentations** — sepia, grain, fading simulate real archive degradation.

## Key Rules

- Never modify embeddings in production without passing the regression gate
- All training runs logged to MLflow (`rhodesli_ml/mlruns/`)
- Original embeddings never overwritten — versioned alongside
- User corrections always override model estimates
- Dry-run default on all scripts that modify data
