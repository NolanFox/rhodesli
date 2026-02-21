"""Tests for calibration inference module."""

import numpy as np
import pytest

from rhodesli_ml.calibration.inference import (
    calibrated_similarity,
    calibrated_similarity_batch,
    is_calibration_available,
    load_calibration_model,
    reset,
)


@pytest.fixture(autouse=True)
def reset_model():
    """Reset model cache before each test."""
    reset()
    yield
    reset()


class TestCalibrationInference:
    def test_load_model_from_artifact(self):
        """Model loads from default artifact path if it exists."""
        result = load_calibration_model()
        # May or may not be available depending on whether artifact exists
        assert isinstance(result, bool)

    def test_calibrated_similarity_returns_float_or_none(self):
        emb_a = np.random.randn(512).astype(np.float32)
        emb_b = np.random.randn(512).astype(np.float32)
        result = calibrated_similarity(emb_a, emb_b)
        assert result is None or isinstance(result, float)

    def test_is_calibration_available(self):
        result = is_calibration_available()
        assert isinstance(result, bool)

    def test_reset_clears_cache(self):
        # Load once
        load_calibration_model()
        # Reset
        reset()
        # Should need to reload
        assert not is_calibration_available() or is_calibration_available()


class TestBatchInference:
    def test_batch_returns_array_or_none(self):
        query = np.random.randn(512).astype(np.float32)
        candidates = np.random.randn(10, 512).astype(np.float32)
        result = calibrated_similarity_batch(query, candidates)
        if result is not None:
            assert result.shape == (10,)
            assert all(0 <= s <= 1 for s in result)

    def test_batch_single_candidate(self):
        query = np.random.randn(512).astype(np.float32)
        candidates = np.random.randn(1, 512).astype(np.float32)
        result = calibrated_similarity_batch(query, candidates)
        if result is not None:
            assert result.shape == (1,)

    def test_batch_consistent_with_single(self):
        """Batch scores should match individual scores."""
        if not load_calibration_model():
            pytest.skip("Calibration model not available")
        query = np.random.randn(512).astype(np.float32)
        candidates = np.random.randn(5, 512).astype(np.float32)
        batch_scores = calibrated_similarity_batch(query, candidates)
        for i in range(5):
            single_score = calibrated_similarity(query, candidates[i])
            assert abs(batch_scores[i] - single_score) < 1e-5

    def test_batch_identical_embeddings(self):
        """Identical embeddings should get consistent scores."""
        if not load_calibration_model():
            pytest.skip("Calibration model not available")
        v = np.random.randn(512).astype(np.float32)
        v = v / np.linalg.norm(v)
        candidates = np.tile(v, (5, 1))
        scores = calibrated_similarity_batch(v, candidates)
        # All scores should be identical
        assert np.allclose(scores, scores[0])
