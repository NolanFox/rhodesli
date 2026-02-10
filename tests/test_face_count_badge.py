"""Tests for face count badge accuracy (BUG-005).

Root cause: _photo_cache was built from embeddings.npy raw detections
(which includes noise), not filtered to registered faces from photo_index.json.

Tests cover:
1. _build_caches filters faces to only registered ones
2. Badge denominator matches registered face count, not raw detection count
3. Photo view "N faces detected" matches filtered face list
4. No photo has an absurd face count (>50)

All tests use synthetic fixtures — no production data files are touched.
"""

import hashlib
import json
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers to build synthetic data matching the real schema
# ---------------------------------------------------------------------------


def _photo_id(filename: str) -> str:
    """Mirror app.main.generate_photo_id — SHA256(basename)[:16]."""
    basename = Path(filename).name
    return hashlib.sha256(basename.encode("utf-8")).hexdigest()[:16]


def _face_id(filename: str, index: int) -> str:
    """Mirror app.main.generate_face_id — {stem}:face{index}."""
    stem = Path(filename).stem
    return f"{stem}:face{index}"


def _make_embedding_entry(filename: str, face_index: int, bbox=None):
    """Create one embedding dict matching the embeddings.npy schema."""
    if bbox is None:
        bbox = [10 * face_index, 10 * face_index, 50 + 10 * face_index, 50 + 10 * face_index]
    return {
        "filename": filename,
        "bbox": np.array(bbox, dtype=np.float32),
        "embeddings": np.random.randn(512).astype(np.float32),
        "det_score": 0.95,
        "quality": 0.8,
    }


def _make_photo_index(photos_spec: dict) -> dict:
    """Build a photo_index.json dict.

    photos_spec: {filename: [registered_face_ids]}
    """
    photos = {}
    face_to_photo = {}
    for filename, face_ids in photos_spec.items():
        pid = _photo_id(filename)
        photos[pid] = {
            "path": f"raw_photos/{filename}",
            "face_ids": list(face_ids),
            "source": "Test Collection",
        }
        for fid in face_ids:
            face_to_photo[fid] = pid
    return {
        "schema_version": 1,
        "photos": photos,
        "face_to_photo": face_to_photo,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def synthetic_data_dir(tmp_path):
    """Create a tmp dir with synthetic embeddings.npy and photo_index.json.

    Scenario modelling BUG-005:
    - photo_clean.jpg: 3 raw detections, all 3 registered -> 3 faces kept
    - photo_noisy.jpg: 10 raw detections, only 2 registered -> 2 faces kept
      (this mimics the newspaper photo with 63 detections / 21 registered)
    - photo_normal.jpg: 5 raw detections, 5 registered -> 5 faces kept
    """
    clean = "photo_clean.jpg"
    noisy = "photo_noisy.jpg"
    normal = "photo_normal.jpg"

    # -- embeddings.npy: raw detections --
    entries = []
    # photo_clean: 3 detections
    for i in range(3):
        entries.append(_make_embedding_entry(clean, i))
    # photo_noisy: 10 detections (noise faces)
    for i in range(10):
        entries.append(_make_embedding_entry(noisy, i))
    # photo_normal: 5 detections
    for i in range(5):
        entries.append(_make_embedding_entry(normal, i))

    emb_path = tmp_path / "embeddings.npy"
    np.save(emb_path, np.array(entries, dtype=object), allow_pickle=True)

    # -- photo_index.json: only registered faces --
    # photo_clean: register all 3
    clean_faces = {_face_id(clean, i) for i in range(3)}
    # photo_noisy: register only 2 of 10
    noisy_faces = {_face_id(noisy, 0), _face_id(noisy, 4)}
    # photo_normal: register all 5
    normal_faces = {_face_id(normal, i) for i in range(5)}

    pi = _make_photo_index({
        clean: clean_faces,
        noisy: noisy_faces,
        normal: normal_faces,
    })
    pi_path = tmp_path / "photo_index.json"
    pi_path.write_text(json.dumps(pi, indent=2))

    return tmp_path


@pytest.fixture()
def caches_from_synthetic(synthetic_data_dir):
    """Run _build_caches() against synthetic data and return (_photo_cache, _face_to_photo_cache)."""
    import app.main as main

    # Point data_path at our synthetic dir
    original_data_path = main.data_path
    main.data_path = synthetic_data_dir
    main._photo_cache = None
    main._face_to_photo_cache = None

    try:
        main._build_caches()
        yield main._photo_cache, main._face_to_photo_cache
    finally:
        # Restore original state so other tests are unaffected
        main.data_path = original_data_path
        main._photo_cache = None
        main._face_to_photo_cache = None


# ---------------------------------------------------------------------------
# Test classes — same names as original for backwards compatibility
# ---------------------------------------------------------------------------


class TestPhotoCacheFaceFiltering:
    """_build_caches must filter faces to only those in photo_index.json."""

    def test_photo_cache_faces_are_filtered(self, caches_from_synthetic):
        """Faces in _photo_cache must only include registered faces from photo_index."""
        photo_cache, _ = caches_from_synthetic

        assert photo_cache, "Photo cache should not be empty"

        # No single photo should have more than 50 faces (absurd threshold)
        for photo_id, photo_data in photo_cache.items():
            face_count = len(photo_data.get("faces", []))
            assert face_count <= 50, (
                f"Photo {photo_id} ({photo_data.get('filename')}) has {face_count} faces "
                f"— likely unfiltered raw detections from embeddings.npy"
            )

    def test_specific_photo_720025_has_2_faces(self, caches_from_synthetic):
        """Noisy photo should have exactly 2 registered faces (not all 10 raw detections).

        This models the original BUG-005 scenario where photo 720025 had 2 registered faces
        but the cache showed all raw detections.
        """
        photo_cache, _ = caches_from_synthetic

        # Find the noisy photo — it had 10 raw detections but only 2 registered
        noisy_pid = _photo_id("photo_noisy.jpg")
        assert noisy_pid in photo_cache, "Noisy photo should be in cache"

        face_count = len(photo_cache[noisy_pid].get("faces", []))
        assert face_count == 2, (
            f"Noisy photo should have 2 faces (registered in photo_index), "
            f"got {face_count}"
        )

    def test_specific_photo_516167_not_63_faces(self, caches_from_synthetic):
        """Noisy photo must NOT have the raw detection count (10), only the registered count (2).

        Models the original BUG-005 scenario where photo 516167 had 63 raw detections
        but only ~21 registered.
        """
        photo_cache, _ = caches_from_synthetic

        noisy_pid = _photo_id("photo_noisy.jpg")
        assert noisy_pid in photo_cache

        face_count = len(photo_cache[noisy_pid].get("faces", []))
        # Must NOT be 10 (the raw detection count)
        assert face_count != 10, (
            "Noisy photo has 10 faces — still using raw embedding count"
        )
        # Must be exactly 2 (the registered count)
        assert face_count == 2, (
            f"Noisy photo has {face_count} faces — should be 2 registered"
        )

    def test_clean_photo_keeps_all_faces(self, caches_from_synthetic):
        """When all detections are registered, all should be kept."""
        photo_cache, _ = caches_from_synthetic

        clean_pid = _photo_id("photo_clean.jpg")
        assert clean_pid in photo_cache

        face_count = len(photo_cache[clean_pid].get("faces", []))
        assert face_count == 3, (
            f"Clean photo should keep all 3 registered faces, got {face_count}"
        )

    def test_normal_photo_keeps_all_faces(self, caches_from_synthetic):
        """Normal photo with 5/5 registered should keep all 5."""
        photo_cache, _ = caches_from_synthetic

        normal_pid = _photo_id("photo_normal.jpg")
        assert normal_pid in photo_cache

        face_count = len(photo_cache[normal_pid].get("faces", []))
        assert face_count == 5, (
            f"Normal photo should keep all 5 registered faces, got {face_count}"
        )

    def test_face_to_photo_cache_only_has_registered_faces(self, caches_from_synthetic):
        """_face_to_photo_cache should only contain registered faces, not noise."""
        _, face_to_photo = caches_from_synthetic

        # Total registered faces: 3 (clean) + 2 (noisy) + 5 (normal) = 10
        assert len(face_to_photo) == 10, (
            f"face_to_photo should have 10 entries (registered only), got {len(face_to_photo)}"
        )

        # Noise faces from noisy photo should NOT be in the cache
        for i in [1, 2, 3, 5, 6, 7, 8, 9]:
            noise_fid = _face_id("photo_noisy.jpg", i)
            assert noise_fid not in face_to_photo, (
                f"Noise face {noise_fid} should not be in face_to_photo_cache"
            )


class TestFaceCountBadge:
    """Badge on photo grid must use registered face count."""

    def test_render_photos_face_counts_reasonable(self, caches_from_synthetic):
        """All face counts in the photo grid data must be reasonable."""
        photo_cache, _ = caches_from_synthetic

        assert photo_cache, "Photo cache should not be empty"

        # Every photo's face list should be reasonable after filtering
        for photo_id, photo_data in photo_cache.items():
            face_count = len(photo_data.get("faces", []))
            assert face_count <= 50, (
                f"Photo {photo_id} ({photo_data.get('filename')}) has {face_count} faces — "
                f"badge would show wrong count"
            )


class TestPhotoViewFaceCount:
    """Photo detail view "N faces detected" must match filtered face list."""

    def test_lightbox_face_count_matches_overlays(self, caches_from_synthetic):
        """The number of faces in the cache should match what overlays would render.

        In production, the /photo/{id}/partial route renders one overlay div per face
        in _photo_cache[photo_id]["faces"]. This test verifies the cache has the correct
        filtered count, which the route uses to render overlays and the "N faces detected"
        label.
        """
        photo_cache, _ = caches_from_synthetic

        # For each photo, the overlay count would equal len(faces)
        # and the "N faces detected" label uses the same list.
        # Verify they match (they come from the same source after filtering).
        for photo_id, photo_data in photo_cache.items():
            faces = photo_data.get("faces", [])
            # Each face must have a face_id (required for overlay rendering)
            for face in faces:
                assert "face_id" in face, (
                    f"Face in photo {photo_id} missing face_id — overlay can't render"
                )
                assert "bbox" in face, (
                    f"Face {face['face_id']} in photo {photo_id} missing bbox — overlay can't position"
                )

        # Specific check: noisy photo should report 2, not 10
        noisy_pid = _photo_id("photo_noisy.jpg")
        noisy_faces = photo_cache[noisy_pid]["faces"]
        assert len(noisy_faces) == 2, (
            f"Lightbox for noisy photo would show {len(noisy_faces)} overlays, expected 2"
        )
