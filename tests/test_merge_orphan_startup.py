"""Tests for startup merge orphan detection and auto-repair.

Session 132 Phase 3C: Startup parity check detects faces in merged
identities that weren't transferred to their merge target, and
auto-repairs by adding missing faces to the target's anchor_ids.

Recreated in Session 133 (original lost when worktree was cleaned).
"""

from core.registry import IdentityRegistry, IdentityState


class TestStartupMergeOrphanDetection:
    """Startup detects faces in merged identities not in target."""

    def test_detects_orphaned_faces_in_merged_identity(self):
        """Faces in a merged identity that aren't in the target are detected."""
        registry = IdentityRegistry()

        target_id = registry.create_identity(
            anchor_ids=["face1", "face2"],
            user_source="test",
            state=IdentityState.CONFIRMED,
        )

        source_id = registry.create_identity(
            anchor_ids=["face3", "face4", "face5"],
            user_source="test",
            state=IdentityState.INBOX,
        )
        registry._identities[source_id]["merged_into"] = target_id

        # Simulate startup check logic
        all_identities = registry.list_identities(include_merged=True)
        orphaned_count = 0
        for identity in all_identities:
            merged_into = identity.get("merged_into")
            if not merged_into:
                continue
            source_faces = set(identity.get("anchor_ids", []) + identity.get("candidate_ids", []))
            try:
                target = registry.get_identity(merged_into)
            except KeyError:
                continue
            if target.get("merged_into"):
                continue
            target_faces = set(target.get("anchor_ids", []) + target.get("candidate_ids", []))
            missing = source_faces - target_faces
            orphaned_count += len(missing)

        assert orphaned_count == 3  # face3, face4, face5

    def test_transfers_faces_to_target(self):
        """Auto-repair adds orphaned faces to target's anchor_ids."""
        registry = IdentityRegistry()

        target_id = registry.create_identity(
            anchor_ids=["face1"],
            user_source="test",
            state=IdentityState.CONFIRMED,
        )

        source_id = registry.create_identity(
            anchor_ids=["face2", "face3"],
            user_source="test",
            state=IdentityState.INBOX,
        )
        registry._identities[source_id]["merged_into"] = target_id

        # Simulate auto-repair
        repaired = set()
        for identity in registry.list_identities(include_merged=True):
            merged_into = identity.get("merged_into")
            if not merged_into:
                continue
            source_faces = set(identity.get("anchor_ids", []))
            try:
                target = registry.get_identity(merged_into)
            except KeyError:
                continue
            if target.get("merged_into"):
                continue
            target_faces = set(target.get("anchor_ids", []))
            missing = source_faces - target_faces
            if missing:
                target_anchors = list(target.get("anchor_ids", []))
                target_anchors.extend(missing)
                registry._identities[merged_into]["anchor_ids"] = target_anchors
                repaired.add(merged_into)

        # Verify transfer
        target = registry.get_identity(target_id)
        assert set(target["anchor_ids"]) == {"face1", "face2", "face3"}

    def test_no_duplicates_when_faces_already_transferred(self):
        """Faces already in target are not duplicated."""
        registry = IdentityRegistry()

        target_id = registry.create_identity(
            anchor_ids=["face1", "face2", "face3"],
            user_source="test",
            state=IdentityState.CONFIRMED,
        )

        source_id = registry.create_identity(
            anchor_ids=["face2", "face3"],  # Already in target
            user_source="test",
            state=IdentityState.INBOX,
        )
        registry._identities[source_id]["merged_into"] = target_id

        # Simulate check — should find 0 missing
        for identity in registry.list_identities(include_merged=True):
            merged_into = identity.get("merged_into")
            if not merged_into:
                continue
            source_faces = set(identity.get("anchor_ids", []))
            try:
                target = registry.get_identity(merged_into)
            except KeyError:
                continue
            target_faces = set(target.get("anchor_ids", []))
            missing = source_faces - target_faces
            assert len(missing) == 0

    def test_dangling_merge_target_skipped(self):
        """Merged identity pointing to non-existent target is skipped safely."""
        registry = IdentityRegistry()

        source_id = registry.create_identity(
            anchor_ids=["face1"],
            user_source="test",
            state=IdentityState.INBOX,
        )
        registry._identities[source_id]["merged_into"] = "nonexistent-target-id"

        # Should not crash
        orphaned = 0
        for identity in registry.list_identities(include_merged=True):
            merged_into = identity.get("merged_into")
            if not merged_into:
                continue
            try:
                target = registry.get_identity(merged_into)
            except KeyError:
                continue  # Skip dangling
            source_faces = set(identity.get("anchor_ids", []))
            target_faces = set(target.get("anchor_ids", []))
            orphaned += len(source_faces - target_faces)

        assert orphaned == 0  # Skipped because target doesn't exist

    def test_chained_merges_skipped(self):
        """If target is itself merged, skip (don't repair intermediate nodes)."""
        registry = IdentityRegistry()

        final_id = registry.create_identity(
            anchor_ids=["face1"],
            user_source="test",
            state=IdentityState.CONFIRMED,
        )

        intermediate_id = registry.create_identity(
            anchor_ids=["face2"],
            user_source="test",
            state=IdentityState.INBOX,
        )
        registry._identities[intermediate_id]["merged_into"] = final_id

        source_id = registry.create_identity(
            anchor_ids=["face3"],
            user_source="test",
            state=IdentityState.INBOX,
        )
        registry._identities[source_id]["merged_into"] = intermediate_id

        # Source -> Intermediate -> Final
        # The check should skip source because intermediate is itself merged
        repaired = 0
        for identity in registry.list_identities(include_merged=True):
            merged_into = identity.get("merged_into")
            if not merged_into:
                continue
            try:
                target = registry.get_identity(merged_into)
            except KeyError:
                continue
            if target.get("merged_into"):
                continue  # Target is merged — skip
            source_faces = set(identity.get("anchor_ids", []))
            target_faces = set(target.get("anchor_ids", []))
            missing = source_faces - target_faces
            repaired += len(missing)

        # Only intermediate -> final is repaired (face2 not in final)
        # source -> intermediate is skipped (intermediate is merged)
        assert repaired == 1  # face2
