"""Integration tests for app/main.py - FastHTML gallery."""

import pytest
import httpx

from app.main import app, parse_quality_from_filename


class TestParseQualityFromFilename:
    """Tests for the parse_quality_from_filename function."""

    def test_extracts_quality_from_standard_format(self):
        """Extracts quality from filename like 'name_21.98_0.jpg'."""
        assert parse_quality_from_filename("brass_rail_21.98_0.jpg") == 21.98

    def test_extracts_quality_with_high_value(self):
        """Handles quality scores above 25."""
        assert parse_quality_from_filename("photo_27.18_2.jpg") == 27.18

    def test_returns_zero_for_invalid_format(self):
        """Returns 0.0 for filenames without quality score."""
        assert parse_quality_from_filename("invalid.jpg") == 0.0

    def test_handles_complex_filename(self):
        """Handles real-world filename format."""
        result = parse_quality_from_filename("603569530_803296_1_24.55_0.jpg")
        assert result == 24.55


class TestGalleryRoute:
    """Integration tests for the gallery endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client for the FastHTML app."""
        transport = httpx.ASGITransport(app=app)
        return httpx.Client(transport=transport, base_url="http://test")

    def test_gallery_returns_200(self, client):
        """GET / returns 200 OK."""
        response = client.get("/")
        assert response.status_code == 200

    def test_gallery_contains_title(self, client):
        """Gallery page contains the title."""
        response = client.get("/")
        assert "Leon Capeluto" in response.text

    def test_gallery_has_css_grid(self, client):
        """Gallery uses CSS grid layout."""
        response = client.get("/")
        assert "display: grid" in response.text or 'class="gallery"' in response.text

    def test_gallery_has_quality_scores(self, client):
        """Gallery displays quality scores."""
        response = client.get("/")
        assert "Quality:" in response.text

    def test_gallery_has_face_cards(self, client):
        """Gallery has face-card elements."""
        response = client.get("/")
        assert "face-card" in response.text

    def test_gallery_has_research_notes_field(self, client):
        """Gallery has research notes textarea."""
        response = client.get("/")
        assert "Research notes" in response.text or "placeholder" in response.text
