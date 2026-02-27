"""Learned similarity calibration on frozen embeddings.

Implemented in Session 72. Uses Siamese MLP (|a-b|, a*b features) on frozen
InsightFace embeddings. See rhodesli_ml/calibration/ for full implementation.

Architecture: CalibrationModel in rhodesli_ml/calibration/model.py
Training: rhodesli_ml/calibration/train.py
Inference: rhodesli_ml/calibration/inference.py
Artifacts: rhodesli_ml/artifacts/calibration_v1.pt

Decision provenance: AD-174
"""

# Re-export for backward compatibility
from rhodesli_ml.calibration.model import CalibrationModel
from rhodesli_ml.calibration.inference import (
    calibrated_similarity,
    calibrated_similarity_batch,
    is_calibration_available,
)

__all__ = [
    "CalibrationModel",
    "calibrated_similarity",
    "calibrated_similarity_batch",
    "is_calibration_available",
]
