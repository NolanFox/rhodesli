"""Production inference for calibrated similarity scoring.

Loads the trained CalibrationModel and provides a simple API for
scoring embedding pairs. Designed for integration into core/neighbors.py.
"""

from pathlib import Path

import numpy as np

_model = None
_model_loaded = False


def _get_default_model_path() -> Path:
    """Default model artifact location."""
    return Path(__file__).resolve().parent.parent / "artifacts" / "calibration_v1.pt"


def load_calibration_model(model_path: Path | None = None) -> bool:
    """Load the calibration model. Returns True if successful.

    Lazy-loads on first call. Thread-safe for single-worker Railway.
    """
    global _model, _model_loaded

    if _model_loaded:
        return _model is not None

    if model_path is None:
        model_path = _get_default_model_path()

    if not model_path.exists():
        _model_loaded = True
        return False

    try:
        import torch
        from rhodesli_ml.calibration.model import CalibrationModel

        checkpoint = torch.load(model_path, weights_only=False, map_location="cpu")
        config = checkpoint.get("config", {})
        model = CalibrationModel(
            embed_dim=config.get("embed_dim", 512),
            hidden_dim=config.get("hidden_dim", 256),
            dropout=config.get("dropout", 0.3),
        )
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        _model = model
        _model_loaded = True
        return True
    except Exception:
        _model_loaded = True
        return False


def calibrated_similarity(emb_a: np.ndarray, emb_b: np.ndarray) -> float | None:
    """Compute calibrated P(same_person) for two embeddings.

    Returns None if calibration model is not available (graceful degradation).
    Returns float in [0, 1] if model is loaded.
    """
    if not load_calibration_model():
        return None

    try:
        import torch
        a = torch.tensor(emb_a, dtype=torch.float32)
        b = torch.tensor(emb_b, dtype=torch.float32)
        return _model.predict(a, b)
    except Exception:
        return None


def is_calibration_available() -> bool:
    """Check if calibration model is loaded and ready."""
    return load_calibration_model()


def reset():
    """Reset model cache (for testing)."""
    global _model, _model_loaded
    _model = None
    _model_loaded = False
