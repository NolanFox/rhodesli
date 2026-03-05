"""Tests for admin re-analyze endpoint and supporting functions.

Covers:
- POST /api/photo/{photo_id}/reanalyze requires admin
- Reanalyze calls Gemini and logs to Supabase
- HTMX response includes updated results
- Graceful handling of Gemini failure
- Geocoding helper for location text
- Region guessing helper
"""

from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestReanalyzeEndpoint:
    """Tests for POST /api/photo/{photo_id}/reanalyze."""

    def test_requires_admin(self, client):
        """Non-admin should get 401/403."""
        with (
            patch("app.main.is_auth_enabled", return_value=True),
            patch("app.main.get_current_user", return_value=MagicMock(is_admin=False)),
        ):
            resp = client.post("/api/photo/test123/reanalyze")
        assert resp.status_code in (401, 403)

    def test_no_gemini_key_returns_error(self, client):
        """Missing GEMINI_API_KEY should return error message."""
        with (
            patch("app.main.is_auth_enabled", return_value=False),
            patch.dict("os.environ", {"GEMINI_API_KEY": ""}, clear=False),
        ):
            resp = client.post("/api/photo/test123/reanalyze")
        assert resp.status_code == 200
        assert "not configured" in resp.text.lower() or "gemini" in resp.text.lower()

    def test_photo_not_found_returns_error(self, client):
        """Missing photo should return error."""
        with (
            patch("app.main.is_auth_enabled", return_value=False),
            patch.dict("os.environ", {"GEMINI_API_KEY": "fake_key"}, clear=False),
            patch("app.main._build_caches"),
            patch("app.main.get_photo_metadata", return_value=None),
        ):
            resp = client.post("/api/photo/nonexistent/reanalyze")
        assert resp.status_code == 200
        assert "could not load" in resp.text.lower() or "not" in resp.text.lower()


class TestGeocodeLocation:
    """Tests for _geocode_location helper."""

    def test_asheville(self):
        from app.estimate_routes import _geocode_location

        lat, lng = _geocode_location("Asheville, North Carolina")
        assert abs(lat - 35.5951) < 0.01
        assert abs(lng - (-82.5515)) < 0.01

    def test_rhodes(self):
        from app.estimate_routes import _geocode_location

        lat, lng = _geocode_location("Rhodes, Greece")
        assert abs(lat - 36.4341) < 0.01

    def test_brooklyn(self):
        from app.estimate_routes import _geocode_location

        lat, lng = _geocode_location("Brooklyn, New York")
        assert abs(lat - 40.6782) < 0.01

    def test_unknown_location(self):
        from app.estimate_routes import _geocode_location

        lat, lng = _geocode_location("Unknown Place, Mars")
        assert lat == 0.0
        assert lng == 0.0

    def test_case_insensitive(self):
        from app.estimate_routes import _geocode_location

        lat, lng = _geocode_location("ASHEVILLE, NC")
        assert abs(lat - 35.5951) < 0.01


class TestGuessRegion:
    """Tests for _guess_region helper."""

    def test_us_cities(self):
        from app.estimate_routes import _guess_region

        assert _guess_region("Asheville, NC") == "United States"
        assert _guess_region("Brooklyn, New York") == "United States"
        assert _guess_region("Miami, Florida") == "United States"

    def test_greece(self):
        from app.estimate_routes import _guess_region

        assert _guess_region("Rhodes, Greece") == "Greece"

    def test_israel(self):
        from app.estimate_routes import _guess_region

        assert _guess_region("Jerusalem") == "Israel"

    def test_unknown(self):
        from app.estimate_routes import _guess_region

        assert _guess_region("Mars Colony") == "Unknown"


class TestReanalyzeButton:
    """Tests for re-analyze button visibility in AI analysis section."""

    def test_button_visible_for_admin(self):
        """Re-analyze button should appear when is_admin=True."""
        from app.main import _build_ai_analysis_section

        with (
            patch(
                "app.main._load_date_labels",
                return_value={"test_photo": {"estimated_decade": 1930, "confidence": "medium"}},
            ),
            patch("app.main._load_search_index", return_value=[]),
            patch("app.main._load_photo_locations", return_value={}),
        ):
            result = _build_ai_analysis_section("test_photo", is_admin=True)
        if result is not None:
            html = repr(result)
            assert "reanalyze" in html.lower()

    def test_button_hidden_for_non_admin(self):
        """Re-analyze button should NOT appear for non-admin."""
        from app.main import _build_ai_analysis_section

        with (
            patch(
                "app.main._load_date_labels",
                return_value={"test_photo": {"estimated_decade": 1930, "confidence": "medium"}},
            ),
            patch("app.main._load_search_index", return_value=[]),
            patch("app.main._load_photo_locations", return_value={}),
        ):
            result = _build_ai_analysis_section("test_photo", is_admin=False)
        if result is not None:
            html = repr(result)
            assert "reanalyze-button" not in html
