"""
Smoke tests for all public routes.

Verifies that every public-facing route returns HTTP 200.
Uses mocked data to avoid dependency on production data files.

IMPORTANT: Does NOT patch pathlib.Path globally, which can leak state
into other tests. Instead, patches high-level app.main functions.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Shared mock data
# ---------------------------------------------------------------------------

_MOCK_IDENTITIES = {
    "identities": {
        "test-confirmed-1": {
            "identity_id": "test-confirmed-1",
            "name": "Leon Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face-a1"],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        },
        "test-unidentified-1": {
            "identity_id": "test-unidentified-1",
            "name": "Unidentified Person 001",
            "state": "INBOX",
            "anchor_ids": [],
            "candidate_ids": ["face-b1"],
            "negative_ids": [],
            "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        },
    },
    "history": [],
}

_MOCK_REL_GRAPH = {
    "schema_version": 1,
    "relationships": [
        {"person_a": "test-confirmed-1", "person_b": "test-unidentified-1",
         "type": "parent_child", "source": "gedcom"},
    ],
    "gedcom_imports": [],
}

_MOCK_LOCATIONS = {
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
}


# ---------------------------------------------------------------------------
# Helper to build all standard patches
# ---------------------------------------------------------------------------

def _build_mock_registry():
    """Build a mock IdentityRegistry from test data."""
    from core.registry import IdentityRegistry

    mock_registry = IdentityRegistry.__new__(IdentityRegistry)
    mock_registry._identities = _MOCK_IDENTITIES["identities"]
    mock_registry._history = []
    mock_registry._path = None
    return mock_registry


def _build_mock_photo_reg():
    """Build a mock PhotoRegistry."""
    mock_photo_reg = MagicMock()
    mock_photo_reg.list_photos = MagicMock(return_value=[])
    mock_photo_reg._photos = {}
    mock_photo_reg.get_photo_for_face = MagicMock(return_value=None)
    mock_photo_reg.get_photos_for_faces = MagicMock(return_value=set())
    return mock_photo_reg


def _standard_patches():
    """
    Return a list of patch context managers that mock data loading
    for all public routes.

    Avoids patching pathlib.Path globally to prevent state leaks
    into other test modules.
    """
    mock_registry = _build_mock_registry()
    mock_photo_reg = _build_mock_photo_reg()

    return [
        patch("app.main.is_auth_enabled", return_value=False),
        patch("app.main.load_registry", return_value=mock_registry),
        patch("app.main.load_photo_registry", return_value=mock_photo_reg),
        patch("app.main._build_caches"),
        patch("app.main.get_crop_files", return_value={}),
        patch("app.main._load_date_labels", return_value={}),
        patch("app.main._load_relationship_graph", return_value=_MOCK_REL_GRAPH),
        patch("app.main._load_photo_locations", return_value=_MOCK_LOCATIONS),
        patch("core.storage.get_photo_url", side_effect=lambda p: f"/photos/{p}"),
    ]


def _run_with_patches(client, method, url, extra_patches=None):
    """Run a request with all standard patches active."""
    patches = _standard_patches()
    if extra_patches:
        patches.extend(extra_patches)
    for p in patches:
        p.start()
    try:
        if method == "GET":
            return client.get(url)
        return client.request(method, url)
    finally:
        for p in patches:
            p.stop()


# ---------------------------------------------------------------------------
# Route smoke tests
# ---------------------------------------------------------------------------


class TestCriticalRoutes:
    """Every public route must return HTTP 200."""

    def test_landing_page(self, client):
        """GET / returns 200."""
        resp = _run_with_patches(client, "GET", "/")
        assert resp.status_code == 200

    def test_photos_page(self, client):
        """GET /photos returns 200."""
        resp = _run_with_patches(client, "GET", "/photos")
        assert resp.status_code == 200

    def test_collections_page(self, client):
        """GET /collections returns 200."""
        resp = _run_with_patches(client, "GET", "/collections")
        assert resp.status_code == 200

    def test_people_page(self, client):
        """GET /people returns 200."""
        resp = _run_with_patches(client, "GET", "/people")
        assert resp.status_code == 200

    def test_map_page(self, client):
        """GET /map returns 200."""
        resp = _run_with_patches(client, "GET", "/map")
        assert resp.status_code == 200

    def test_connect_page(self, client):
        """GET /connect returns 200."""
        resp = _run_with_patches(client, "GET", "/connect")
        assert resp.status_code == 200

    def test_tree_page(self, client):
        """GET /tree returns 200."""
        resp = _run_with_patches(client, "GET", "/tree")
        assert resp.status_code == 200

    def test_timeline_page(self, client):
        """GET /timeline returns 200."""
        resp = _run_with_patches(client, "GET", "/timeline")
        assert resp.status_code == 200

    def test_compare_page(self, client):
        """GET /compare returns 200."""
        resp = _run_with_patches(client, "GET", "/compare")
        assert resp.status_code == 200

    def test_identify_unidentified_person(self, client):
        """GET /identify/{id} returns 200 for an unidentified person."""
        resp = _run_with_patches(client, "GET", "/identify/test-unidentified-1")
        assert resp.status_code == 200
