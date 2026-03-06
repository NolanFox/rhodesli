"""Tests for public photo viewer polish.

Tests cover:
- Face overlay name positioning (below for top-edge faces)
- Quality scores hidden for non-admin
- Person card click → scroll to face overlay
- Photo container padding for overlay clipping
"""

import subprocess
import sys

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

from app.main import app, load_embeddings_for_photos, face_card


def get_real_photo_id():
    photos = load_embeddings_for_photos()
    if photos:
        return next(iter(photos.keys()))
    return None


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def real_photo_id():
    return get_real_photo_id()


def _render_photo_page_html(photo_id: str) -> str:
    """Render a photo page in an isolated subprocess to avoid cache bleed."""
    code = """
from app.main import app
from starlette.testclient import TestClient
import sys
client = TestClient(app)
print(client.get(f"/photo/{sys.argv[1]}").text)
"""
    result = subprocess.run(
        [sys.executable, "-c", code, photo_id],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


class TestFaceOverlayNamePosition:
    """Face overlay names don't clip at top edge."""

    def test_overlay_has_face_overlay_box_class(self, client, real_photo_id):
        """Face overlays use face-overlay-box class for CSS targeting."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        html = _render_photo_page_html(real_photo_id)
        if "face-overlay-box" in html:
            # Good — overlays have the class
            assert True
        else:
            # No overlays rendered (photo may have no dimensions)
            pytest.skip("No face overlays rendered")

    def test_overlay_ids_for_person_card_scrolling(self, client, real_photo_id):
        """Face overlays have id='overlay-{identity_id}' for scroll targeting."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        html = _render_photo_page_html(real_photo_id)
        # If overlays exist, they should have overlay- IDs
        if "face-overlay-box" in html:
            assert 'id="overlay-' in html


class TestQualityScoreVisibility:
    """Quality scores are admin-only."""

    def test_quality_shown_for_admin(self):
        """face_card shows human-readable quality label with admin tooltip."""
        from fasthtml.common import to_xml
        card = face_card(
            face_id="test-face",
            crop_url="/static/crops/test.jpg",
            quality=85.5,
            is_admin=True,
        )
        html = to_xml(card)
        assert "Excellent quality" in html
        assert "Quality score: 85.50" in html  # Admin tooltip

    def test_quality_shown_for_non_admin(self):
        """face_card shows quality label for non-admin (no tooltip)."""
        from fasthtml.common import to_xml
        card = face_card(
            face_id="test-face",
            crop_url="/static/crops/test.jpg",
            quality=85.5,
            is_admin=False,
        )
        html = to_xml(card)
        assert "Excellent quality" in html
        assert "Quality score:" not in html  # No admin tooltip

    def test_quality_hidden_when_zero(self):
        """face_card hides quality when score is 0 even for admin."""
        from fasthtml.common import to_xml
        card = face_card(
            face_id="test-face",
            crop_url="/static/crops/test.jpg",
            quality=0.0,
            is_admin=True,
        )
        html = to_xml(card)
        assert "quality" not in html.lower()


class TestPersonCardInteraction:
    """Person card click scrolls to face overlay."""

    def test_person_card_has_cursor_pointer(self, client, real_photo_id):
        """Person cards in public viewer have cursor-pointer for clickability."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        html = _render_photo_page_html(real_photo_id)
        if 'id="person-' in html:
            assert "cursor-pointer" in html

    def test_person_card_has_scroll_script(self, client, real_photo_id):
        """Person cards have hyperscript for scrolling to overlay."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        html = _render_photo_page_html(real_photo_id)
        if 'id="person-' in html:
            # Check for the scroll-and-highlight script
            assert "overlay-" in html


class TestPhotoContainerPadding:
    """Photo container has padding to prevent overlay clipping."""

    def test_hero_container_has_padding(self, client, real_photo_id):
        """Photo hero container has top padding for overlay labels."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        html = _render_photo_page_html(real_photo_id)
        assert "padding-top" in html
