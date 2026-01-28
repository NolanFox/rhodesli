"""
Tests for temporal priors and era classification.

These tests verify the era-constrained matching logic as documented in
docs/adr_002_temporal_priors.md.
"""

import numpy as np
import pytest


class TestEraEstimate:
    """Tests for era classification data structure."""

    def test_era_estimate_has_required_fields(self):
        """EraEstimate should have era, probabilities, and confidence."""
        from core.temporal import EraEstimate

        estimate = EraEstimate(
            era="1890-1910",
            probabilities={"1890-1910": 0.7, "1910-1930": 0.2, "1930-1950": 0.1},
            confidence=0.5,
        )

        assert estimate.era == "1890-1910"
        assert estimate.probabilities["1890-1910"] == 0.7
        assert estimate.confidence == 0.5

    def test_era_probabilities_sum_to_one(self):
        """Era probabilities should sum to 1.0."""
        from core.temporal import EraEstimate

        probs = {"1890-1910": 0.5, "1910-1930": 0.3, "1930-1950": 0.2}
        estimate = EraEstimate(era="1890-1910", probabilities=probs, confidence=0.2)

        assert abs(sum(estimate.probabilities.values()) - 1.0) < 1e-6


class TestTemporalPenalty:
    """Tests for temporal penalty computation."""

    def test_same_era_no_penalty(self):
        """Same era should have zero penalty."""
        from core.temporal import compute_temporal_penalty, EraEstimate

        era1 = EraEstimate(
            era="1910-1930",
            probabilities={"1890-1910": 0.0, "1910-1930": 1.0, "1930-1950": 0.0},
            confidence=1.0,
        )
        era2 = EraEstimate(
            era="1910-1930",
            probabilities={"1890-1910": 0.0, "1910-1930": 1.0, "1930-1950": 0.0},
            confidence=1.0,
        )

        penalty = compute_temporal_penalty(era1, era2)

        assert penalty == 0.0

    def test_adjacent_eras_mild_penalty(self):
        """Adjacent eras should have mild penalty."""
        from core.temporal import compute_temporal_penalty, EraEstimate

        era1 = EraEstimate(
            era="1890-1910",
            probabilities={"1890-1910": 1.0, "1910-1930": 0.0, "1930-1950": 0.0},
            confidence=1.0,
        )
        era2 = EraEstimate(
            era="1910-1930",
            probabilities={"1890-1910": 0.0, "1910-1930": 1.0, "1930-1950": 0.0},
            confidence=1.0,
        )

        penalty = compute_temporal_penalty(era1, era2)

        # Adjacent eras get -2.0 penalty
        assert penalty == -2.0

    def test_non_adjacent_eras_severe_penalty(self):
        """Non-adjacent eras should have severe penalty."""
        from core.temporal import compute_temporal_penalty, EraEstimate

        era1 = EraEstimate(
            era="1890-1910",
            probabilities={"1890-1910": 1.0, "1910-1930": 0.0, "1930-1950": 0.0},
            confidence=1.0,
        )
        era2 = EraEstimate(
            era="1930-1950",
            probabilities={"1890-1910": 0.0, "1910-1930": 0.0, "1930-1950": 1.0},
            confidence=1.0,
        )

        penalty = compute_temporal_penalty(era1, era2)

        # Non-adjacent eras get -10.0 penalty
        assert penalty == -10.0

    def test_uncertain_era_smooths_penalty(self):
        """Uncertain era estimates should produce smoothed penalties."""
        from core.temporal import compute_temporal_penalty, EraEstimate

        # High confidence in different eras
        era1_confident = EraEstimate(
            era="1890-1910",
            probabilities={"1890-1910": 1.0, "1910-1930": 0.0, "1930-1950": 0.0},
            confidence=1.0,
        )
        era2_confident = EraEstimate(
            era="1930-1950",
            probabilities={"1890-1910": 0.0, "1910-1930": 0.0, "1930-1950": 1.0},
            confidence=1.0,
        )

        # Uncertain: could be any era
        era1_uncertain = EraEstimate(
            era="1890-1910",
            probabilities={"1890-1910": 0.4, "1910-1930": 0.3, "1930-1950": 0.3},
            confidence=0.1,
        )
        era2_uncertain = EraEstimate(
            era="1930-1950",
            probabilities={"1890-1910": 0.3, "1910-1930": 0.3, "1930-1950": 0.4},
            confidence=0.1,
        )

        penalty_confident = compute_temporal_penalty(era1_confident, era2_confident)
        penalty_uncertain = compute_temporal_penalty(era1_uncertain, era2_uncertain)

        # Uncertain estimates should have less severe penalty
        assert penalty_uncertain > penalty_confident  # Less negative = closer to 0

    def test_penalty_is_symmetric(self):
        """Temporal penalty should be symmetric."""
        from core.temporal import compute_temporal_penalty, EraEstimate

        era1 = EraEstimate(
            era="1890-1910",
            probabilities={"1890-1910": 0.8, "1910-1930": 0.15, "1930-1950": 0.05},
            confidence=0.65,
        )
        era2 = EraEstimate(
            era="1930-1950",
            probabilities={"1890-1910": 0.1, "1910-1930": 0.2, "1930-1950": 0.7},
            confidence=0.5,
        )

        penalty_12 = compute_temporal_penalty(era1, era2)
        penalty_21 = compute_temporal_penalty(era2, era1)

        assert np.isclose(penalty_12, penalty_21)


class TestMLSWithTemporal:
    """Tests for MLS integrated with temporal priors."""

    def test_mls_with_temporal_adds_penalty(self):
        """MLS with temporal should add penalty to base MLS."""
        from core.temporal import mls_with_temporal, EraEstimate

        mu1 = np.random.randn(512).astype(np.float32)
        mu1 = mu1 / np.linalg.norm(mu1)
        mu2 = mu1.copy()  # Identical embeddings
        sigma_sq = np.full(512, 0.1, dtype=np.float32)

        era_same = EraEstimate(
            era="1910-1930",
            probabilities={"1890-1910": 0.0, "1910-1930": 1.0, "1930-1950": 0.0},
            confidence=1.0,
        )
        era_different = EraEstimate(
            era="1930-1950",
            probabilities={"1890-1910": 0.0, "1910-1930": 0.0, "1930-1950": 1.0},
            confidence=1.0,
        )

        # Same era: penalty = 0
        score_same_era = mls_with_temporal(
            mu1, sigma_sq, era_same,
            mu2, sigma_sq, era_same
        )

        # Adjacent era: penalty = -2.0
        score_adjacent = mls_with_temporal(
            mu1, sigma_sq, era_same,
            mu2, sigma_sq, era_different
        )

        assert score_same_era > score_adjacent
        assert np.isclose(score_same_era - score_adjacent, 2.0)

    def test_temporal_eliminates_cross_era_false_positives(self):
        """
        CRITICAL TEST: Cross-era matches should be effectively eliminated.

        Two similar faces from incompatible eras (1890-1910 vs 1930-1950)
        should score much lower than the same faces from compatible eras.
        """
        from core.temporal import mls_with_temporal, EraEstimate
        from core.pfe import mutual_likelihood_score

        # Two very similar embeddings (would match without temporal constraint)
        mu1 = np.random.randn(512).astype(np.float32)
        mu1 = mu1 / np.linalg.norm(mu1)
        mu2 = mu1 + np.random.randn(512).astype(np.float32) * 0.05
        mu2 = mu2 / np.linalg.norm(mu2)
        sigma_sq = np.full(512, 0.1, dtype=np.float32)

        # Base MLS without temporal (should be high for similar faces)
        base_mls = mutual_likelihood_score(mu1, sigma_sq, mu2, sigma_sq)

        # Cross-era comparison (1890s vs 1940s - impossible)
        era_1890s = EraEstimate(
            era="1890-1910",
            probabilities={"1890-1910": 0.95, "1910-1930": 0.05, "1930-1950": 0.0},
            confidence=0.9,
        )
        era_1940s = EraEstimate(
            era="1930-1950",
            probabilities={"1890-1910": 0.0, "1910-1930": 0.05, "1930-1950": 0.95},
            confidence=0.9,
        )

        cross_era_mls = mls_with_temporal(
            mu1, sigma_sq, era_1890s,
            mu2, sigma_sq, era_1940s
        )

        # Cross-era penalty should dominate
        # The -10.0 penalty should make cross_era_mls much lower
        assert cross_era_mls < base_mls - 8.0, (
            f"Cross-era penalty should dominate. "
            f"Base MLS: {base_mls:.2f}, Cross-era MLS: {cross_era_mls:.2f}"
        )


class TestEraClassifier:
    """Tests for CLIP-based era classification."""

    @pytest.fixture
    def sample_image(self):
        """Create a sample image array for testing."""
        # 224x224 RGB image (CLIP input size)
        return np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)

    def test_classify_era_returns_era_estimate(self, sample_image):
        """Era classifier should return an EraEstimate."""
        from core.temporal import classify_era, EraEstimate

        result = classify_era(sample_image)

        assert isinstance(result, EraEstimate)
        assert result.era in ["1890-1910", "1910-1930", "1930-1950"]

    def test_classify_era_probabilities_sum_to_one(self, sample_image):
        """Era probabilities should sum to 1.0."""
        from core.temporal import classify_era

        result = classify_era(sample_image)

        prob_sum = sum(result.probabilities.values())
        assert abs(prob_sum - 1.0) < 1e-5

    def test_classify_era_confidence_is_valid(self, sample_image):
        """Confidence should be in [0, 1]."""
        from core.temporal import classify_era

        result = classify_era(sample_image)

        assert 0.0 <= result.confidence <= 1.0

    def test_classify_era_handles_grayscale(self):
        """Should handle grayscale images."""
        from core.temporal import classify_era

        grayscale_image = np.random.randint(0, 255, (224, 224), dtype=np.uint8)
        result = classify_era(grayscale_image)

        assert result.era in ["1890-1910", "1910-1930", "1930-1950"]


class TestTemporalIntegration:
    """Integration tests for the temporal pipeline."""

    def test_classify_and_score_workflow(self):
        """Test the full workflow: classify eras, then score with temporal."""
        from core.temporal import classify_era, mls_with_temporal

        # Two sample images
        image1 = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
        image2 = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)

        # Classify eras
        era1 = classify_era(image1)
        era2 = classify_era(image2)

        # Create face embeddings
        mu1 = np.random.randn(512).astype(np.float32)
        mu2 = np.random.randn(512).astype(np.float32)
        sigma_sq = np.full(512, 0.1, dtype=np.float32)

        # Score with temporal
        score = mls_with_temporal(mu1, sigma_sq, era1, mu2, sigma_sq, era2)

        # Should return a valid score
        assert isinstance(score, float)
        assert not np.isnan(score)
        assert not np.isinf(score)
