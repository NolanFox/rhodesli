"""Tests for photo ID consistency between embeddings and photo_index.json.

Verifies that the source lookup fallback works correctly when photo IDs
differ between systems (SHA256-based in embeddings vs inbox-style in
photo_index.json).
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_photo_index():
    """Load photo_index.json."""
    path = DATA_DIR / "photo_index.json"
    if not path.exists():
        pytest.skip("photo_index.json not found")
    with open(path) as f:
        return json.load(f)


class TestPhotoSourceLookup:
    """Test that _build_caches correctly resolves sources for all photos."""

    def test_all_photos_have_sources(self):
        """Every photo in _photo_cache should have a non-empty source after _build_caches."""
        import app.main as main

        # Reset caches to force rebuild
        main._photo_cache = None
        main._face_to_photo_cache = None
        main._build_caches()

        if not main._photo_cache:
            pytest.skip("No embeddings data available")

        missing_source = []
        for photo_id, photo_data in main._photo_cache.items():
            source = photo_data.get("source", "")
            if not source:
                missing_source.append((photo_id, photo_data.get("filename", "unknown")))

        assert missing_source == [], (
            f"{len(missing_source)} photos have no source: "
            + ", ".join(f"{pid} ({fn})" for pid, fn in missing_source[:5])
        )

    def test_betty_capeluto_collection_count(self):
        """All 13 Betty Capeluto photos should be findable by source filter."""
        import app.main as main

        main._photo_cache = None
        main._face_to_photo_cache = None
        main._build_caches()

        if not main._photo_cache:
            pytest.skip("No embeddings data available")

        betty_photos = [
            pid for pid, pdata in main._photo_cache.items()
            if pdata.get("source") == "Betty Capeluto Miami Collection"
        ]
        assert len(betty_photos) == 13, (
            f"Expected 13 Betty Capeluto photos, got {len(betty_photos)}"
        )

    def test_all_collections_represented(self):
        """All collections in photo_index.json should appear in _photo_cache sources."""
        import app.main as main

        pi = load_photo_index()

        # Get expected collections from photo_index.json
        expected_sources = set()
        for photo_data in pi["photos"].values():
            source = photo_data.get("source", "")
            if source:
                expected_sources.add(source)

        main._photo_cache = None
        main._face_to_photo_cache = None
        main._build_caches()

        if not main._photo_cache:
            pytest.skip("No embeddings data available")

        actual_sources = set()
        for photo_data in main._photo_cache.values():
            source = photo_data.get("source", "")
            if source:
                actual_sources.add(source)

        missing = expected_sources - actual_sources
        assert missing == set(), f"Collections missing from _photo_cache: {missing}"


class TestPhotoIndexConsistency:
    """Test that photo_index.json and embeddings.npy are consistent."""

    def test_photo_counts_match(self):
        """photo_index.json and embeddings should have same number of unique photos."""
        import app.main as main

        pi = load_photo_index()

        main._photo_cache = None
        main._face_to_photo_cache = None
        main._build_caches()

        if not main._photo_cache:
            pytest.skip("No embeddings data available")

        index_count = len(pi["photos"])
        cache_count = len(main._photo_cache)
        assert cache_count == index_count, (
            f"Embeddings have {cache_count} photos but photo_index.json has {index_count}"
        )

    def test_every_photo_index_path_in_embeddings(self):
        """Every photo path in photo_index.json should have a matching entry in embeddings."""
        import app.main as main

        pi = load_photo_index()

        main._photo_cache = None
        main._face_to_photo_cache = None
        main._build_caches()

        if not main._photo_cache:
            pytest.skip("No embeddings data available")

        # Build filename set from _photo_cache
        cache_filenames = set()
        for photo_data in main._photo_cache.values():
            cache_filenames.add(Path(photo_data["filename"]).name)

        # Check every photo_index.json entry has a matching filename
        missing = []
        for pid, pdata in pi["photos"].items():
            path = pdata.get("path", "")
            if path and Path(path).name not in cache_filenames:
                missing.append((pid, path))

        assert missing == [], (
            f"{len(missing)} photo_index entries not in embeddings: "
            + ", ".join(f"{pid}" for pid, _ in missing[:5])
        )

    def test_no_empty_source_in_photo_index(self):
        """Every photo in photo_index.json should have a non-empty source."""
        pi = load_photo_index()

        missing = []
        for pid, pdata in pi["photos"].items():
            if not pdata.get("source"):
                missing.append(pid)

        assert missing == [], f"{len(missing)} photos have no source in photo_index.json"
