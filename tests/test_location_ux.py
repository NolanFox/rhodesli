"""Tests for location estimate UX in the AI Analysis section.

Covers:
- Location label + confidence badge rendering
- Leaflet map rendering when lat/lng available
- No location section when no data
- Admin vs non-admin correction form visibility
- _load_photo_locations() returns dict

Session 81 Act 3.
"""

import pytest
from unittest.mock import patch, MagicMock
from contextlib import ExitStack


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def date_labels_with_location():
    """Date labels with location_estimate text from Gemini."""
    return {
        "photo_loc_1": {
            "photo_id": "photo_loc_1",
            "source": "gemini",
            "estimated_decade": 1930,
            "best_year_estimate": 1935,
            "confidence": "high",
            "probable_range": [1930, 1940],
            "scene_description": "Street scene in Rhodes.",
            "location_estimate": "Likely Rhodes, Greece based on Ottoman-era architecture.",
        },
        "photo_no_loc": {
            "photo_id": "photo_no_loc",
            "source": "gemini",
            "estimated_decade": 1950,
            "best_year_estimate": 1952,
            "confidence": "medium",
            "probable_range": [1948, 1955],
            "scene_description": "Indoor family gathering.",
        },
    }


@pytest.fixture
def photo_locations_data():
    """Geocoded photo location data (simulates photo_locations.json content)."""
    return {
        "photo_loc_1": {
            "photo_id": "photo_loc_1",
            "lat": 36.4413,
            "lng": 28.2261,
            "location_name": "Rhodes, Greece",
            "region": "Mediterranean",
            "confidence": "high",
            "source": "gemini",
            "location_estimate": "Likely Rhodes, Greece based on Ottoman-era architecture.",
        },
    }


@pytest.fixture
def photo_locations_medium_confidence():
    """Location data with medium confidence."""
    return {
        "photo_loc_1": {
            "photo_id": "photo_loc_1",
            "lat": 40.7128,
            "lng": -74.006,
            "location_name": "New York City",
            "region": "United States",
            "confidence": "medium",
            "source": "gemini",
            "location_estimate": "United States, likely New York.",
        },
    }


@pytest.fixture
def photo_locations_low_confidence():
    """Location data with low confidence."""
    return {
        "photo_loc_1": {
            "photo_id": "photo_loc_1",
            "lat": 25.7617,
            "lng": -80.1918,
            "location_name": "Miami, Florida",
            "region": "United States",
            "confidence": "low",
            "source": "gemini",
            "location_estimate": "Possibly Florida based on vegetation.",
        },
    }


@pytest.fixture
def photo_locations_no_coords():
    """Location data without lat/lng (no map should render)."""
    return {
        "photo_loc_1": {
            "photo_id": "photo_loc_1",
            "location_name": "Unknown US city",
            "region": "United States",
            "confidence": "low",
            "source": "gemini",
            "location_estimate": "Architecture suggests United States.",
        },
    }


def _setup_caches(main_module, date_labels, photo_locations, search_index=None):
    """Set caches on main module for testing."""
    main_module._date_labels_cache = date_labels
    main_module._photo_locations_cache = photo_locations
    main_module._search_index_cache = search_index or []


def _clear_caches(main_module):
    """Clear test caches."""
    main_module._date_labels_cache = None
    main_module._photo_locations_cache = None
    main_module._search_index_cache = None


# ---------------------------------------------------------------------------
# Location Label + Confidence Badge
# ---------------------------------------------------------------------------

class TestLocationLabelAndBadge:
    """Location name and confidence badge render correctly."""

    def test_location_name_shown(self, date_labels_with_location, photo_locations_data):
        """Location name appears in the AI analysis section."""
        import app.main as main_module
        from fasthtml.common import to_xml
        _setup_caches(main_module, date_labels_with_location, photo_locations_data)
        try:
            section = main_module._build_ai_analysis_section("photo_loc_1")
            html = to_xml(section)
            assert "Rhodes, Greece" in html
        finally:
            _clear_caches(main_module)

    def test_location_region_shown(self, date_labels_with_location, photo_locations_data):
        """Location region appended after location name."""
        import app.main as main_module
        from fasthtml.common import to_xml
        _setup_caches(main_module, date_labels_with_location, photo_locations_data)
        try:
            section = main_module._build_ai_analysis_section("photo_loc_1")
            html = to_xml(section)
            assert "Mediterranean" in html
        finally:
            _clear_caches(main_module)

    def test_high_confidence_badge(self, date_labels_with_location, photo_locations_data):
        """High confidence badge uses emerald styling."""
        import app.main as main_module
        from fasthtml.common import to_xml
        _setup_caches(main_module, date_labels_with_location, photo_locations_data)
        try:
            section = main_module._build_ai_analysis_section("photo_loc_1")
            html = to_xml(section)
            assert "Confidence: high" in html
            assert "emerald" in html
        finally:
            _clear_caches(main_module)

    def test_medium_confidence_badge(self, date_labels_with_location, photo_locations_medium_confidence):
        """Medium confidence badge uses amber styling."""
        import app.main as main_module
        from fasthtml.common import to_xml
        _setup_caches(main_module, date_labels_with_location, photo_locations_medium_confidence)
        try:
            section = main_module._build_ai_analysis_section("photo_loc_1")
            html = to_xml(section)
            # Check for location-specific medium confidence
            # (date also has high confidence badge, so check location section specifically)
            assert "Confidence: medium" in html
            assert "amber" in html
        finally:
            _clear_caches(main_module)

    def test_low_confidence_badge(self, date_labels_with_location, photo_locations_low_confidence):
        """Low confidence badge uses red styling."""
        import app.main as main_module
        from fasthtml.common import to_xml
        _setup_caches(main_module, date_labels_with_location, photo_locations_low_confidence)
        try:
            section = main_module._build_ai_analysis_section("photo_loc_1")
            html = to_xml(section)
            assert "Confidence: low" in html
            assert "red" in html
        finally:
            _clear_caches(main_module)

    def test_location_estimate_section_heading(self, date_labels_with_location, photo_locations_data):
        """Location Estimate heading appears in the section."""
        import app.main as main_module
        from fasthtml.common import to_xml
        _setup_caches(main_module, date_labels_with_location, photo_locations_data)
        try:
            section = main_module._build_ai_analysis_section("photo_loc_1")
            html = to_xml(section)
            assert "Location Estimate" in html
        finally:
            _clear_caches(main_module)


# ---------------------------------------------------------------------------
# Evidence Text
# ---------------------------------------------------------------------------

class TestLocationEvidence:
    """Gemini evidence text renders in location section."""

    def test_evidence_text_shown(self, date_labels_with_location, photo_locations_data):
        """Gemini reasoning text appears with location-evidence testid."""
        import app.main as main_module
        from fasthtml.common import to_xml
        _setup_caches(main_module, date_labels_with_location, photo_locations_data)
        try:
            section = main_module._build_ai_analysis_section("photo_loc_1")
            html = to_xml(section)
            assert "Ottoman-era architecture" in html
            assert 'data-testid="location-evidence"' in html
        finally:
            _clear_caches(main_module)

    def test_evidence_from_label_fallback(self, date_labels_with_location):
        """When only label has location_estimate (no photo_locations), still shows it."""
        import app.main as main_module
        from fasthtml.common import to_xml
        _setup_caches(main_module, date_labels_with_location, {})
        try:
            section = main_module._build_ai_analysis_section("photo_loc_1")
            html = to_xml(section)
            assert "Ottoman-era architecture" in html
        finally:
            _clear_caches(main_module)


# ---------------------------------------------------------------------------
# Leaflet Map
# ---------------------------------------------------------------------------

class TestLeafletMap:
    """Embedded map renders when geocoded data available."""

    def test_map_renders_with_lat_lng(self, date_labels_with_location, photo_locations_data):
        """Map container with data-testid='location-map' when lat/lng present."""
        import app.main as main_module
        from fasthtml.common import to_xml
        _setup_caches(main_module, date_labels_with_location, photo_locations_data)
        try:
            section = main_module._build_ai_analysis_section("photo_loc_1")
            html = to_xml(section)
            assert 'data-testid="location-map"' in html
            assert "leaflet" in html.lower()
        finally:
            _clear_caches(main_module)

    def test_map_has_correct_coordinates(self, date_labels_with_location, photo_locations_data):
        """Map initialization uses the correct lat/lng from location data."""
        import app.main as main_module
        from fasthtml.common import to_xml
        _setup_caches(main_module, date_labels_with_location, photo_locations_data)
        try:
            section = main_module._build_ai_analysis_section("photo_loc_1")
            html = to_xml(section)
            assert "36.4413" in html
            assert "28.2261" in html
        finally:
            _clear_caches(main_module)

    def test_no_map_without_lat_lng(self, date_labels_with_location, photo_locations_no_coords):
        """No map element when location data lacks lat/lng."""
        import app.main as main_module
        from fasthtml.common import to_xml
        _setup_caches(main_module, date_labels_with_location, photo_locations_no_coords)
        try:
            section = main_module._build_ai_analysis_section("photo_loc_1")
            html = to_xml(section)
            # Location section should exist (location_name present) but no map
            assert "Location Estimate" in html
            assert 'data-testid="location-map"' not in html
        finally:
            _clear_caches(main_module)

    def test_map_uses_carto_dark_tiles(self, date_labels_with_location, photo_locations_data):
        """Map tile layer uses CARTO dark tiles to match theme."""
        import app.main as main_module
        from fasthtml.common import to_xml
        _setup_caches(main_module, date_labels_with_location, photo_locations_data)
        try:
            section = main_module._build_ai_analysis_section("photo_loc_1")
            html = to_xml(section)
            assert "cartocdn.com/dark_all" in html
        finally:
            _clear_caches(main_module)


# ---------------------------------------------------------------------------
# No Location Section
# ---------------------------------------------------------------------------

class TestNoLocationSection:
    """No location section when photo has no location data."""

    def test_no_location_section_when_no_data(self, date_labels_with_location):
        """Photo without location data does not show Location Estimate section."""
        import app.main as main_module
        from fasthtml.common import to_xml
        _setup_caches(main_module, date_labels_with_location, {})
        try:
            section = main_module._build_ai_analysis_section("photo_no_loc")
            html = to_xml(section)
            assert "Location Estimate" not in html
            assert 'data-testid="location-estimate"' not in html
        finally:
            _clear_caches(main_module)

    def test_location_estimate_testid_present_when_data_exists(self, date_labels_with_location, photo_locations_data):
        """Location section has data-testid='location-estimate' when data present."""
        import app.main as main_module
        from fasthtml.common import to_xml
        _setup_caches(main_module, date_labels_with_location, photo_locations_data)
        try:
            section = main_module._build_ai_analysis_section("photo_loc_1")
            html = to_xml(section)
            assert 'data-testid="location-estimate"' in html
        finally:
            _clear_caches(main_module)


# ---------------------------------------------------------------------------
# Admin vs Non-Admin
# ---------------------------------------------------------------------------

class TestLocationAdminCorrection:
    """Admin correction form visibility."""

    def test_admin_sees_correction_form(self, date_labels_with_location, photo_locations_data):
        """Admin user sees the location correction form."""
        import app.main as main_module
        from fasthtml.common import to_xml
        _setup_caches(main_module, date_labels_with_location, photo_locations_data)
        try:
            section = main_module._build_ai_analysis_section("photo_loc_1", is_admin=True)
            html = to_xml(section)
            assert 'data-testid="location-correction-form"' in html
            assert 'data-testid="correction-location"' in html
        finally:
            _clear_caches(main_module)

    def test_non_admin_no_correction_form(self, date_labels_with_location, photo_locations_data):
        """Non-admin user does NOT see the location correction form."""
        import app.main as main_module
        from fasthtml.common import to_xml
        _setup_caches(main_module, date_labels_with_location, photo_locations_data)
        try:
            section = main_module._build_ai_analysis_section("photo_loc_1", is_admin=False)
            html = to_xml(section)
            assert 'data-testid="location-correction-form"' not in html
            assert 'data-testid="correction-location"' not in html
        finally:
            _clear_caches(main_module)

    def test_admin_map_marker_draggable(self, date_labels_with_location, photo_locations_data):
        """Admin gets a draggable map marker."""
        import app.main as main_module
        from fasthtml.common import to_xml
        _setup_caches(main_module, date_labels_with_location, photo_locations_data)
        try:
            section = main_module._build_ai_analysis_section("photo_loc_1", is_admin=True)
            html = to_xml(section)
            assert "draggable: true" in html
        finally:
            _clear_caches(main_module)

    def test_non_admin_map_marker_not_draggable(self, date_labels_with_location, photo_locations_data):
        """Non-admin gets a non-draggable map marker."""
        import app.main as main_module
        from fasthtml.common import to_xml
        _setup_caches(main_module, date_labels_with_location, photo_locations_data)
        try:
            section = main_module._build_ai_analysis_section("photo_loc_1", is_admin=False)
            html = to_xml(section)
            assert "draggable" not in html
        finally:
            _clear_caches(main_module)


# ---------------------------------------------------------------------------
# _load_photo_locations
# ---------------------------------------------------------------------------

class TestLoadPhotoLocations:
    """_load_photo_locations() function behavior."""

    def test_returns_dict(self):
        """_load_photo_locations() returns a dict."""
        import app.main as main_module
        # Clear cache to force reload
        main_module._photo_locations_cache = None
        try:
            result = main_module._load_photo_locations()
            assert isinstance(result, dict)
        finally:
            main_module._photo_locations_cache = None

    def test_returns_empty_dict_when_no_file(self, tmp_path):
        """Returns empty dict when photo_locations.json does not exist."""
        import app.main as main_module
        from pathlib import Path
        main_module._photo_locations_cache = None
        original_data_dir = main_module.DATA_DIR
        try:
            main_module.DATA_DIR = str(tmp_path)
            result = main_module._load_photo_locations()
            assert result == {}
        finally:
            main_module.DATA_DIR = original_data_dir
            main_module._photo_locations_cache = None

    def test_caches_result(self):
        """Subsequent calls return cached result."""
        import app.main as main_module
        main_module._photo_locations_cache = {"cached": True}
        try:
            result = main_module._load_photo_locations()
            assert result == {"cached": True}
        finally:
            main_module._photo_locations_cache = None

    def test_loads_from_json_file(self, tmp_path):
        """Loads photo locations from JSON file."""
        import app.main as main_module
        import json
        from pathlib import Path

        locations_data = {
            "version": 1,
            "photos": {
                "test_photo": {
                    "photo_id": "test_photo",
                    "lat": 36.4413,
                    "lng": 28.2261,
                    "location_name": "Rhodes, Greece",
                }
            }
        }
        locations_path = tmp_path / "photo_locations.json"
        locations_path.write_text(json.dumps(locations_data))

        original_data_dir = main_module.DATA_DIR
        main_module._photo_locations_cache = None
        try:
            main_module.DATA_DIR = str(tmp_path)
            result = main_module._load_photo_locations()
            assert "test_photo" in result
            assert result["test_photo"]["location_name"] == "Rhodes, Greece"
            assert result["test_photo"]["lat"] == 36.4413
        finally:
            main_module.DATA_DIR = original_data_dir
            main_module._photo_locations_cache = None
