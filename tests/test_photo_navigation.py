"""Tests for Phase 2: Photo navigation with keyboard arrows and lightbox prev/next."""

import pytest
from unittest.mock import patch, MagicMock


class TestPhotoNavUrl:
    """Tests for the _photo_nav_url helper function."""

    def test_first_photo_has_next_only(self):
        """First photo in collection has next_id but no prev_id."""
        from app.main import _photo_nav_url
        photos = [{"photo_id": f"p{i}"} for i in range(5)]
        url = _photo_nav_url("p0", 0, photos, 5)
        assert "prev_id" not in url
        assert "next_id=p1" in url
        assert "nav_idx=0" in url
        assert "nav_total=5" in url

    def test_last_photo_has_prev_only(self):
        """Last photo in collection has prev_id but no next_id."""
        from app.main import _photo_nav_url
        photos = [{"photo_id": f"p{i}"} for i in range(5)]
        url = _photo_nav_url("p4", 4, photos, 5)
        assert "prev_id=p3" in url
        assert "next_id" not in url

    def test_middle_photo_has_both(self):
        """Middle photo has both prev_id and next_id."""
        from app.main import _photo_nav_url
        photos = [{"photo_id": f"p{i}"} for i in range(5)]
        url = _photo_nav_url("p2", 2, photos, 5)
        assert "prev_id=p1" in url
        assert "next_id=p3" in url
        assert "nav_idx=2" in url

    def test_single_photo_has_no_nav(self):
        """Single photo in collection has no prev/next."""
        from app.main import _photo_nav_url
        photos = [{"photo_id": "p0"}]
        url = _photo_nav_url("p0", 0, photos, 1)
        assert "prev_id" not in url
        assert "next_id" not in url


class TestPhotoViewNavigation:
    """Tests for navigation elements in photo_view_content."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_nav_buttons_rendered_with_context(self, mock_reg, mock_dim, mock_meta):
        """Prev/next buttons appear when navigation context is provided."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
            "source": "Test Collection",
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content(
            "p1", is_partial=True,
            prev_id="p0", next_id="p2",
            nav_idx=1, nav_total=5
        )
        html = to_xml(result)

        # Prev button
        assert 'id="photo-nav-prev"' in html
        assert "/photo/p0/partial" in html
        # Next button
        assert 'id="photo-nav-next"' in html
        assert "/photo/p2/partial" in html
        # Counter
        assert "2 / 5" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_no_nav_without_context(self, mock_reg, mock_dim, mock_meta):
        """No navigation buttons when no context provided."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
            "source": "Test Collection",
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True)
        html = to_xml(result)

        assert 'id="photo-nav-prev"' not in html
        assert 'id="photo-nav-next"' not in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_keyboard_script_included(self, mock_reg, mock_dim, mock_meta):
        """Keyboard navigation script included when nav context present."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content(
            "p1", is_partial=True,
            prev_id="p0", next_id="p2",
            nav_idx=1, nav_total=3
        )
        html = to_xml(result)

        assert "ArrowLeft" in html
        assert "ArrowRight" in html
        assert "Escape" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_first_photo_no_prev_button(self, mock_reg, mock_dim, mock_meta):
        """First photo has next but no prev button."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content(
            "p0", is_partial=True,
            next_id="p1",
            nav_idx=0, nav_total=3
        )
        html = to_xml(result)

        assert 'id="photo-nav-prev"' not in html
        assert 'id="photo-nav-next"' in html
        assert "1 / 3" in html


class TestPhotoModalEscape:
    """Tests for photo modal keyboard handling."""

    def test_photo_modal_has_escape_handler(self):
        """Photo modal has Escape key handler."""
        from app.main import photo_modal, to_xml

        html = to_xml(photo_modal())
        assert "Escape" in html
        assert 'tabindex="-1"' in html


class TestPhotosGridNavScript:
    """Tests for the navigation script embedded in the photos grid."""

    @patch("app.main._build_caches")
    @patch("app.main._photo_cache", {
        "p1": {"filename": "a.jpg", "source": "Test", "faces": []},
        "p2": {"filename": "b.jpg", "source": "Test", "faces": []},
        "p3": {"filename": "c.jpg", "source": "Test", "faces": []},
    })
    @patch("app.main.get_identity_for_face", return_value=None)
    @patch("app.main.photo_url", side_effect=lambda f: f"/photos/{f}")
    def test_photos_section_includes_nav_script(self, mock_url, mock_id, mock_cache):
        """Photos section embeds JS with photo ID list for keyboard navigation."""
        from app.main import render_photos_section, to_xml

        registry = MagicMock()
        html = to_xml(render_photos_section(
            {"photos": 3}, registry, set()
        ))

        assert "window._photoNavIds" in html
        assert "photoNavTo" in html
        assert "ArrowLeft" in html
        assert "ArrowRight" in html
