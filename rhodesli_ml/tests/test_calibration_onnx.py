"""Tests for ONNX export, inference, and fallback chain."""

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from rhodesli_ml.calibration.inference import (
    calibrated_similarity,
    calibrated_similarity_batch,
    get_backend,
    load_calibration_model,
    reset,
)


ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts"
ONNX_PATH = ARTIFACTS_DIR / "calibration_v1.onnx"
PT_PATH = ARTIFACTS_DIR / "calibration_v1.pt"


@pytest.fixture(autouse=True)
def reset_model():
    """Reset model cache before each test."""
    reset()
    yield
    reset()


class TestONNXExport:
    """Tests for the ONNX export script."""

    @pytest.mark.skipif(not PT_PATH.exists(), reason="No .pt model to export")
    def test_export_produces_valid_onnx(self, tmp_path):
        from rhodesli_ml.calibration.export_onnx import export_to_onnx

        output = tmp_path / "test_model.onnx"
        result = export_to_onnx(PT_PATH, output)
        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0

    @pytest.mark.skipif(not PT_PATH.exists(), reason="No .pt model to export")
    def test_export_validates_against_pytorch(self, tmp_path):
        from rhodesli_ml.calibration.export_onnx import export_to_onnx, validate_onnx

        output = tmp_path / "test_model.onnx"
        export_to_onnx(PT_PATH, output)
        max_diff = validate_onnx(PT_PATH, output, n_samples=20)
        assert max_diff < 1e-5

    def test_export_nonexistent_model_raises(self, tmp_path):
        from rhodesli_ml.calibration.export_onnx import export_to_onnx

        with pytest.raises(FileNotFoundError):
            export_to_onnx(tmp_path / "nonexistent.pt", tmp_path / "out.onnx")


class TestONNXInference:
    """Tests for the ONNX inference module directly."""

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="No .onnx model")
    def test_single_prediction(self):
        from rhodesli_ml.calibration.inference_onnx import ONNXCalibrationInference

        model = ONNXCalibrationInference(ONNX_PATH)
        emb_a = np.random.randn(512).astype(np.float32)
        emb_b = np.random.randn(512).astype(np.float32)
        score = model.predict(emb_a, emb_b)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="No .onnx model")
    def test_batch_prediction(self):
        from rhodesli_ml.calibration.inference_onnx import ONNXCalibrationInference

        model = ONNXCalibrationInference(ONNX_PATH)
        query = np.random.randn(512).astype(np.float32)
        candidates = np.random.randn(10, 512).astype(np.float32)
        scores = model.predict_batch(query, candidates)
        assert scores.shape == (10,)
        assert all(0.0 <= s <= 1.0 for s in scores)

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="No .onnx model")
    def test_batch_consistent_with_single(self):
        from rhodesli_ml.calibration.inference_onnx import ONNXCalibrationInference

        model = ONNXCalibrationInference(ONNX_PATH)
        query = np.random.randn(512).astype(np.float32)
        candidates = np.random.randn(5, 512).astype(np.float32)
        batch_scores = model.predict_batch(query, candidates)
        for i in range(5):
            single = model.predict(query, candidates[i])
            assert abs(batch_scores[i] - single) < 1e-5

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="No .onnx model")
    def test_identical_embeddings_high_score(self):
        from rhodesli_ml.calibration.inference_onnx import ONNXCalibrationInference

        model = ONNXCalibrationInference(ONNX_PATH)
        v = np.random.randn(512).astype(np.float32)
        v = v / np.linalg.norm(v)
        score = model.predict(v, v)
        assert score > 0.5, f"Same embedding should score high, got {score}"

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="No .onnx model")
    def test_2d_input_accepted(self):
        from rhodesli_ml.calibration.inference_onnx import ONNXCalibrationInference

        model = ONNXCalibrationInference(ONNX_PATH)
        emb_a = np.random.randn(1, 512).astype(np.float32)
        emb_b = np.random.randn(1, 512).astype(np.float32)
        score = model.predict(emb_a, emb_b)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


class TestFallbackChain:
    """Tests for ONNX→PyTorch→None fallback in inference.py."""

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="No .onnx model")
    def test_prefers_onnx_when_available(self):
        """ONNX should be preferred over PyTorch when both exist."""
        result = load_calibration_model()
        assert result is True
        assert get_backend() == "onnx"

    @pytest.mark.skipif(not PT_PATH.exists(), reason="No .pt model")
    def test_falls_back_to_pytorch_when_no_onnx(self, tmp_path):
        """When ONNX is not available, falls back to PyTorch."""
        import shutil

        # Copy .pt to a temp dir (no .onnx)
        pt_copy = tmp_path / "calibration_v1.pt"
        shutil.copy(PT_PATH, pt_copy)
        result = load_calibration_model(model_path=pt_copy)
        assert result is True
        assert get_backend() == "pytorch"

    def test_returns_false_when_no_models(self, tmp_path):
        """Returns False when no model files exist."""
        result = load_calibration_model(model_path=tmp_path / "nonexistent.pt")
        assert result is False
        assert get_backend() is None

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="No .onnx model")
    def test_onnx_scores_match_pytorch_scores(self):
        """ONNX and PyTorch backends should produce matching scores."""
        import torch

        from rhodesli_ml.calibration.model import CalibrationModel

        # Load ONNX via inference.py
        load_calibration_model()
        assert get_backend() == "onnx"

        np.random.seed(42)
        emb_a = np.random.randn(512).astype(np.float32)
        emb_b = np.random.randn(512).astype(np.float32)
        onnx_score = calibrated_similarity(emb_a, emb_b)

        # Load PyTorch directly
        checkpoint = torch.load(PT_PATH, weights_only=False, map_location="cpu")
        config = checkpoint.get("config", {})
        model = CalibrationModel(
            embed_dim=config.get("embed_dim", 512),
            hidden_dim=config.get("hidden_dim", 32),
            dropout=config.get("dropout", 0.5),
        )
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        pt_score = model.predict(
            torch.tensor(emb_a), torch.tensor(emb_b)
        )

        assert abs(onnx_score - pt_score) < 1e-5

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="No .onnx model")
    def test_batch_via_onnx_backend(self):
        """Batch inference works through the ONNX backend."""
        load_calibration_model()
        assert get_backend() == "onnx"

        query = np.random.randn(512).astype(np.float32)
        candidates = np.random.randn(5, 512).astype(np.float32)
        scores = calibrated_similarity_batch(query, candidates)
        assert scores is not None
        assert scores.shape == (5,)
        assert all(0.0 <= s <= 1.0 for s in scores)

    def test_graceful_degradation_no_model(self, tmp_path):
        """Returns None when no model is available."""
        # Force no model by loading from empty dir
        load_calibration_model(model_path=tmp_path / "nonexistent.pt")
        emb_a = np.random.randn(512).astype(np.float32)
        emb_b = np.random.randn(512).astype(np.float32)
        assert calibrated_similarity(emb_a, emb_b) is None
        query = np.random.randn(512).astype(np.float32)
        candidates = np.random.randn(5, 512).astype(np.float32)
        assert calibrated_similarity_batch(query, candidates) is None

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="No .onnx model")
    def test_reset_allows_reload(self):
        """After reset, model can be reloaded."""
        load_calibration_model()
        assert get_backend() == "onnx"
        reset()
        assert get_backend() is None
        load_calibration_model()
        assert get_backend() == "onnx"
