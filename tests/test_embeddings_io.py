"""
Tests for atomic embeddings I/O operations.

These tests verify that embeddings can be safely appended atomically
while preserving existing data.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest


class TestAtomicAppendEmbeddings:
    """Tests for atomic_append_embeddings function."""

    def test_atomic_append_creates_file_if_missing(self):
        """Should create new embeddings file if it doesn't exist."""
        from core.embeddings_io import atomic_append_embeddings

        with tempfile.TemporaryDirectory() as tmpdir:
            embeddings_path = Path(tmpdir) / "embeddings.npy"

            new_faces = [
                {"face_id": "face_001", "mu": [0.1] * 512},
                {"face_id": "face_002", "mu": [0.2] * 512},
            ]

            count = atomic_append_embeddings(embeddings_path, new_faces)

            assert count == 2
            assert embeddings_path.exists()

            # Verify contents
            loaded = np.load(embeddings_path, allow_pickle=True)
            assert len(loaded) == 2
            assert loaded[0]["face_id"] == "face_001"
            assert loaded[1]["face_id"] == "face_002"

    def test_atomic_append_preserves_existing(self):
        """Should preserve existing embeddings when appending."""
        from core.embeddings_io import atomic_append_embeddings

        with tempfile.TemporaryDirectory() as tmpdir:
            embeddings_path = Path(tmpdir) / "embeddings.npy"

            # Create initial file
            existing = [
                {"face_id": "existing_001", "mu": [0.3] * 512},
            ]
            np.save(embeddings_path, existing, allow_pickle=True)

            # Append new faces
            new_faces = [
                {"face_id": "new_001", "mu": [0.4] * 512},
                {"face_id": "new_002", "mu": [0.5] * 512},
            ]

            count = atomic_append_embeddings(embeddings_path, new_faces)

            assert count == 2

            # Verify all data preserved
            loaded = np.load(embeddings_path, allow_pickle=True)
            assert len(loaded) == 3
            face_ids = [f["face_id"] for f in loaded]
            assert "existing_001" in face_ids
            assert "new_001" in face_ids
            assert "new_002" in face_ids

    def test_atomic_append_empty_list_does_nothing(self):
        """Should not modify file when appending empty list."""
        from core.embeddings_io import atomic_append_embeddings

        with tempfile.TemporaryDirectory() as tmpdir:
            embeddings_path = Path(tmpdir) / "embeddings.npy"

            # Create initial file
            existing = [{"face_id": "existing_001", "mu": [0.3] * 512}]
            np.save(embeddings_path, existing, allow_pickle=True)

            count = atomic_append_embeddings(embeddings_path, [])

            assert count == 0

            # Verify unchanged
            loaded = np.load(embeddings_path, allow_pickle=True)
            assert len(loaded) == 1

    def test_atomic_append_creates_parent_dirs(self):
        """Should create parent directories if they don't exist."""
        from core.embeddings_io import atomic_append_embeddings

        with tempfile.TemporaryDirectory() as tmpdir:
            embeddings_path = Path(tmpdir) / "nested" / "dir" / "embeddings.npy"

            new_faces = [{"face_id": "face_001", "mu": [0.1] * 512}]

            count = atomic_append_embeddings(embeddings_path, new_faces)

            assert count == 1
            assert embeddings_path.exists()


class TestLoadEmbeddings:
    """Tests for loading embeddings."""

    def test_load_embeddings_returns_list(self):
        """Should return embeddings as a list of dicts."""
        from core.embeddings_io import load_embeddings

        with tempfile.TemporaryDirectory() as tmpdir:
            embeddings_path = Path(tmpdir) / "embeddings.npy"
            existing = [
                {"face_id": "face_001", "mu": [0.1] * 512},
                {"face_id": "face_002", "mu": [0.2] * 512},
            ]
            np.save(embeddings_path, existing, allow_pickle=True)

            loaded = load_embeddings(embeddings_path)

            assert isinstance(loaded, list)
            assert len(loaded) == 2

    def test_load_embeddings_missing_file_returns_empty(self):
        """Should return empty list for missing file."""
        from core.embeddings_io import load_embeddings

        with tempfile.TemporaryDirectory() as tmpdir:
            embeddings_path = Path(tmpdir) / "missing.npy"

            loaded = load_embeddings(embeddings_path)

            assert loaded == []
