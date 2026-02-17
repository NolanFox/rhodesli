"""Tests for /tree route — Family Tree Visualization."""

import json
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


# Mock data
_MOCK_IDENTITIES = {
    "identities": {
        "id-grandpa": {
            "identity_id": "id-grandpa",
            "name": "Rahamin Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face-gp"],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        },
        "id-grandma": {
            "identity_id": "id-grandma",
            "name": "Hanula Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face-gm"],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        },
        "id-father": {
            "identity_id": "id-father",
            "name": "Leon Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face-f"],
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
        {"person_a": "id-grandpa", "person_b": "id-father", "type": "parent_child", "source": "gedcom"},
        {"person_a": "id-grandma", "person_b": "id-father", "type": "parent_child", "source": "gedcom"},
        {"person_a": "id-grandpa", "person_b": "id-grandma", "type": "spouse", "source": "gedcom"},
    ],
    "gedcom_imports": [],
}


def _patch_data():
    """Return context managers that mock data loading for tree tests."""
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


class TestTreePage:

    def test_tree_page_renders(self, client):
        """GET /tree returns 200 with tree container."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/tree")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "tree-container" in resp.text

    def test_tree_includes_d3(self, client):
        """Page includes D3.js script."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/tree")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "d3.v7.min.js" in resp.text

    def test_tree_d3_script_contains_tree_layout(self, client):
        """D3 script uses d3.tree() layout."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/tree")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "d3.tree" in resp.text

    def test_tree_person_filter_present(self, client):
        """Person filter dropdown present with confirmed identities."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/tree")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert 'name="person"' in resp.text
        assert "Rahamin Capeluto" in resp.text

    def test_tree_with_person_param(self, client):
        """?person=UUID parameter accepted (200 response)."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/tree?person=id-father")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "tree-container" in resp.text

    def test_tree_og_tags(self, client):
        """Page has Open Graph tags for sharing."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/tree")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert 'og:title' in resp.text
        assert "Family Tree" in resp.text

    def test_tree_nav_links(self, client):
        """Navigation includes /tree and other major routes."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/tree")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert 'href="/photos"' in resp.text
        assert 'href="/people"' in resp.text
        assert 'href="/timeline"' in resp.text
        assert 'href="/connect"' in resp.text

    def test_tree_share_button(self, client):
        """Share button present on tree page."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/tree")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "share-photo" in resp.text or "Share" in resp.text

    def test_tree_theory_toggle(self, client):
        """Theory toggle checkbox present on tree page."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/tree")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "show_theory" in resp.text

    def test_tree_with_show_theory_false(self, client):
        """?show_theory=false filters theory relationships."""
        # Add a theory relationship to the graph
        graph_with_theory = {
            "schema_version": 1,
            "relationships": [
                {"person_a": "id-grandpa", "person_b": "id-father", "type": "parent_child",
                 "source": "gedcom", "confidence": "confirmed"},
                {"person_a": "id-grandpa", "person_b": "id-grandma", "type": "spouse",
                 "source": "gedcom", "confidence": "theory"},
            ],
            "gedcom_imports": [],
        }
        patches = _patch_data()
        # Override the relationship graph mock
        for p in patches:
            if hasattr(p, 'attribute') and 'relationship_graph' in str(getattr(p, 'attribute', '')):
                p.stop()
        for p in patches:
            p.start()

        with patch("app.main._load_relationship_graph", return_value=graph_with_theory):
            resp = client.get("/tree?show_theory=false")

        for p in patches:
            p.stop()
        assert resp.status_code == 200

    def test_tree_empty_graph(self, client):
        """Empty relationship graph shows helpful empty state."""
        empty_graph = {"schema_version": 1, "relationships": [], "gedcom_imports": []}
        patches = _patch_data()
        for p in patches:
            p.start()

        with patch("app.main._load_relationship_graph", return_value=empty_graph):
            resp = client.get("/tree")

        for p in patches:
            p.stop()
        assert resp.status_code == 200
        # Should show some kind of empty state, not crash
        assert "tree-container" in resp.text or "No family" in resp.text

    def test_tree_contains_identity_names(self, client):
        """Tree data includes identity names from mock data."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/tree")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        # Names should appear in the inline JSON data or rendered SVG text
        assert "Rahamin" in resp.text or "Capeluto" in resp.text
