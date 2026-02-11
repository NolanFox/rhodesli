# Rhodesli ML Pipeline

Machine learning components for the Rhodesli heritage photo archive.
**Separate from the web app** — these dependencies (PyTorch, Lightning, MLflow) are NOT deployed to Railway.

## Setup

```bash
cd rhodesli_ml
pip install -e ".[dev]"
```

## Components

| Directory | Purpose |
|-----------|---------|
| `config/` | YAML configs for training hyperparams and paths |
| `data/` | Signal harvesting, label generation, augmentations |
| `models/` | PyTorch Lightning modules (date classifier, similarity calibrator) |
| `evaluation/` | Regression gate, embedding health, ranking stability |
| `training/` | Training scripts |
| `scripts/` | CLI tools (label generation, evaluation, export) |
| `notebooks/` | Exploration and visualization |

## Architecture Decisions

1. **No backbone fine-tuning yet.** InsightFace embeddings stay frozen.
2. **First intervention:** Learned similarity calibration (small MLP) on frozen embeddings.
3. **PyTorch entry point:** Date/era estimation via transfer learning (ResNet-18 or EfficientNet-B0).
4. **Framework:** PyTorch Lightning + MLflow from day 1.
5. **Evaluation gate mandatory** before any production changes.

## Key Rules

- Never modify embeddings in production without passing the regression gate
- All training runs logged to MLflow
- Original embeddings never overwritten — versioned alongside
- User corrections always override model estimates
