"""
Tests for identity-level rejection (Not Same Person feature - D1-D4).

Tests the reject_identity_pair() method which records that two identities
are definitively NOT the same person. This is a strong negative signal
stored in negative_ids with "identity:" prefix.
"""

import pytest


class TestRejectIdentityPair:
    """Tests for reject_identity_pair() method in IdentityRegistry."""

    def test_reject_adds_identity_to_negative_ids(self):
        """Rejecting identity should add identity: prefixed ID to negative_ids."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        id_a = registry.create_identity(anchor_ids=["face_a"], user_source="test")
        id_b = registry.create_identity(anchor_ids=["face_b"], user_source="test")

        registry.reject_identity_pair(id_a, id_b, user_source="web")

        identity_a = registry.get_identity(id_a)
        assert f"identity:{id_b}" in identity_a["negative_ids"]

    def test_reject_is_bidirectional(self):
        """Rejection should be stored in both identities (A rejects B, B rejects A)."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        id_a = registry.create_identity(anchor_ids=["face_a"], user_source="test")
        id_b = registry.create_identity(anchor_ids=["face_b"], user_source="test")

        registry.reject_identity_pair(id_a, id_b, user_source="web")

        identity_a = registry.get_identity(id_a)
        identity_b = registry.get_identity(id_b)
        assert f"identity:{id_b}" in identity_a["negative_ids"]
        assert f"identity:{id_a}" in identity_b["negative_ids"]

    def test_reject_records_event(self):
        """Rejection should record event with REJECT action and metadata."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        id_a = registry.create_identity(anchor_ids=["face_a"], user_source="test")
        id_b = registry.create_identity(anchor_ids=["face_b"], user_source="test")

        registry.reject_identity_pair(id_a, id_b, user_source="web")

        history_a = registry.get_history(id_a)
        reject_events = [e for e in history_a if e["action"] == "reject"]
        assert len(reject_events) == 1
        assert reject_events[0]["metadata"]["rejected_identity_id"] == id_b
        assert reject_events[0]["metadata"]["type"] == "identity_pair"

    def test_reject_increments_version(self):
        """Rejection should increment version_id for both identities."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        id_a = registry.create_identity(anchor_ids=["face_a"], user_source="test")
        id_b = registry.create_identity(anchor_ids=["face_b"], user_source="test")

        version_a_before = registry.get_identity(id_a)["version_id"]
        version_b_before = registry.get_identity(id_b)["version_id"]

        registry.reject_identity_pair(id_a, id_b, user_source="web")

        version_a_after = registry.get_identity(id_a)["version_id"]
        version_b_after = registry.get_identity(id_b)["version_id"]

        assert version_a_after == version_a_before + 1
        assert version_b_after == version_b_before + 1

    def test_reject_idempotent(self):
        """Rejecting the same pair twice should not duplicate entries."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        id_a = registry.create_identity(anchor_ids=["face_a"], user_source="test")
        id_b = registry.create_identity(anchor_ids=["face_b"], user_source="test")

        registry.reject_identity_pair(id_a, id_b, user_source="web")
        registry.reject_identity_pair(id_a, id_b, user_source="web")

        identity_a = registry.get_identity(id_a)
        # Should only appear once
        count = identity_a["negative_ids"].count(f"identity:{id_b}")
        assert count == 1

    def test_reject_unknown_identity_raises(self):
        """Rejecting unknown identity should raise KeyError."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        id_a = registry.create_identity(anchor_ids=["face_a"], user_source="test")

        with pytest.raises(KeyError):
            registry.reject_identity_pair(id_a, "unknown-id", user_source="web")


class TestIsIdentityRejected:
    """Tests for is_identity_rejected() helper method."""

    def test_returns_true_for_rejected_pair(self):
        """Should return True for identities that have been rejected."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        id_a = registry.create_identity(anchor_ids=["face_a"], user_source="test")
        id_b = registry.create_identity(anchor_ids=["face_b"], user_source="test")

        registry.reject_identity_pair(id_a, id_b, user_source="web")

        assert registry.is_identity_rejected(id_a, id_b) is True

    def test_returns_true_symmetric(self):
        """Should return True regardless of argument order (A,B or B,A)."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        id_a = registry.create_identity(anchor_ids=["face_a"], user_source="test")
        id_b = registry.create_identity(anchor_ids=["face_b"], user_source="test")

        registry.reject_identity_pair(id_a, id_b, user_source="web")

        assert registry.is_identity_rejected(id_a, id_b) is True
        assert registry.is_identity_rejected(id_b, id_a) is True

    def test_returns_false_for_non_rejected_pair(self):
        """Should return False for identities that have NOT been rejected."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        id_a = registry.create_identity(anchor_ids=["face_a"], user_source="test")
        id_b = registry.create_identity(anchor_ids=["face_b"], user_source="test")
        id_c = registry.create_identity(anchor_ids=["face_c"], user_source="test")

        registry.reject_identity_pair(id_a, id_b, user_source="web")

        assert registry.is_identity_rejected(id_a, id_c) is False
        assert registry.is_identity_rejected(id_b, id_c) is False

    def test_returns_false_for_unknown_identity(self):
        """Should return False when checking unknown identity."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        id_a = registry.create_identity(anchor_ids=["face_a"], user_source="test")

        assert registry.is_identity_rejected(id_a, "unknown-id") is False
        assert registry.is_identity_rejected("unknown-id", id_a) is False
