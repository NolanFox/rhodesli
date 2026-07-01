"""Tests for CORAL date estimation ONNX export and validation."""

import numpy as np
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts"
ONNX_PATH = ARTIFACTS_DIR / "date_estimation_v1.onnx"


def _best_checkpoint():
    """Return the best local date-estimation checkpoint, if present."""
    ckpt_dir = Path(__file__).resolve().parent.parent / "checkpoints"
    if not ckpt_dir.exists():
        return None

    best_ckpt = None
    best_mae = float("inf")
    for epoch_dir in ckpt_dir.iterdir():
        if not epoch_dir.is_dir():
            continue
        for f in epoch_dir.glob("*.ckpt"):
            if "mae_decades=" not in f.stem:
                continue
            mae = float(f.stem.split("mae_decades=")[1])
            if mae < best_mae:
                best_mae = mae
                best_ckpt = f
    return best_ckpt


class TestONNXExportScript:
    """Tests for the export script utilities."""

    def test_find_best_checkpoint(self):
        """_find_best_checkpoint returns the checkpoint with lowest MAE."""
        from rhodesli_ml.scripts.export_date_onnx import _find_best_checkpoint

        best = _find_best_checkpoint()
        # Should find something (we have checkpoints in the repo)
        if best is not None:
            assert best.exists()
            assert best.suffix == ".ckpt"
            assert "mae_decades=" in best.stem

    def test_find_best_checkpoint_returns_lowest_mae(self):
        """Best checkpoint should have the lowest MAE value."""
        from rhodesli_ml.scripts.export_date_onnx import _find_best_checkpoint

        best = _find_best_checkpoint()
        if best is not None:
            mae_str = best.stem.split("mae_decades=")[1]
            mae = float(mae_str)
            # Our best checkpoint has MAE <= 0.40
            assert mae <= 0.40, f"Best MAE {mae} seems too high"


@pytest.mark.skipif(
    not ONNX_PATH.exists(),
    reason="ONNX model not exported yet",
)
class TestONNXModel:
    """Tests for the exported ONNX model."""

    def test_onnx_file_exists(self):
        """ONNX model file exists and is non-empty."""
        assert ONNX_PATH.exists()
        assert ONNX_PATH.stat().st_size > 0

    def test_onnx_loadable(self):
        """ONNX model loads with onnxruntime."""
        import onnxruntime as ort

        session = ort.InferenceSession(str(ONNX_PATH))
        assert session is not None

    def test_onnx_input_shape(self):
        """ONNX model accepts (batch, 3, 224, 224) input."""
        import onnxruntime as ort

        session = ort.InferenceSession(str(ONNX_PATH))
        inputs = session.get_inputs()
        assert len(inputs) == 1
        assert inputs[0].name == "image"
        # Dynamic batch, then 3, 224, 224
        shape = inputs[0].shape
        assert shape[1] == 3
        assert shape[2] == 224
        assert shape[3] == 224

    def test_onnx_output_shape_batch1(self):
        """Output shape is (1, 10) for batch=1 — CORAL has K-1 logits for K=11 classes."""
        import onnxruntime as ort

        session = ort.InferenceSession(str(ONNX_PATH))
        img = np.random.randn(1, 3, 224, 224).astype(np.float32)
        result = session.run(None, {"image": img})
        assert result[0].shape == (1, 10)

    def test_onnx_output_shape_batch4(self):
        """Dynamic batch axis works with batch=4."""
        import onnxruntime as ort

        session = ort.InferenceSession(str(ONNX_PATH))
        img = np.random.randn(4, 3, 224, 224).astype(np.float32)
        result = session.run(None, {"image": img})
        assert result[0].shape == (4, 10)

    def test_onnx_output_name(self):
        """Output is named 'ordinal_logits'."""
        import onnxruntime as ort

        session = ort.InferenceSession(str(ONNX_PATH))
        outputs = session.get_outputs()
        assert len(outputs) == 1
        assert outputs[0].name == "ordinal_logits"

    def test_onnx_deterministic(self):
        """Same input produces same output (no stochastic layers)."""
        import onnxruntime as ort

        session = ort.InferenceSession(str(ONNX_PATH))
        img = np.random.randn(1, 3, 224, 224).astype(np.float32)
        result1 = session.run(None, {"image": img})[0]
        result2 = session.run(None, {"image": img})[0]
        np.testing.assert_array_equal(result1, result2)

    def test_onnx_vs_pytorch_predictions_match(self):
        """ONNX and PyTorch produce the same decade predictions."""
        pytest.importorskip("torch", exc_type=ImportError)  # CI lacks torch (Session 168 Fable P0)
        import onnxruntime as ort

        best_ckpt = _best_checkpoint()
        if best_ckpt is None:
            pytest.skip("No checkpoint found")

        import torch
        from rhodesli_ml.models.date_classifier import (
            DateEstimationModel,
            ordinal_logits_to_probs,
        )

        model = DateEstimationModel.load_from_checkpoint(
            str(best_ckpt), map_location="cpu"
        )
        model.eval()

        session = ort.InferenceSession(str(ONNX_PATH))

        # Test 20 random inputs
        for _ in range(20):
            img = np.random.randn(1, 3, 224, 224).astype(np.float32)

            with torch.no_grad():
                pt_logits = model(torch.tensor(img))
                pt_probs = ordinal_logits_to_probs(pt_logits)
                pt_class = pt_probs.argmax(dim=1).item()

            ort_logits = session.run(None, {"image": img})[0]
            # Convert ordinal logits to class probs
            cumprobs = 1.0 / (1.0 + np.exp(-ort_logits[0]))
            probs = np.zeros(11)
            probs[0] = 1.0 - cumprobs[0]
            for k in range(1, len(cumprobs)):
                probs[k] = cumprobs[k - 1] - cumprobs[k]
            probs[-1] = cumprobs[-1]
            probs = np.clip(probs, 0, 1)
            probs /= probs.sum()
            ort_class = np.argmax(probs)

            assert pt_class == ort_class, (
                f"Class mismatch: PyTorch={pt_class}, ONNX={ort_class}"
            )

    def test_onnx_logit_tolerance(self):
        """Raw logit differences stay within acceptable tolerance for CNN."""
        pytest.importorskip("torch", exc_type=ImportError)  # CI lacks torch (Session 168 Fable P0)
        import onnxruntime as ort

        best_ckpt = _best_checkpoint()
        if best_ckpt is None:
            pytest.skip("No checkpoint found")

        import torch
        from rhodesli_ml.models.date_classifier import DateEstimationModel

        model = DateEstimationModel.load_from_checkpoint(
            str(best_ckpt), map_location="cpu"
        )
        model.eval()

        session = ort.InferenceSession(str(ONNX_PATH))

        max_diff = 0.0
        for _ in range(50):
            img = np.random.randn(1, 3, 224, 224).astype(np.float32)
            with torch.no_grad():
                pt = model(torch.tensor(img)).numpy()
            ort_out = session.run(None, {"image": img})[0]
            diff = np.max(np.abs(pt - ort_out))
            max_diff = max(max_diff, diff)

        # EfficientNet-B0 has deeper computation path than calibration MLP,
        # so numerical differences up to ~0.05 are expected (AD-129)
        assert max_diff < 0.05, f"Max diff {max_diff} exceeds 0.05 tolerance"
