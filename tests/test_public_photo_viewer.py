"""Tests for the public shareable photo viewer at /photo/{photo_id}.

Pruned: CSS class assertions (group class, hidden class checks, relative
container regex). Kept: access control, 404 handling, content rendering,
functional navigation, admin inline edit.
"""

import re
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


class TestPublicPhotoViewerAccess:
    """Public photo viewer requires no authentication."""

    def test_public_access_returns_200(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200

    def test_public_access_with_auth_enabled(self, client, real_photo_id, auth_enabled, no_user):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200

    def test_page_contains_rhodesli_branding(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert "Rhodesli" in response.text


class TestPublicPhotoViewer404:
    """404 handling for invalid photo IDs."""

    def test_invalid_photo_id_returns_404(self, client):
        response = client.get("/photo/nonexistent-photo-id-12345")
        assert response.status_code == 404
        assert "Photo not found" in response.text

    def test_404_page_has_explore_link(self, client):
        response = client.get("/photo/nonexistent-photo-id-12345")
        assert "Explore the Archive" in response.text


class TestPublicPhotoViewerContent:
    """Content rendering tests for photos with real data."""

    def test_photo_image_rendered(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert "<img" in response.text.lower()

    def test_person_cards_section(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert "People in this photo" in response.text or "Person in this photo" in response.text

    def test_face_count_display(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert "detected" in response.text


class TestPhotoCarousel:
    """Photo carousel navigation."""

    def test_nav_arrows_present(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        has_prev = 'title="Previous photo"' in html
        has_next = 'title="Next photo"' in html
        assert has_prev or has_next

    def test_position_indicator(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        position = re.findall(r"Photo \d+ of \d+", response.text)
        assert len(position) > 0

    def test_collection_link_visible(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        collection_links = re.findall(r'href="/collection/[^"]+"', response.text)
        assert len(collection_links) > 0


class TestFaceClickBehavior:
    """Face clicks navigate to person/identify pages."""

    @pytest.mark.xfail(
        reason="Flaky under xdist: shared app state race condition (passes in isolation)",
        strict=False,
    )
    def test_person_cards_link_to_person_or_identify(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        from app.main import app

        c = TestClient(app)
        html = c.get(f"/photo/{real_photo_id}").text
        card_links = re.findall(r'<a[^>]*href="(/person/[^"]+|/identify/[^"]+)"[^>]*class="no-underline', html)
        assert len(card_links) > 0


class TestUX103BackNavigation:
    """UX-103: Back navigation."""

    def test_back_to_photos_link_present(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert "Back to Photos" in response.text
        assert 'href="/photos"' in response.text


class TestUX103MetadataOverlay:
    """UX-103: Metadata overlay on photo hero image."""

    def test_metadata_overlay_present(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert 'data-testid="photo-metadata-overlay"' in response.text

    def test_anonymous_sees_metadata_overlay(self, client, real_photo_id, auth_enabled, no_user):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert 'data-testid="photo-metadata-overlay"' in response.text


class TestPhotoInlineEdit:
    """Admin inline editing for photo collection/source."""

    def test_admin_sees_inline_edit(self, client, real_photo_id, auth_disabled):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert 'data-testid="photo-inline-edit"' in response.text

    def test_anonymous_no_inline_edit(self, client, real_photo_id, auth_enabled, no_user):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert 'data-testid="photo-inline-edit"' not in response.text
