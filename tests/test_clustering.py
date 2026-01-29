"""
Tests for identity clustering with MLS and temporal priors.

These tests verify the clustering logic as documented in
docs/adr_003_identity_clustering.md.
"""

import numpy as np
import pytest


class TestMLSToDistance:
    """Tests for MLS to distance conversion."""

    def test_higher_mls_produces_lower_distance(self):
        """Higher MLS (more similar) should produce lower distance."""
        from core.clustering import mls_to_distance

        # With shifted distance (max_mls - mls), higher MLS = lower distance
        max_mls = 1000
        assert mls_to_distance(-100, max_mls) > mls_to_distance(-50, max_mls)
        assert mls_to_distance(-50, max_mls) > mls_to_distance(0, max_mls)
        assert mls_to_distance(0, max_mls) > mls_to_distance(100, max_mls)

    def test_distance_is_shifted_from_max(self):
        """Distance should be max_mls - MLS (non-negative, best match = 0)."""
        from core.clustering import mls_to_distance

        # Distance = max_mls - mls
        max_mls = 1000
        assert mls_to_distance(1000, max_mls) == 0  # Best match has distance 0
        assert mls_to_distance(500, max_mls) == 500
        assert mls_to_distance(0, max_mls) == 1000

    def test_distance_is_non_negative(self):
        """Distance must be non-negative for scipy linkage."""
        from core.clustering import mls_to_distance

        max_mls = 750
        # All MLS values <= max_mls produce non-negative distances
        for mls in [750, 500, 0, -500]:
            assert mls_to_distance(mls, max_mls) >= 0


class TestMLSToProbability:
    """Tests for MLS to probability conversion."""

    def test_returns_value_between_0_and_1(self):
        """Probability should be in [0, 1]."""
        from core.clustering import mls_to_probability

        for mls in [-1000, -500, 0, 500, 1000]:
            prob = mls_to_probability(mls)
            assert 0 <= prob <= 1

    def test_higher_mls_produces_higher_probability(self):
        """Higher MLS should produce higher match probability."""
        from core.clustering import mls_to_probability

        assert mls_to_probability(-500) < mls_to_probability(0)
        assert mls_to_probability(0) < mls_to_probability(500)

    def test_zero_mls_produces_50_percent(self):
        """MLS=0 should produce approximately 50% probability."""
        from core.clustering import mls_to_probability

        prob = mls_to_probability(0)
        assert 0.45 <= prob <= 0.55


class TestComputeMatchRange:
    """Tests for computing match probability ranges within clusters."""

    def test_single_face_returns_none(self):
        """A cluster with one face has no pairs, so no range."""
        from core.clustering import compute_match_range
        from core.temporal import EraEstimate

        face = {
            "mu": np.random.randn(512).astype(np.float32),
            "sigma_sq": np.full(512, 0.1, dtype=np.float32),
            "era": EraEstimate(
                era="1910-1930",
                probabilities={"1890-1910": 0.1, "1910-1930": 0.8, "1930-1950": 0.1},
                confidence=0.7,
            ),
        }

        result = compute_match_range([face])

        assert result is None

    def test_two_faces_returns_single_score_as_range(self):
        """A cluster with two faces has one pair."""
        from core.clustering import compute_match_range
        from core.temporal import EraEstimate

        era = EraEstimate(
            era="1910-1930",
            probabilities={"1890-1910": 0.0, "1910-1930": 1.0, "1930-1950": 0.0},
            confidence=1.0,
        )

        mu = np.random.randn(512).astype(np.float32)
        mu = mu / np.linalg.norm(mu)

        face1 = {
            "mu": mu,
            "sigma_sq": np.full(512, 0.1, dtype=np.float32),
            "era": era,
        }
        face2 = {
            "mu": mu + np.random.randn(512).astype(np.float32) * 0.01,
            "sigma_sq": np.full(512, 0.1, dtype=np.float32),
            "era": era,
        }

        min_prob, max_prob = compute_match_range([face1, face2])

        # Single pair, so min == max
        assert np.isclose(min_prob, max_prob, atol=0.01)

    def test_returns_min_max_probabilities(self):
        """Should return (min_prob, max_prob) for cluster."""
        from core.clustering import compute_match_range
        from core.temporal import EraEstimate

        era = EraEstimate(
            era="1910-1930",
            probabilities={"1890-1910": 0.0, "1910-1930": 1.0, "1930-1950": 0.0},
            confidence=1.0,
        )

        # Create 3 faces with varying similarity
        mu_base = np.random.randn(512).astype(np.float32)
        mu_base = mu_base / np.linalg.norm(mu_base)

        faces = [
            {
                "mu": mu_base,
                "sigma_sq": np.full(512, 0.1, dtype=np.float32),
                "era": era,
            },
            {
                "mu": mu_base + np.random.randn(512).astype(np.float32) * 0.05,
                "sigma_sq": np.full(512, 0.1, dtype=np.float32),
                "era": era,
            },
            {
                "mu": mu_base + np.random.randn(512).astype(np.float32) * 0.1,
                "sigma_sq": np.full(512, 0.1, dtype=np.float32),
                "era": era,
            },
        ]

        min_prob, max_prob = compute_match_range(faces)

        assert 0 <= min_prob <= 1
        assert 0 <= max_prob <= 1
        assert min_prob <= max_prob


class TestClusterIdentities:
    """Tests for the main clustering function."""

    def test_empty_input_returns_empty_list(self):
        """No faces should produce no clusters."""
        from core.clustering import cluster_identities

        result = cluster_identities([])

        assert result == []

    def test_single_face_returns_singleton_cluster(self):
        """One face should produce one cluster with that face."""
        from core.clustering import cluster_identities
        from core.temporal import EraEstimate

        face = {
            "mu": np.random.randn(512).astype(np.float32),
            "sigma_sq": np.full(512, 0.1, dtype=np.float32),
            "era": EraEstimate(
                era="1910-1930",
                probabilities={"1890-1910": 0.1, "1910-1930": 0.8, "1930-1950": 0.1},
                confidence=0.7,
            ),
            "filename": "test.jpg",
        }

        clusters = cluster_identities([face])

        assert len(clusters) == 1
        assert len(clusters[0]["faces"]) == 1
        assert clusters[0]["faces"][0]["filename"] == "test.jpg"

    def test_identical_faces_cluster_together(self):
        """Identical embeddings should cluster into same group."""
        from core.clustering import cluster_identities
        from core.temporal import EraEstimate

        era = EraEstimate(
            era="1910-1930",
            probabilities={"1890-1910": 0.0, "1910-1930": 1.0, "1930-1950": 0.0},
            confidence=1.0,
        )

        mu = np.random.randn(512).astype(np.float32)
        mu = mu / np.linalg.norm(mu)
        sigma_sq = np.full(512, 0.1, dtype=np.float32)

        faces = [
            {"mu": mu.copy(), "sigma_sq": sigma_sq.copy(), "era": era, "filename": "a.jpg"},
            {"mu": mu.copy(), "sigma_sq": sigma_sq.copy(), "era": era, "filename": "b.jpg"},
        ]

        clusters = cluster_identities(faces)

        # Should be one cluster with both faces
        assert len(clusters) == 1
        assert len(clusters[0]["faces"]) == 2

    def test_different_faces_stay_separate(self):
        """Very different embeddings should not cluster together."""
        from core.clustering import cluster_identities
        from core.temporal import EraEstimate

        era = EraEstimate(
            era="1910-1930",
            probabilities={"1890-1910": 0.0, "1910-1930": 1.0, "1930-1950": 0.0},
            confidence=1.0,
        )

        # Very low uncertainty (high quality photo) - makes embedding differences matter
        sigma_sq = np.full(512, 0.001, dtype=np.float32)

        # Two anti-correlated embeddings (maximally different)
        mu1 = np.random.randn(512).astype(np.float32)
        mu1 = mu1 / np.linalg.norm(mu1)
        mu2 = -mu1  # Anti-correlated

        faces = [
            {"mu": mu1, "sigma_sq": sigma_sq.copy(), "era": era, "filename": "a.jpg"},
            {"mu": mu2, "sigma_sq": sigma_sq.copy(), "era": era, "filename": "b.jpg"},
        ]

        clusters = cluster_identities(faces)

        # Should be two separate clusters
        assert len(clusters) == 2

    def test_cross_era_faces_stay_separate(self):
        """
        CRITICAL TEST: Similar faces from incompatible eras should not cluster.
        """
        from core.clustering import cluster_identities
        from core.temporal import EraEstimate

        # Same embedding, but different eras
        mu = np.random.randn(512).astype(np.float32)
        mu = mu / np.linalg.norm(mu)
        sigma_sq = np.full(512, 0.1, dtype=np.float32)

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

        faces = [
            {"mu": mu.copy(), "sigma_sq": sigma_sq.copy(), "era": era_1890s, "filename": "1890s.jpg"},
            {"mu": mu.copy(), "sigma_sq": sigma_sq.copy(), "era": era_1940s, "filename": "1940s.jpg"},
        ]

        clusters = cluster_identities(faces)

        # Should be two separate clusters despite identical embeddings
        assert len(clusters) == 2, (
            "Cross-era faces should not cluster together. "
            "Temporal penalty should prevent clustering."
        )

    def test_clusters_are_stable_across_runs(self):
        """Clustering should be deterministic."""
        from core.clustering import cluster_identities
        from core.temporal import EraEstimate

        era = EraEstimate(
            era="1910-1930",
            probabilities={"1890-1910": 0.1, "1910-1930": 0.8, "1930-1950": 0.1},
            confidence=0.7,
        )

        np.random.seed(42)
        faces = []
        for i in range(5):
            mu = np.random.randn(512).astype(np.float32)
            faces.append({
                "mu": mu,
                "sigma_sq": np.full(512, 0.1, dtype=np.float32),
                "era": era,
                "filename": f"face_{i}.jpg",
            })

        # Run clustering twice
        clusters1 = cluster_identities(faces.copy())
        clusters2 = cluster_identities(faces.copy())

        # Should produce identical results
        assert len(clusters1) == len(clusters2)
        for c1, c2 in zip(clusters1, clusters2):
            filenames1 = sorted([f["filename"] for f in c1["faces"]])
            filenames2 = sorted([f["filename"] for f in c2["faces"]])
            assert filenames1 == filenames2

    def test_cluster_contains_match_range(self):
        """Each cluster should have a match_range field."""
        from core.clustering import cluster_identities
        from core.temporal import EraEstimate

        era = EraEstimate(
            era="1910-1930",
            probabilities={"1890-1910": 0.0, "1910-1930": 1.0, "1930-1950": 0.0},
            confidence=1.0,
        )

        mu = np.random.randn(512).astype(np.float32)
        mu = mu / np.linalg.norm(mu)

        faces = [
            {"mu": mu.copy(), "sigma_sq": np.full(512, 0.1, dtype=np.float32), "era": era, "filename": "a.jpg"},
            {"mu": mu + 0.01, "sigma_sq": np.full(512, 0.1, dtype=np.float32), "era": era, "filename": "b.jpg"},
        ]

        clusters = cluster_identities(faces)

        assert len(clusters) == 1
        assert "match_range" in clusters[0]
        if clusters[0]["match_range"] is not None:
            min_prob, max_prob = clusters[0]["match_range"]
            assert 0 <= min_prob <= 1
            assert 0 <= max_prob <= 1


class TestFormatMatchRange:
    """Tests for formatting match probability ranges."""

    def test_formats_as_percentage_range(self):
        """Should format as 'XX%-YY%'."""
        from core.clustering import format_match_range

        result = format_match_range((0.82, 0.91))

        assert result == "82%-91%"

    def test_handles_none(self):
        """Should handle None (singleton cluster)."""
        from core.clustering import format_match_range

        result = format_match_range(None)

        assert result == "N/A"

    def test_rounds_appropriately(self):
        """Should round to nearest integer percent."""
        from core.clustering import format_match_range

        result = format_match_range((0.825, 0.914))

        assert result == "82%-91%"
