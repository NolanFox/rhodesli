"""Tests for photo context navigator (Light Table) feature."""

import hashlib
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.main import app, generate_photo_id, load_embeddings_for_photos


def get_real_photo_id():
    """
    Get a real photo_id from the embeddings for testing.

    Returns None if no embeddings are available.
    """
    photos = load_embeddings_for_photos()
    if photos:
        return next(iter(photos.keys()))
    return None


class TestPhotoContextAPI:
    """Tests for GET /api/photo/<photo_id> endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client for the FastHTML app."""
        return TestClient(app)

    @pytest.fixture
    def real_photo_id(self):
        """Get a real photo_id from embeddings."""
        return get_real_photo_id()

    def test_photo_endpoint_returns_json(self, client):
        """GET /api/photo/<id> returns JSON content-type."""
        response = client.get("/api/photo/test-photo-id")
        # Should return JSON even for 404
        assert response.headers.get("content-type", "").startswith("application/json")

    def test_unknown_photo_returns_404(self, client):
        """GET /api/photo/<id> returns 404 for unknown photo."""
        response = client.get("/api/photo/nonexistent-photo-id")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data

    def test_photo_response_structure(self, client, real_photo_id):
        """GET /api/photo/<id> returns expected JSON structure."""
        if not real_photo_id:
            pytest.skip("No embeddings available for testing")

        response = client.get(f"/api/photo/{real_photo_id}")
        assert response.status_code == 200

        data = response.json()
        # Required fields
        assert "photo_url" in data
        assert "image_width" in data
        assert "image_height" in data
        assert "faces" in data
        assert isinstance(data["faces"], list)
        assert len(data["faces"]) > 0  # Should have at least one face

    def test_face_object_structure(self, client, real_photo_id):
        """Each face in response has required fields."""
        if not real_photo_id:
            pytest.skip("No embeddings available for testing")

        response = client.get(f"/api/photo/{real_photo_id}")
        assert response.status_code == 200

        data = response.json()
        for face in data["faces"]:
            assert "face_id" in face
            assert "bbox" in face
            assert "display_name" in face
            assert "identity_id" in face
            assert "is_selected" in face
            # bbox should have x, y, w, h
            bbox = face["bbox"]
            assert "x" in bbox
            assert "y" in bbox
            assert "w" in bbox
            assert "h" in bbox


class TestPhotoViewRoute:
    """Tests for photo view HTML endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client for the FastHTML app."""
        return TestClient(app)

    @pytest.fixture
    def real_photo_id(self):
        """Get a real photo_id from embeddings."""
        return get_real_photo_id()

    def test_photo_view_returns_html(self, client):
        """GET /photo/<id> returns HTML."""
        response = client.get("/photo/test-photo-id")
        content_type = response.headers.get("content-type", "")
        assert "text/html" in content_type

    def test_photo_view_partial_returns_html_fragment(self, client):
        """GET /photo/<id>/partial returns HTML fragment for HTMX."""
        response = client.get("/photo/test-photo-id/partial")
        content_type = response.headers.get("content-type", "")
        assert "text/html" in content_type

    def test_photo_view_not_found_shows_error(self, client):
        """Photo view shows error for unknown photo."""
        response = client.get("/photo/nonexistent-id")
        assert response.status_code == 200  # Still returns HTML page
        assert "Photo not found" in response.text

    def test_photo_view_contains_photo_image(self, client, real_photo_id):
        """Photo view contains an image element."""
        if not real_photo_id:
            pytest.skip("No embeddings available for testing")

        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200
        assert "<img" in response.text
        assert "/photos/" in response.text  # Static path to photos

    def test_photo_view_contains_face_overlays(self, client, real_photo_id):
        """Photo view contains face overlay elements."""
        if not real_photo_id:
            pytest.skip("No embeddings available for testing")

        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200
        # Look for absolute positioned overlay divs
        assert "face-overlay" in response.text
        assert "absolute" in response.text

    def test_photo_view_partial_is_fragment(self, client, real_photo_id):
        """Partial view returns just the content, not full page."""
        if not real_photo_id:
            pytest.skip("No embeddings available for testing")

        response = client.get(f"/photo/{real_photo_id}/partial")
        assert response.status_code == 200
        assert "photo-viewer" in response.text
        # Partial should not have full page structure
        # (though FastHTML might still wrap it - this tests the content)
        assert "<img" in response.text


class TestViewPhotoButton:
    """Tests for View Photo button in face cards."""

    @pytest.fixture
    def client(self):
        """Create test client for the FastHTML app."""
        return TestClient(app)

    def test_main_page_contains_modal(self, client):
        """Main page includes the photo modal container."""
        response = client.get("/")
        assert response.status_code == 200
        assert "photo-modal" in response.text
        assert "photo-modal-content" in response.text

    def test_main_page_modal_is_hidden(self, client):
        """Modal is hidden by default."""
        response = client.get("/")
        assert 'id="photo-modal"' in response.text
        assert 'class="hidden' in response.text

    def test_face_cards_have_view_photo_button(self, client):
        """Face cards include View Photo button when data is available."""
        response = client.get("/")
        # If there's identity data, there should be View Photo buttons
        if "View Photo" in response.text:
            assert "/photo/" in response.text
            assert "hx-get" in response.text.lower()


class TestGeneratePhotoId:
    """Tests for photo ID generation."""

    def test_photo_id_is_deterministic(self):
        """Same filename always produces same photo_id."""
        filename = "test_photo.jpg"
        id1 = generate_photo_id(filename)
        id2 = generate_photo_id(filename)
        assert id1 == id2

    def test_photo_id_uses_basename_only(self):
        """Photo ID ignores directory path."""
        id1 = generate_photo_id("test.jpg")
        id2 = generate_photo_id("/some/path/test.jpg")
        id3 = generate_photo_id("other/path/test.jpg")
        assert id1 == id2 == id3

    def test_photo_id_is_16_chars(self):
        """Photo ID is 16 character hex string."""
        photo_id = generate_photo_id("test.jpg")
        assert len(photo_id) == 16
        # Should be valid hex
        int(photo_id, 16)

    def test_different_files_different_ids(self):
        """Different filenames produce different IDs."""
        id1 = generate_photo_id("photo1.jpg")
        id2 = generate_photo_id("photo2.jpg")
        assert id1 != id2
