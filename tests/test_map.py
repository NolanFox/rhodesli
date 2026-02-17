"""Tests for /map route and geocoding pipeline."""

import json
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


_MOCK_PHOTO_INDEX = {
    "schema_version": 1,
    "photos": {
        "photo-1": {
            "photo_id": "photo-1",
            "path": "image001.jpg",
            "face_ids": ["face-a1"],
            "collection": "Vida NYC",
        },
        "photo-2": {
            "photo_id": "photo-2",
            "path": "image002.jpg",
            "face_ids": ["face-b1"],
            "collection": "Betty Miami",
        },
    },
    "face_to_photo": {
        "face-a1": "photo-1",
        "face-b1": "photo-2",
    },
}

_MOCK_LOCATIONS = {
    "version": 1,
    "photos": {
        "photo-1": {
            "photo_id": "photo-1",
            "lat": 40.7128,
            "lng": -74.006,
            "location_name": "New York City",
            "location_key": "nyc",
            "region": "United States",
            "location_estimate": "New York City",
            "confidence": "high",
            "all_matches": [{"key": "nyc", "name": "New York City"}],
        },
        "photo-2": {
            "photo_id": "photo-2",
            "lat": 25.7617,
            "lng": -80.1918,
            "location_name": "Miami, Florida",
            "location_key": "miami",
            "region": "United States",
            "location_estimate": "Miami, Florida",
            "confidence": "high",
            "all_matches": [{"key": "miami", "name": "Miami, Florida"}],
        },
    },
}

_MOCK_IDENTITIES = {
    "identities": {
        "id-a": {
            "identity_id": "id-a", "name": "Leon Capeluto", "state": "CONFIRMED",
            "anchor_ids": ["face-a1"], "candidate_ids": [], "negative_ids": [],
            "version_id": 1, "created_at": "2025-01-01T00:00:00Z", "updated_at": "2025-01-01T00:00:00Z",
        },
    },
    "history": [],
}


def _patch_map():
    from core.registry import IdentityRegistry
    mock_registry = IdentityRegistry.__new__(IdentityRegistry)
    mock_registry._identities = _MOCK_IDENTITIES["identities"]
    mock_registry._history = []
    mock_registry._path = None

    mock_photo_reg = MagicMock()
    mock_photo_reg.list_photos = MagicMock(return_value=[])
    mock_photo_reg.get_photo = MagicMock(return_value=None)
    mock_photo_reg.get_photo_for_face = MagicMock(return_value=None)

    import pathlib
    orig_exists = pathlib.Path.exists
    orig_read_text = pathlib.Path.read_text

    def mock_exists(self):
        s = str(self)
        if "photo_locations" in s:
            return True
        if "photo_index" in s:
            return True
        if "co_occurrence" in s or "relationships" in s:
            return False
        return orig_exists(self)

    def mock_read_text(self, **kwargs):
        s = str(self)
        if "photo_locations" in s:
            return json.dumps(_MOCK_LOCATIONS)
        if "photo_index" in s:
            return json.dumps(_MOCK_PHOTO_INDEX)
        return orig_read_text(self, **kwargs)

    return [
        patch("app.main.is_auth_enabled", return_value=False),
        patch("app.main.load_registry", return_value=mock_registry),
        patch("app.main.load_photo_registry", return_value=mock_photo_reg),
        patch("app.main._build_caches"),
        patch("app.main.get_crop_files", return_value={}),
        patch("core.storage.get_photo_url", side_effect=lambda p: f"/photos/{p}"),
        patch("app.main._load_date_labels", return_value={}),
        patch.object(pathlib.Path, "exists", mock_exists),
        patch.object(pathlib.Path, "read_text", mock_read_text),
    ]


class TestMapPage:
    def test_renders(self, client):
        patches = _patch_map()
        for p in patches: p.start()
        resp = client.get("/map")
        for p in patches: p.stop()
        assert resp.status_code == 200
        assert "Map" in resp.text

    def test_leaflet_loaded(self, client):
        patches = _patch_map()
        for p in patches: p.start()
        resp = client.get("/map")
        for p in patches: p.stop()
        assert "leaflet" in resp.text.lower()

    def test_map_container(self, client):
        patches = _patch_map()
        for p in patches: p.start()
        resp = client.get("/map")
        for p in patches: p.stop()
        assert "map-container" in resp.text

    def test_markers_in_script(self, client):
        patches = _patch_map()
        for p in patches: p.start()
        resp = client.get("/map")
        for p in patches: p.stop()
        assert "New York City" in resp.text
        assert "Miami" in resp.text

    def test_og_tags(self, client):
        patches = _patch_map()
        for p in patches: p.start()
        resp = client.get("/map")
        for p in patches: p.stop()
        assert "og:title" in resp.text

    def test_nav_links(self, client):
        patches = _patch_map()
        for p in patches: p.start()
        resp = client.get("/map")
        for p in patches: p.stop()
        assert 'href="/photos"' in resp.text
        assert 'href="/people"' in resp.text
        assert 'href="/timeline"' in resp.text
        assert 'href="/connect"' in resp.text

    def test_collection_filter(self, client):
        patches = _patch_map()
        for p in patches: p.start()
        resp = client.get("/map")
        for p in patches: p.stop()
        assert "All collections" in resp.text

    def test_share_button(self, client):
        patches = _patch_map()
        for p in patches: p.start()
        resp = client.get("/map")
        for p in patches: p.stop()
        assert "share-photo" in resp.text

    def test_photo_count_summary(self, client):
        patches = _patch_map()
        for p in patches: p.start()
        resp = client.get("/map")
        for p in patches: p.stop()
        assert "2 photos" in resp.text
        assert "2 locations" in resp.text

    def test_marker_clustering(self, client):
        patches = _patch_map()
        for p in patches: p.start()
        resp = client.get("/map")
        for p in patches: p.stop()
        assert "markercluster" in resp.text.lower()


class TestGeocodingScript:
    """Test the geocoding dictionary matching logic."""

    def test_match_rhodes(self):
        from scripts.geocode_photos import match_location, load_location_dictionary
        dictionary = load_location_dictionary()
        matches = match_location("Likely Rhodes, Greece or New York City", dictionary)
        assert len(matches) >= 1
        names = [m["name"] for m in matches]
        assert "Rhodes, Greece" in names

    def test_match_nyc(self):
        from scripts.geocode_photos import match_location, load_location_dictionary
        dictionary = load_location_dictionary()
        matches = match_location("New York City, USA", dictionary)
        assert len(matches) >= 1
        assert matches[0]["name"] == "New York City"

    def test_match_lower_east_side_specific(self):
        from scripts.geocode_photos import match_location, load_location_dictionary
        dictionary = load_location_dictionary()
        matches = match_location("Lower East Side, Manhattan, New York City (Rivington Street)", dictionary)
        # Lower East Side should be first (more specific than NYC)
        assert matches[0]["name"] == "Lower East Side, Manhattan"

    def test_match_miami(self):
        from scripts.geocode_photos import match_location, load_location_dictionary
        dictionary = load_location_dictionary()
        matches = match_location("Likely USA (Miami or Tampa, Florida)", dictionary)
        names = [m["name"] for m in matches]
        assert "Miami, Florida" in names

    def test_match_congo(self):
        from scripts.geocode_photos import match_location, load_location_dictionary
        dictionary = load_location_dictionary()
        matches = match_location("Elisabethville (Lubumbashi), Belgian Congo", dictionary)
        assert len(matches) >= 1
        assert "Congo" in matches[0]["name"]

    def test_no_match_unknown(self):
        from scripts.geocode_photos import match_location, load_location_dictionary
        dictionary = load_location_dictionary()
        matches = match_location("Unknown (studio portrait)", dictionary)
        assert len(matches) == 0

    def test_specificity_ordering(self):
        from scripts.geocode_photos import match_location, load_location_dictionary
        dictionary = load_location_dictionary()
        # Brooklyn should be more specific than NYC
        matches = match_location("Brooklyn, New York", dictionary)
        assert matches[0]["name"] == "Brooklyn, New York"

    def test_geocode_all(self):
        from scripts.geocode_photos import geocode_all, load_location_dictionary
        dictionary = load_location_dictionary()
        labels = [
            {"photo_id": "p1", "location_estimate": "Rhodes, Greece"},
            {"photo_id": "p2", "location_estimate": "New York City, USA"},
            {"photo_id": "p3", "location_estimate": "Unknown (studio portrait)"},
        ]
        results = geocode_all(labels, dictionary)
        assert "p1" in results
        assert "p2" in results
        assert "p3" not in results  # Unknown should not match
        assert results["p1"]["location_name"] == "Rhodes, Greece"
        assert results["p2"]["lat"] == 40.7128
