"""
Tests for Mutual Likelihood Score (MLS) and Probabilistic Face Embeddings.

These tests verify the core mathematical properties of MLS as documented in
docs/adr_001_mls_math.md.
"""

import numpy as np
import pytest


class TestMutualLikelihoodScore:
    """Tests for the MLS formula."""

    def test_mls_returns_float(self):
        """MLS should return a single float score."""
        from core.pfe import mutual_likelihood_score

        mu1 = np.random.randn(512).astype(np.float32)
        mu2 = np.random.randn(512).astype(np.float32)
        sigma_sq1 = np.full(512, 0.1, dtype=np.float32)
        sigma_sq2 = np.full(512, 0.1, dtype=np.float32)

        result = mutual_likelihood_score(mu1, sigma_sq1, mu2, sigma_sq2)

        assert isinstance(result, float)

    def test_mls_is_symmetric(self):
        """MLS(f1, f2) should equal MLS(f2, f1)."""
        from core.pfe import mutual_likelihood_score

        mu1 = np.random.randn(512).astype(np.float32)
        mu2 = np.random.randn(512).astype(np.float32)
        sigma_sq1 = np.full(512, 0.1, dtype=np.float32)
        sigma_sq2 = np.full(512, 0.2, dtype=np.float32)

        score_12 = mutual_likelihood_score(mu1, sigma_sq1, mu2, sigma_sq2)
        score_21 = mutual_likelihood_score(mu2, sigma_sq2, mu1, sigma_sq1)

        assert np.isclose(score_12, score_21)

    def test_identical_embeddings_score_higher_than_different(self):
        """Identical embeddings should have higher MLS than different ones."""
        from core.pfe import mutual_likelihood_score

        mu = np.random.randn(512).astype(np.float32)
        mu_different = np.random.randn(512).astype(np.float32)
        sigma_sq = np.full(512, 0.1, dtype=np.float32)

        # Identical embeddings
        score_identical = mutual_likelihood_score(mu, sigma_sq, mu, sigma_sq)
        # Different embeddings
        score_different = mutual_likelihood_score(mu, sigma_sq, mu_different, sigma_sq)

        assert score_identical > score_different

    def test_increasing_sigma_lowers_mls_for_identical_embeddings(self):
        """
        CRITICAL TEST: For identical embeddings, increasing σ² should lower MLS.

        This is the core uncertainty property: confident matches of the same face
        score higher than uncertain matches of the same face.

        NOTE (scalar sigma fix - docs/adr_006_scalar_sigma_fix.md):
        With scalar sigma, this property only holds for truly identical embeddings.
        For "similar but different" embeddings, lower σ² amplifies the differences,
        which is actually correct behavior for clustering (small differences matter
        more for high-quality photos).
        """
        from core.pfe import mutual_likelihood_score

        # Identical embeddings (same face, same photo)
        mu = np.random.randn(512).astype(np.float32)
        mu = mu / np.linalg.norm(mu)  # Normalize

        # Low uncertainty (high quality photo)
        sigma_sq_low = np.full(512, 0.01, dtype=np.float32)
        # High uncertainty (degraded photo)
        sigma_sq_high = np.full(512, 1.0, dtype=np.float32)

        # Compare confident match vs uncertain match OF SAME EMBEDDING
        score_confident = mutual_likelihood_score(mu, sigma_sq_low, mu, sigma_sq_low)
        score_uncertain = mutual_likelihood_score(mu, sigma_sq_high, mu, sigma_sq_high)

        # CRITICAL: Uncertain match should score LOWER
        assert score_confident > score_uncertain, (
            f"Increasing σ² should lower MLS for identical embeddings. "
            f"Got confident={score_confident:.2f}, uncertain={score_uncertain:.2f}"
        )

    def test_mls_is_negative_or_zero(self):
        """MLS should be in (-∞, 0] as it's a log-likelihood."""
        from core.pfe import mutual_likelihood_score

        mu1 = np.random.randn(512).astype(np.float32)
        mu2 = np.random.randn(512).astype(np.float32)
        sigma_sq = np.full(512, 0.1, dtype=np.float32)

        result = mutual_likelihood_score(mu1, sigma_sq, mu2, sigma_sq)

        assert result <= 0, f"MLS should be <= 0, got {result}"

    def test_mls_handles_edge_case_identical_embeddings(self):
        """When μ1 = μ2, MLS should equal just the uncertainty penalty."""
        from core.pfe import mutual_likelihood_score

        mu = np.ones(512, dtype=np.float32)
        sigma_sq = np.full(512, 0.5, dtype=np.float32)

        result = mutual_likelihood_score(mu, sigma_sq, mu, sigma_sq)

        # When μ1 = μ2, the Mahalanobis term is 0
        # MLS = -Σ log(σ1² + σ2²) = -512 * log(1.0) = 0
        expected = -512 * np.log(1.0)  # = 0
        assert np.isclose(result, expected, atol=1e-5)


class TestComputeSigmaSq:
    """Tests for deriving σ² from quality signals."""

    def test_returns_correct_shape(self):
        """Should return σ² with shape (512,)."""
        from core.pfe import compute_sigma_sq

        result = compute_sigma_sq(det_score=0.9, face_area=10000)

        assert result.shape == (512,)
        assert result.dtype == np.float32

    def test_high_quality_produces_low_sigma(self):
        """High detection score and large face should produce low σ²."""
        from core.pfe import compute_sigma_sq

        sigma_sq_high_quality = compute_sigma_sq(det_score=0.99, face_area=50000)
        sigma_sq_low_quality = compute_sigma_sq(det_score=0.5, face_area=1000)

        # High quality should have lower uncertainty
        assert sigma_sq_high_quality.mean() < sigma_sq_low_quality.mean()

    def test_sigma_is_bounded(self):
        """σ² should be within [min_sigma_sq, max_sigma_sq]."""
        from core.pfe import compute_sigma_sq

        min_sigma = 0.01
        max_sigma = 1.0

        # Test extreme cases
        sigma_best = compute_sigma_sq(det_score=1.0, face_area=100000,
                                       min_sigma_sq=min_sigma, max_sigma_sq=max_sigma)
        sigma_worst = compute_sigma_sq(det_score=0.0, face_area=0,
                                        min_sigma_sq=min_sigma, max_sigma_sq=max_sigma)

        # Use np.isclose due to float32 precision
        assert sigma_best.min() >= min_sigma - 1e-6
        assert sigma_worst.max() <= max_sigma + 1e-6

    def test_det_score_affects_sigma(self):
        """Detection score should inversely affect σ²."""
        from core.pfe import compute_sigma_sq

        sigma_high_det = compute_sigma_sq(det_score=0.95, face_area=10000)
        sigma_low_det = compute_sigma_sq(det_score=0.5, face_area=10000)

        assert sigma_high_det.mean() < sigma_low_det.mean()

    def test_face_area_affects_sigma(self):
        """Larger face area should produce lower σ²."""
        from core.pfe import compute_sigma_sq

        sigma_large_face = compute_sigma_sq(det_score=0.8, face_area=50000)
        sigma_small_face = compute_sigma_sq(det_score=0.8, face_area=1000)

        assert sigma_large_face.mean() < sigma_small_face.mean()


class TestPFEIntegration:
    """Integration tests for the full PFE workflow."""

    def test_create_pfe_from_face_data(self):
        """Should create a PFE from face detection results."""
        from core.pfe import create_pfe

        face_data = {
            "embedding": np.random.randn(512).astype(np.float32),
            "det_score": 0.85,
            "bbox": [100, 100, 200, 250],  # 100x150 face
        }
        image_shape = (480, 640)  # height, width

        pfe = create_pfe(face_data, image_shape)

        assert "mu" in pfe
        assert "sigma_sq" in pfe
        assert pfe["mu"].shape == (512,)
        assert pfe["sigma_sq"].shape == (512,)

    def test_pfe_preserves_original_metadata(self):
        """PFE should preserve filename, filepath, bbox, det_score."""
        from core.pfe import create_pfe

        face_data = {
            "filename": "test.jpg",
            "filepath": "/path/to/test.jpg",
            "embedding": np.random.randn(512).astype(np.float32),
            "det_score": 0.85,
            "bbox": [100, 100, 200, 250],
        }
        image_shape = (480, 640)

        pfe = create_pfe(face_data, image_shape)

        assert pfe["filename"] == "test.jpg"
        assert pfe["filepath"] == "/path/to/test.jpg"
        assert pfe["det_score"] == 0.85
        assert pfe["bbox"] == [100, 100, 200, 250]
