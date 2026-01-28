"""
Tests for the Identity Registry.

These tests verify the registry behavior as documented in
docs/adr_004_identity_registry.md.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest


class TestIdentityCreation:
    """Tests for creating identities."""

    def test_create_identity_returns_identity_id(self):
        """Creating an identity should return an identity_id."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            name="Test Person",
            user_source="manual",
        )

        assert identity_id is not None
        assert isinstance(identity_id, str)
        assert len(identity_id) > 0

    def test_create_identity_sets_proposed_state(self):
        """New identities should start in PROPOSED state."""
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            user_source="manual",
        )

        identity = registry.get_identity(identity_id)
        assert identity["state"] == IdentityState.PROPOSED.value

    def test_create_identity_initializes_version(self):
        """New identities should have version_id = 1."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            user_source="manual",
        )

        identity = registry.get_identity(identity_id)
        assert identity["version_id"] == 1

    def test_create_identity_records_event(self):
        """Creating an identity should record a 'create' event."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            user_source="manual",
        )

        history = registry.get_history(identity_id)
        assert len(history) == 1
        assert history[0]["action"] == "create"
        assert history[0]["face_ids"] == ["face_001"]
        assert history[0]["user_source"] == "manual"


class TestIdentityState:
    """Tests for identity state transitions."""

    def test_confirm_identity_changes_state(self):
        """Confirming an identity should change state to CONFIRMED."""
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            user_source="manual",
        )

        registry.confirm_identity(identity_id, user_source="manual")

        identity = registry.get_identity(identity_id)
        assert identity["state"] == IdentityState.CONFIRMED.value

    def test_confirm_increments_version(self):
        """Confirming should increment version_id."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            user_source="manual",
        )

        registry.confirm_identity(identity_id, user_source="manual")

        identity = registry.get_identity(identity_id)
        assert identity["version_id"] == 2

    def test_contest_identity_changes_state(self):
        """Contesting an identity should change state to CONTESTED."""
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            user_source="manual",
        )
        registry.confirm_identity(identity_id, user_source="manual")

        registry.contest_identity(identity_id, user_source="manual", reason="Disputed")

        identity = registry.get_identity(identity_id)
        assert identity["state"] == IdentityState.CONTESTED.value

    def test_state_change_records_event(self):
        """State changes should be recorded in history."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            user_source="manual",
        )
        registry.confirm_identity(identity_id, user_source="manual")

        history = registry.get_history(identity_id)
        assert len(history) == 2
        assert history[1]["action"] == "state_change"


class TestAnchorManagement:
    """Tests for managing anchor faces."""

    def test_promote_candidate_moves_to_anchors(self):
        """Promoting a candidate should move it to anchor_ids."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            candidate_ids=["face_002"],
            user_source="manual",
        )

        registry.promote_candidate(
            identity_id,
            face_id="face_002",
            user_source="manual",
            confidence_weight=1.0,
        )

        identity = registry.get_identity(identity_id)
        assert "face_002" in identity["anchor_ids"]
        assert "face_002" not in identity["candidate_ids"]

    def test_promote_increments_version(self):
        """Promoting should increment version_id."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            candidate_ids=["face_002"],
            user_source="manual",
        )

        registry.promote_candidate(
            identity_id,
            face_id="face_002",
            user_source="manual",
        )

        identity = registry.get_identity(identity_id)
        assert identity["version_id"] == 2

    def test_promote_records_event_with_weight(self):
        """Promote should record event with confidence_weight."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            candidate_ids=["face_002"],
            user_source="manual",
        )

        registry.promote_candidate(
            identity_id,
            face_id="face_002",
            user_source="manual",
            confidence_weight=0.8,
        )

        history = registry.get_history(identity_id)
        promote_event = [e for e in history if e["action"] == "promote"][0]
        assert promote_event["confidence_weight"] == 0.8


class TestNegativeEvidence:
    """Tests for negative evidence handling."""

    def test_reject_candidate_moves_to_negative(self):
        """Rejecting a candidate should move it to negative_ids."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            candidate_ids=["face_002"],
            user_source="manual",
        )

        registry.reject_candidate(
            identity_id,
            face_id="face_002",
            user_source="manual",
        )

        identity = registry.get_identity(identity_id)
        assert "face_002" in identity["negative_ids"]
        assert "face_002" not in identity["candidate_ids"]

    def test_reject_does_not_affect_anchors(self):
        """Rejecting should not affect anchor_ids."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            candidate_ids=["face_002"],
            user_source="manual",
        )

        registry.reject_candidate(
            identity_id,
            face_id="face_002",
            user_source="manual",
        )

        identity = registry.get_identity(identity_id)
        assert identity["anchor_ids"] == ["face_001"]


class TestUndo:
    """Tests for undo functionality."""

    def test_undo_promote_restores_candidate(self):
        """Undoing a promote should restore face to candidates."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            candidate_ids=["face_002"],
            user_source="manual",
        )

        registry.promote_candidate(
            identity_id,
            face_id="face_002",
            user_source="manual",
        )

        # Undo the promote
        registry.undo(identity_id, user_source="manual")

        identity = registry.get_identity(identity_id)
        assert "face_002" not in identity["anchor_ids"]
        assert "face_002" in identity["candidate_ids"]

    def test_undo_reject_restores_candidate(self):
        """Undoing a reject should restore face to candidates."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            candidate_ids=["face_002"],
            user_source="manual",
        )

        registry.reject_candidate(
            identity_id,
            face_id="face_002",
            user_source="manual",
        )

        # Undo the reject
        registry.undo(identity_id, user_source="manual")

        identity = registry.get_identity(identity_id)
        assert "face_002" not in identity["negative_ids"]
        assert "face_002" in identity["candidate_ids"]

    def test_undo_records_event(self):
        """Undo should record an event."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            candidate_ids=["face_002"],
            user_source="manual",
        )
        registry.promote_candidate(
            identity_id,
            face_id="face_002",
            user_source="manual",
        )

        registry.undo(identity_id, user_source="manual")

        history = registry.get_history(identity_id)
        assert history[-1]["action"] == "undo"


class TestPersistence:
    """Tests for saving and loading registry."""

    def test_save_creates_json_file(self):
        """Saving should create a JSON file."""
        from core.registry import IdentityRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "identities.json"
            registry = IdentityRegistry()
            registry.create_identity(
                anchor_ids=["face_001"],
                user_source="manual",
            )

            registry.save(path)

            assert path.exists()
            with open(path) as f:
                data = json.load(f)
            assert "identities" in data
            assert "history" in data
            assert "schema_version" in data

    def test_load_restores_identities(self):
        """Loading should restore saved identities."""
        from core.registry import IdentityRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "identities.json"

            # Save
            registry1 = IdentityRegistry()
            identity_id = registry1.create_identity(
                anchor_ids=["face_001"],
                name="Test Person",
                user_source="manual",
            )
            registry1.save(path)

            # Load
            registry2 = IdentityRegistry.load(path)

            identity = registry2.get_identity(identity_id)
            assert identity["name"] == "Test Person"
            assert identity["anchor_ids"] == ["face_001"]

    def test_load_restores_history(self):
        """Loading should restore event history."""
        from core.registry import IdentityRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "identities.json"

            # Save with events
            registry1 = IdentityRegistry()
            identity_id = registry1.create_identity(
                anchor_ids=["face_001"],
                candidate_ids=["face_002"],
                user_source="manual",
            )
            registry1.promote_candidate(
                identity_id,
                face_id="face_002",
                user_source="manual",
            )
            registry1.save(path)

            # Load
            registry2 = IdentityRegistry.load(path)

            history = registry2.get_history(identity_id)
            assert len(history) == 2


class TestReplay:
    """Tests for deterministic replay from events."""

    def test_replay_reconstructs_state(self):
        """Replaying events should reconstruct identity state."""
        from core.registry import IdentityRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "identities.json"

            # Create complex state
            registry1 = IdentityRegistry()
            identity_id = registry1.create_identity(
                anchor_ids=["face_001"],
                candidate_ids=["face_002", "face_003"],
                user_source="manual",
            )
            registry1.promote_candidate(identity_id, "face_002", "manual")
            registry1.reject_candidate(identity_id, "face_003", "manual")
            registry1.confirm_identity(identity_id, "manual")
            registry1.save(path)

            # Load and verify state matches
            registry2 = IdentityRegistry.load(path)
            identity = registry2.get_identity(identity_id)

            assert identity["anchor_ids"] == ["face_001", "face_002"]
            assert identity["candidate_ids"] == []
            assert identity["negative_ids"] == ["face_003"]
            assert identity["state"] == "CONFIRMED"
            assert identity["version_id"] == 4

    def test_replay_is_deterministic(self):
        """Replaying the same events should produce identical state."""
        from core.registry import IdentityRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "identities.json"

            # Create state
            registry1 = IdentityRegistry()
            identity_id = registry1.create_identity(
                anchor_ids=["face_001"],
                candidate_ids=["face_002"],
                user_source="manual",
            )
            registry1.promote_candidate(identity_id, "face_002", "manual")
            registry1.save(path)

            # Load twice
            registry2 = IdentityRegistry.load(path)
            registry3 = IdentityRegistry.load(path)

            # Compare states
            id2 = registry2.get_identity(identity_id)
            id3 = registry3.get_identity(identity_id)

            assert id2 == id3


class TestVersioning:
    """Tests for version tracking."""

    def test_version_increments_on_each_change(self):
        """Version should increment on each material change."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            candidate_ids=["face_002", "face_003"],
            user_source="manual",
        )

        assert registry.get_identity(identity_id)["version_id"] == 1

        registry.promote_candidate(identity_id, "face_002", "manual")
        assert registry.get_identity(identity_id)["version_id"] == 2

        registry.reject_candidate(identity_id, "face_003", "manual")
        assert registry.get_identity(identity_id)["version_id"] == 3

        registry.confirm_identity(identity_id, "manual")
        assert registry.get_identity(identity_id)["version_id"] == 4

    def test_event_records_previous_version(self):
        """Events should record previous_version_id."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            candidate_ids=["face_002"],
            user_source="manual",
        )
        registry.promote_candidate(identity_id, "face_002", "manual")

        history = registry.get_history(identity_id)
        assert history[0]["previous_version_id"] == 0  # create
        assert history[1]["previous_version_id"] == 1  # promote


class TestListOperations:
    """Tests for listing and querying identities."""

    def test_list_all_identities(self):
        """Should list all identities."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        id1 = registry.create_identity(anchor_ids=["face_001"], user_source="manual")
        id2 = registry.create_identity(anchor_ids=["face_002"], user_source="manual")

        identities = registry.list_identities()

        assert len(identities) == 2
        assert id1 in [i["identity_id"] for i in identities]
        assert id2 in [i["identity_id"] for i in identities]

    def test_list_by_state(self):
        """Should filter identities by state."""
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()
        id1 = registry.create_identity(anchor_ids=["face_001"], user_source="manual")
        id2 = registry.create_identity(anchor_ids=["face_002"], user_source="manual")
        registry.confirm_identity(id1, "manual")

        proposed = registry.list_identities(state=IdentityState.PROPOSED)
        confirmed = registry.list_identities(state=IdentityState.CONFIRMED)

        assert len(proposed) == 1
        assert len(confirmed) == 1
        assert proposed[0]["identity_id"] == id2
        assert confirmed[0]["identity_id"] == id1
