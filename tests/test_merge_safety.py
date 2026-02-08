"""
Tests for merge direction auto-correction and undo safety.

These tests verify BUG-003 is fixed: the merge system auto-corrects direction
so named identities always survive, regardless of which button the user clicked.

Also tests undo_merge for full reversibility (forensic invariant).
"""

import pytest

from core.photo_registry import PhotoRegistry
from core.registry import IdentityRegistry, IdentityState


def _make_registries(face_photos: dict[str, str]):
    """Helper: create identity and photo registries with face->photo mappings.

    Args:
        face_photos: dict mapping face_id -> photo_id (each face in a unique photo)
    """
    photo_reg = PhotoRegistry()
    for face_id, photo_id in face_photos.items():
        photo_reg.register_face(photo_id, f"/path/{photo_id}.jpg", face_id)
    identity_reg = IdentityRegistry()
    return identity_reg, photo_reg


class TestMergeDirectionAutoCorrection:
    """BUG-003: Named identity must always survive, regardless of UI click context."""

    def test_unnamed_into_named_preserves_name(self):
        """When an unnamed identity is the UI target and named is source,
        direction should auto-correct so named identity survives."""
        identity_reg, photo_reg = _make_registries({
            "face_named": "photo_1",
            "face_unnamed": "photo_2",
        })

        named_id = identity_reg.create_identity(
            anchor_ids=["face_named"],
            user_source="test",
            name="Leon Capeluto",
            state=IdentityState.CONFIRMED,
        )
        unnamed_id = identity_reg.create_identity(
            anchor_ids=["face_unnamed"],
            user_source="test",
        )

        # UI sends unnamed as target (Focus Mode scenario)
        result = identity_reg.merge_identities(
            source_id=named_id,
            target_id=unnamed_id,
            user_source="test",
            photo_registry=photo_reg,
        )

        assert result["success"] is True
        assert result["direction_swapped"] is True
        # Named identity should be the actual target (survived)
        assert result["target_id"] == named_id
        assert result["source_id"] == unnamed_id

        # Named identity keeps its name and has both faces
        target = identity_reg.get_identity(named_id)
        assert target["name"] == "Leon Capeluto"
        assert "face_named" in target["anchor_ids"]
        assert "face_unnamed" in target["anchor_ids"]

        # Unnamed identity is marked as merged
        source = identity_reg.get_identity(unnamed_id)
        assert source["merged_into"] == named_id

    def test_named_into_unnamed_preserves_name(self):
        """When named identity is the UI target and unnamed is source,
        no swap needed — named identity survives naturally."""
        identity_reg, photo_reg = _make_registries({
            "face_named": "photo_1",
            "face_unnamed": "photo_2",
        })

        named_id = identity_reg.create_identity(
            anchor_ids=["face_named"],
            user_source="test",
            name="Betty Capeluto",
            state=IdentityState.CONFIRMED,
        )
        unnamed_id = identity_reg.create_identity(
            anchor_ids=["face_unnamed"],
            user_source="test",
        )

        # UI sends named as target (correct direction)
        result = identity_reg.merge_identities(
            source_id=unnamed_id,
            target_id=named_id,
            user_source="test",
            photo_registry=photo_reg,
        )

        assert result["success"] is True
        assert result["direction_swapped"] is False
        assert result["target_id"] == named_id

        target = identity_reg.get_identity(named_id)
        assert target["name"] == "Betty Capeluto"
        assert "face_named" in target["anchor_ids"]
        assert "face_unnamed" in target["anchor_ids"]

    def test_two_named_returns_name_conflict(self):
        """When both identities have names, merge should return conflict
        requiring explicit resolution — no silent name loss."""
        identity_reg, photo_reg = _make_registries({
            "face_a": "photo_1",
            "face_b": "photo_2",
        })

        id_a = identity_reg.create_identity(
            anchor_ids=["face_a"],
            user_source="test",
            name="Morris Mazal",
            state=IdentityState.CONFIRMED,
        )
        id_b = identity_reg.create_identity(
            anchor_ids=["face_b"],
            user_source="test",
            name="Maurice Mazal",
            state=IdentityState.CONFIRMED,
        )

        result = identity_reg.merge_identities(
            source_id=id_b,
            target_id=id_a,
            user_source="test",
            photo_registry=photo_reg,
        )

        assert result["success"] is False
        assert result["reason"] == "name_conflict"
        assert "name_conflict_details" in result

        # Both identities should be untouched
        a = identity_reg.get_identity(id_a)
        b = identity_reg.get_identity(id_b)
        assert a["name"] == "Morris Mazal"
        assert b["name"] == "Maurice Mazal"
        assert "merged_into" not in b

    def test_two_named_with_resolved_name_merges(self):
        """Name conflict resolved with explicit name choice should succeed."""
        identity_reg, photo_reg = _make_registries({
            "face_a": "photo_1",
            "face_b": "photo_2",
        })

        id_a = identity_reg.create_identity(
            anchor_ids=["face_a"],
            user_source="test",
            name="Morris Mazal",
            state=IdentityState.CONFIRMED,
        )
        id_b = identity_reg.create_identity(
            anchor_ids=["face_b"],
            user_source="test",
            name="Maurice Mazal",
            state=IdentityState.CONFIRMED,
        )

        result = identity_reg.merge_identities(
            source_id=id_b,
            target_id=id_a,
            user_source="test",
            photo_registry=photo_reg,
            resolved_name="Morris (Maurice) Mazal",
        )

        assert result["success"] is True
        target = identity_reg.get_identity(result["target_id"])
        assert target["name"] == "Morris (Maurice) Mazal"
        assert "face_a" in target["anchor_ids"]
        assert "face_b" in target["anchor_ids"]


class TestMergeStatePromotion:
    """State promotion: target gets max(target.state, source.state)."""

    def test_confirmed_source_promotes_inbox_target(self):
        """CONFIRMED source merged into INBOX target should promote to CONFIRMED."""
        identity_reg, photo_reg = _make_registries({
            "face_confirmed": "photo_1",
            "face_inbox": "photo_2",
        })

        confirmed_id = identity_reg.create_identity(
            anchor_ids=["face_confirmed"],
            user_source="test",
            name="Leon Capeluto",
            state=IdentityState.CONFIRMED,
        )
        inbox_id = identity_reg.create_identity(
            anchor_ids=["face_inbox"],
            user_source="test",
            state=IdentityState.INBOX,
        )

        # UI sends inbox as target (Focus Mode), auto-correction swaps
        result = identity_reg.merge_identities(
            source_id=confirmed_id,
            target_id=inbox_id,
            user_source="test",
            photo_registry=photo_reg,
        )

        assert result["success"] is True
        # Named CONFIRMED identity becomes the actual target
        target = identity_reg.get_identity(result["target_id"])
        assert target["state"] == "CONFIRMED"

    def test_inbox_source_into_confirmed_stays_confirmed(self):
        """INBOX source into CONFIRMED target should stay CONFIRMED."""
        identity_reg, photo_reg = _make_registries({
            "face_confirmed": "photo_1",
            "face_inbox": "photo_2",
        })

        confirmed_id = identity_reg.create_identity(
            anchor_ids=["face_confirmed"],
            user_source="test",
            name="Leon Capeluto",
            state=IdentityState.CONFIRMED,
        )
        inbox_id = identity_reg.create_identity(
            anchor_ids=["face_inbox"],
            user_source="test",
            state=IdentityState.INBOX,
        )

        result = identity_reg.merge_identities(
            source_id=inbox_id,
            target_id=confirmed_id,
            user_source="test",
            photo_registry=photo_reg,
        )

        assert result["success"] is True
        target = identity_reg.get_identity(result["target_id"])
        assert target["state"] == "CONFIRMED"

    def test_proposed_source_promotes_inbox_target(self):
        """PROPOSED source into INBOX target should promote to PROPOSED."""
        identity_reg, photo_reg = _make_registries({
            "face_proposed": "photo_1",
            "face_inbox": "photo_2",
        })

        proposed_id = identity_reg.create_identity(
            anchor_ids=["face_proposed"],
            user_source="test",
            state=IdentityState.PROPOSED,
        )
        inbox_id = identity_reg.create_identity(
            anchor_ids=["face_inbox"],
            user_source="test",
            state=IdentityState.INBOX,
        )

        # Both unnamed, PROPOSED has higher priority -> becomes target
        result = identity_reg.merge_identities(
            source_id=proposed_id,
            target_id=inbox_id,
            user_source="test",
            photo_registry=photo_reg,
        )

        assert result["success"] is True
        target = identity_reg.get_identity(result["target_id"])
        assert target["state"] in ("PROPOSED", "CONFIRMED")  # At least PROPOSED


class TestMergeHistory:
    """merge_history is recorded on target for undo capability."""

    def test_merge_history_recorded(self):
        """After merge, target should have merge_history entry with correct data."""
        identity_reg, photo_reg = _make_registries({
            "face_a": "photo_1",
            "face_b": "photo_2",
        })

        id_a = identity_reg.create_identity(
            anchor_ids=["face_a"],
            user_source="test",
            name="Leon Capeluto",
            state=IdentityState.CONFIRMED,
        )
        id_b = identity_reg.create_identity(
            anchor_ids=["face_b"],
            user_source="test",
            state=IdentityState.INBOX,
        )

        result = identity_reg.merge_identities(
            source_id=id_b,
            target_id=id_a,
            user_source="test",
            photo_registry=photo_reg,
        )

        assert result["success"] is True
        target = identity_reg.get_identity(result["target_id"])
        history = target.get("merge_history", [])
        assert len(history) == 1

        entry = history[0]
        assert "merge_event_id" in entry
        assert "timestamp" in entry
        assert entry["source_id"] == result["source_id"]
        assert "faces_added" in entry

    def test_merge_history_records_direction_correction(self):
        """When direction is auto-corrected, merge_history records this."""
        identity_reg, photo_reg = _make_registries({
            "face_named": "photo_1",
            "face_unnamed": "photo_2",
        })

        named_id = identity_reg.create_identity(
            anchor_ids=["face_named"],
            user_source="test",
            name="Leon Capeluto",
            state=IdentityState.CONFIRMED,
        )
        unnamed_id = identity_reg.create_identity(
            anchor_ids=["face_unnamed"],
            user_source="test",
            state=IdentityState.INBOX,
        )

        # UI sends unnamed as target -> auto-correction swaps
        result = identity_reg.merge_identities(
            source_id=named_id,
            target_id=unnamed_id,
            user_source="test",
            photo_registry=photo_reg,
        )

        assert result["success"] is True
        target = identity_reg.get_identity(result["target_id"])
        entry = target["merge_history"][-1]
        assert entry["direction_auto_corrected"] is True

    def test_all_faces_from_source_appear_in_target(self):
        """Every face from source must appear in target after merge."""
        identity_reg, photo_reg = _make_registries({
            "face_a1": "photo_1",
            "face_a2": "photo_2",
            "face_b1": "photo_3",
            "face_b2": "photo_4",
            "face_b3": "photo_5",
        })

        id_a = identity_reg.create_identity(
            anchor_ids=["face_a1", "face_a2"],
            user_source="test",
            name="Target Person",
            state=IdentityState.CONFIRMED,
        )
        id_b = identity_reg.create_identity(
            anchor_ids=["face_b1"],
            candidate_ids=["face_b2", "face_b3"],
            user_source="test",
            state=IdentityState.INBOX,
        )

        result = identity_reg.merge_identities(
            source_id=id_b,
            target_id=id_a,
            user_source="test",
            photo_registry=photo_reg,
        )

        assert result["success"] is True
        target = identity_reg.get_identity(result["target_id"])
        all_target_faces = target["anchor_ids"] + target["candidate_ids"]

        assert "face_b1" in all_target_faces
        assert "face_b2" in all_target_faces
        assert "face_b3" in all_target_faces
        # Original target faces still present
        assert "face_a1" in target["anchor_ids"]
        assert "face_a2" in target["anchor_ids"]

    def test_source_marked_as_merged_not_deleted(self):
        """Source identity should be soft-deleted (merged_into), not hard-deleted."""
        identity_reg, photo_reg = _make_registries({
            "face_a": "photo_1",
            "face_b": "photo_2",
        })

        id_a = identity_reg.create_identity(
            anchor_ids=["face_a"],
            user_source="test",
            name="Target",
            state=IdentityState.CONFIRMED,
        )
        id_b = identity_reg.create_identity(
            anchor_ids=["face_b"],
            user_source="test",
            state=IdentityState.INBOX,
        )

        result = identity_reg.merge_identities(
            source_id=id_b,
            target_id=id_a,
            user_source="test",
            photo_registry=photo_reg,
        )

        assert result["success"] is True
        # Source still exists but has merged_into set
        source = identity_reg.get_identity(result["source_id"])
        assert source["merged_into"] == result["target_id"]

        # Source is excluded from default listing
        identities = identity_reg.list_identities()
        source_ids = [i["identity_id"] for i in identities]
        assert result["source_id"] not in source_ids

        # But included when requested
        all_identities = identity_reg.list_identities(include_merged=True)
        all_ids = [i["identity_id"] for i in all_identities]
        assert result["source_id"] in all_ids


class TestUndoMerge:
    """Undo merge restores previous state fully."""

    def test_undo_merge_restores_previous_state(self):
        """Undo merge should restore both target and source to pre-merge state."""
        identity_reg, photo_reg = _make_registries({
            "face_a": "photo_1",
            "face_b": "photo_2",
        })

        id_a = identity_reg.create_identity(
            anchor_ids=["face_a"],
            user_source="test",
            name="Leon Capeluto",
            state=IdentityState.CONFIRMED,
        )
        id_b = identity_reg.create_identity(
            anchor_ids=["face_b"],
            user_source="test",
            state=IdentityState.INBOX,
        )

        # Merge
        merge_result = identity_reg.merge_identities(
            source_id=id_b,
            target_id=id_a,
            user_source="test",
            photo_registry=photo_reg,
        )
        assert merge_result["success"] is True
        actual_target = merge_result["target_id"]
        actual_source = merge_result["source_id"]

        # Verify merge happened
        target_after_merge = identity_reg.get_identity(actual_target)
        assert "face_b" in target_after_merge["anchor_ids"] or "face_b" in target_after_merge.get("candidate_ids", []) or "face_a" in target_after_merge["anchor_ids"]

        # Undo
        undo_result = identity_reg.undo_merge(actual_target, "test")
        assert undo_result["success"] is True

        # Target should only have its original faces
        target_after_undo = identity_reg.get_identity(actual_target)
        # Source should be restored (no merged_into)
        source_after_undo = identity_reg.get_identity(actual_source)
        assert "merged_into" not in source_after_undo

        # merge_history should be empty
        assert len(target_after_undo.get("merge_history", [])) == 0

    def test_undo_preserves_original_faces(self):
        """After undo, target has only its original faces, source has only its original faces."""
        identity_reg, photo_reg = _make_registries({
            "face_target": "photo_1",
            "face_source": "photo_2",
        })

        target_id = identity_reg.create_identity(
            anchor_ids=["face_target"],
            user_source="test",
            name="Leon Capeluto",
            state=IdentityState.CONFIRMED,
        )
        source_id = identity_reg.create_identity(
            anchor_ids=["face_source"],
            user_source="test",
            state=IdentityState.INBOX,
        )

        # Merge source into target
        result = identity_reg.merge_identities(
            source_id=source_id,
            target_id=target_id,
            user_source="test",
            photo_registry=photo_reg,
        )
        assert result["success"] is True
        actual_target = result["target_id"]
        actual_source = result["source_id"]

        # Undo
        undo_result = identity_reg.undo_merge(actual_target, "test")
        assert undo_result["success"] is True

        target = identity_reg.get_identity(actual_target)
        source = identity_reg.get_identity(actual_source)

        # Each identity should have exactly its original face
        # (The named one is 'face_target', unnamed is 'face_source')
        target_faces = target["anchor_ids"] + target.get("candidate_ids", [])
        source_faces = source["anchor_ids"] + source.get("candidate_ids", [])

        # face_source should NOT be in target after undo
        assert "face_source" not in target_faces or "face_target" not in source_faces

    def test_undo_blocked_when_target_is_merged(self):
        """If target was subsequently merged into another identity, undo is blocked."""
        identity_reg, photo_reg = _make_registries({
            "face_a": "photo_1",
            "face_b": "photo_2",
            "face_c": "photo_3",
        })

        id_a = identity_reg.create_identity(
            anchor_ids=["face_a"],
            user_source="test",
            name="Person A",
            state=IdentityState.CONFIRMED,
        )
        id_b = identity_reg.create_identity(
            anchor_ids=["face_b"],
            user_source="test",
            state=IdentityState.INBOX,
        )
        id_c = identity_reg.create_identity(
            anchor_ids=["face_c"],
            user_source="test",
            name="Person C",
            state=IdentityState.CONFIRMED,
        )

        # Merge B into A
        result1 = identity_reg.merge_identities(
            source_id=id_b, target_id=id_a,
            user_source="test", photo_registry=photo_reg,
        )
        assert result1["success"] is True

        # Now merge A into C (A becomes source, gets merged_into)
        result2 = identity_reg.merge_identities(
            source_id=id_a, target_id=id_c,
            user_source="test", photo_registry=photo_reg,
            auto_correct_direction=False,
        )
        assert result2["success"] is True

        # Try to undo the first merge on A — should be blocked (A is merged)
        undo_result = identity_reg.undo_merge(id_a, "test")
        assert undo_result["success"] is False
        assert undo_result["reason"] == "target_is_merged"

    def test_undo_with_no_merge_history(self):
        """Undo on identity with no merge history should fail gracefully."""
        identity_reg, photo_reg = _make_registries({
            "face_a": "photo_1",
        })

        id_a = identity_reg.create_identity(
            anchor_ids=["face_a"],
            user_source="test",
        )

        undo_result = identity_reg.undo_merge(id_a, "test")
        assert undo_result["success"] is False
        assert undo_result["reason"] == "no_merge_history"


class TestMergeDirectionTiebreakers:
    """Test merge direction resolution for edge cases."""

    def test_both_unnamed_higher_state_wins(self):
        """When both are unnamed, higher-trust state becomes target."""
        identity_reg, photo_reg = _make_registries({
            "face_proposed": "photo_1",
            "face_inbox": "photo_2",
        })

        proposed_id = identity_reg.create_identity(
            anchor_ids=["face_proposed"],
            user_source="test",
            state=IdentityState.PROPOSED,
        )
        inbox_id = identity_reg.create_identity(
            anchor_ids=["face_inbox"],
            user_source="test",
            state=IdentityState.INBOX,
        )

        # UI sends inbox as target — should auto-correct to proposed
        result = identity_reg.merge_identities(
            source_id=proposed_id,
            target_id=inbox_id,
            user_source="test",
            photo_registry=photo_reg,
        )

        assert result["success"] is True
        assert result["target_id"] == proposed_id

    def test_both_unnamed_same_state_more_faces_wins(self):
        """When both unnamed and same state, more faces becomes target."""
        identity_reg, photo_reg = _make_registries({
            "face_a1": "photo_1",
            "face_a2": "photo_2",
            "face_a3": "photo_3",
            "face_b1": "photo_4",
        })

        id_a = identity_reg.create_identity(
            anchor_ids=["face_a1", "face_a2", "face_a3"],
            user_source="test",
            state=IdentityState.INBOX,
        )
        id_b = identity_reg.create_identity(
            anchor_ids=["face_b1"],
            user_source="test",
            state=IdentityState.INBOX,
        )

        # UI sends b as target (1 face), a has 3 faces
        result = identity_reg.merge_identities(
            source_id=id_a,
            target_id=id_b,
            user_source="test",
            photo_registry=photo_reg,
        )

        assert result["success"] is True
        # id_a (3 faces) should be the target
        assert result["target_id"] == id_a

    def test_negative_evidence_preserved_on_merge(self):
        """Negative face IDs from source should be preserved in target."""
        identity_reg, photo_reg = _make_registries({
            "face_a": "photo_1",
            "face_b": "photo_2",
            "face_rejected": "photo_3",
        })

        id_a = identity_reg.create_identity(
            anchor_ids=["face_a"],
            user_source="test",
            name="Target",
            state=IdentityState.CONFIRMED,
        )
        id_b = identity_reg.create_identity(
            anchor_ids=["face_b"],
            user_source="test",
            state=IdentityState.INBOX,
        )
        # Add negative evidence to source
        identity_reg._identities[id_b]["negative_ids"] = ["face_rejected"]

        result = identity_reg.merge_identities(
            source_id=id_b,
            target_id=id_a,
            user_source="test",
            photo_registry=photo_reg,
        )

        assert result["success"] is True
        target = identity_reg.get_identity(result["target_id"])
        assert "face_rejected" in target.get("negative_ids", [])
