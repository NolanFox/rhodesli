"""Tests for date estimation inference module (ONNX + fallback chain)."""

import numpy as np
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from rhodesli_ml.date_inference import inference


ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts"
ONNX_PATH = ARTIFACTS_DIR / "date_estimation_v1.onnx"


@pytest.fixture(autouse=True)
def reset_model_cache():
    """Reset model cache before each test."""
    inference.reset()
    yield
    inference.reset()


class TestInferenceONNX:
    """Tests for ONNX-based inference."""

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="ONNX model not available")
    def test_load_onnx_model(self):
        """Model loads via ONNX backend."""
        assert inference.load_date_model()
        assert inference.get_backend() == "onnx"

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="ONNX model not available")
    def test_predict_date_returns_dict(self):
        """predict_date returns expected structure."""
        # Create a dummy 100x100 RGB image
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = inference.predict_date(image)

        assert result is not None
        assert "predicted_decade" in result
        assert "confidence" in result
        assert "decade_probabilities" in result
        assert "expected_year" in result
        assert "source" in result

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="ONNX model not available")
    def test_predict_date_decade_is_valid(self):
        """Predicted decade is in valid range."""
        image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        result = inference.predict_date(image)

        assert result is not None
        assert result["predicted_decade"] in range(1900, 2010, 10)

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="ONNX model not available")
    def test_predict_date_probabilities_sum_to_one(self):
        """Decade probabilities sum to approximately 1.0."""
        image = np.random.randint(0, 255, (150, 150, 3), dtype=np.uint8)
        result = inference.predict_date(image)

        assert result is not None
        probs = result["decade_probabilities"]
        total = sum(probs.values())
        assert abs(total - 1.0) < 0.01, f"Probabilities sum to {total}, not ~1.0"

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="ONNX model not available")
    def test_predict_date_confidence_range(self):
        """Confidence is between 0 and 1."""
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = inference.predict_date(image)

        assert result is not None
        assert 0.0 <= result["confidence"] <= 1.0

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="ONNX model not available")
    def test_predict_date_expected_year_in_range(self):
        """Expected year is between 1900 and 2010."""
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = inference.predict_date(image)

        assert result is not None
        assert 1900 <= result["expected_year"] <= 2010

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="ONNX model not available")
    def test_predict_date_source_is_coral(self):
        """Source field identifies the model."""
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = inference.predict_date(image)

        assert result is not None
        assert result["source"] == "coral_v1"

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="ONNX model not available")
    def test_predict_date_all_decades_present(self):
        """All 11 decades (1900-2000) are present in probabilities."""
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = inference.predict_date(image)

        assert result is not None
        decades = result["decade_probabilities"]
        expected_keys = [str(d) for d in range(1900, 2010, 10)]
        for key in expected_keys:
            assert key in decades, f"Missing decade {key}"

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="ONNX model not available")
    def test_predict_date_deterministic(self):
        """Same image produces same prediction."""
        np.random.seed(42)
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result1 = inference.predict_date(image)
        result2 = inference.predict_date(image)

        assert result1["predicted_decade"] == result2["predicted_decade"]
        assert result1["confidence"] == result2["confidence"]


class TestGracefulDegradation:
    """Tests for graceful degradation when model is unavailable."""

    def test_no_model_returns_none(self):
        """predict_date returns None when no model is available."""
        # Point to empty dir where no ONNX or checkpoint exists
        with patch.object(inference, "_get_artifact_dir", return_value=Path("/nonexistent")):
            with patch.object(inference, "_find_best_checkpoint", return_value=None):
                image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
                result = inference.predict_date(image)
                assert result is None

    def test_no_model_backend_is_none(self):
        """Backend is None when no model loaded."""
        with patch.object(inference, "_get_artifact_dir", return_value=Path("/nonexistent")):
            with patch.object(inference, "_find_best_checkpoint", return_value=None):
                inference.load_date_model()
                assert inference.get_backend() is None

    def test_is_available_false_when_no_model(self):
        """is_date_model_available returns False when no model exists."""
        with patch.object(inference, "_get_artifact_dir", return_value=Path("/nonexistent")):
            with patch.object(inference, "_find_best_checkpoint", return_value=None):
                assert not inference.is_date_model_available()


class TestONNXInferenceClass:
    """Direct tests for ONNXDateEstimationInference class."""

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="ONNX model not available")
    def test_predict_from_tensor_shape(self):
        """predict_from_tensor works with correct input shape."""
        from rhodesli_ml.date_inference.inference_onnx import ONNXDateEstimationInference

        model = ONNXDateEstimationInference(ONNX_PATH)
        tensor = np.random.randn(1, 3, 224, 224).astype(np.float32)
        result = model.predict_from_tensor(tensor)

        assert "predicted_decade" in result
        assert "decade_probabilities" in result

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="ONNX model not available")
    def test_predict_from_tensor_3d_input(self):
        """predict_from_tensor works with 3D input (auto-batches)."""
        from rhodesli_ml.date_inference.inference_onnx import ONNXDateEstimationInference

        model = ONNXDateEstimationInference(ONNX_PATH)
        tensor = np.random.randn(3, 224, 224).astype(np.float32)
        result = model.predict_from_tensor(tensor)

        assert "predicted_decade" in result

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="ONNX model not available")
    def test_predict_from_image_any_size(self):
        """predict_from_image handles arbitrary image sizes."""
        from rhodesli_ml.date_inference.inference_onnx import ONNXDateEstimationInference

        model = ONNXDateEstimationInference(ONNX_PATH)

        # Test various sizes
        for h, w in [(50, 50), (800, 600), (100, 300)]:
            image = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
            result = model.predict_from_image(image)
            assert "predicted_decade" in result

    @pytest.mark.skipif(not ONNX_PATH.exists(), reason="ONNX model not available")
    def test_ordinal_logits_to_probs_valid(self):
        """CORAL logit conversion produces valid probability distribution."""
        from rhodesli_ml.date_inference.inference_onnx import ONNXDateEstimationInference

        model = ONNXDateEstimationInference(ONNX_PATH)

        # Test with known logits
        logits = np.array([2.0, 1.5, 1.0, 0.5, 0.0, -0.5, -1.0, -1.5, -2.0, -2.5])
        probs = model._ordinal_logits_to_probs(logits)

        assert len(probs) == 11
        assert all(p >= 0 for p in probs)
        assert abs(sum(probs) - 1.0) < 1e-6
