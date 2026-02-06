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
        assert "face_002" in registry.get_anchor_face_ids(identity_id)
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
        assert registry.get_anchor_face_ids(identity_id) == ["face_001"]


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
        assert "face_002" not in registry.get_anchor_face_ids(identity_id)
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

            assert registry2.get_anchor_face_ids(identity_id) == ["face_001", "face_002"]
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


class TestInboxState:
    """Tests for INBOX state and provenance support."""

    def test_create_identity_with_inbox_state(self):
        """Creating an identity with state=INBOX should honor that state."""
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            user_source="ingest_pipeline",
            state=IdentityState.INBOX,
        )

        identity = registry.get_identity(identity_id)
        assert identity["state"] == IdentityState.INBOX.value

    def test_provenance_stored_on_create(self):
        """Provenance dict should be stored when provided."""
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()
        provenance = {
            "source": "inbox_ingest",
            "job_id": "abc123",
            "filename": "photo.jpg",
        }
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            user_source="ingest_pipeline",
            state=IdentityState.INBOX,
            provenance=provenance,
        )

        identity = registry.get_identity(identity_id)
        assert identity["provenance"] == provenance

    def test_move_inbox_to_proposed(self):
        """move_to_proposed should transition INBOX -> PROPOSED."""
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            user_source="ingest_pipeline",
            state=IdentityState.INBOX,
        )

        registry.move_to_proposed(identity_id, user_source="ui_review")

        identity = registry.get_identity(identity_id)
        assert identity["state"] == IdentityState.PROPOSED.value
        assert identity["version_id"] == 2

    def test_list_inbox_identities(self):
        """list_identities(state=INBOX) should return only inbox identities."""
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()
        inbox_id = registry.create_identity(
            anchor_ids=["face_001"],
            user_source="ingest_pipeline",
            state=IdentityState.INBOX,
        )
        proposed_id = registry.create_identity(
            anchor_ids=["face_002"],
            user_source="manual",
        )

        inbox_list = registry.list_identities(state=IdentityState.INBOX)
        proposed_list = registry.list_identities(state=IdentityState.PROPOSED)

        assert len(inbox_list) == 1
        assert inbox_list[0]["identity_id"] == inbox_id
        assert len(proposed_list) == 1
        assert proposed_list[0]["identity_id"] == proposed_id


class TestGetCandidateFaceIds:
    """Tests for get_candidate_face_ids() method (B2 thumbnail support)."""

    def test_returns_candidate_ids_as_strings(self):
        """Should return list of face ID strings from candidate_ids."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            candidate_ids=["face_002", "face_003"],
            user_source="test",
        )

        candidates = registry.get_candidate_face_ids(identity_id)
        assert candidates == ["face_002", "face_003"]

    def test_returns_empty_list_when_no_candidates(self):
        """Should return empty list when identity has no candidates."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            user_source="test",
        )

        candidates = registry.get_candidate_face_ids(identity_id)
        assert candidates == []

    def test_raises_keyerror_for_unknown_identity(self):
        """Should raise KeyError for unknown identity."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()

        with pytest.raises(KeyError):
            registry.get_candidate_face_ids("unknown-id")


class TestSearchIdentities:
    """Tests for search_identities() method (manual search support)."""

    def test_case_insensitive_match(self):
        """Search should match names case-insensitively."""
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            name="John Smith",
            user_source="test",
        )
        registry.confirm_identity(identity_id, user_source="test")

        # Should match regardless of case
        results = registry.search_identities("john")
        assert len(results) == 1
        assert results[0]["identity_id"] == identity_id

        results = registry.search_identities("JOHN")
        assert len(results) == 1
        assert results[0]["identity_id"] == identity_id

        results = registry.search_identities("JoHn")
        assert len(results) == 1
        assert results[0]["identity_id"] == identity_id

    def test_confirmed_only_filtering(self):
        """Search should only return CONFIRMED identities."""
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()

        # Create CONFIRMED identity
        confirmed_id = registry.create_identity(
            anchor_ids=["face_001"],
            name="Alice Confirmed",
            user_source="test",
        )
        registry.confirm_identity(confirmed_id, user_source="test")

        # Create PROPOSED identity (should not appear)
        proposed_id = registry.create_identity(
            anchor_ids=["face_002"],
            name="Alice Proposed",
            user_source="test",
        )

        # Create INBOX identity (should not appear)
        inbox_id = registry.create_identity(
            anchor_ids=["face_003"],
            name="Alice Inbox",
            user_source="test",
            state=IdentityState.INBOX,
        )

        # Create REJECTED identity (should not appear)
        rejected_id = registry.create_identity(
            anchor_ids=["face_004"],
            name="Alice Rejected",
            user_source="test",
            state=IdentityState.INBOX,
        )
        registry.reject_identity(rejected_id, user_source="test")

        results = registry.search_identities("Alice")
        assert len(results) == 1
        assert results[0]["identity_id"] == confirmed_id

    def test_excludes_current_identity(self):
        """Search should exclude the identity specified by exclude_id."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()

        id_a = registry.create_identity(
            anchor_ids=["face_001"],
            name="Test Person",
            user_source="test",
        )
        registry.confirm_identity(id_a, user_source="test")

        id_b = registry.create_identity(
            anchor_ids=["face_002"],
            name="Test Person",
            user_source="test",
        )
        registry.confirm_identity(id_b, user_source="test")

        # Without exclusion, both should match
        results = registry.search_identities("Test")
        assert len(results) == 2

        # With exclusion, only one should match
        results = registry.search_identities("Test", exclude_id=id_a)
        assert len(results) == 1
        assert results[0]["identity_id"] == id_b

    def test_excludes_merged_identities(self):
        """Search should not return merged identities."""
        from core.registry import IdentityRegistry
        from unittest.mock import MagicMock

        registry = IdentityRegistry()

        target_id = registry.create_identity(
            anchor_ids=["face_001"],
            name="John Target",
            user_source="test",
        )
        registry.confirm_identity(target_id, user_source="test")

        source_id = registry.create_identity(
            anchor_ids=["face_002"],
            name="John Source",
            user_source="test",
        )
        registry.confirm_identity(source_id, user_source="test")

        # Before merge, both should appear
        results = registry.search_identities("John")
        assert len(results) == 2

        # Create mock photo registry for merge
        mock_photo_registry = MagicMock()
        mock_photo_registry.get_photos_for_faces.return_value = set()

        # Merge source into target (auto_correct_direction=False to skip
        # name conflict detection -- this test is about search exclusion)
        registry.merge_identities(
            source_id=source_id,
            target_id=target_id,
            user_source="test",
            photo_registry=mock_photo_registry,
            auto_correct_direction=False,
        )

        # After merge, only target should appear
        results = registry.search_identities("John")
        assert len(results) == 1
        assert results[0]["identity_id"] == target_id

    def test_empty_query_returns_empty_list(self):
        """Empty or whitespace query should return empty list."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            name="John Smith",
            user_source="test",
        )
        registry.confirm_identity(identity_id, user_source="test")

        assert registry.search_identities("") == []
        assert registry.search_identities("   ") == []

    def test_result_structure(self):
        """Results should have correct structure with identity_id, name, face_count, preview_face_id."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001", "face_002"],
            candidate_ids=["face_003"],
            name="Jane Doe",
            user_source="test",
        )
        registry.confirm_identity(identity_id, user_source="test")

        results = registry.search_identities("Jane")
        assert len(results) == 1

        result = results[0]
        assert result["identity_id"] == identity_id
        assert result["name"] == "Jane Doe"
        assert result["face_count"] == 3  # 2 anchors + 1 candidate
        assert result["preview_face_id"] == "face_001"  # First anchor

    def test_respects_limit(self):
        """Search should respect the limit parameter."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()

        # Create 5 confirmed identities
        for i in range(5):
            identity_id = registry.create_identity(
                anchor_ids=[f"face_{i:03d}"],
                name=f"Test Person {i}",
                user_source="test",
            )
            registry.confirm_identity(identity_id, user_source="test")

        # Default limit (10) should return all 5
        results = registry.search_identities("Test")
        assert len(results) == 5

        # Custom limit should be respected
        results = registry.search_identities("Test", limit=3)
        assert len(results) == 3

    def test_substring_match(self):
        """Search should find substring matches, not just prefix."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            name="John Smith Jr.",
            user_source="test",
        )
        registry.confirm_identity(identity_id, user_source="test")

        # Prefix match
        results = registry.search_identities("John")
        assert len(results) == 1

        # Substring match (middle)
        results = registry.search_identities("Smith")
        assert len(results) == 1

        # Substring match (suffix)
        results = registry.search_identities("Jr")
        assert len(results) == 1

    def test_no_match_returns_empty_list(self):
        """Query with no matches should return empty list."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            name="John Smith",
            user_source="test",
        )
        registry.confirm_identity(identity_id, user_source="test")

        results = registry.search_identities("xyz123")
        assert results == []


class TestListIdentitiesByJob:
    """Tests for list_identities_by_job() method (job cleanup support)."""

    def test_returns_identities_with_matching_job_id(self):
        """Should return identities where provenance.job_id matches."""
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            user_source="ingest_pipeline",
            state=IdentityState.INBOX,
            provenance={
                "source": "inbox_ingest",
                "job_id": "job_abc123",
                "filename": "photo.jpg",
            },
        )

        results = registry.list_identities_by_job("job_abc123")

        assert len(results) == 1
        assert results[0]["identity_id"] == identity_id
        assert results[0]["provenance"]["job_id"] == "job_abc123"

    def test_returns_empty_list_when_no_match(self):
        """Should return empty list when no identities match job_id."""
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()
        registry.create_identity(
            anchor_ids=["face_001"],
            user_source="ingest_pipeline",
            state=IdentityState.INBOX,
            provenance={
                "source": "inbox_ingest",
                "job_id": "job_abc123",
                "filename": "photo.jpg",
            },
        )

        results = registry.list_identities_by_job("job_xyz999")

        assert results == []

    def test_excludes_identities_from_other_jobs(self):
        """Should only return identities from the specified job."""
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()

        # Create identity from job A
        id_job_a = registry.create_identity(
            anchor_ids=["face_001"],
            user_source="ingest_pipeline",
            state=IdentityState.INBOX,
            provenance={"job_id": "job_a", "source": "inbox_ingest"},
        )

        # Create identity from job B
        id_job_b = registry.create_identity(
            anchor_ids=["face_002"],
            user_source="ingest_pipeline",
            state=IdentityState.INBOX,
            provenance={"job_id": "job_b", "source": "inbox_ingest"},
        )

        # Create identity without provenance
        id_no_prov = registry.create_identity(
            anchor_ids=["face_003"],
            user_source="manual",
        )

        results = registry.list_identities_by_job("job_a")

        assert len(results) == 1
        assert results[0]["identity_id"] == id_job_a

    def test_returns_multiple_identities_from_same_job(self):
        """Should return all identities created by the same job."""
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()

        # Create multiple identities from same job (e.g., multiple faces in upload)
        id_1 = registry.create_identity(
            anchor_ids=["face_001"],
            user_source="ingest_pipeline",
            state=IdentityState.INBOX,
            provenance={"job_id": "batch_job", "source": "inbox_ingest"},
        )
        id_2 = registry.create_identity(
            anchor_ids=["face_002"],
            user_source="ingest_pipeline",
            state=IdentityState.INBOX,
            provenance={"job_id": "batch_job", "source": "inbox_ingest"},
        )
        id_3 = registry.create_identity(
            anchor_ids=["face_003"],
            user_source="ingest_pipeline",
            state=IdentityState.INBOX,
            provenance={"job_id": "batch_job", "source": "inbox_ingest"},
        )

        results = registry.list_identities_by_job("batch_job")

        assert len(results) == 3
        result_ids = {r["identity_id"] for r in results}
        assert result_ids == {id_1, id_2, id_3}

    def test_returns_copy_not_reference(self):
        """Returned identities should be copies to prevent mutation."""
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            user_source="ingest_pipeline",
            state=IdentityState.INBOX,
            provenance={"job_id": "test_job", "source": "inbox_ingest"},
        )

        results = registry.list_identities_by_job("test_job")

        # Mutate the returned copy
        results[0]["name"] = "MUTATED"

        # Original should be unchanged
        original = registry.get_identity(identity_id)
        assert original["name"] is None
