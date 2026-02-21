"""Production inference for calibrated similarity scoring.

Loads the calibration model and provides a simple API for scoring
embedding pairs. Designed for integration into core/neighbors.py.

Loading priority (AD-128):
  1. ONNX model via onnxruntime (production — lightweight, 15MB)
  2. PyTorch model via torch (local development — 500MB+)
  3. None — graceful degradation to raw Euclidean similarity
"""

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

_model = None
_model_loaded = False
_model_backend = None  # "onnx", "pytorch", or None


def _get_artifact_dir() -> Path:
    """Artifact directory containing model files."""
    return Path(__file__).resolve().parent.parent / "artifacts"


def load_calibration_model(model_path: Path | None = None) -> bool:
    """Load the calibration model. Returns True if successful.

    Tries ONNX first (production), then PyTorch (local development).
    Lazy-loads on first call. Thread-safe for single-worker Railway.
    Per AD-120: logs which backend was loaded, warns on fallback.
    """
    global _model, _model_loaded, _model_backend

    if _model_loaded:
        return _model is not None

    artifact_dir = _get_artifact_dir() if model_path is None else model_path.parent

    # Try ONNX first (production path — lightweight)
    onnx_path = artifact_dir / "calibration_v1.onnx"
    if onnx_path.exists():
        try:
            from rhodesli_ml.calibration.inference_onnx import ONNXCalibrationInference

            _model = ONNXCalibrationInference(onnx_path)
            _model_loaded = True
            _model_backend = "onnx"
            logger.info("Calibration model loaded: ONNX (%s)", onnx_path.name)
            return True
        except Exception as e:
            logger.warning("ONNX model found but failed to load: %s", e)

    # Try PyTorch (local development path)
    pt_path = model_path if model_path is not None else artifact_dir / "calibration_v1.pt"
    if pt_path.exists():
        try:
            import torch

            from rhodesli_ml.calibration.model import CalibrationModel

            checkpoint = torch.load(pt_path, weights_only=False, map_location="cpu")
            config = checkpoint.get("config", {})
            model = CalibrationModel(
                embed_dim=config.get("embed_dim", 512),
                hidden_dim=config.get("hidden_dim", 32),
                dropout=config.get("dropout", 0.5),
            )
            model.load_state_dict(checkpoint["model_state_dict"])
            model.eval()
            _model = model
            _model_loaded = True
            _model_backend = "pytorch"
            logger.info("Calibration model loaded: PyTorch (%s)", pt_path.name)
            return True
        except Exception as e:
            logger.warning("PyTorch model found but failed to load: %s", e)

    _model_loaded = True
    _model_backend = None
    logger.warning("No calibration model available — using raw Euclidean similarity")
    return False


def calibrated_similarity(emb_a: np.ndarray, emb_b: np.ndarray) -> float | None:
    """Compute calibrated P(same_person) for two embeddings.

    Returns None if calibration model is not available (graceful degradation).
    Returns float in [0, 1] if model is loaded.
    """
    if not load_calibration_model():
        return None

    try:
        if _model_backend == "onnx":
            return _model.predict(emb_a, emb_b)
        else:
            import torch

            a = torch.tensor(emb_a, dtype=torch.float32)
            b = torch.tensor(emb_b, dtype=torch.float32)
            return _model.predict(a, b)
    except Exception:
        return None


def calibrated_similarity_batch(
    query_emb: np.ndarray, candidate_embs: np.ndarray
) -> np.ndarray | None:
    """Compute calibrated P(same_person) for one query vs many candidates.

    Args:
        query_emb: (512,) numpy array
        candidate_embs: (N, 512) numpy array

    Returns:
        (N,) numpy array of probabilities, or None if model unavailable.
    """
    if not load_calibration_model():
        return None

    try:
        if _model_backend == "onnx":
            return _model.predict_batch(query_emb, candidate_embs)
        else:
            import torch

            q = torch.tensor(query_emb, dtype=torch.float32).unsqueeze(0)
            q_expanded = q.expand(len(candidate_embs), -1)
            c = torch.tensor(candidate_embs, dtype=torch.float32)
            _model.eval()
            with torch.no_grad():
                scores = _model(q_expanded, c).squeeze(-1)
            return scores.numpy()
    except Exception:
        return None


def is_calibration_available() -> bool:
    """Check if calibration model is loaded and ready."""
    return load_calibration_model()


def get_backend() -> str | None:
    """Return which backend is active: 'onnx', 'pytorch', or None."""
    return _model_backend


def reset():
    """Reset model cache (for testing)."""
    global _model, _model_loaded, _model_backend
    _model = None
    _model_loaded = False
    _model_backend = None
