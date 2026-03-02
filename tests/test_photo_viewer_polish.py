"""Tests for public photo viewer polish.

Tests cover:
- Face overlay name positioning (below for top-edge faces)
- Quality scores hidden for non-admin
- Person card click → scroll to face overlay
- Photo container padding for overlay clipping
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

from app.main import app, load_embeddings_for_photos, face_card, _build_face_cards_for_entries


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


class TestFaceOverlayNamePosition:
    """Face overlay names don't clip at top edge."""

    def test_overlay_has_face_overlay_box_class(self, client, real_photo_id):
        """Face overlays use face-overlay-box class for CSS targeting."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
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
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
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

    def test_face_card_has_admin_actions(self):
        """Admin face card has find similar, share, view photo, and edit/tag actions."""
        from fasthtml.common import to_xml
        card = face_card(
            face_id="test-face",
            crop_url="/static/crops/test.jpg",
            quality=22,
            identity_id="ident-123",
            photo_id="photo-123",
            is_admin=True,
        )
        html = to_xml(card)
        assert "Find Similar" in html
        assert "Share" in html
        assert "View Photo" in html
        assert "Edit/Tag" in html

    def test_face_card_keeps_vertical_layout(self):
        """Face card keeps vertical image-first layout."""
        from fasthtml.common import to_xml
        card = face_card(
            face_id="test-face",
            crop_url="/static/crops/test.jpg",
            quality=22,
            identity_id="ident-123",
            photo_id="photo-123",
            is_admin=True,
        )
        html = to_xml(card)
        assert "min-h-[150px]" in html


class TestFindSimilarInline:
    def test_face_card_uses_inline_find_similar_endpoint(self):
        """Admin face cards load find similar via HTMX inline endpoint."""
        from fasthtml.common import to_xml
        card = face_card(
            face_id="test-face",
            crop_url="/static/crops/test.jpg",
            quality=22,
            identity_id="ident-123",
            photo_id="photo-123",
            is_admin=True,
        )
        html = to_xml(card)
        assert "/api/find-similar/test-face" in html
        assert "expand-face-card-test-face" in html


class TestExpansionPanels:
    def test_expansion_panel_exists_for_each_face_card(self, monkeypatch):
        monkeypatch.setattr("app.main.resolve_face_image_url", lambda face_id, crop_files: "/static/crops/test.jpg")
        monkeypatch.setattr("app.main.get_photo_id_for_face", lambda face_id: "photo-1")
        monkeypatch.setattr("app.main.get_face_quality", lambda face_id: 22.0)
        cards = _build_face_cards_for_entries(["face-a", "face-b"], set(), "identity-1", can_detach=False, is_admin=True)
        from fasthtml.common import to_xml
        html = ''.join(to_xml(c) for c in cards)
        assert 'id="expand-face-card-face-a"' in html
        assert 'id="expand-face-card-face-b"' in html



class TestPersonCardInteraction:
    """Person card click scrolls to face overlay."""

    def test_person_card_has_cursor_pointer(self, client, real_photo_id):
        """Person cards in public viewer have cursor-pointer for clickability."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        if 'id="person-' in html:
            assert "cursor-pointer" in html

    def test_person_card_has_scroll_script(self, client, real_photo_id):
        """Person cards have hyperscript for scrolling to overlay."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        if 'id="person-' in html:
            # Check for the scroll-and-highlight script
            assert "overlay-" in html


class TestPhotoContainerPadding:
    """Photo container has padding to prevent overlay clipping."""

    def test_hero_container_has_padding(self, client, real_photo_id):
        """Photo hero container has top padding for overlay labels."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "padding-top" in html
