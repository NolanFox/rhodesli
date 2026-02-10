"""Tests for face count badge accuracy (BUG-005).

Root cause: _photo_cache was built from embeddings.npy raw detections
(which includes noise), not filtered to registered faces from photo_index.json.

Tests cover:
1. _build_caches filters faces to only registered ones
2. Badge denominator matches registered face count, not raw detection count
3. Photo view "N faces detected" matches filtered face list
4. No photo has an absurd face count (>50)
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient


class TestPhotoCacheFaceFiltering:
    """_build_caches must filter faces to only those in photo_index.json."""

    def test_photo_cache_faces_are_filtered(self):
        """Faces in _photo_cache must only include registered faces from photo_index."""
        import app.main as main
        # Reset cache to force rebuild
        main._photo_cache = None
        main._face_to_photo_cache = None
        main._build_caches()

        if not main._photo_cache:
            pytest.skip("No photo cache (no embeddings.npy)")

        # No single photo should have more than 50 faces (absurd threshold)
        for photo_id, photo_data in main._photo_cache.items():
            face_count = len(photo_data.get("faces", []))
            assert face_count <= 50, (
                f"Photo {photo_id} ({photo_data.get('filename')}) has {face_count} faces "
                f"— likely unfiltered raw detections from embeddings.npy"
            )

    def test_specific_photo_720025_has_2_faces(self):
        """Photo 603575393.720025.jpg should have exactly 2 registered faces."""
        import app.main as main
        main._photo_cache = None
        main._face_to_photo_cache = None
        main._build_caches()

        if not main._photo_cache:
            pytest.skip("No photo cache")

        # Find the photo by filename
        found = False
        for photo_id, photo_data in main._photo_cache.items():
            if "720025" in photo_data.get("filename", ""):
                found = True
                face_count = len(photo_data.get("faces", []))
                assert face_count == 2, (
                    f"Photo 720025 should have 2 faces (registered in photo_index), "
                    f"got {face_count}"
                )
                break
        if not found:
            pytest.skip("Photo 720025 not found in cache")

    def test_specific_photo_516167_not_63_faces(self):
        """Photo 603575318.516167.jpg must NOT have 63 faces (raw detection count)."""
        import app.main as main
        main._photo_cache = None
        main._face_to_photo_cache = None
        main._build_caches()

        if not main._photo_cache:
            pytest.skip("No photo cache")

        for photo_id, photo_data in main._photo_cache.items():
            if "516167" in photo_data.get("filename", ""):
                face_count = len(photo_data.get("faces", []))
                assert face_count != 63, (
                    f"Photo 516167 has 63 faces — still using raw embedding count"
                )
                assert face_count <= 30, (
                    f"Photo 516167 has {face_count} faces — should be ~21 registered"
                )
                break


class TestFaceCountBadge:
    """Badge on photo grid must use registered face count."""

    def test_render_photos_face_counts_reasonable(self):
        """All face counts in the photo grid data must be reasonable."""
        import app.main as main
        main._photo_cache = None
        main._face_to_photo_cache = None
        main._build_caches()

        if not main._photo_cache:
            pytest.skip("No photo cache")

        # Every photo's face list should be reasonable after filtering
        for photo_id, photo_data in main._photo_cache.items():
            face_count = len(photo_data.get("faces", []))
            assert face_count <= 50, (
                f"Photo {photo_id} ({photo_data.get('filename')}) has {face_count} faces — "
                f"badge would show wrong count"
            )


class TestPhotoViewFaceCount:
    """Photo detail view "N faces detected" must match filtered face list."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_lightbox_face_count_matches_overlays(self, client):
        """'N faces detected' must equal the number of face overlay divs."""
        import re
        import app.main as main

        # Reset cache
        main._photo_cache = None
        main._face_to_photo_cache = None
        main._build_caches()

        if not main._photo_cache:
            pytest.skip("No photo cache")

        # Pick a photo that has faces
        test_photo_id = None
        for pid, pdata in main._photo_cache.items():
            if len(pdata.get("faces", [])) >= 2:
                test_photo_id = pid
                break

        if not test_photo_id:
            pytest.skip("No photo with 2+ faces found")

        response = client.get(f"/photo/{test_photo_id}/partial")
        assert response.status_code == 200

        # Count face overlay divs
        overlay_count = response.text.count('data-face-id=')

        # Extract "N faces detected" number
        match = re.search(r'(\d+)\s+faces?\s+detected', response.text)
        if match:
            reported_count = int(match.group(1))
            assert reported_count == overlay_count, (
                f"Reported {reported_count} faces detected but rendered {overlay_count} overlays"
            )
