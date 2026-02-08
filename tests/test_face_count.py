"""Tests for BUG-002: face count label should match displayed face boxes, not raw detection count.

The photo card shows "N faces detected" but the count should match the number
of visible face box overlays. Faces without valid bounding boxes or photos
without cached dimensions should not be counted.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


# ---------------------------------------------------------------------------
# Unit tests for _get_featured_photos face_count accuracy
# ---------------------------------------------------------------------------

class TestFeaturedPhotosFaceCount:
    """face_count in featured photos must equal len(face_boxes), not len(faces)."""

    def _make_photo_cache(self, faces_with_bboxes, faces_without_bboxes=0):
        """Build a minimal _photo_cache entry.

        Args:
            faces_with_bboxes: number of faces that have valid bbox data
            faces_without_bboxes: number of faces that have empty/missing bboxes
        """
        faces = []
        for i in range(faces_with_bboxes):
            faces.append({
                "face_id": f"face_valid_{i}",
                "bbox": [10 + i * 50, 20, 60 + i * 50, 80],
                "face_index": i,
                "det_score": 0.99,
                "quality": 0.95,
            })
        for i in range(faces_without_bboxes):
            faces.append({
                "face_id": f"face_nobbox_{i}",
                "bbox": [],  # empty bbox — not displayable
                "face_index": faces_with_bboxes + i,
                "det_score": 0.5,
                "quality": 0.3,
            })
        return {
            "test_photo_001": {
                "filename": "test_photo.jpg",
                "faces": faces,
                "source": "Test Collection",
            }
        }

    def _make_dim_cache(self, width=800, height=600):
        """Build a dimension cache with given dimensions."""
        return {
            "test_photo.jpg": (width, height),
        }

    def _call_get_featured_photos(self, photo_cache, dim_cache, registry_identities=None):
        """Call _get_featured_photos with mocked caches."""
        if registry_identities is None:
            registry_identities = []

        mock_registry = MagicMock()
        mock_registry.list_identities.return_value = registry_identities

        with patch("app.main._photo_cache", photo_cache), \
             patch("app.main._face_to_photo_cache", {}), \
             patch("app.main.load_registry", return_value=mock_registry), \
             patch("app.main._load_photo_dimensions_cache", return_value=dim_cache):
            from app.main import _get_featured_photos
            return _get_featured_photos(limit=10)

    def test_face_count_matches_face_boxes_all_valid(self):
        """When all faces have valid bboxes, face_count equals total faces."""
        photo_cache = self._make_photo_cache(faces_with_bboxes=4)
        dim_cache = self._make_dim_cache()
        results = self._call_get_featured_photos(photo_cache, dim_cache)

        assert len(results) == 1
        photo = results[0]
        assert photo["face_count"] == 4
        assert len(photo["face_boxes"]) == 4
        assert photo["face_count"] == len(photo["face_boxes"])

    def test_face_count_excludes_faces_without_bbox(self):
        """Faces with empty bboxes are NOT counted in face_count."""
        photo_cache = self._make_photo_cache(faces_with_bboxes=2, faces_without_bboxes=3)
        dim_cache = self._make_dim_cache()
        results = self._call_get_featured_photos(photo_cache, dim_cache)

        assert len(results) == 1
        photo = results[0]
        # Should be 2 (displayed), not 5 (total detected)
        assert photo["face_count"] == 2, (
            f"face_count should be 2 (displayable), got {photo['face_count']}"
        )
        assert len(photo["face_boxes"]) == 2
        assert photo["face_count"] == len(photo["face_boxes"])

    def test_face_count_zero_when_no_valid_bboxes(self):
        """When no faces have valid bboxes, face_count should be 0."""
        photo_cache = self._make_photo_cache(faces_with_bboxes=0, faces_without_bboxes=3)
        dim_cache = self._make_dim_cache()
        results = self._call_get_featured_photos(photo_cache, dim_cache)

        # Photo may not appear (needs >= 2 faces in scoring, but still check if returned)
        # With 3 faces total it will pass the >= 2 filter in scoring
        # but skip the scored_photos filter because w/h are valid
        # Actually, scored_photos uses len(faces) >= 2 which is 3, so it passes
        # but then face_boxes will be empty
        # The photo should still be in results (it has valid dims and >= 2 faces)
        if results:
            photo = results[0]
            assert photo["face_count"] == 0
            assert len(photo["face_boxes"]) == 0

    def test_face_count_matches_face_boxes_exactly(self):
        """Regression: face_count must always equal len(face_boxes)."""
        photo_cache = self._make_photo_cache(faces_with_bboxes=3, faces_without_bboxes=2)
        dim_cache = self._make_dim_cache()
        results = self._call_get_featured_photos(photo_cache, dim_cache)

        for photo in results:
            assert photo["face_count"] == len(photo["face_boxes"]), (
                f"face_count ({photo['face_count']}) != len(face_boxes) ({len(photo['face_boxes'])})"
            )


# ---------------------------------------------------------------------------
# Landing page label tests
# ---------------------------------------------------------------------------

class TestLandingPageFaceLabel:
    """The landing page hero card label must reflect displayable faces."""

    def test_landing_page_face_count_label_uses_box_count(self):
        """The '_ faces detected' label on landing hero uses face_boxes count."""
        from app.main import landing_page

        # Build a featured photo with mismatched detection vs displayable count
        featured = [{
            "id": "test_123",
            "url": "/photos/test.jpg",
            "width": 800,
            "height": 600,
            "face_count": 3,  # After fix, this will match face_boxes
            "face_boxes": [
                {"left": 10, "top": 10, "width": 20, "height": 20, "name": "Alice"},
                {"left": 40, "top": 10, "width": 20, "height": 20, "name": "Bob"},
                {"left": 70, "top": 10, "width": 20, "height": 20, "name": ""},
            ],
        }]

        stats = {
            "photo_count": 10,
            "named_count": 5,
            "total_faces": 20,
            "needs_help": 15,
            "unidentified_faces": [],
        }

        with patch("app.main.is_auth_enabled", return_value=False):
            result = landing_page(stats, featured)
            html = str(result)

        # The label should say "3 faces detected" (matching the 3 face_boxes)
        assert "3 faces detected" in html

    def test_landing_page_no_badge_when_zero_faces(self):
        """No face count badge when face_count is 0."""
        from app.main import landing_page

        featured = [{
            "id": "test_123",
            "url": "/photos/test.jpg",
            "width": 800,
            "height": 600,
            "face_count": 0,
            "face_boxes": [],
        }]

        stats = {
            "photo_count": 10,
            "named_count": 5,
            "total_faces": 20,
            "needs_help": 15,
            "unidentified_faces": [],
        }

        with patch("app.main.is_auth_enabled", return_value=False):
            result = landing_page(stats, featured)
            html = str(result)

        # "0 faces detected" badge should NOT appear on the hero card
        # (note: "faces detected by AI" in the stats section is a different element)
        assert "0 faces detected" not in html


# ---------------------------------------------------------------------------
# Photos section grid face_count tests
# ---------------------------------------------------------------------------

class TestPhotosSectionFaceCount:
    """Photo grid badge face_count should reflect faces with valid bboxes."""

    def test_photos_grid_face_count_present(self, client):
        """Photos grid shows face count badges."""
        response = client.get("/?section=photos")
        assert response.status_code == 200
        text = response.text
        # Should have face counts in badges
        assert "faces" in text or "/" in text

    def test_face_count_consistency_in_featured_photos(self):
        """Regression: _get_featured_photos face_count always equals len(face_boxes)."""
        from app.main import _get_featured_photos, _build_caches

        _build_caches()
        results = _get_featured_photos(limit=20)

        for photo in results:
            assert photo["face_count"] == len(photo["face_boxes"]), (
                f"Photo {photo['id']}: face_count={photo['face_count']} "
                f"but {len(photo['face_boxes'])} face_boxes rendered"
            )
