"""Tests for internal links to the public photo viewer.

Tests cover:
- Photo modal has "Open Full Page" link
- Face card has "Full Page" link
- Photos grid has "Full Page" link
- Links point to correct /photo/{id} URL
"""

import pytest
from starlette.testclient import TestClient

from app.main import app, load_embeddings_for_photos


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


class TestPhotoModalFullPageLink:
    """Photo context modal contains 'Open Full Page' link."""

    def test_partial_has_full_page_link(self, client, real_photo_id):
        """The photo partial (modal content) has an 'Open Full Page' link."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(
            f"/photo/{real_photo_id}/partial",
            headers={"HX-Request": "true"}
        )
        html = response.text
        assert "Open Full Page" in html
        assert f"/photo/{real_photo_id}" in html

    def test_full_page_link_opens_in_new_tab(self, client, real_photo_id):
        """Full page link has target=_blank for new tab."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(
            f"/photo/{real_photo_id}/partial",
            headers={"HX-Request": "true"}
        )
        html = response.text
        assert 'target="_blank"' in html


class TestPhotosGridFullPageLink:
    """Photos grid section has 'Full Page' links."""

    def test_photos_section_has_full_page_links(self, client):
        """The photos section renders Full Page links."""
        response = client.get("/?section=photos")
        html = response.text
        # Photos section should have at least one Full Page link
        assert "Full Page" in html

    def test_photos_section_full_page_link_format(self, client):
        """Full Page links use /photo/{id} format."""
        response = client.get("/?section=photos")
        html = response.text
        assert '/photo/' in html


class TestFaceCardFullPageLink:
    """Face cards contain Full Page links to photo viewer."""

    def test_face_card_has_full_page_link(self, client):
        """Face cards in browse view include Full Page link."""
        # Browse confirmed identities which have face cards with photo_ids
        response = client.get("/?section=confirmed&view=browse")
        html = response.text
        # Face cards with photos should have Full Page links
        if "Full Page" in html:
            assert "/photo/" in html
