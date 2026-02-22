"""Production inference for date estimation.

Loads the CORAL date estimation model and provides a simple API for
predicting photo dates from raw images.

Loading priority (AD-129, following AD-128 pattern):
  1. ONNX model via onnxruntime (production — lightweight, 15MB)
  2. PyTorch model via Lightning (local development — 500MB+)
  3. None — graceful degradation (no date prediction available)
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


def _get_checkpoint_dir() -> Path:
    """Checkpoint directory for PyTorch fallback."""
    return Path(__file__).resolve().parent.parent / "checkpoints"


def _find_best_checkpoint() -> Path | None:
    """Find the best date estimation checkpoint by MAE."""
    ckpt_dir = _get_checkpoint_dir()
    if not ckpt_dir.exists():
        return None

    best_mae = float("inf")
    best_path = None
    for epoch_dir in ckpt_dir.iterdir():
        if not epoch_dir.is_dir() or not epoch_dir.name.startswith("date-epoch="):
            continue
        for ckpt_file in epoch_dir.glob("*.ckpt"):
            if "mae_decades=" in ckpt_file.stem:
                try:
                    mae = float(ckpt_file.stem.split("mae_decades=")[1])
                    if mae < best_mae:
                        best_mae = mae
                        best_path = ckpt_file
                except (ValueError, IndexError):
                    continue

    return best_path


def load_date_model(model_path: Path | None = None) -> bool:
    """Load the date estimation model. Returns True if successful.

    Tries ONNX first (production), then PyTorch (local development).
    Lazy-loads on first call. Per AD-120: logs which backend was loaded.
    """
    global _model, _model_loaded, _model_backend

    if _model_loaded:
        return _model is not None

    artifact_dir = _get_artifact_dir()

    # Try ONNX first (production path — lightweight)
    onnx_path = artifact_dir / "date_estimation_v1.onnx"
    if onnx_path.exists():
        try:
            from rhodesli_ml.date_inference.inference_onnx import (
                ONNXDateEstimationInference,
            )

            _model = ONNXDateEstimationInference(onnx_path)
            _model_loaded = True
            _model_backend = "onnx"
            logger.info(
                "Date estimation model loaded: ONNX (%s, %.1f MB)",
                onnx_path.name,
                onnx_path.stat().st_size / (1024 * 1024),
            )
            return True
        except Exception as e:
            logger.warning("ONNX date model found but failed to load: %s", e)

    # Try PyTorch (local development path)
    ckpt = model_path or _find_best_checkpoint()
    if ckpt is not None and ckpt.exists():
        try:
            import torch
            from rhodesli_ml.models.date_classifier import DateEstimationModel

            model = DateEstimationModel.load_from_checkpoint(
                str(ckpt), map_location="cpu"
            )
            model.eval()
            _model = model
            _model_loaded = True
            _model_backend = "pytorch"
            logger.info("Date estimation model loaded: PyTorch (%s)", ckpt.name)
            return True
        except Exception as e:
            logger.warning("PyTorch date model found but failed to load: %s", e)

    _model_loaded = True
    _model_backend = None
    logger.warning(
        "No date estimation model available — date predictions disabled"
    )
    return False


def predict_date(image: np.ndarray) -> dict | None:
    """Predict the decade of a photo from a raw RGB image.

    Args:
        image: HWC uint8 RGB numpy array (any size).

    Returns:
        Dict with predicted_decade, confidence, decade_probabilities, expected_year,
        source. Or None if model is not available.
    """
    if not load_date_model():
        return None

    try:
        if _model_backend == "onnx":
            return _model.predict_from_image(image)
        else:
            # PyTorch path — use training val transforms
            import torch
            from rhodesli_ml.data.augmentations import get_val_transforms
            from rhodesli_ml.models.date_classifier import ordinal_logits_to_probs
            from rhodesli_ml.data.date_dataset import index_to_decade, NUM_DECADES

            transform = get_val_transforms()
            from PIL import Image

            pil_img = Image.fromarray(image)
            tensor = transform(pil_img).unsqueeze(0)

            with torch.no_grad():
                logits = _model(tensor)
                probs = ordinal_logits_to_probs(logits)[0]

            decades = [1900 + i * 10 for i in range(NUM_DECADES)]
            predicted_idx = int(probs.argmax().item())
            predicted_decade = decades[predicted_idx]
            confidence = float(probs[predicted_idx].item())
            midpoints = [d + 5 for d in decades]
            expected_year = sum(
                m * float(p) for m, p in zip(midpoints, probs)
            )

            return {
                "predicted_decade": predicted_decade,
                "confidence": round(confidence, 3),
                "decade_probabilities": {
                    str(d): round(float(p), 4) for d, p in zip(decades, probs)
                },
                "expected_year": round(expected_year),
                "source": "coral_v1",
            }
    except Exception as e:
        logger.error("Date prediction failed: %s", e)
        return None


def is_date_model_available() -> bool:
    """Check if date estimation model is loaded and ready."""
    return load_date_model()


def get_backend() -> str | None:
    """Return which backend is active: 'onnx', 'pytorch', or None."""
    return _model_backend


def reset():
    """Reset model cache (for testing)."""
    global _model, _model_loaded, _model_backend
    _model = None
    _model_loaded = False
    _model_backend = None
