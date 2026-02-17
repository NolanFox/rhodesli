"""Tests for /connect route — Six Degrees Connection Finder."""

import json
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_disabled():
    with patch("app.main.is_auth_enabled", return_value=False):
        yield


# Mock data
_MOCK_IDENTITIES = {
    "identities": {
        "id-a": {
            "identity_id": "id-a",
            "name": "Big Leon Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face-a1"],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        },
        "id-b": {
            "identity_id": "id-b",
            "name": "Moise Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face-b1"],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        },
        "id-c": {
            "identity_id": "id-c",
            "name": "Victoria Capuano",
            "state": "CONFIRMED",
            "anchor_ids": ["face-c1"],
            "candidate_ids": [],
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
        {"person_a": "id-a", "person_b": "id-b", "type": "parent_child", "source": "gedcom"},
        {"person_a": "id-a", "person_b": "id-c", "type": "spouse", "source": "gedcom"},
    ],
    "gedcom_imports": [],
}

_MOCK_COOCCUR = {
    "schema_version": 1,
    "edges": [
        {"person_a": "id-b", "person_b": "id-c", "shared_photos": ["p1", "p2"], "count": 2},
    ],
}


def _patch_data():
    """Return context managers that mock data loading for connect tests."""
    from core.registry import IdentityRegistry

    mock_registry = IdentityRegistry.__new__(IdentityRegistry)
    mock_registry._identities = _MOCK_IDENTITIES["identities"]
    mock_registry._history = []
    mock_registry._path = None

    mock_photo_reg = MagicMock()
    mock_photo_reg.get_photo_for_face = MagicMock(return_value="photo-1")

    patches = [
        patch("app.main.is_auth_enabled", return_value=False),
        patch("app.main.load_registry", return_value=mock_registry),
        patch("app.main.load_photo_registry", return_value=mock_photo_reg),
        patch("app.main._build_caches"),
        patch("app.main.get_crop_files", return_value={}),
        patch("app.main._load_relationship_graph", return_value=_MOCK_REL_GRAPH),
    ]
    return patches


class TestConnectPage:

    def test_connect_page_renders(self, client):
        """GET /connect returns 200 with form."""
        patches = _patch_data()
        for p in patches:
            p.start()
        # Also patch the cooccur file read
        with patch("builtins.open", side_effect=FileNotFoundError):
            with patch("pathlib.Path.exists", return_value=False):
                resp = client.get("/connect")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "Connect People" in resp.text

    def test_connect_form_present(self, client):
        """Page has person selectors and submit button."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/connect")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert 'name="person_a"' in resp.text
        assert 'name="person_b"' in resp.text
        assert "Find Connection" in resp.text

    def test_connect_with_two_people(self, client):
        """Finding connection between two related people shows path."""
        patches = _patch_data()
        # Patch the co-occurrence file reading
        cooccur_patch = patch.object(
            type(next(iter([])).__class__) if False else type(MagicMock()),
            'exists', return_value=True,
        )
        for p in patches:
            p.start()

        # Need to also mock the co-occurrence file read
        import pathlib
        orig_exists = pathlib.Path.exists
        orig_read_text = pathlib.Path.read_text

        def mock_exists(self):
            if "co_occurrence" in str(self):
                return True
            return orig_exists(self)

        def mock_read_text(self, **kwargs):
            if "co_occurrence" in str(self):
                return json.dumps(_MOCK_COOCCUR)
            return orig_read_text(self, **kwargs)

        with patch.object(pathlib.Path, 'exists', mock_exists):
            with patch.object(pathlib.Path, 'read_text', mock_read_text):
                resp = client.get("/connect?person_a=id-a&person_b=id-b")

        for p in patches:
            p.stop()

        assert resp.status_code == 200
        assert "connection-result" in resp.text or "connection-path" in resp.text

    def test_connect_d3_graph_present(self, client):
        """Page includes D3.js visualization container."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/connect")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "graph-container" in resp.text
        assert "d3.v7.min.js" in resp.text

    def test_connect_nav_links(self, client):
        """Navigation includes all major routes."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/connect")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert 'href="/photos"' in resp.text
        assert 'href="/people"' in resp.text
        assert 'href="/timeline"' in resp.text
        assert 'href="/compare"' in resp.text

    def test_connect_og_tags(self, client):
        """Page has Open Graph tags for sharing."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/connect")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "og:title" in resp.text
        assert "Connect People" in resp.text

    def test_connect_share_button_with_selection(self, client):
        """Share button appears when both people are selected."""
        patches = _patch_data()
        for p in patches:
            p.start()

        import pathlib
        orig_exists = pathlib.Path.exists
        orig_read_text = pathlib.Path.read_text

        def mock_exists(self):
            if "co_occurrence" in str(self):
                return True
            return orig_exists(self)

        def mock_read_text(self, **kwargs):
            if "co_occurrence" in str(self):
                return json.dumps(_MOCK_COOCCUR)
            return orig_read_text(self, **kwargs)

        with patch.object(pathlib.Path, 'exists', mock_exists):
            with patch.object(pathlib.Path, 'read_text', mock_read_text):
                resp = client.get("/connect?person_a=id-a&person_b=id-b")

        for p in patches:
            p.stop()

        assert resp.status_code == 200
        assert "share-photo" in resp.text

    def test_connect_person_options(self, client):
        """Dropdowns contain confirmed identity names."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/connect")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "Big Leon Capeluto" in resp.text
        assert "Moise Capeluto" in resp.text
        assert "Victoria Capuano" in resp.text

    def test_connect_with_invalid_person_ids(self, client):
        """Passing invalid person IDs should not 500 — graceful degradation."""
        patches = _patch_data()
        for p in patches:
            p.start()

        import pathlib
        orig_exists = pathlib.Path.exists
        orig_read_text = pathlib.Path.read_text

        def mock_exists(self):
            if "co_occurrence" in str(self):
                return True
            return orig_exists(self)

        def mock_read_text(self, **kwargs):
            if "co_occurrence" in str(self):
                return json.dumps(_MOCK_COOCCUR)
            return orig_read_text(self, **kwargs)

        with patch.object(pathlib.Path, 'exists', mock_exists):
            with patch.object(pathlib.Path, 'read_text', mock_read_text):
                resp = client.get("/connect?person_a=nonexistent-id&person_b=also-invalid")

        for p in patches:
            p.stop()

        assert resp.status_code == 200
        assert "Unknown" in resp.text
