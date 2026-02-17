"""Tests for /collections and /collection/{slug} routes."""

import json
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app, _collection_slug


@pytest.fixture
def client():
    return TestClient(app)


_MOCK_PHOTO_INDEX = {
    "schema_version": 1,
    "photos": {
        "photo-1": {
            "photo_id": "photo-1",
            "path": "image001.jpg",
            "face_ids": ["face-a1", "face-b1"],
            "source": "Vida NYC",
            "collection": "Vida NYC",
        },
        "photo-2": {
            "photo_id": "photo-2",
            "path": "image002.jpg",
            "face_ids": ["face-c1"],
            "source": "Betty Miami",
            "collection": "Betty Miami",
        },
        "photo-3": {
            "photo_id": "photo-3",
            "path": "image003.jpg",
            "face_ids": [],
            "source": "Vida NYC",
            "collection": "Vida NYC",
        },
    },
    "face_to_photo": {
        "face-a1": "photo-1",
        "face-b1": "photo-1",
        "face-c1": "photo-2",
    },
}

_MOCK_IDENTITIES = {
    "identities": {
        "id-a": {
            "identity_id": "id-a", "name": "Leon Capeluto", "state": "CONFIRMED",
            "anchor_ids": ["face-a1"], "candidate_ids": [], "negative_ids": [],
            "version_id": 1, "created_at": "2025-01-01T00:00:00Z", "updated_at": "2025-01-01T00:00:00Z",
        },
        "id-b": {
            "identity_id": "id-b", "name": "Unidentified Person 42", "state": "INBOX",
            "anchor_ids": ["face-b1"], "candidate_ids": [], "negative_ids": [],
            "version_id": 1, "created_at": "2025-01-01T00:00:00Z", "updated_at": "2025-01-01T00:00:00Z",
        },
        "id-c": {
            "identity_id": "id-c", "name": "Betty Capeluto", "state": "CONFIRMED",
            "anchor_ids": ["face-c1"], "candidate_ids": [], "negative_ids": [],
            "version_id": 1, "created_at": "2025-01-01T00:00:00Z", "updated_at": "2025-01-01T00:00:00Z",
        },
    },
    "history": [],
}


def _patch_collections():
    from core.registry import IdentityRegistry
    mock_registry = IdentityRegistry.__new__(IdentityRegistry)
    mock_registry._identities = _MOCK_IDENTITIES["identities"]
    mock_registry._history = []
    mock_registry._path = None

    mock_photo_reg = MagicMock()
    mock_photo_reg.list_photos = MagicMock(return_value=[])
    mock_photo_reg.get_photo_for_face = MagicMock(return_value=None)

    import pathlib
    orig_exists = pathlib.Path.exists
    orig_read_text = pathlib.Path.read_text

    def mock_exists(self):
        if "photo_index" in str(self):
            return True
        if "co_occurrence" in str(self) or "relationships" in str(self):
            return False
        return orig_exists(self)

    def mock_read_text(self, **kwargs):
        if "photo_index" in str(self):
            return json.dumps(_MOCK_PHOTO_INDEX)
        return orig_read_text(self, **kwargs)

    return [
        patch("app.main.is_auth_enabled", return_value=False),
        patch("app.main.load_registry", return_value=mock_registry),
        patch("app.main.load_photo_registry", return_value=mock_photo_reg),
        patch("app.main._build_caches"),
        patch("app.main.get_crop_files", return_value={}),
        patch("core.storage.get_photo_url", side_effect=lambda p: f"/photos/{p}"),
        patch.object(pathlib.Path, "exists", mock_exists),
        patch.object(pathlib.Path, "read_text", mock_read_text),
    ]


class TestCollectionSlug:
    def test_basic_slug(self):
        assert _collection_slug("Vida Capeluto NYC Collection") == "vida-capeluto-nyc-collection"

    def test_special_chars(self):
        assert _collection_slug("Jews of Rhodes: Family Memories & Heritage") == "jews-of-rhodes-family-memories-heritage"

    def test_newspapers(self):
        assert _collection_slug("Newspapers.com") == "newspapers-com"


class TestCollectionsDirectory:
    def test_page_renders(self, client):
        patches = _patch_collections()
        for p in patches: p.start()
        resp = client.get("/collections")
        for p in patches: p.stop()
        assert resp.status_code == 200
        assert "Collections" in resp.text

    def test_shows_all_collections(self, client):
        patches = _patch_collections()
        for p in patches: p.start()
        resp = client.get("/collections")
        for p in patches: p.stop()
        assert "Vida NYC" in resp.text
        assert "Betty Miami" in resp.text

    def test_has_nav(self, client):
        patches = _patch_collections()
        for p in patches: p.start()
        resp = client.get("/collections")
        for p in patches: p.stop()
        assert 'href="/photos"' in resp.text
        assert 'href="/people"' in resp.text
        assert 'href="/connect"' in resp.text

    def test_og_tags(self, client):
        patches = _patch_collections()
        for p in patches: p.start()
        resp = client.get("/collections")
        for p in patches: p.stop()
        assert "og:title" in resp.text


class TestCollectionDetail:
    def test_renders(self, client):
        patches = _patch_collections()
        for p in patches: p.start()
        resp = client.get("/collection/vida-nyc")
        for p in patches: p.stop()
        assert resp.status_code == 200
        assert "Vida NYC" in resp.text

    def test_photo_grid(self, client):
        patches = _patch_collections()
        for p in patches: p.start()
        resp = client.get("/collection/vida-nyc")
        for p in patches: p.stop()
        assert "collection-photo" in resp.text

    def test_share_button(self, client):
        patches = _patch_collections()
        for p in patches: p.start()
        resp = client.get("/collection/vida-nyc")
        for p in patches: p.stop()
        assert "Share Collection" in resp.text

    def test_timeline_link(self, client):
        patches = _patch_collections()
        for p in patches: p.start()
        resp = client.get("/collection/vida-nyc")
        for p in patches: p.stop()
        assert "/timeline?" in resp.text

    def test_not_found(self, client):
        patches = _patch_collections()
        for p in patches: p.start()
        resp = client.get("/collection/nonexistent-collection")
        for p in patches: p.stop()
        assert "Collection Not Found" in resp.text

    def test_breadcrumb(self, client):
        patches = _patch_collections()
        for p in patches: p.start()
        resp = client.get("/collection/vida-nyc")
        for p in patches: p.stop()
        assert 'href="/collections"' in resp.text

    def test_people_section(self, client):
        patches = _patch_collections()
        for p in patches: p.start()
        resp = client.get("/collection/vida-nyc")
        for p in patches: p.stop()
        assert "Leon Capeluto" in resp.text

    def test_help_identify_banner(self, client):
        patches = _patch_collections()
        for p in patches: p.start()
        resp = client.get("/collection/vida-nyc")
        for p in patches: p.stop()
        assert "help-identify-banner" in resp.text
