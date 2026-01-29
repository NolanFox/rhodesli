"""
Tests for Bayesian PFE fusion and variance guardrails.

These tests verify the fusion math and safety mechanisms as documented in
docs/adr_004_identity_registry.md.
"""

import numpy as np
import pytest


class TestBayesianFusion:
    """Tests for Bayesian-inspired PFE fusion."""

    def test_fuse_single_anchor_returns_same(self):
        """Fusing a single anchor should return its μ and σ²."""
        from core.fusion import fuse_anchors

        mu = np.random.randn(512).astype(np.float32)
        sigma_sq = np.full(512, 0.1, dtype=np.float32)

        anchors = [{"mu": mu, "sigma_sq": sigma_sq, "confidence_weight": 1.0}]

        fused_mu, fused_sigma_sq = fuse_anchors(anchors)

        assert np.allclose(fused_mu, mu)
        assert np.allclose(fused_sigma_sq, sigma_sq)

    def test_fuse_identical_anchors_reduces_variance(self):
        """Fusing identical anchors should reduce variance."""
        from core.fusion import fuse_anchors

        mu = np.random.randn(512).astype(np.float32)
        sigma_sq = np.full(512, 0.1, dtype=np.float32)

        anchors = [
            {"mu": mu.copy(), "sigma_sq": sigma_sq.copy(), "confidence_weight": 1.0},
            {"mu": mu.copy(), "sigma_sq": sigma_sq.copy(), "confidence_weight": 1.0},
        ]

        fused_mu, fused_sigma_sq = fuse_anchors(anchors)

        # Variance should decrease with more identical observations
        # For n identical observations: fused_σ² = σ² / n
        expected_sigma_sq = sigma_sq / 2
        assert np.allclose(fused_sigma_sq, expected_sigma_sq)

    def test_fuse_uses_inverse_variance_weighting(self):
        """Lower variance anchors should contribute more to fused μ."""
        from core.fusion import fuse_anchors

        # Two different μ values with different variances
        mu1 = np.ones(512, dtype=np.float32)
        mu2 = np.zeros(512, dtype=np.float32)

        # Low variance (high confidence) for mu1
        sigma_sq1 = np.full(512, 0.01, dtype=np.float32)
        # High variance (low confidence) for mu2
        sigma_sq2 = np.full(512, 1.0, dtype=np.float32)

        anchors = [
            {"mu": mu1, "sigma_sq": sigma_sq1, "confidence_weight": 1.0},
            {"mu": mu2, "sigma_sq": sigma_sq2, "confidence_weight": 1.0},
        ]

        fused_mu, _ = fuse_anchors(anchors)

        # fused_mu should be closer to mu1 (lower variance)
        dist_to_mu1 = np.linalg.norm(fused_mu - mu1)
        dist_to_mu2 = np.linalg.norm(fused_mu - mu2)

        assert dist_to_mu1 < dist_to_mu2

    def test_fuse_respects_confidence_weight(self):
        """Confidence weight should scale inverse variance."""
        from core.fusion import fuse_anchors

        mu1 = np.ones(512, dtype=np.float32)
        mu2 = np.zeros(512, dtype=np.float32)
        sigma_sq = np.full(512, 0.1, dtype=np.float32)

        # Equal variance, but mu2 has higher confidence weight
        anchors = [
            {"mu": mu1, "sigma_sq": sigma_sq.copy(), "confidence_weight": 1.0},
            {"mu": mu2, "sigma_sq": sigma_sq.copy(), "confidence_weight": 10.0},
        ]

        fused_mu, _ = fuse_anchors(anchors)

        # fused_mu should be closer to mu2 (higher confidence weight)
        dist_to_mu1 = np.linalg.norm(fused_mu - mu1)
        dist_to_mu2 = np.linalg.norm(fused_mu - mu2)

        assert dist_to_mu2 < dist_to_mu1

    def test_fuse_multiple_weak_creates_stronger(self):
        """
        CRITICAL TEST: Multiple weak photos should fuse into a stronger anchor.

        This is the core value proposition of Bayesian fusion.
        """
        from core.fusion import fuse_anchors

        # 5 similar but noisy observations
        base_mu = np.random.randn(512).astype(np.float32)
        base_mu = base_mu / np.linalg.norm(base_mu)

        anchors = []
        for _ in range(5):
            # Each observation has noise and high variance
            noisy_mu = base_mu + np.random.randn(512).astype(np.float32) * 0.05
            noisy_mu = noisy_mu / np.linalg.norm(noisy_mu)
            sigma_sq = np.full(512, 0.5, dtype=np.float32)  # High uncertainty
            anchors.append({
                "mu": noisy_mu,
                "sigma_sq": sigma_sq,
                "confidence_weight": 1.0,
            })

        fused_mu, fused_sigma_sq = fuse_anchors(anchors)

        # Fused variance should be much lower than individual variances
        individual_var = anchors[0]["sigma_sq"][0]
        fused_var = fused_sigma_sq[0]

        assert fused_var < individual_var / 3, (
            f"Fused variance {fused_var} should be < {individual_var / 3}"
        )

    def test_fuse_empty_raises_error(self):
        """Fusing empty anchor list should raise error."""
        from core.fusion import fuse_anchors

        with pytest.raises(ValueError, match="No anchors"):
            fuse_anchors([])


class TestVarianceExplosionGuardrail:
    """Tests for the variance explosion guardrail."""

    def test_check_variance_explosion_passes_for_similar(self):
        """Similar faces should pass the variance check."""
        from core.fusion import check_variance_explosion

        mu1 = np.random.randn(512).astype(np.float32)
        mu1 = mu1 / np.linalg.norm(mu1)
        mu2 = mu1 + np.random.randn(512).astype(np.float32) * 0.01  # Very similar
        mu2 = mu2 / np.linalg.norm(mu2)

        sigma_sq = np.full(512, 0.1, dtype=np.float32)

        anchors = [
            {"mu": mu1, "sigma_sq": sigma_sq.copy(), "confidence_weight": 1.0},
            {"mu": mu2, "sigma_sq": sigma_sq.copy(), "confidence_weight": 1.0},
        ]

        result = check_variance_explosion(anchors)

        assert result["safe"] is True

    def test_check_variance_explosion_fails_for_dissimilar(self):
        """
        CRITICAL TEST: Dissimilar faces should trigger variance explosion.

        This prevents merging faces that don't belong together.
        """
        from core.fusion import check_variance_explosion

        # Two completely different embeddings
        mu1 = np.random.randn(512).astype(np.float32)
        mu1 = mu1 / np.linalg.norm(mu1)
        mu2 = -mu1  # Anti-correlated (maximally different)

        sigma_sq = np.full(512, 0.1, dtype=np.float32)

        anchors = [
            {"mu": mu1, "sigma_sq": sigma_sq.copy(), "confidence_weight": 1.0},
            {"mu": mu2, "sigma_sq": sigma_sq.copy(), "confidence_weight": 1.0},
        ]

        result = check_variance_explosion(anchors, k=1.5)

        assert result["safe"] is False
        assert "fused_sigma_mean" in result
        assert "max_input_sigma" in result

    def test_variance_explosion_uses_k_threshold(self):
        """Threshold K should control explosion detection."""
        from core.fusion import check_variance_explosion

        mu1 = np.random.randn(512).astype(np.float32)
        mu1 = mu1 / np.linalg.norm(mu1)  # Normalize like other tests
        mu2 = np.random.randn(512).astype(np.float32)
        mu2 = mu2 / np.linalg.norm(mu2)  # Normalize like other tests
        sigma_sq = np.full(512, 0.1, dtype=np.float32)

        anchors = [
            {"mu": mu1, "sigma_sq": sigma_sq.copy(), "confidence_weight": 1.0},
            {"mu": mu2, "sigma_sq": sigma_sq.copy(), "confidence_weight": 1.0},
        ]

        # Very permissive K should pass
        result_permissive = check_variance_explosion(anchors, k=100.0)
        assert result_permissive["safe"] is True

        # Very strict K should fail for any difference
        result_strict = check_variance_explosion(anchors, k=0.1)
        assert result_strict["safe"] is False


class TestFusionIgnoresNonAnchors:
    """Tests that fusion ignores candidates and negative_ids."""

    def test_fusion_uses_only_anchor_ids(self):
        """Fusion should only use faces in anchor_ids."""
        from core.fusion import compute_identity_fusion
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            candidate_ids=["face_002"],
            user_source="manual",
        )

        # Mock face data
        face_data = {
            "face_001": {
                "mu": np.ones(512, dtype=np.float32),
                "sigma_sq": np.full(512, 0.1, dtype=np.float32),
            },
            "face_002": {
                "mu": np.zeros(512, dtype=np.float32),  # Different!
                "sigma_sq": np.full(512, 0.1, dtype=np.float32),
            },
        }

        fused_mu, fused_sigma_sq = compute_identity_fusion(
            registry, identity_id, face_data
        )

        # Should match face_001 only
        assert np.allclose(fused_mu, face_data["face_001"]["mu"])

    def test_rejected_faces_do_not_poison_anchors(self):
        """
        CRITICAL TEST: Rejected faces must not affect anchor fusion.
        """
        from core.fusion import compute_identity_fusion
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001", "face_002"],
            candidate_ids=["face_003"],
            user_source="manual",
        )

        # Reject face_003
        registry.reject_candidate(identity_id, "face_003", "manual")

        # Mock face data - face_003 is very different
        base_mu = np.ones(512, dtype=np.float32)
        face_data = {
            "face_001": {
                "mu": base_mu.copy(),
                "sigma_sq": np.full(512, 0.1, dtype=np.float32),
            },
            "face_002": {
                "mu": base_mu.copy(),
                "sigma_sq": np.full(512, 0.1, dtype=np.float32),
            },
            "face_003": {
                "mu": -base_mu,  # Opposite direction - would poison if included
                "sigma_sq": np.full(512, 0.1, dtype=np.float32),
            },
        }

        fused_mu, _ = compute_identity_fusion(registry, identity_id, face_data)

        # Fused should be close to base_mu, not affected by face_003
        assert np.allclose(fused_mu, base_mu, atol=0.01)


class TestSafePromote:
    """Tests for safe promotion with variance check."""

    def test_safe_promote_succeeds_for_similar(self):
        """Promoting a similar face should succeed."""
        from core.fusion import safe_promote_candidate
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            candidate_ids=["face_002"],
            user_source="manual",
        )

        mu = np.random.randn(512).astype(np.float32)
        mu = mu / np.linalg.norm(mu)

        face_data = {
            "face_001": {
                "mu": mu.copy(),
                "sigma_sq": np.full(512, 0.1, dtype=np.float32),
            },
            "face_002": {
                "mu": mu + np.random.randn(512).astype(np.float32) * 0.01,
                "sigma_sq": np.full(512, 0.1, dtype=np.float32),
            },
        }

        result = safe_promote_candidate(
            registry, identity_id, "face_002", face_data, "manual"
        )

        assert result["success"] is True
        assert "face_002" in registry.get_identity(identity_id)["anchor_ids"]

    def test_safe_promote_rejects_dissimilar(self):
        """Promoting a dissimilar face should fail and mark CONTESTED."""
        from core.fusion import safe_promote_candidate
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            candidate_ids=["face_002"],
            user_source="manual",
        )

        face_data = {
            "face_001": {
                "mu": np.ones(512, dtype=np.float32),
                "sigma_sq": np.full(512, 0.1, dtype=np.float32),
            },
            "face_002": {
                "mu": -np.ones(512, dtype=np.float32),  # Opposite!
                "sigma_sq": np.full(512, 0.1, dtype=np.float32),
            },
        }

        result = safe_promote_candidate(
            registry, identity_id, "face_002", face_data, "manual"
        )

        assert result["success"] is False
        assert result["reason"] == "variance_explosion"

        # Identity should be marked CONTESTED
        identity = registry.get_identity(identity_id)
        assert identity["state"] == IdentityState.CONTESTED.value

        # face_002 should NOT be in anchors
        assert "face_002" not in identity["anchor_ids"]
        assert "face_002" in identity["candidate_ids"]


class TestReEvaluation:
    """Tests for re-evaluation when anchors change."""

    def test_anchor_change_flags_reevaluation(self):
        """Significant anchor change should flag for re-evaluation."""
        from core.fusion import should_reevaluate_rejections

        # Before: high variance
        old_sigma_sq = np.full(512, 0.5, dtype=np.float32)

        # After: much lower variance (shrunk by >10%)
        new_sigma_sq = np.full(512, 0.1, dtype=np.float32)

        result = should_reevaluate_rejections(old_sigma_sq, new_sigma_sq)

        assert result is True

    def test_minor_change_no_reevaluation(self):
        """Minor anchor change should not flag for re-evaluation."""
        from core.fusion import should_reevaluate_rejections

        old_sigma_sq = np.full(512, 0.5, dtype=np.float32)
        new_sigma_sq = np.full(512, 0.48, dtype=np.float32)  # Only 4% change

        result = should_reevaluate_rejections(old_sigma_sq, new_sigma_sq)

        assert result is False

    def test_reevaluation_does_not_auto_merge(self):
        """Re-evaluation should surface candidates but NOT auto-merge."""
        from core.fusion import get_reevaluation_candidates
        from core.registry import IdentityRegistry
        from core.temporal import EraEstimate

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            candidate_ids=[],
            user_source="manual",
        )

        # Reject a face
        registry._identities[identity_id]["negative_ids"] = ["face_002"]

        mu = np.random.randn(512).astype(np.float32)
        mu = mu / np.linalg.norm(mu)

        era = EraEstimate(
            era="1910-1930",
            probabilities={"1890-1910": 0.0, "1910-1930": 1.0, "1930-1950": 0.0},
            confidence=1.0,
        )

        face_data = {
            "face_001": {
                "mu": mu.copy(),
                "sigma_sq": np.full(512, 0.1, dtype=np.float32),
                "era": era,
            },
            "face_002": {
                "mu": mu + np.random.randn(512).astype(np.float32) * 0.01,
                "sigma_sq": np.full(512, 0.1, dtype=np.float32),
                "era": era,
            },
        }

        candidates = get_reevaluation_candidates(
            registry, identity_id, face_data
        )

        # Should surface face_002 as a candidate for review
        assert len(candidates) > 0

        # But it should still be in negative_ids, not auto-merged
        identity = registry.get_identity(identity_id)
        assert "face_002" in identity["negative_ids"]
        assert "face_002" not in identity["anchor_ids"]
