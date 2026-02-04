"""
Tests for the File Hash Registry.

The FileHashRegistry enables idempotent ingestion by tracking
which files have already been processed based on content hash.
"""

import json
import tempfile
from pathlib import Path

import pytest


class TestComputeHash:
    """Tests for SHA256 hash computation."""

    def test_compute_hash_is_deterministic(self):
        """Same file content should always produce the same hash."""
        from core.file_hash_registry import FileHashRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.jpg"
            filepath.write_bytes(b"test image content")

            hash1 = FileHashRegistry.compute_hash(filepath)
            hash2 = FileHashRegistry.compute_hash(filepath)

            assert hash1 == hash2
            assert len(hash1) == 64  # SHA256 produces 64 hex chars

    def test_different_content_produces_different_hash(self):
        """Different file content should produce different hashes."""
        from core.file_hash_registry import FileHashRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            file_a = Path(tmpdir) / "a.jpg"
            file_b = Path(tmpdir) / "b.jpg"

            file_a.write_bytes(b"content A")
            file_b.write_bytes(b"content B")

            hash_a = FileHashRegistry.compute_hash(file_a)
            hash_b = FileHashRegistry.compute_hash(file_b)

            assert hash_a != hash_b


class TestRegisterAndLookup:
    """Tests for registering and looking up file hashes."""

    def test_register_and_lookup(self):
        """Registered files should be retrievable via lookup."""
        from core.file_hash_registry import FileHashRegistry

        registry = FileHashRegistry()
        registry.register_file(
            file_hash="abc123hash",
            face_ids=["face_001", "face_002"],
            job_id="job_xyz",
            filename="photo.jpg",
        )

        result = registry.lookup("abc123hash")

        assert result is not None
        assert result["face_ids"] == ["face_001", "face_002"]
        assert result["job_id"] == "job_xyz"
        assert result["filename"] == "photo.jpg"

    def test_lookup_returns_none_for_unknown_hash(self):
        """Lookup should return None for unregistered hashes."""
        from core.file_hash_registry import FileHashRegistry

        registry = FileHashRegistry()

        result = registry.lookup("unknown_hash")

        assert result is None

    def test_get_face_ids_for_hash(self):
        """get_face_ids_for_hash should return face IDs or empty list."""
        from core.file_hash_registry import FileHashRegistry

        registry = FileHashRegistry()
        registry.register_file(
            file_hash="hash123",
            face_ids=["face_a", "face_b"],
            job_id="job_1",
            filename="file.jpg",
        )

        # Known hash
        face_ids = registry.get_face_ids_for_hash("hash123")
        assert face_ids == ["face_a", "face_b"]

        # Unknown hash
        face_ids = registry.get_face_ids_for_hash("unknown")
        assert face_ids == []


class TestRemoveByJob:
    """Tests for removing entries by job_id."""

    def test_remove_by_job_removes_matching_entries(self):
        """remove_by_job should remove all entries for the specified job."""
        from core.file_hash_registry import FileHashRegistry

        registry = FileHashRegistry()
        registry.register_file("hash1", ["face_1"], "job_a", "file1.jpg")
        registry.register_file("hash2", ["face_2"], "job_a", "file2.jpg")
        registry.register_file("hash3", ["face_3"], "job_b", "file3.jpg")

        removed = registry.remove_by_job("job_a")

        assert set(removed) == {"hash1", "hash2"}
        assert registry.lookup("hash1") is None
        assert registry.lookup("hash2") is None
        assert registry.lookup("hash3") is not None  # job_b entry retained

    def test_remove_by_job_returns_empty_list_when_no_match(self):
        """remove_by_job should return empty list when no entries match."""
        from core.file_hash_registry import FileHashRegistry

        registry = FileHashRegistry()
        registry.register_file("hash1", ["face_1"], "job_a", "file1.jpg")

        removed = registry.remove_by_job("nonexistent_job")

        assert removed == []
        assert registry.lookup("hash1") is not None


class TestPersistence:
    """Tests for saving and loading registry."""

    def test_save_creates_json_file(self):
        """save() should create a JSON file with correct structure."""
        from core.file_hash_registry import FileHashRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "hashes.json"
            registry = FileHashRegistry()
            registry.register_file("hash1", ["face_1"], "job_1", "file.jpg")

            registry.save(path)

            assert path.exists()
            with open(path) as f:
                data = json.load(f)
            assert "schema_version" in data
            assert data["schema_version"] == 1
            assert "hashes" in data
            assert "hash1" in data["hashes"]

    def test_load_restores_registry(self):
        """load() should restore saved registry state."""
        from core.file_hash_registry import FileHashRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "hashes.json"

            # Save
            registry1 = FileHashRegistry()
            registry1.register_file("hash1", ["face_1", "face_2"], "job_1", "file.jpg")
            registry1.save(path)

            # Load
            registry2 = FileHashRegistry.load(path)

            result = registry2.lookup("hash1")
            assert result is not None
            assert result["face_ids"] == ["face_1", "face_2"]
            assert result["job_id"] == "job_1"

    def test_load_returns_empty_registry_for_missing_file(self):
        """load() should return empty registry if file doesn't exist."""
        from core.file_hash_registry import FileHashRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nonexistent.json"

            registry = FileHashRegistry.load(path)

            assert registry.lookup("anything") is None
