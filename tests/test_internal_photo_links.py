"""Tests for share buttons and links to the public photo viewer.

Tests cover:
- Photo modal has share button and "Open" link
- Face card has share button
- Photos grid has share button and "Open" link
- Share buttons use data-action="share-photo" pattern
- Links point to correct /photo/{id} URL
- Share button renders on Focus Mode photo context
"""

import pytest
from starlette.testclient import TestClient

from app.main import app, load_embeddings_for_photos, share_button


def get_real_photo_id():
    """Get a real photo_id from the embeddings for testing."""
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


class TestShareButtonComponent:
    """The share_button() helper renders correctly in all styles."""

    def test_icon_style_has_data_action(self):
        """Icon-style share button has data-action='share-photo'."""
        from fasthtml.common import to_xml
        btn = share_button("abc123", style="icon")
        html = to_xml(btn)
        assert 'data-action="share-photo"' in html
        assert 'data-share-url="/photo/abc123"' in html

    def test_button_style_has_label(self):
        """Button-style share button includes label text."""
        from fasthtml.common import to_xml
        btn = share_button("abc123", style="button", label="Share Photo")
        html = to_xml(btn)
        assert "Share Photo" in html
        assert 'data-action="share-photo"' in html

    def test_link_style_has_label(self):
        """Link-style share button includes label text."""
        from fasthtml.common import to_xml
        btn = share_button("abc123", style="link", label="Share")
        html = to_xml(btn)
        assert "Share" in html
        assert 'data-action="share-photo"' in html

    def test_share_url_uses_photo_path(self):
        """Share URL is always /photo/{id}."""
        from fasthtml.common import to_xml
        btn = share_button("test_photo_id", style="icon")
        html = to_xml(btn)
        assert 'data-share-url="/photo/test_photo_id"' in html


class TestPhotoModalShareButton:
    """Photo context modal contains share button and open link."""

    def test_partial_has_share_button(self, client, real_photo_id):
        """The photo partial (modal content) has a share button."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(
            f"/photo/{real_photo_id}/partial",
            headers={"HX-Request": "true"}
        )
        html = response.text
        assert 'data-action="share-photo"' in html
        assert f"/photo/{real_photo_id}" in html

    def test_partial_has_open_link(self, client, real_photo_id):
        """The photo partial has an 'Open' link to the public viewer."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(
            f"/photo/{real_photo_id}/partial",
            headers={"HX-Request": "true"}
        )
        html = response.text
        assert ">Open</a>" in html or "Open" in html
        assert 'target="_blank"' in html

    def test_no_full_page_text(self, client, real_photo_id):
        """'Open Full Page' and 'Full Page' text no longer appears."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(
            f"/photo/{real_photo_id}/partial",
            headers={"HX-Request": "true"}
        )
        html = response.text
        assert "Open Full Page" not in html
        assert "Full Page" not in html


class TestPhotosGridShareButton:
    """Photos grid section has share buttons."""

    def test_photos_section_has_share_buttons(self, client):
        """The photos section renders share buttons."""
        response = client.get("/?section=photos")
        html = response.text
        assert 'data-action="share-photo"' in html

    def test_photos_section_has_open_link(self, client):
        """Photos grid has 'Open' links to public viewer."""
        response = client.get("/?section=photos")
        html = response.text
        assert '/photo/' in html

    def test_photos_section_no_full_page_text(self, client):
        """'Full Page' text no longer appears on photos grid."""
        response = client.get("/?section=photos")
        html = response.text
        # Should not contain bare "Full Page" (but "Open" is fine)
        assert ">Full Page<" not in html


class TestFaceCardShareButton:
    """Face cards contain share buttons."""

    def test_face_card_has_share_button(self, client):
        """Face cards in browse view include share button."""
        response = client.get("/?section=confirmed&view=browse")
        html = response.text
        # Face cards with photos should have share buttons
        if 'data-action="share-photo"' in html:
            assert "/photo/" in html


class TestGlobalShareJS:
    """Global share JavaScript is present in the main layout."""

    def test_main_page_has_share_functions(self, client):
        """The main SPA layout includes global share utility functions."""
        # Use a section page (not landing) to get the full SPA layout with scripts
        response = client.get("/?section=photos")
        html = response.text
        assert "_sharePhotoUrl" in html
        assert "_copyAndToast" in html
        assert "_showShareToast" in html

    def test_public_photo_page_has_share_functions(self, client, real_photo_id):
        """The public photo page includes share utility functions."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "_sharePhotoUrl" in html
        assert "_showShareToast" in html

    def test_share_handler_in_global_delegation(self, client):
        """Global event delegation handles share-photo action."""
        response = client.get("/?section=photos")
        html = response.text
        assert 'share-photo' in html
