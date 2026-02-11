"""Model registry: tracks trained models, checkpoints, and evaluation results.

Uses MLflow for experiment tracking. Each model version is associated with:
- Training config (hyperparameters, data split)
- Evaluation metrics (golden set accuracy, regression gate results)
- Checkpoint path (local or remote)
"""

# Placeholder — will be implemented after first model training run.
#
# Integration points:
# - MLflow tracking server (local file-based initially)
# - Golden set evaluation results from evaluation/regression_gate.py
# - ONNX export metadata from scripts/export_onnx.py
