"""
Tests for the Face Detach functionality.

Detach allows splitting a face from an identity into a new identity.
This is the reverse of merge - useful for correcting errors.
"""

import pytest


class TestDetachFace:
    """Tests for detaching faces from identities."""

    def test_detach_creates_new_identity(self):
        """Detaching a face should create a new identity with that face."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_a", "face_b"],
            name="Test Person",
            user_source="manual",
        )

        result = registry.detach_face(
            identity_id=identity_id,
            face_id="face_b",
            user_source="manual",
        )

        assert result["success"] is True
        assert "to_identity_id" in result
        assert result["to_identity_id"] != identity_id

        # New identity should exist with the detached face
        new_identity = registry.get_identity(result["to_identity_id"])
        assert "face_b" in registry.get_anchor_face_ids(result["to_identity_id"])

    def test_source_identity_updated(self):
        """Detaching a face should remove it from the source identity."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_a", "face_b"],
            name="Test Person",
            user_source="manual",
        )

        registry.detach_face(
            identity_id=identity_id,
            face_id="face_b",
            user_source="manual",
        )

        # Source identity should only have face_a
        anchor_ids = registry.get_anchor_face_ids(identity_id)
        assert "face_a" in anchor_ids
        assert "face_b" not in anchor_ids

    def test_detach_only_face_fails(self):
        """Cannot detach the only face from an identity."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_a"],
            name="Solo Person",
            user_source="manual",
        )

        result = registry.detach_face(
            identity_id=identity_id,
            face_id="face_a",
            user_source="manual",
        )

        assert result["success"] is False
        assert result["reason"] == "only_face"

    def test_detach_nonexistent_face_fails(self):
        """Cannot detach a face that doesn't exist in the identity."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_a", "face_b"],
            user_source="manual",
        )

        result = registry.detach_face(
            identity_id=identity_id,
            face_id="face_nonexistent",
            user_source="manual",
        )

        assert result["success"] is False
        assert result["reason"] == "face_not_found"

    def test_detach_records_event(self):
        """Detach should record an event in history."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_a", "face_b"],
            user_source="manual",
        )

        result = registry.detach_face(
            identity_id=identity_id,
            face_id="face_b",
            user_source="manual",
        )

        # Source identity should have detach event
        history = registry.get_history(identity_id)
        detach_events = [e for e in history if e["action"] == "detach"]
        assert len(detach_events) == 1
        assert detach_events[0]["metadata"]["to_identity_id"] == result["to_identity_id"]

    def test_detach_increments_version(self):
        """Detach should increment the source identity's version."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_a", "face_b"],
            user_source="manual",
        )

        initial_version = registry.get_identity(identity_id)["version_id"]

        registry.detach_face(
            identity_id=identity_id,
            face_id="face_b",
            user_source="manual",
        )

        new_version = registry.get_identity(identity_id)["version_id"]
        assert new_version == initial_version + 1

    def test_detached_identity_is_proposed(self):
        """New identity from detach should be in PROPOSED state."""
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_a", "face_b"],
            user_source="manual",
        )

        result = registry.detach_face(
            identity_id=identity_id,
            face_id="face_b",
            user_source="manual",
        )

        new_identity = registry.get_identity(result["to_identity_id"])
        assert new_identity["state"] == IdentityState.PROPOSED.value

    def test_detach_works_with_dict_anchors(self):
        """Detach should work when anchors are dicts (structured format)."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_a"],
            candidate_ids=["face_b"],
            user_source="manual",
        )
        # Promote to get dict format anchor
        registry.promote_candidate(identity_id, "face_b", "manual", confidence_weight=0.8)

        result = registry.detach_face(
            identity_id=identity_id,
            face_id="face_b",
            user_source="manual",
        )

        assert result["success"] is True
        # Source should only have face_a
        assert registry.get_anchor_face_ids(identity_id) == ["face_a"]
        # New identity should have face_b
        assert "face_b" in registry.get_anchor_face_ids(result["to_identity_id"])


class TestDetachUX:
    """Detach button uses non-alarming styling and explains reversibility."""

    def test_detach_button_not_red(self):
        """Detach button should use neutral styling, not red (detach is non-destructive)."""
        from fasthtml.common import to_xml
        from app.main import face_card

        card = face_card("face_a", "/static/crops/test.jpg", quality=0.5, show_detach=True)
        html = to_xml(card)

        # Should have Detach button
        assert "Detach" in html
        # Should NOT use red styling (detach is non-destructive)
        assert "text-red-400" not in html
        # Should use neutral slate color
        assert "text-slate-400" in html

    def test_detach_confirm_explains_reversibility(self):
        """Detach confirmation should explain you can merge back."""
        from fasthtml.common import to_xml
        from app.main import face_card

        card = face_card("face_a", "/static/crops/test.jpg", quality=0.5, show_detach=True)
        html = to_xml(card)

        assert "merge it back" in html.lower()
