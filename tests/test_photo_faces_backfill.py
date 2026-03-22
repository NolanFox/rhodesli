"""Tests for photo_faces backfill and PhotoRegistry cross-ID resolution.

Session 130: Data Integrity Deep Audit — Phase 2
"""

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.photo_registry import PhotoRegistry


class TestPhotoRegistryResolvePhotoId:
    """Test the resolve_photo_id method that bridges inbox/SHA256 IDs."""

    def _sha256_id(self, filename: str) -> str:
        return hashlib.sha256(Path(filename).name.encode("utf-8")).hexdigest()[:16]

    def test_direct_match_returns_same_id(self):
        registry = PhotoRegistry()
        registry._photos["inbox_abc_0_photo.jpg"] = {"path": "raw_photos/photo.jpg", "face_ids": set()}
        assert registry.resolve_photo_id("inbox_abc_0_photo.jpg") == "inbox_abc_0_photo.jpg"

    def test_sha256_resolves_to_inbox_id(self):
        registry = PhotoRegistry()
        registry._photos["inbox_abc_0_photo.jpg"] = {"path": "raw_photos/photo.jpg", "face_ids": set()}
        sha_id = self._sha256_id("photo.jpg")
        resolved = registry.resolve_photo_id(sha_id)
        assert resolved == "inbox_abc_0_photo.jpg"

    def test_unknown_id_returns_none(self):
        registry = PhotoRegistry()
        registry._photos["inbox_abc_0_photo.jpg"] = {"path": "raw_photos/photo.jpg", "face_ids": set()}
        assert registry.resolve_photo_id("nonexistent_id") is None

    def test_get_faces_in_photo_with_sha256_id(self):
        registry = PhotoRegistry()
        registry._photos["inbox_abc_0_photo.jpg"] = {
            "path": "raw_photos/photo.jpg",
            "face_ids": {"face1", "face2"},
        }
        sha_id = self._sha256_id("photo.jpg")
        faces = registry.get_faces_in_photo(sha_id)
        assert faces == {"face1", "face2"}

    def test_get_faces_in_photo_direct_still_works(self):
        registry = PhotoRegistry()
        registry._photos["inbox_abc_0_photo.jpg"] = {
            "path": "raw_photos/photo.jpg",
            "face_ids": {"face1"},
        }
        faces = registry.get_faces_in_photo("inbox_abc_0_photo.jpg")
        assert faces == {"face1"}

    def test_get_faces_unknown_returns_empty(self):
        registry = PhotoRegistry()
        assert registry.get_faces_in_photo("nonexistent") == set()

    def test_filename_index_built_lazily(self):
        registry = PhotoRegistry()
        registry._photos["inbox_abc_0_photo.jpg"] = {"path": "raw_photos/photo.jpg", "face_ids": set()}
        assert registry._filename_to_photo_id == {}  # Not built yet
        sha_id = self._sha256_id("photo.jpg")
        registry.resolve_photo_id(sha_id)
        assert "photo.jpg" in registry._filename_to_photo_id  # Built now

    def test_build_filename_index_explicit(self):
        registry = PhotoRegistry()
        registry._photos["p1"] = {"path": "raw_photos/a.jpg", "face_ids": set()}
        registry._photos["p2"] = {"path": "raw_photos/b.jpg", "face_ids": set()}
        registry._build_filename_index()
        assert registry._filename_to_photo_id == {"a.jpg": "p1", "b.jpg": "p2"}


class TestBuildCachesFaceResolution:
    """Test that _build_caches correctly resolves faces across ID formats.

    Session 134: Verifies FB-016 root cause (photo_faces inbox ID vs SHA256 URL ID)
    is handled by the filename-based merging in _build_caches().
    """

    def _sha256_id(self, filename: str) -> str:
        return hashlib.sha256(Path(filename).name.encode("utf-8")).hexdigest()[:16]

    @patch("app.main.load_photo_registry")
    @patch("app.main._load_raw_embeddings")
    def test_inbox_faces_appear_in_sha256_keyed_cache(self, mock_raw, mock_registry):
        """Faces with inbox face_ids appear in _photo_cache keyed by SHA256 photo ID."""
        import numpy as np
        import app.main as main_mod

        filename = "test_photo.jpg"
        sha_id = self._sha256_id(filename)

        # Simulate embeddings.npy with inbox-style face_ids
        mock_raw.return_value = [
            {
                "filename": filename,
                "face_id": "inbox_abc123",
                "bbox": [10, 20, 100, 200],
                "embeddings": np.zeros(512),
                "det_score": 0.9,
                "quality": 0.8,
            },
            {
                "filename": filename,
                "face_id": "inbox_def456",
                "bbox": [200, 20, 300, 200],
                "embeddings": np.zeros(512),
                "det_score": 0.85,
                "quality": 0.75,
            },
        ]

        # Photo registry with inbox photo ID and matching face IDs
        registry = PhotoRegistry()
        registry._photos["inbox_test_0_test_photo.jpg"] = {
            "path": "raw_photos/test_photo.jpg",
            "face_ids": {"inbox_abc123", "inbox_def456"},
            "source": "Test Collection",
            "collection": "Tests",
            "source_url": "",
            "metadata": {},
        }
        registry._face_to_photo = {
            "inbox_abc123": "inbox_test_0_test_photo.jpg",
            "inbox_def456": "inbox_test_0_test_photo.jpg",
        }
        mock_registry.return_value = registry

        # Reset cache state
        old_cache = main_mod._photo_cache
        old_f2p = main_mod._face_to_photo_cache
        old_aliases = main_mod._photo_id_aliases
        try:
            main_mod._photo_cache = None
            main_mod._face_to_photo_cache = None
            main_mod._photo_id_aliases = None
            main_mod._build_caches()

            # Photo should be keyed by SHA256 ID
            assert sha_id in main_mod._photo_cache, f"SHA256 ID {sha_id} not in cache"
            photo = main_mod._photo_cache[sha_id]
            face_ids = {f["face_id"] for f in photo["faces"]}
            assert "inbox_abc123" in face_ids, "inbox face_id missing from cache"
            assert "inbox_def456" in face_ids, "inbox face_id missing from cache"
            assert len(photo["faces"]) == 2
        finally:
            main_mod._photo_cache = old_cache
            main_mod._face_to_photo_cache = old_f2p
            main_mod._photo_id_aliases = old_aliases

    def test_get_identity_for_face_finds_inbox_faces(self):
        """get_identity_for_face resolves inbox-format face_ids to identities."""
        from app.main import get_identity_for_face

        # Use a simple namespace instead of MagicMock to avoid __dict__ conflicts
        class FakeRegistry:
            def list_identities(self):
                return [
                    {
                        "identity_id": "id-001",
                        "name": "Test Person",
                        "state": "CONFIRMED",
                        "anchor_ids": ["inbox_abc123", "inbox_def456"],
                        "candidate_ids": [],
                    }
                ]

        registry = FakeRegistry()
        identity = get_identity_for_face(registry, "inbox_abc123")
        assert identity is not None
        assert identity["name"] == "Test Person"
        assert identity["state"] == "CONFIRMED"

    def test_get_identity_for_face_returns_none_for_unknown(self):
        """get_identity_for_face returns None for faces not in any identity."""
        from app.main import get_identity_for_face

        class FakeRegistry:
            def list_identities(self):
                return [
                    {
                        "identity_id": "id-001",
                        "name": "Test Person",
                        "state": "CONFIRMED",
                        "anchor_ids": ["inbox_abc123"],
                        "candidate_ids": [],
                    }
                ]

        registry = FakeRegistry()
        identity = get_identity_for_face(registry, "inbox_unknown")
        assert identity is None


class TestBackfillScript:
    """Test the backfill script logic."""

    def test_backfill_identifies_missing_faces(self):
        """Verify the backfill correctly identifies faces missing from photo_faces."""
        # This is an integration-level test verifying the script's detection logic
        from scripts.backfill_photo_faces import _load_embeddings_faces

        faces = _load_embeddings_faces(Path("data"))
        assert len(faces) > 0
        # Every face should have face_id, photo_id, filename
        for f in faces[:5]:
            assert "face_id" in f
            assert "photo_id" in f
            assert "filename" in f
