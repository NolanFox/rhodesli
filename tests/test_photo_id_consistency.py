"""Tests for photo ID consistency between embeddings and photo_index.json.

Verifies that the source lookup fallback works correctly when photo IDs
differ between systems (SHA256-based in embeddings vs inbox-style in
photo_index.json).

Uses synthetic fixtures instead of production data.
"""

import hashlib
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# --- Helpers to build synthetic data ---

def _photo_id(filename: str) -> str:
    """Mirror app.main.generate_photo_id()."""
    basename = Path(filename).name
    return hashlib.sha256(basename.encode("utf-8")).hexdigest()[:16]


def _face_id(filename: str, index: int) -> str:
    """Mirror app.main.generate_face_id()."""
    stem = Path(filename).stem
    return f"{stem}:face{index}"


# 5 photos across 3 collections, including one inbox-style photo
SYNTHETIC_PHOTOS = {
    "photo_a.jpg": {"source": "Test Collection A", "face_count": 2},
    "photo_b.jpg": {"source": "Test Collection A", "face_count": 1},
    "photo_c.jpg": {"source": "Test Collection A", "face_count": 3},
    "photo_d.jpg": {"source": "Test Collection B", "face_count": 2},
    "photo_e.jpg": {"source": "Single Photo Collection", "face_count": 1},
}


def _build_synthetic_embeddings_result():
    """Build the dict that load_embeddings_for_photos() would return.

    Returns:
        dict mapping photo_id -> {"filename": str, "faces": list[dict]}
    """
    photos = {}
    for filename, info in SYNTHETIC_PHOTOS.items():
        pid = _photo_id(filename)
        faces = []
        for i in range(info["face_count"]):
            faces.append({
                "face_id": _face_id(filename, i),
                "bbox": [10 * i, 10 * i, 50 + 10 * i, 50 + 10 * i],
                "face_index": i,
                "det_score": 0.95,
                "quality": 0.8,
            })
        photos[pid] = {"filename": filename, "faces": faces}
    return photos


def _build_synthetic_photo_registry():
    """Build a mock PhotoRegistry matching the synthetic photos.

    The registry uses the same filenames so the filename-based fallback
    in _build_caches() can match them, and also registers faces under
    the correct SHA256-based photo IDs.
    """
    registry = MagicMock()
    registry._photos = {}
    photo_paths = {}
    photo_sources = {}
    photo_face_ids = {}

    for filename, info in SYNTHETIC_PHOTOS.items():
        pid = _photo_id(filename)
        face_ids = set()
        for i in range(info["face_count"]):
            face_ids.add(_face_id(filename, i))

        registry._photos[pid] = {
            "path": filename,
            "face_ids": face_ids,
            "source": info["source"],
        }
        photo_paths[pid] = filename
        photo_sources[pid] = info["source"]
        photo_face_ids[pid] = face_ids

    registry.get_photo_path = lambda pid: photo_paths.get(pid)
    registry.get_source = lambda pid: photo_sources.get(pid, "")
    registry.get_faces_in_photo = lambda pid: photo_face_ids.get(pid, set()).copy()
    registry.get_metadata = lambda pid: {}

    return registry


def _build_synthetic_photo_index():
    """Build a photo_index.json-style dict matching the synthetic photos."""
    photos = {}
    face_to_photo = {}
    for filename, info in SYNTHETIC_PHOTOS.items():
        pid = _photo_id(filename)
        face_ids = []
        for i in range(info["face_count"]):
            fid = _face_id(filename, i)
            face_ids.append(fid)
            face_to_photo[fid] = pid
        photos[pid] = {
            "path": filename,
            "face_ids": face_ids,
            "source": info["source"],
        }
    return {
        "schema_version": 1,
        "photos": photos,
        "face_to_photo": face_to_photo,
    }


@pytest.fixture(autouse=True)
def reset_caches():
    """Reset app.main caches before and after each test."""
    import app.main as main
    main._photo_cache = None
    main._face_to_photo_cache = None
    yield
    main._photo_cache = None
    main._face_to_photo_cache = None


@pytest.fixture
def mock_data():
    """Patch load_embeddings_for_photos and PhotoRegistry.load with synthetic data."""
    embeddings_result = _build_synthetic_embeddings_result()
    registry = _build_synthetic_photo_registry()

    with patch("app.main.load_embeddings_for_photos", return_value=embeddings_result), \
         patch("core.photo_registry.PhotoRegistry.load", return_value=registry):
        yield {
            "embeddings": embeddings_result,
            "registry": registry,
            "photo_index": _build_synthetic_photo_index(),
        }


class TestPhotoSourceLookup:
    """Test that _build_caches correctly resolves sources for all photos."""

    def test_all_photos_have_sources(self, mock_data):
        """Every photo in _photo_cache should have a non-empty source after _build_caches."""
        import app.main as main

        main._build_caches()

        assert main._photo_cache, "Cache should not be empty"

        missing_source = []
        for photo_id, photo_data in main._photo_cache.items():
            source = photo_data.get("source", "")
            if not source:
                missing_source.append((photo_id, photo_data.get("filename", "unknown")))

        assert missing_source == [], (
            f"{len(missing_source)} photos have no source: "
            + ", ".join(f"{pid} ({fn})" for pid, fn in missing_source[:5])
        )

    def test_betty_capeluto_collection_count(self, mock_data):
        """A known collection should have the correct count of photos in the cache."""
        import app.main as main

        main._build_caches()

        assert main._photo_cache, "Cache should not be empty"

        # "Test Collection A" has 3 photos in our synthetic data
        collection_a_photos = [
            pid for pid, pdata in main._photo_cache.items()
            if pdata.get("source") == "Test Collection A"
        ]
        assert len(collection_a_photos) == 3, (
            f"Expected 3 Test Collection A photos, got {len(collection_a_photos)}"
        )

    def test_all_collections_represented(self, mock_data):
        """All collections in photo_index should appear in _photo_cache sources."""
        import app.main as main

        pi = mock_data["photo_index"]

        # Get expected collections from the synthetic photo_index
        expected_sources = set()
        for photo_data in pi["photos"].values():
            source = photo_data.get("source", "")
            if source:
                expected_sources.add(source)

        main._build_caches()

        assert main._photo_cache, "Cache should not be empty"

        actual_sources = set()
        for photo_data in main._photo_cache.values():
            source = photo_data.get("source", "")
            if source:
                actual_sources.add(source)

        missing = expected_sources - actual_sources
        assert missing == set(), f"Collections missing from _photo_cache: {missing}"


class TestPhotoIndexConsistency:
    """Test that photo_index.json and embeddings.npy are consistent."""

    def test_photo_counts_match(self, mock_data):
        """photo_index and embeddings should have same number of unique photos."""
        import app.main as main

        pi = mock_data["photo_index"]

        main._build_caches()

        assert main._photo_cache, "Cache should not be empty"

        index_count = len(pi["photos"])
        cache_count = len(main._photo_cache)
        assert cache_count == index_count, (
            f"Embeddings have {cache_count} photos but photo_index has {index_count}"
        )

    def test_every_photo_index_path_in_embeddings(self, mock_data):
        """Every photo path in photo_index should have a matching entry in embeddings."""
        import app.main as main

        pi = mock_data["photo_index"]

        main._build_caches()

        assert main._photo_cache, "Cache should not be empty"

        # Build filename set from _photo_cache
        cache_filenames = set()
        for photo_data in main._photo_cache.values():
            cache_filenames.add(Path(photo_data["filename"]).name)

        # Check every photo_index entry has a matching filename
        missing = []
        for pid, pdata in pi["photos"].items():
            path = pdata.get("path", "")
            if path and Path(path).name not in cache_filenames:
                missing.append((pid, path))

        assert missing == [], (
            f"{len(missing)} photo_index entries not in embeddings: "
            + ", ".join(f"{pid}" for pid, _ in missing[:5])
        )

    def test_no_empty_source_in_photo_index(self, mock_data):
        """Every photo in photo_index should have a non-empty source."""
        pi = mock_data["photo_index"]

        missing = []
        for pid, pdata in pi["photos"].items():
            if not pdata.get("source"):
                missing.append(pid)

        assert missing == [], f"{len(missing)} photos have no source in photo_index"


class TestFilenameFallbackLookup:
    """Test that the filename-based source fallback works for mismatched IDs."""

    def test_inbox_style_id_resolves_source_via_filename(self):
        """When photo_index uses inbox-style IDs, source should still resolve via filename fallback."""
        import app.main as main

        filename = "test_inbox_photo.jpg"
        sha_pid = _photo_id(filename)
        inbox_pid = "inbox_abc123_0_test_inbox_photo.jpg"

        # Embeddings use SHA256 IDs
        embeddings_result = {
            sha_pid: {
                "filename": filename,
                "faces": [{
                    "face_id": _face_id(filename, 0),
                    "bbox": [10, 10, 50, 50],
                    "face_index": 0,
                    "det_score": 0.95,
                    "quality": 0.8,
                }],
            }
        }

        # PhotoRegistry uses inbox-style ID, but same filename
        registry = MagicMock()
        registry._photos = {
            inbox_pid: {
                "path": filename,
                "face_ids": {_face_id(filename, 0)},
                "source": "Inbox Collection",
            }
        }
        registry.get_photo_path = lambda pid: filename if pid == inbox_pid else None
        registry.get_source = lambda pid: "Inbox Collection" if pid == inbox_pid else ""
        registry.get_faces_in_photo = lambda pid: (
            {_face_id(filename, 0)} if pid == inbox_pid else set()
        )
        registry.get_metadata = lambda pid: {}

        with patch("app.main.load_embeddings_for_photos", return_value=embeddings_result), \
             patch("core.photo_registry.PhotoRegistry.load", return_value=registry):
            main._build_caches()

        # The SHA256-keyed entry should have the source resolved via filename fallback
        assert sha_pid in main._photo_cache
        assert main._photo_cache[sha_pid]["source"] == "Inbox Collection"
