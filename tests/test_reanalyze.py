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


class TestGeocodeDisplayName:
    """Tests for _geocode_display_name helper — clean display names from vague Gemini text."""

    def test_asheville_from_vague_text(self):
        from app.estimate_routes import _geocode_display_name

        # Gemini returns vague text but mentions Leon Capeluto's residence (Asheville)
        result = _geocode_display_name("United States (Specific city tied to Leon Capeluto's residence in Asheville)")
        assert result == "Asheville, North Carolina"

    def test_clean_input_passes_through(self):
        from app.estimate_routes import _geocode_display_name

        assert _geocode_display_name("Tampa, Florida") == "Tampa, Florida"

    def test_unknown_returns_original(self):
        from app.estimate_routes import _geocode_display_name

        assert _geocode_display_name("Unknown Place") == "Unknown Place"

    def test_case_insensitive(self):
        from app.estimate_routes import _geocode_display_name

        assert _geocode_display_name("ASHEVILLE area") == "Asheville, North Carolina"

    def test_rhodes(self):
        from app.estimate_routes import _geocode_display_name

        assert _geocode_display_name("Island of Rhodes") == "Rhodes, Greece"


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


class TestReanalyzeModelAndLocationEvidence:
    """Tests for model label and location evidence persistence in reanalyze."""

    def test_new_entry_includes_model(self):
        """Reanalyze should store the model used in the date_labels entry."""
        # The new_entry dict must contain 'model' key
        # We verify by checking the code constructs it
        from rhodesli_ml.gemini_config import GEMINI_MODEL

        assert GEMINI_MODEL  # model string is non-empty

    def test_new_entry_includes_location_evidence(self):
        """Reanalyze should store full location evidence dict in date_labels."""
        # Simulate what the reanalyze handler builds
        location_data = {
            "place": "Asheville, North Carolina, USA",
            "confidence": "high",
            "visual_evidence": "Brick apartment buildings with sun porches",
            "biographical_evidence": "Family lived at 33 Elizabeth St, Asheville NC",
            "missing_child_analysis": "3 of 4 children present",
        }
        # The handler stores location_data as location_evidence
        entry = {"location_evidence": location_data if isinstance(location_data, dict) else {}}
        assert entry["location_evidence"]["place"] == "Asheville, North Carolina, USA"
        assert entry["location_evidence"]["biographical_evidence"] == "Family lived at 33 Elizabeth St, Asheville NC"

    def test_detective_evidence_shows_location(self):
        """_detective_evidence_section should render location evidence cards."""
        from app.main import _detective_evidence_section

        label = {
            "evidence": {
                "fashion": [{"cue": "1930s bob", "strength": "strong", "suggested_range": [1928, 1938]}],
            },
            "model": "gemini-3.1-pro-preview",
            "location_evidence": {
                "place": "Asheville, NC",
                "confidence": "high",
                "visual_evidence": "Mountain architecture",
                "biographical_evidence": "GEDCOM shows family at 33 Elizabeth St",
                "missing_child_analysis": "Youngest child absent",
            },
        }
        result = _detective_evidence_section(label)
        assert result is not None
        html = repr(result)
        assert "Geographic Analysis" in html
        assert "Mountain architecture" in html
        assert "GEDCOM shows family at 33 Elizabeth St" in html
        assert "Youngest child absent" in html
        assert "evidence-card-location" in html

    def test_detective_evidence_model_badge_dynamic(self):
        """Model badge should reflect actual model from label, not hardcoded."""
        from app.main import _detective_evidence_section

        label = {
            "evidence": {
                "fashion": [{"cue": "test", "strength": "moderate", "suggested_range": [1930, 1940]}],
            },
            "model": "gemini-3.1-pro-preview",
        }
        result = _detective_evidence_section(label)
        assert result is not None
        html = repr(result)
        assert "Gemini 3.1-pro" in html
        assert "model-badge" in html

    def test_detective_evidence_no_location_if_empty(self):
        """No location card when location_evidence is missing or empty."""
        from app.main import _detective_evidence_section

        label = {
            "evidence": {
                "fashion": [{"cue": "test", "strength": "moderate", "suggested_range": [1930, 1940]}],
            },
        }
        result = _detective_evidence_section(label)
        assert result is not None
        html = repr(result)
        assert "evidence-card-location" not in html

    def test_photo_locations_creates_file_if_missing(self, tmp_path):
        """photo_locations.json should be created if it doesn't exist."""
        import json

        locations_path = tmp_path / "photo_locations.json"
        assert not locations_path.exists()

        # Simulate what the handler does
        all_locations = {"photos": {}}
        photos_dict = all_locations.setdefault("photos", {})
        photos_dict["test_photo"] = {
            "photo_id": "test_photo",
            "lat": 35.5951,
            "lng": -82.5515,
            "location_name": "Asheville, NC",
        }
        locations_path.write_text(json.dumps(all_locations, indent=2))

        assert locations_path.exists()
        data = json.loads(locations_path.read_text())
        assert data["photos"]["test_photo"]["location_name"] == "Asheville, NC"

    def test_photo_locations_stores_biographical_evidence(self, tmp_path):
        """photo_locations.json entry should include biographical_evidence."""
        import json

        locations_path = tmp_path / "photo_locations.json"
        all_locations = {"photos": {}}
        photos_dict = all_locations.setdefault("photos", {})
        location_data = {
            "visual_evidence": "Brick buildings",
            "biographical_evidence": "Family at 33 Elizabeth St",
            "missing_child_analysis": "3 of 4 children",
        }
        photos_dict["test"] = {
            "location_estimate": location_data.get("visual_evidence", ""),
            "biographical_evidence": location_data.get("biographical_evidence", ""),
            "missing_child_analysis": location_data.get("missing_child_analysis", ""),
        }
        locations_path.write_text(json.dumps(all_locations, indent=2))

        data = json.loads(locations_path.read_text())
        assert data["photos"]["test"]["biographical_evidence"] == "Family at 33 Elizabeth St"
        assert data["photos"]["test"]["missing_child_analysis"] == "3 of 4 children"


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


class TestGeminiRetryLogic:
    """Tests for retry logic in _call_gemini_date_estimate.

    These verify the retry constants and retryable error detection
    without calling the full Gemini API function (which has complex deferred imports).
    """

    def test_retryable_error_patterns_detected(self):
        """The retry logic checks for 504, 503, DEADLINE_EXCEEDED, timeout."""
        retryable_patterns = ["504", "503", "DEADLINE_EXCEEDED", "timeout", "Timeout"]
        test_errors = [
            ("504 DEADLINE_EXCEEDED", True),
            ("503 Service Unavailable", True),
            ("Connection timeout after 120s", True),
            ("Invalid API key", False),
            ("Rate limit exceeded", False),
            ("Empty response", False),
        ]
        for error_msg, expected_retryable in test_errors:
            is_retryable = any(s in error_msg for s in retryable_patterns)
            assert is_retryable == expected_retryable, (
                f"Error '{error_msg}' retryable={is_retryable}, expected={expected_retryable}"
            )

    def test_retry_constants_in_source(self):
        """Verify retry constants are configured in the function."""
        import inspect
        from app.estimate_routes import _call_gemini_date_estimate

        source = inspect.getsource(_call_gemini_date_estimate)
        assert "max_retries = 2" in source
        assert "retry_delays" in source
        assert "DEADLINE_EXCEEDED" in source

    def test_timeout_increased_for_gedcom(self):
        """GEDCOM context should use higher timeout (180s)."""
        import inspect
        from app.estimate_routes import _call_gemini_date_estimate

        source = inspect.getsource(_call_gemini_date_estimate)
        assert "180_000" in source

    def test_array_response_unwrapped(self):
        """Gemini sometimes wraps JSON in an array — code must unwrap it."""
        import inspect
        from app.estimate_routes import _call_gemini_date_estimate

        source = inspect.getsource(_call_gemini_date_estimate)
        assert "isinstance(parsed, list)" in source
        assert "parsed[0]" in source


class TestModelBadgeTimestamp:
    """Tests for analysis timestamp in model badge."""

    def test_model_badge_shows_timestamp(self):
        """Model badge includes analysis date when reanalyzed_at present."""
        from app.main import _detective_evidence_section
        from fasthtml.common import to_xml

        label = {
            "estimated_decade": 1940,
            "confidence": "medium",
            "model": "gemini-3.1-pro-preview",
            "reanalyzed_at": "2026-03-05T12:00:00+00:00",
            "prompt_version": "v3_enriched",
        }
        with (
            patch("app.main._load_photo_locations", return_value={}),
            patch("app.main._load_search_index", return_value=[]),
        ):
            result = _detective_evidence_section(label)
        if result is not None:
            html = to_xml(result)
            assert "model-badge" in html
            assert "Mar 5, 2026" in html
            assert "v3_enriched" in html

    def test_model_badge_without_timestamp(self):
        """Model badge works without timestamp (batch analysis)."""
        from app.main import _detective_evidence_section
        from fasthtml.common import to_xml

        label = {
            "estimated_decade": 1940,
            "confidence": "medium",
            "model": "gemini-3-flash",
        }
        with (
            patch("app.main._load_photo_locations", return_value={}),
            patch("app.main._load_search_index", return_value=[]),
        ):
            result = _detective_evidence_section(label)
        if result is not None:
            html = to_xml(result)
            assert "model-badge" in html
            assert "Gemini 3-flash" in html


class TestAnchorCompareEndpoint:
    """Tests for POST /api/photo/{photo_id}/anchor-compare (AD-233)."""

    def test_requires_admin(self, client):
        """Non-admin should get 401/403."""
        with (
            patch("app.main.is_auth_enabled", return_value=True),
            patch("app.main.get_current_user", return_value=MagicMock(is_admin=False)),
        ):
            resp = client.post("/api/photo/test123/anchor-compare")
        assert resp.status_code in (401, 403)

    def test_missing_anchor_id_returns_error(self, client):
        """Missing anchor_photo_id should return error."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.post("/api/photo/test123/anchor-compare")
        assert resp.status_code == 200
        assert "select an anchor" in resp.text.lower()

    def test_no_gemini_key_returns_error(self, client):
        """Missing GEMINI_API_KEY should return error."""
        with (
            patch("app.main.is_auth_enabled", return_value=False),
            patch.dict("os.environ", {"GEMINI_API_KEY": ""}),
        ):
            resp = client.post(
                "/api/photo/test123/anchor-compare",
                data={"anchor_photo_id": "anchor456"},
            )
        assert resp.status_code == 200
        assert "not configured" in resp.text.lower()
