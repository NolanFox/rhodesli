"""Training loop for similarity calibration model (Phase 2).

Trains a small MLP on embedding pairs + metadata signals to output
calibrated match probabilities. Uses confirmed pairs (positive) and
rejections + hard negatives (negative).

Usage:
    python -m rhodesli_ml.training.train_calibrator --config config/calibration.yaml
"""

# Placeholder — will be implemented after signal harvester validates
# sufficient training data (50+ confirmed pairs, 20+ rejections).
#
# Pipeline:
# 1. Harvest training signal via data/signal_harvester.py
# 2. Load embeddings, compute pair features
# 3. Train MLP with BCE loss + hard negative upweighting
# 4. Evaluate on golden set (must beat current Euclidean thresholds)
# 5. Run regression gate
# 6. Export to ONNX for production inference
