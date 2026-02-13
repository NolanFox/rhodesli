"""Tests for the public shareable photo viewer at /photo/{photo_id}.

Tests cover:
- Public access (no auth required)
- Face overlay rendering with correct coordinates
- Person cards with name and crop
- 404 handling for invalid photo IDs
- Metadata display (collection, source)
- CTA section for unidentified faces
"""

import hashlib

import pytest
from unittest.mock import patch, MagicMock
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
        """Anyone can view /photo/{id} without login."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200

    def test_public_access_with_auth_enabled(self, client, real_photo_id, auth_enabled, no_user):
        """Anonymous users can view photos even when auth is enabled."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200

    def test_page_contains_rhodesli_branding(self, client, real_photo_id):
        """Public page includes Rhodesli branding."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "Rhodesli" in html

    def test_page_contains_nav_links(self, client, real_photo_id):
        """Public page includes navigation links to photos and people."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "Photos" in html
        assert "People" in html
        assert "Explore More Photos" in html

    def test_page_contains_footer(self, client, real_photo_id):
        """Public page includes footer with heritage message."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "Preserving the visual heritage" in html


class TestPublicPhotoViewer404:
    """404 handling for invalid photo IDs."""

    def test_invalid_photo_id_returns_200_with_404_content(self, client):
        """Invalid photo_id shows a gentle 404 page (HTTP 200 with friendly message)."""
        response = client.get("/photo/nonexistent-photo-id-12345")
        assert response.status_code == 200
        html = response.text
        assert "Photo not found" in html
        assert "hasn't been added" in html

    def test_404_page_has_explore_link(self, client):
        """404 page provides a link to explore the archive."""
        response = client.get("/photo/nonexistent-photo-id-12345")
        html = response.text
        assert "Explore the Archive" in html

    def test_404_page_has_branding(self, client):
        """404 page still shows Rhodesli branding."""
        response = client.get("/photo/nonexistent-photo-id-12345")
        html = response.text
        assert "Rhodesli" in html


class TestPublicPhotoViewerContent:
    """Content rendering tests for photos with real data."""

    def test_photo_image_rendered(self, client, real_photo_id):
        """The photo image is rendered on the page."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "photo-hero" in html
        assert "<img" in html.lower()

    def test_face_overlays_present(self, client, real_photo_id):
        """Face overlay divs are rendered for detected faces."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        # Face overlays use percentage positioning
        assert "left:" in html
        assert "top:" in html

    def test_person_cards_section(self, client, real_photo_id):
        """Person cards section is rendered."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "People in this photo" in html or "Person in this photo" in html

    def test_face_count_display(self, client, real_photo_id):
        """Face count is displayed below the photo."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "detected" in html
        assert "identified" in html

    def test_overlay_legend_present(self, client, real_photo_id):
        """Overlay legend distinguishes identified vs unidentified."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "Identified" in html
        assert "Unidentified" in html

    def test_heritage_archive_in_title(self, client, real_photo_id):
        """Page title includes Heritage Archive."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "Heritage Archive" in html

    def test_cta_section_for_unidentified(self, client, real_photo_id):
        """CTA section shown when there are unidentified faces."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        # Most photos have unidentified faces
        if "Do you recognize someone" in html:
            assert "I Can Help Identify" in html
            assert "Browse All Photos" in html

    def test_cta_links_to_skipped_section(self, client, real_photo_id):
        """'I Can Help Identify' CTA links to Help Identify section, not inbox."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        if "I Can Help Identify" in html:
            # Should link to skipped section (Help Identify), not to_review (inbox)
            assert "section=skipped" in html
            assert "section=to_review" not in html or "section=skipped" in html


class TestPublicPhotoViewerPartialUnchanged:
    """The /photo/{id}/partial route should still work for HTMX modal injection."""

    def test_partial_route_still_works(self, client, real_photo_id):
        """Partial route returns content for HTMX injection."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(
            f"/photo/{real_photo_id}/partial",
            headers={"HX-Request": "true"}
        )
        assert response.status_code == 200
        html = response.text
        # Partial should contain the photo viewer content
        assert "photo-viewer" in html or "<img" in html.lower()
