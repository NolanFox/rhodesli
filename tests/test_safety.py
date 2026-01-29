"""
Tests for Safety Foundation: PhotoRegistry and validate_merge.

These tests verify that physical impossibility constraints are enforced:
- Two faces in the same photo cannot belong to the same identity
- All merge operations must pass validation

See task spec for design rationale.
"""

import json
import tempfile
from pathlib import Path

import pytest


class TestPhotoRegistry:
    """Tests for PhotoRegistry functionality."""

    def test_register_face_stores_mapping(self):
        """Registering a face should store photo -> face mapping."""
        from core.photo_registry import PhotoRegistry

        registry = PhotoRegistry()
        registry.register_face(
            photo_id="photo_abc123",
            path="/images/photo1.jpg",
            face_id="photo1:face0",
        )

        faces = registry.get_faces_in_photo("photo_abc123")
        assert "photo1:face0" in faces

    def test_register_multiple_faces_same_photo(self):
        """Multiple faces in same photo should all be tracked."""
        from core.photo_registry import PhotoRegistry

        registry = PhotoRegistry()
        registry.register_face("photo_abc123", "/images/photo1.jpg", "photo1:face0")
        registry.register_face("photo_abc123", "/images/photo1.jpg", "photo1:face1")

        faces = registry.get_faces_in_photo("photo_abc123")
        assert len(faces) == 2
        assert "photo1:face0" in faces
        assert "photo1:face1" in faces

    def test_get_photo_for_face(self):
        """Should retrieve photo_id for a given face_id."""
        from core.photo_registry import PhotoRegistry

        registry = PhotoRegistry()
        registry.register_face("photo_abc123", "/images/photo1.jpg", "photo1:face0")

        photo_id = registry.get_photo_for_face("photo1:face0")
        assert photo_id == "photo_abc123"

    def test_get_photo_for_unknown_face_returns_none(self):
        """Unknown face_id should return None."""
        from core.photo_registry import PhotoRegistry

        registry = PhotoRegistry()
        photo_id = registry.get_photo_for_face("unknown:face0")
        assert photo_id is None

    def test_get_faces_in_unknown_photo_returns_empty(self):
        """Unknown photo_id should return empty set."""
        from core.photo_registry import PhotoRegistry

        registry = PhotoRegistry()
        faces = registry.get_faces_in_photo("unknown_photo")
        assert faces == set()


class TestPhotoRegistryPersistence:
    """Tests for PhotoRegistry save/load."""

    def test_save_creates_json_file(self):
        """Saving should create a JSON file."""
        from core.photo_registry import PhotoRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "photo_index.json"
            registry = PhotoRegistry()
            registry.register_face("photo_abc123", "/images/photo1.jpg", "photo1:face0")

            registry.save(path)

            assert path.exists()
            with open(path) as f:
                data = json.load(f)
            assert "photos" in data
            assert "face_to_photo" in data

    def test_load_restores_mappings(self):
        """Loading should restore all mappings."""
        from core.photo_registry import PhotoRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "photo_index.json"

            # Save
            registry1 = PhotoRegistry()
            registry1.register_face("photo_abc123", "/images/photo1.jpg", "photo1:face0")
            registry1.register_face("photo_abc123", "/images/photo1.jpg", "photo1:face1")
            registry1.register_face("photo_def456", "/images/photo2.jpg", "photo2:face0")
            registry1.save(path)

            # Load
            registry2 = PhotoRegistry.load(path)

            # Verify photo -> faces mapping
            faces1 = registry2.get_faces_in_photo("photo_abc123")
            assert len(faces1) == 2
            assert "photo1:face0" in faces1
            assert "photo1:face1" in faces1

            faces2 = registry2.get_faces_in_photo("photo_def456")
            assert len(faces2) == 1
            assert "photo2:face0" in faces2

            # Verify face -> photo mapping
            assert registry2.get_photo_for_face("photo1:face0") == "photo_abc123"
            assert registry2.get_photo_for_face("photo2:face0") == "photo_def456"

    def test_save_load_preserves_path_metadata(self):
        """File paths should be preserved through save/load."""
        from core.photo_registry import PhotoRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "photo_index.json"

            registry1 = PhotoRegistry()
            registry1.register_face("photo_abc123", "/images/photo1.jpg", "photo1:face0")
            registry1.save(path)

            registry2 = PhotoRegistry.load(path)

            # Path should be accessible (implementation detail, but useful)
            with open(path) as f:
                data = json.load(f)
            assert data["photos"]["photo_abc123"]["path"] == "/images/photo1.jpg"


class TestValidateMerge:
    """Tests for merge validation logic."""

    def test_merge_blocked_when_same_photo(self):
        """Merge should be blocked when identities share a photo."""
        from core.photo_registry import PhotoRegistry
        from core.registry import IdentityRegistry, validate_merge

        photo_registry = PhotoRegistry()
        photo_registry.register_face("photo_abc123", "/images/photo1.jpg", "face_a")
        photo_registry.register_face("photo_abc123", "/images/photo1.jpg", "face_b")

        identity_registry = IdentityRegistry()
        id_a = identity_registry.create_identity(
            anchor_ids=["face_a"],
            user_source="test",
        )
        id_b = identity_registry.create_identity(
            anchor_ids=["face_b"],
            user_source="test",
        )

        can_merge, reason = validate_merge(id_a, id_b, identity_registry, photo_registry)

        assert can_merge is False
        assert reason == "co_occurrence"

    def test_merge_allowed_different_photos(self):
        """Merge should be allowed when identities are from different photos."""
        from core.photo_registry import PhotoRegistry
        from core.registry import IdentityRegistry, validate_merge

        photo_registry = PhotoRegistry()
        photo_registry.register_face("photo_abc123", "/images/photo1.jpg", "face_a")
        photo_registry.register_face("photo_def456", "/images/photo2.jpg", "face_b")

        identity_registry = IdentityRegistry()
        id_a = identity_registry.create_identity(
            anchor_ids=["face_a"],
            user_source="test",
        )
        id_b = identity_registry.create_identity(
            anchor_ids=["face_b"],
            user_source="test",
        )

        can_merge, reason = validate_merge(id_a, id_b, identity_registry, photo_registry)

        assert can_merge is True
        assert reason == "ok"

    def test_merge_blocked_multi_photo_overlap(self):
        """Merge blocked when identities with multiple photos have ANY overlap."""
        from core.photo_registry import PhotoRegistry
        from core.registry import IdentityRegistry, validate_merge

        photo_registry = PhotoRegistry()
        # Identity A has faces in photos 1 and 2
        photo_registry.register_face("photo_1", "/images/photo1.jpg", "face_a1")
        photo_registry.register_face("photo_2", "/images/photo2.jpg", "face_a2")
        # Identity B has faces in photos 2 and 3 (overlaps on photo_2)
        photo_registry.register_face("photo_2", "/images/photo2.jpg", "face_b1")
        photo_registry.register_face("photo_3", "/images/photo3.jpg", "face_b2")

        identity_registry = IdentityRegistry()
        id_a = identity_registry.create_identity(
            anchor_ids=["face_a1", "face_a2"],
            user_source="test",
        )
        id_b = identity_registry.create_identity(
            anchor_ids=["face_b1", "face_b2"],
            user_source="test",
        )

        can_merge, reason = validate_merge(id_a, id_b, identity_registry, photo_registry)

        assert can_merge is False
        assert reason == "co_occurrence"

    def test_merge_considers_candidates_and_anchors(self):
        """Merge validation should check ALL face_ids (anchors + candidates)."""
        from core.photo_registry import PhotoRegistry
        from core.registry import IdentityRegistry, validate_merge

        photo_registry = PhotoRegistry()
        photo_registry.register_face("photo_1", "/images/photo1.jpg", "anchor_a")
        photo_registry.register_face("photo_1", "/images/photo1.jpg", "candidate_b")

        identity_registry = IdentityRegistry()
        # Identity A has anchor in photo_1
        id_a = identity_registry.create_identity(
            anchor_ids=["anchor_a"],
            user_source="test",
        )
        # Identity B has candidate in same photo_1
        id_b = identity_registry.create_identity(
            anchor_ids=[],
            candidate_ids=["candidate_b"],
            user_source="test",
        )

        can_merge, reason = validate_merge(id_a, id_b, identity_registry, photo_registry)

        assert can_merge is False
        assert reason == "co_occurrence"


class TestValidateMergeLogging:
    """Tests for merge validation logging."""

    def test_failed_merge_is_logged(self, caplog):
        """Failed merge attempts should be logged."""
        import logging

        from core.photo_registry import PhotoRegistry
        from core.registry import IdentityRegistry, validate_merge

        photo_registry = PhotoRegistry()
        photo_registry.register_face("photo_1", "/images/photo1.jpg", "face_a")
        photo_registry.register_face("photo_1", "/images/photo1.jpg", "face_b")

        identity_registry = IdentityRegistry()
        id_a = identity_registry.create_identity(anchor_ids=["face_a"], user_source="test")
        id_b = identity_registry.create_identity(anchor_ids=["face_b"], user_source="test")

        with caplog.at_level(logging.WARNING):
            validate_merge(id_a, id_b, identity_registry, photo_registry)

        assert "co_occurrence" in caplog.text
        assert id_a in caplog.text
        assert id_b in caplog.text
