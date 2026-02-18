"""Tests for age on face overlays in the photo viewer.

When a confirmed identity has a birth year AND the photo has a date estimate,
the face overlay should show "Name, ~age" (e.g., "Big Leon, ~32").
When either is missing, only the name should appear.

Session 48 — completing Phase 2F from Session 47 prompt.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestAgeOnFaceOverlay:
    """Age display on face overlays in photo_view_content()."""

    @patch("app.main._load_date_labels")
    @patch("app.main._get_birth_year")
    @patch("app.main.get_identity_for_face")
    @patch("app.main.load_registry")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.get_photo_metadata")
    def test_age_shown_with_confirmed_birth_year_and_photo_date(
        self, mock_meta, mock_dim, mock_reg, mock_ident, mock_birth, mock_labels
    ):
        """Confirmed identity with birth year + photo with date => shows age."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [{"face_id": "face1", "bbox": [100, 100, 200, 200]}],
            "source": "Test",
        }
        mock_reg.return_value = MagicMock()
        mock_ident.return_value = {
            "identity_id": "id-123",
            "name": "Big Leon",
            "state": "CONFIRMED",
            "anchor_ids": ["face1"],
            "candidate_ids": [],
        }
        # Birth year 1920, confirmed
        mock_birth.return_value = (1920, "confirmed", None)
        # Photo from 1952
        mock_labels.return_value = {"p1": {"best_year_estimate": 1952}}

        result = photo_view_content("p1", is_partial=True)
        html = to_xml(result)

        # Should show "Big Leon, ~32"
        assert "Big Leon, ~32" in html

    @patch("app.main._load_date_labels")
    @patch("app.main._get_birth_year")
    @patch("app.main.get_identity_for_face")
    @patch("app.main.load_registry")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.get_photo_metadata")
    def test_no_age_without_confirmed_birth_year(
        self, mock_meta, mock_dim, mock_reg, mock_ident, mock_birth, mock_labels
    ):
        """Confirmed identity WITHOUT birth year => name only, no age."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [{"face_id": "face1", "bbox": [100, 100, 200, 200]}],
            "source": "Test",
        }
        mock_reg.return_value = MagicMock()
        mock_ident.return_value = {
            "identity_id": "id-123",
            "name": "Big Leon",
            "state": "CONFIRMED",
            "anchor_ids": ["face1"],
            "candidate_ids": [],
        }
        # No birth year
        mock_birth.return_value = (None, None, None)
        mock_labels.return_value = {"p1": {"best_year_estimate": 1952}}

        result = photo_view_content("p1", is_partial=True)
        html = to_xml(result)

        # Should show name only, no tilde-age
        assert "Big Leon" in html
        assert "~" not in html.split("Big Leon")[1].split("<")[0]

    @patch("app.main._load_date_labels")
    @patch("app.main._get_birth_year")
    @patch("app.main.get_identity_for_face")
    @patch("app.main.load_registry")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.get_photo_metadata")
    def test_no_age_without_photo_date(
        self, mock_meta, mock_dim, mock_reg, mock_ident, mock_birth, mock_labels
    ):
        """Confirmed identity with birth year but photo WITHOUT date => name only."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [{"face_id": "face1", "bbox": [100, 100, 200, 200]}],
            "source": "Test",
        }
        mock_reg.return_value = MagicMock()
        mock_ident.return_value = {
            "identity_id": "id-123",
            "name": "Big Leon",
            "state": "CONFIRMED",
            "anchor_ids": ["face1"],
            "candidate_ids": [],
        }
        # Birth year exists
        mock_birth.return_value = (1920, "confirmed", None)
        # No date for this photo
        mock_labels.return_value = {}

        result = photo_view_content("p1", is_partial=True)
        html = to_xml(result)

        # Should show name only
        assert "Big Leon" in html
        assert "~" not in html.split("Big Leon")[1].split("<")[0]

    @patch("app.main._load_date_labels")
    @patch("app.main._get_birth_year")
    @patch("app.main.get_identity_for_face")
    @patch("app.main.load_registry")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.get_photo_metadata")
    def test_no_age_on_proposed_identity(
        self, mock_meta, mock_dim, mock_reg, mock_ident, mock_birth, mock_labels
    ):
        """PROPOSED identity even with birth year + photo date => no age (not confirmed)."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [{"face_id": "face1", "bbox": [100, 100, 200, 200]}],
            "source": "Test",
        }
        mock_reg.return_value = MagicMock()
        mock_ident.return_value = {
            "identity_id": "id-123",
            "name": "Possible Match",
            "state": "PROPOSED",
            "anchor_ids": [],
            "candidate_ids": ["face1"],
        }
        # Even though birth year and date exist, PROPOSED should not show age
        mock_birth.return_value = (1920, "confirmed", None)
        mock_labels.return_value = {"p1": {"best_year_estimate": 1952}}

        result = photo_view_content("p1", is_partial=True)
        html = to_xml(result)

        # PROPOSED faces use hover tooltip, should not have age
        assert "~32" not in html
