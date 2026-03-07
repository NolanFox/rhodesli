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
    """Set caches on main module and route modules for testing."""
    import app.page_routes as page_mod

    main_module._date_labels_cache = date_labels
    main_module._photo_locations_cache = photo_locations
    page_mod._photo_locations_cache = photo_locations
    main_module._search_index_cache = search_index or []


def _clear_caches(main_module):
    """Clear test caches."""
    import app.page_routes as page_mod

    main_module._date_labels_cache = None
    main_module._photo_locations_cache = None
    page_mod._photo_locations_cache = None
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
        """Map tile layer uses CARTO dark tiles (in global Leaflet init script)."""
        import app.main as main_module
        from fasthtml.common import to_xml

        # CARTO dark tiles URL is in the global page header script
        # (loaded dynamically via DOMContentLoaded + Leaflet onload)
        hdrs_html = "".join(to_xml(h) for h in main_module.app.hdrs)
        assert "cartocdn.com/dark_all" in hdrs_html


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
        """Admin gets a draggable map marker (data-draggable attribute)."""
        import app.main as main_module
        from fasthtml.common import to_xml

        _setup_caches(main_module, date_labels_with_location, photo_locations_data)
        try:
            section = main_module._build_ai_analysis_section("photo_loc_1", is_admin=True)
            html = to_xml(section)
            assert 'data-draggable="true"' in html
        finally:
            _clear_caches(main_module)

    def test_non_admin_map_marker_not_draggable(self, date_labels_with_location, photo_locations_data):
        """Non-admin gets a non-draggable map marker (data-draggable=false)."""
        import app.main as main_module
        from fasthtml.common import to_xml

        _setup_caches(main_module, date_labels_with_location, photo_locations_data)
        try:
            section = main_module._build_ai_analysis_section("photo_loc_1", is_admin=False)
            html = to_xml(section)
            assert 'data-draggable="false"' in html
        finally:
            _clear_caches(main_module)


# ---------------------------------------------------------------------------
# _load_photo_locations
# ---------------------------------------------------------------------------


class TestLoadPhotoLocations:
    """_load_photo_locations() function behavior."""

    def _clear_loc_cache(self, main_module):
        """Clear photo locations cache on both main and page_routes modules."""
        import app.page_routes as page_mod

        main_module._photo_locations_cache = None
        page_mod._photo_locations_cache = None

    def _set_loc_cache(self, main_module, value):
        """Set photo locations cache on both main and page_routes modules."""
        import app.page_routes as page_mod

        main_module._photo_locations_cache = value
        page_mod._photo_locations_cache = value

    def test_returns_dict(self):
        """_load_photo_locations() returns a dict."""
        import app.main as main_module

        # Clear cache to force reload
        self._clear_loc_cache(main_module)
        try:
            result = main_module._load_photo_locations()
            assert isinstance(result, dict)
        finally:
            self._clear_loc_cache(main_module)

    def test_returns_empty_dict_when_no_file(self, tmp_path):
        """Returns empty dict when photo_locations.json does not exist."""
        import app.main as main_module

        self._clear_loc_cache(main_module)
        original_data_dir = main_module.DATA_DIR
        try:
            main_module.DATA_DIR = str(tmp_path)
            result = main_module._load_photo_locations()
            assert result == {}
        finally:
            main_module.DATA_DIR = original_data_dir
            self._clear_loc_cache(main_module)

    def test_caches_result(self):
        """Subsequent calls return cached result."""
        import app.main as main_module

        self._set_loc_cache(main_module, {"cached": True})
        try:
            result = main_module._load_photo_locations()
            assert result == {"cached": True}
        finally:
            self._clear_loc_cache(main_module)

    def test_loads_from_json_file(self, tmp_path):
        """Loads photo locations from JSON file."""
        import app.main as main_module
        import json

        locations_data = {
            "version": 1,
            "photos": {
                "test_photo": {
                    "photo_id": "test_photo",
                    "lat": 36.4413,
                    "lng": 28.2261,
                    "location_name": "Rhodes, Greece",
                }
            },
        }
        locations_path = tmp_path / "photo_locations.json"
        locations_path.write_text(json.dumps(locations_data))

        original_data_dir = main_module.DATA_DIR
        self._clear_loc_cache(main_module)
        try:
            main_module.DATA_DIR = str(tmp_path)
            result = main_module._load_photo_locations()
            assert "test_photo" in result
            assert result["test_photo"]["location_name"] == "Rhodes, Greece"
            assert result["test_photo"]["lat"] == 36.4413
        finally:
            main_module.DATA_DIR = original_data_dir
            self._clear_loc_cache(main_module)

    def test_dual_keys_inbox_ids_to_sha256(self, tmp_path):
        """inbox_* IDs are also keyed by SHA256 of their filename."""
        import app.main as main_module
        import json
        import hashlib

        inbox_id = "inbox_staged-20260210-182610_5_757557421.130308"
        filename = "757557421.130308.jpg"
        sha_id = hashlib.sha256(filename.encode("utf-8")).hexdigest()[:16]

        locations_data = {
            "version": 1,
            "photos": {
                inbox_id: {
                    "photo_id": inbox_id,
                    "lat": 25.7617,
                    "lng": -80.1918,
                    "location_name": "Miami, Florida",
                }
            },
        }
        locations_path = tmp_path / "photo_locations.json"
        locations_path.write_text(json.dumps(locations_data))

        # Also need photo_index.json for the registry lookup
        photo_index = {
            "schema_version": 1,
            "photos": {
                inbox_id: {
                    "path": filename,
                    "face_ids": [],
                    "source": "test",
                }
            },
            "face_to_photo": {},
        }
        photo_index_path = tmp_path / "photo_index.json"
        photo_index_path.write_text(json.dumps(photo_index))

        original_data_dir = main_module.DATA_DIR
        original_data_path = main_module.data_path
        self._clear_loc_cache(main_module)
        try:
            main_module.DATA_DIR = str(tmp_path)
            main_module.data_path = tmp_path
            result = main_module._load_photo_locations()
            # Original inbox key still works
            assert inbox_id in result
            # SHA256 key also works
            assert sha_id in result, f"SHA256 key {sha_id} not found in {list(result.keys())}"
            assert result[sha_id]["location_name"] == "Miami, Florida"
            assert result[sha_id]["lat"] == 25.7617
        finally:
            main_module.DATA_DIR = original_data_dir
            main_module.data_path = original_data_path
            self._clear_loc_cache(main_module)

    def test_dual_key_matches_leon_restaurant_photo(self, tmp_path):
        """Specific regression test for Leon's Restaurant photo ID mismatch."""
        import app.main as main_module
        import json
        import hashlib

        inbox_id = "inbox_staged-20260210-182610_5_757557421.130308"
        filename = "757557421.130308.jpg"
        expected_sha = "3192877a90a174e9"
        actual_sha = hashlib.sha256(filename.encode("utf-8")).hexdigest()[:16]
        assert actual_sha == expected_sha, f"SHA mismatch: {actual_sha} != {expected_sha}"

        locations_data = {
            "version": 1,
            "photos": {
                inbox_id: {
                    "photo_id": inbox_id,
                    "lat": 25.7617,
                    "lng": -80.1918,
                    "location_name": "Miami, Florida",
                }
            },
        }
        (tmp_path / "photo_locations.json").write_text(json.dumps(locations_data))
        photo_index = {
            "schema_version": 1,
            "photos": {inbox_id: {"path": filename, "face_ids": [], "source": "test"}},
            "face_to_photo": {},
        }
        (tmp_path / "photo_index.json").write_text(json.dumps(photo_index))

        original_data_dir = main_module.DATA_DIR
        original_data_path = main_module.data_path
        self._clear_loc_cache(main_module)
        try:
            main_module.DATA_DIR = str(tmp_path)
            main_module.data_path = tmp_path
            result = main_module._load_photo_locations()
            assert expected_sha in result, f"Leon's photo SHA {expected_sha} not in locations"
        finally:
            main_module.DATA_DIR = original_data_dir
            main_module.data_path = original_data_path
            self._clear_loc_cache(main_module)
