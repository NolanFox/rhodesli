"""
Tests for mathematical integrity: undo determinism and replay proof.

These tests verify the registry produces deterministic, reversible results:
- Undo operations restore exact previous state
- Fusion math is reversible within floating-point tolerance
- Replay from events produces identical state
"""

import numpy as np
import pytest


class TestUndoDeterminism:
    """Tests for undo operation determinism."""

    def test_promote_undo_restores_exact_state(self):
        """
        CRITICAL TEST: Promote then undo should restore exact original state.

        Round-trip:
        1. Create identity with 1 anchor
        2. Record original fusion (μ, σ²)
        3. Promote 3 candidates to anchors
        4. Record intermediate fusions
        5. Undo all 3 promotions in reverse order
        6. ASSERT: final fusion == original fusion (tolerance ≤ 1e-6)
        """
        from core.fusion import compute_identity_fusion
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()

        # Create face data with distinct embeddings
        np.random.seed(42)  # Deterministic
        face_data = {}
        for i in range(4):
            mu = np.random.randn(512).astype(np.float32)
            mu = mu / np.linalg.norm(mu)  # Normalize
            sigma_sq = np.full(512, 0.1 + i * 0.01, dtype=np.float32)
            face_data[f"face_{i:03d}"] = {"mu": mu, "sigma_sq": sigma_sq}

        # Create identity with first face as anchor
        identity_id = registry.create_identity(
            anchor_ids=["face_000"],
            candidate_ids=["face_001", "face_002", "face_003"],
            user_source="test",
        )

        # Record original fusion
        original_mu, original_sigma_sq = compute_identity_fusion(
            registry, identity_id, face_data
        )

        # Promote 3 candidates
        for i in range(1, 4):
            registry.promote_candidate(identity_id, f"face_{i:03d}", "test")

        # Record post-promotion fusion
        post_mu, post_sigma_sq = compute_identity_fusion(
            registry, identity_id, face_data
        )

        # Fusion should have changed
        assert not np.allclose(original_mu, post_mu, atol=1e-6)
        assert not np.allclose(original_sigma_sq, post_sigma_sq, atol=1e-6)

        # Undo all 3 promotions in reverse order
        for _ in range(3):
            registry.undo(identity_id, "test")

        # Record final fusion
        final_mu, final_sigma_sq = compute_identity_fusion(
            registry, identity_id, face_data
        )

        # CRITICAL: final should match original exactly
        assert np.allclose(original_mu, final_mu, atol=1e-6), (
            f"μ drift detected: max diff = {np.abs(original_mu - final_mu).max()}"
        )
        assert np.allclose(original_sigma_sq, final_sigma_sq, atol=1e-6), (
            f"σ² drift detected: max diff = {np.abs(original_sigma_sq - final_sigma_sq).max()}"
        )

    def test_reject_undo_restores_exact_state(self):
        """Reject then undo should restore candidate membership (order-independent)."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()

        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            candidate_ids=["face_002", "face_003"],
            user_source="test",
        )

        # Record original state
        original = registry.get_identity(identity_id)
        original_candidates = set(original["candidate_ids"])
        original_negatives = set(original["negative_ids"])

        # Reject candidate
        registry.reject_candidate(identity_id, "face_002", "test")

        # Undo rejection
        registry.undo(identity_id, "test")

        # Verify membership restoration (order doesn't affect fusion)
        final = registry.get_identity(identity_id)
        assert set(final["candidate_ids"]) == original_candidates
        assert set(final["negative_ids"]) == original_negatives

    def test_state_change_undo_restores_previous_state(self):
        """State change then undo should restore previous state."""
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()

        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            user_source="test",
        )

        # Confirm then contest
        registry.confirm_identity(identity_id, "test")
        registry.contest_identity(identity_id, "test", reason="Disputed")

        # Undo contest
        registry.undo(identity_id, "test")

        identity = registry.get_identity(identity_id)
        assert identity["state"] == IdentityState.CONFIRMED.value

        # Undo confirm
        registry.undo(identity_id, "test")

        identity = registry.get_identity(identity_id)
        assert identity["state"] == IdentityState.PROPOSED.value


class TestReplayDeterminism:
    """Tests for replay producing identical state."""

    def test_replay_produces_identical_state(self):
        """
        Loading from events should produce identical state to live operations.
        """
        import tempfile
        from pathlib import Path

        from core.registry import IdentityRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "identities.json"

            # Create complex state
            registry1 = IdentityRegistry()
            identity_id = registry1.create_identity(
                anchor_ids=["face_001"],
                candidate_ids=["face_002", "face_003", "face_004"],
                user_source="test",
            )

            # Perform operations
            registry1.promote_candidate(identity_id, "face_002", "test")
            registry1.reject_candidate(identity_id, "face_003", "test")
            registry1.confirm_identity(identity_id, "test")
            registry1.undo(identity_id, "test")  # Undo confirm
            registry1.promote_candidate(identity_id, "face_004", "test")

            registry1.save(path)

            # Load and compare
            registry2 = IdentityRegistry.load(path)

            id1 = registry1.get_identity(identity_id)
            id2 = registry2.get_identity(identity_id)

            # All fields should match exactly
            assert id1["anchor_ids"] == id2["anchor_ids"]
            assert id1["candidate_ids"] == id2["candidate_ids"]
            assert id1["negative_ids"] == id2["negative_ids"]
            assert id1["state"] == id2["state"]
            assert id1["version_id"] == id2["version_id"]

    def test_fusion_is_deterministic_given_same_anchors(self):
        """
        Same anchor set should always produce identical fusion.
        """
        from core.fusion import fuse_anchors

        np.random.seed(123)

        # Create anchors
        anchors = []
        for i in range(3):
            mu = np.random.randn(512).astype(np.float32)
            sigma_sq = np.full(512, 0.1, dtype=np.float32)
            anchors.append({
                "mu": mu,
                "sigma_sq": sigma_sq,
                "confidence_weight": 1.0,
            })

        # Fuse multiple times
        results = []
        for _ in range(10):
            mu, sigma_sq = fuse_anchors(anchors)
            results.append((mu.copy(), sigma_sq.copy()))

        # All results should be identical
        for i in range(1, len(results)):
            assert np.array_equal(results[0][0], results[i][0])
            assert np.array_equal(results[0][1], results[i][1])


class TestFloatingPointStability:
    """Tests for floating-point stability in fusion operations."""

    def test_fusion_order_independence(self):
        """
        Fusion should produce same result regardless of anchor order.

        This tests associativity of the weighted average.
        """
        from core.fusion import fuse_anchors

        np.random.seed(456)

        anchors = []
        for i in range(5):
            mu = np.random.randn(512).astype(np.float32)
            sigma_sq = np.full(512, 0.1 + i * 0.02, dtype=np.float32)
            anchors.append({
                "mu": mu,
                "sigma_sq": sigma_sq,
                "confidence_weight": 1.0,
            })

        # Fuse in different orders
        import random

        results = []
        for _ in range(10):
            shuffled = anchors.copy()
            random.shuffle(shuffled)
            mu, sigma_sq = fuse_anchors(shuffled)
            results.append((mu, sigma_sq))

        # All results should be identical (within float32 tolerance)
        for i in range(1, len(results)):
            assert np.allclose(results[0][0], results[i][0], atol=1e-6), (
                f"Order-dependent μ: max diff = {np.abs(results[0][0] - results[i][0]).max()}"
            )
            assert np.allclose(results[0][1], results[i][1], atol=1e-6), (
                f"Order-dependent σ²: max diff = {np.abs(results[0][1] - results[i][1]).max()}"
            )

    def test_batch_fusion_is_canonical(self):
        """
        Batch fusion is the canonical form - incremental fusion is different.

        This test documents that fusing anchors all at once produces
        the authoritative result. The registry always recomputes fusion
        from the full anchor set, never incrementally.
        """
        from core.fusion import fuse_anchors

        np.random.seed(789)

        anchors = []
        for i in range(3):
            mu = np.random.randn(512).astype(np.float32)
            sigma_sq = np.full(512, 0.1, dtype=np.float32)
            anchors.append({
                "mu": mu,
                "sigma_sq": sigma_sq,
                "confidence_weight": 1.0,
            })

        # Batch fusion multiple times should be identical
        result1_mu, result1_sigma_sq = fuse_anchors(anchors)
        result2_mu, result2_sigma_sq = fuse_anchors(anchors)

        assert np.array_equal(result1_mu, result2_mu)
        assert np.array_equal(result1_sigma_sq, result2_sigma_sq)
