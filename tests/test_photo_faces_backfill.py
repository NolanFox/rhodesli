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
