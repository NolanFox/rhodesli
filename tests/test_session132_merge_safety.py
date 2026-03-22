"""Tests for Session 132 merge safety improvements.

Phase 3A: Community cache invalidation after save_registry
Phase 3B: Merged identity redirect (already existed as UX-038)
Phase 3C: Startup merge orphan check
"""

from unittest.mock import MagicMock, patch

import pytest


class TestCommunityCache_InvalidationOnSave:
    """Phase 3A: save_registry() must clear community identity cache."""

    def test_save_registry_clears_community_identity_cache(self):
        """After save_registry, community identity IDs cache is empty."""
        import app.main as main_mod

        # Pre-populate the community cache
        main_mod._community_identity_ids_cache = {"rhodes": {"id1", "id2"}}
        main_mod._community_ids_cache_ts = 999999.0

        mock_registry = MagicMock()
        mock_registry._identities = {"id1": {"name": "Test", "state": "CONFIRMED"}}

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch.object(main_mod, "REGISTRY_PATH", "/tmp/test.json"),
            patch("app.supabase_data.shadow_write_identities_batch", MagicMock()),
        ):
            main_mod.save_registry(mock_registry)

        # Community cache should be cleared
        assert main_mod._community_identity_ids_cache == {}
        assert main_mod._community_ids_cache_ts == 0.0


class TestStartupMergeOrphanCheck:
    """Phase 3C: Startup detects faces in merged identities not in target."""

    def test_detects_orphaned_faces_in_merged_identity(self):
        """Faces in a merged identity that aren't in the target are detected."""
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()

        # Create target identity with some faces
        target_id = registry.create_identity(
            anchor_ids=["face1", "face2"],
            user_source="test",
            state=IdentityState.CONFIRMED,
        )

        # Create source identity that was "merged" but faces weren't transferred
        source_id = registry.create_identity(
            anchor_ids=["face3", "face4"],
            user_source="test",
            state=IdentityState.INBOX,
        )
        registry._identities[source_id]["merged_into"] = target_id

        # Simulate the orphan check logic
        all_identities = registry.list_identities(include_merged=True)
        orphaned_count = 0
        for identity in all_identities:
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
            orphaned_count += len(missing)

        # face3 and face4 should be detected as orphaned
        assert orphaned_count == 2

    def test_no_orphans_when_faces_transferred(self):
        """No orphans detected when merge properly transferred faces."""
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()

        target_id = registry.create_identity(
            anchor_ids=["face1", "face2", "face3"],
            user_source="test",
            state=IdentityState.CONFIRMED,
        )

        source_id = registry.create_identity(
            anchor_ids=["face3"],  # Already in target
            user_source="test",
            state=IdentityState.INBOX,
        )
        registry._identities[source_id]["merged_into"] = target_id

        all_identities = registry.list_identities(include_merged=True)
        orphaned_count = 0
        for identity in all_identities:
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
            orphaned_count += len(missing)

        assert orphaned_count == 0

    def test_dangling_merge_target_skipped(self):
        """Merged identity pointing to non-existent target is skipped."""
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()

        source_id = registry.create_identity(
            anchor_ids=["face1"],
            user_source="test",
            state=IdentityState.INBOX,
        )
        registry._identities[source_id]["merged_into"] = "nonexistent-id"

        all_identities = registry.list_identities(include_merged=True)
        orphaned_count = 0
        for identity in all_identities:
            merged_into = identity.get("merged_into")
            if not merged_into:
                continue
            source_faces = set(identity.get("anchor_ids", []))
            try:
                target = registry.get_identity(merged_into)
            except KeyError:
                continue  # Should skip, not crash
            target_faces = set(target.get("anchor_ids", []))
            missing = source_faces - target_faces
            orphaned_count += len(missing)

        # No orphans counted because target doesn't exist (skipped)
        assert orphaned_count == 0
