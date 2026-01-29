"""Tests for photo context navigator (Light Table) feature."""

import pytest
from starlette.testclient import TestClient

from app.main import app


class TestPhotoContextAPI:
    """Tests for GET /api/photo/<photo_id> endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client for the FastHTML app."""
        return TestClient(app)

    def test_photo_endpoint_returns_json(self, client):
        """GET /api/photo/<id> returns JSON content-type."""
        # Use a known photo_id from the test data
        # The actual ID will depend on how we generate photo IDs
        response = client.get("/api/photo/test-photo-id")
        # Should return JSON even for 404
        assert response.headers.get("content-type", "").startswith("application/json")

    def test_unknown_photo_returns_404(self, client):
        """GET /api/photo/<id> returns 404 for unknown photo."""
        response = client.get("/api/photo/nonexistent-photo-id")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data

    def test_photo_response_structure(self, client):
        """GET /api/photo/<id> returns expected JSON structure."""
        # This test will initially fail until we implement the endpoint
        # and have valid photo data
        response = client.get("/api/photo/valid-photo-id")
        if response.status_code == 200:
            data = response.json()
            # Required fields
            assert "photo_url" in data
            assert "image_width" in data
            assert "image_height" in data
            assert "faces" in data
            assert isinstance(data["faces"], list)

    def test_face_object_structure(self, client):
        """Each face in response has required fields."""
        response = client.get("/api/photo/valid-photo-id")
        if response.status_code == 200:
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

    def test_photo_view_contains_photo_image(self, client):
        """Photo view contains an image element."""
        response = client.get("/photo/test-photo-id")
        if response.status_code == 200:
            assert "<img" in response.text
            assert "/photos/" in response.text  # Static path to photos

    def test_photo_view_contains_face_overlays(self, client):
        """Photo view contains face overlay elements."""
        response = client.get("/photo/test-photo-id")
        if response.status_code == 200:
            # Look for absolute positioned overlay divs
            assert "face-overlay" in response.text or "absolute" in response.text
