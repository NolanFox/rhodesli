"""Tests for merge face transfer integrity (Lesson 154).

Root cause: merge_identities() copies faces from source to target in memory,
but if the Supabase write fails or faces aren't properly transferred, the source
gets marked as merged (hidden from list_identities) while its faces remain
orphaned — they exist only in the merged source, invisible to the UI.

These tests verify:
1. All source faces are in the target after merge
2. get_identity_for_face finds faces after merge (excludes merged identities)
3. The post-merge verification catches orphaned faces
4. System-wide audit: no merged identity should have faces not in its target
"""

import json
import pytest
from core.registry import IdentityRegistry, IdentityState
from core.photo_registry import PhotoRegistry


@pytest.fixture()
def registry_with_identities():
    """Create a registry with two identities ready to merge."""
    registry = IdentityRegistry()
    photo_registry = PhotoRegistry()

    # Create target identity with 3 faces
    target_id = registry.create_identity(
        anchor_ids=["face_a1", "face_a2", "face_a3"],
        user_source="test",
        state=IdentityState.CONFIRMED,
    )
    registry.rename_identity(target_id, "Target Person", user_source="test")

    # Create source identity with 4 faces
    source_id = registry.create_identity(
        anchor_ids=["face_b1", "face_b2", "face_b3", "face_b4"],
        user_source="test",
        state=IdentityState.INBOX,
    )

    # Register all faces in different photos (no co-occurrence)
    for i, fid in enumerate(["face_a1", "face_a2", "face_a3", "face_b1", "face_b2", "face_b3", "face_b4"]):
        photo_registry.register_face(f"photo_{i}", f"photo_{i}.jpg", fid)

    return registry, photo_registry, target_id, source_id


class TestMergeFaceTransfer:
    """All source faces must be in the target after merge."""

    def test_all_source_faces_in_target_after_merge(self, registry_with_identities):
        registry, photo_registry, target_id, source_id = registry_with_identities

        result = registry.merge_identities(source_id, target_id, "test", photo_registry)
        assert result["success"]

        actual_target_id = result["target_id"]
        target = registry._identities[actual_target_id]
        target_faces = set(target.get("anchor_ids", []) + target.get("candidate_ids", []))

        # All 4 source faces must be in target
        for fid in ["face_b1", "face_b2", "face_b3", "face_b4"]:
            assert fid in target_faces, f"Source face {fid} missing from target after merge"

        # All 3 original target faces must still be there
        for fid in ["face_a1", "face_a2", "face_a3"]:
            assert fid in target_faces, f"Original target face {fid} missing after merge"

    def test_get_identity_for_face_finds_merged_faces(self, registry_with_identities):
        """get_identity_for_face must find faces after merge, even though source is hidden."""
        registry, photo_registry, target_id, source_id = registry_with_identities

        result = registry.merge_identities(source_id, target_id, "test", photo_registry)
        assert result["success"]

        actual_target_id = result["target_id"]

        # Build face lookup (simulating what app does)
        face_lookup = {}
        for identity in registry.list_identities():
            all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
            for fid in all_face_ids:
                face_lookup[fid] = identity

        # All source faces must resolve to the target identity
        for fid in ["face_b1", "face_b2", "face_b3", "face_b4"]:
            found = face_lookup.get(fid)
            assert found is not None, f"Face {fid} not found via list_identities after merge"
            assert found["identity_id"] == actual_target_id, (
                f"Face {fid} resolves to {found['identity_id']}, expected {actual_target_id}"
            )

    def test_source_is_hidden_after_merge(self, registry_with_identities):
        """Merged source identity must not appear in list_identities."""
        registry, photo_registry, target_id, source_id = registry_with_identities

        result = registry.merge_identities(source_id, target_id, "test", photo_registry)
        assert result["success"]

        actual_source_id = result["source_id"]
        visible_ids = {i["identity_id"] for i in registry.list_identities()}
        assert actual_source_id not in visible_ids, "Merged source should be hidden"

    def test_merged_source_faces_not_orphaned(self, registry_with_identities):
        """No face in a merged identity should be absent from its target."""
        registry, photo_registry, target_id, source_id = registry_with_identities

        result = registry.merge_identities(source_id, target_id, "test", photo_registry)
        assert result["success"]

        # Run the orphan audit
        orphans = _find_merge_orphans(registry)
        assert len(orphans) == 0, f"Found {len(orphans)} orphaned faces after merge: {orphans}"


class TestMergeWithDirectionSwap:
    """Faces must transfer correctly even when merge direction is auto-corrected."""

    def test_direction_swap_preserves_all_faces(self):
        registry = IdentityRegistry()
        photo_registry = PhotoRegistry()

        # Source has a name (higher priority → becomes target after swap)
        source_id = registry.create_identity(
            anchor_ids=["face_named_1", "face_named_2"],
            user_source="test",
            state=IdentityState.CONFIRMED,
        )
        registry.rename_identity(source_id, "Named Person", user_source="test")

        # Target is unidentified (lower priority → becomes source after swap)
        target_id = registry.create_identity(
            anchor_ids=["face_unnamed_1", "face_unnamed_2", "face_unnamed_3"],
            user_source="test",
            state=IdentityState.INBOX,
        )

        # Register in separate photos
        for i, fid in enumerate(["face_named_1", "face_named_2", "face_unnamed_1", "face_unnamed_2", "face_unnamed_3"]):
            photo_registry.register_face(f"photo_{i}", f"photo_{i}.jpg", fid)

        result = registry.merge_identities(source_id, target_id, "test", photo_registry)
        assert result["success"]
        assert result["direction_swapped"]  # Should have swapped

        actual_target_id = result["target_id"]
        target_data = registry._identities[actual_target_id]
        all_target_faces = set(target_data.get("anchor_ids", []) + target_data.get("candidate_ids", []))

        # ALL 5 faces must be in the actual target
        all_faces = {"face_named_1", "face_named_2", "face_unnamed_1", "face_unnamed_2", "face_unnamed_3"}
        for fid in all_faces:
            assert fid in all_target_faces, f"Face {fid} missing after direction-swapped merge"


class TestChainedMerges:
    """Faces must survive through chains: A→B→C."""

    def test_chained_merge_preserves_all_faces(self):
        registry = IdentityRegistry()
        photo_registry = PhotoRegistry()

        # Create 3 identities
        a_id = registry.create_identity(anchor_ids=["face_a"], user_source="test", state=IdentityState.INBOX)
        b_id = registry.create_identity(anchor_ids=["face_b"], user_source="test", state=IdentityState.INBOX)
        c_id = registry.create_identity(anchor_ids=["face_c"], user_source="test", state=IdentityState.CONFIRMED)
        registry.rename_identity(c_id, "Person C", user_source="test")

        for i, fid in enumerate(["face_a", "face_b", "face_c"]):
            photo_registry.register_face(f"photo_{i}", f"photo_{i}.jpg", fid)

        # Merge A → B
        r1 = registry.merge_identities(a_id, b_id, "test", photo_registry)
        assert r1["success"]

        # Merge B → C
        r2 = registry.merge_identities(b_id, c_id, "test", photo_registry)
        assert r2["success"]

        # All faces should be in C
        actual_target = registry._identities[r2["target_id"]]
        all_faces = set(actual_target.get("anchor_ids", []) + actual_target.get("candidate_ids", []))
        assert "face_a" in all_faces, "face_a lost in chain A→B→C"
        assert "face_b" in all_faces, "face_b lost in chain A→B→C"
        assert "face_c" in all_faces, "face_c lost in chain A→B→C"

        # And no orphans
        orphans = _find_merge_orphans(registry)
        assert len(orphans) == 0, f"Chained merge produced orphans: {orphans}"


def _find_merge_orphans(registry: IdentityRegistry) -> list[dict]:
    """Find faces in merged identities that are not in their target.

    This is the structural invariant: every face in a merged identity
    must also exist in the surviving (target) identity.
    """
    orphans = []
    for iid, ident in registry._identities.items():
        merged_into = ident.get("merged_into")
        if not merged_into:
            continue

        target = registry._identities.get(merged_into)
        if not target:
            continue

        target_faces = set(target.get("anchor_ids", []) + target.get("candidate_ids", []))

        for fid in ident.get("anchor_ids", []) + ident.get("candidate_ids", []):
            if fid and fid not in target_faces:
                orphans.append(
                    {
                        "face_id": fid,
                        "source_id": iid,
                        "source_name": ident.get("name", ""),
                        "target_id": merged_into,
                        "target_name": target.get("name", ""),
                    }
                )

    return orphans
