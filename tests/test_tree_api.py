"""Tests for tree API endpoints — lazy loading, search, expand."""

import json
from unittest.mock import patch, MagicMock

import pytest

# Minimal relationship graph for testing
_TEST_GRAPH = {
    "schema_version": 1,
    "relationships": [
        {"person_a": "father-1", "person_b": "child-1", "type": "parent_child", "source": "gedcom"},
        {"person_a": "mother-1", "person_b": "child-1", "type": "parent_child", "source": "gedcom"},
        {"person_a": "father-1", "person_b": "mother-1", "type": "spouse", "source": "gedcom"},
        {"person_a": "child-1", "person_b": "grandchild-1", "type": "parent_child", "source": "gedcom"},
        {"person_a": "father-1", "person_b": "child-2", "type": "parent_child", "source": "gedcom"},
        {"person_a": "mother-1", "person_b": "child-2", "type": "parent_child", "source": "gedcom"},
    ],
    "gedcom_imports": [],
}

_TEST_IDENTITIES = {
    "identities": {
        "father-1": {"identity_id": "father-1", "name": "Big Leon Capeluto", "state": "CONFIRMED",
                      "metadata": {"gender": "M", "birth_year": "1902"}, "anchor_ids": [], "candidate_ids": []},
        "mother-1": {"identity_id": "mother-1", "name": "Rachel Capeluto", "state": "CONFIRMED",
                      "metadata": {"gender": "F", "birth_year": "1905"}, "anchor_ids": [], "candidate_ids": []},
        "child-1": {"identity_id": "child-1", "name": "Nace Capeluto", "state": "CONFIRMED",
                     "metadata": {"gender": "M", "birth_year": "1930"}, "anchor_ids": [], "candidate_ids": []},
        "child-2": {"identity_id": "child-2", "name": "Betty Capeluto", "state": "CONFIRMED",
                     "metadata": {"gender": "F", "birth_year": "1933"}, "anchor_ids": [], "candidate_ids": []},
        "grandchild-1": {"identity_id": "grandchild-1", "name": "Leon Capeluto Jr", "state": "CONFIRMED",
                          "metadata": {"gender": "M", "birth_year": "1955"}, "anchor_ids": [], "candidate_ids": []},
    },
    "schema_version": 1,
}


@pytest.fixture
def mock_tree_data():
    """Mock data loading for tree API tests."""
    with patch("app.main._load_relationship_graph", return_value=_TEST_GRAPH), \
         patch("app.main._load_gedcom_individuals", return_value=[]), \
         patch("app.main._load_gedcom_face_links", return_value={}), \
         patch("app.main.get_crop_files", return_value=set()):
        # Also need to mock load_registry to return test identities
        mock_registry = MagicMock()
        mock_registry.list_identities.return_value = list(_TEST_IDENTITIES["identities"].values())

        def mock_get_identity(pid):
            ident = _TEST_IDENTITIES["identities"].get(pid)
            if not ident:
                raise KeyError(pid)
            return ident

        mock_registry.get_identity = mock_get_identity

        with patch("app.main.load_registry", return_value=mock_registry):
            yield


class TestTreeDataEndpoint:
    def test_returns_json_with_nodes(self, client, mock_tree_data):
        resp = client.get("/api/tree/data?person_id=father-1&depth=1")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "focal_person" in data
        assert len(data["nodes"]) > 0

    def test_focal_person_included(self, client, mock_tree_data):
        resp = client.get("/api/tree/data?person_id=child-1&depth=1")
        data = resp.json()
        ids = [n["id"] for n in data["nodes"]]
        assert "child-1" in ids

    def test_depth_1_includes_immediate_family(self, client, mock_tree_data):
        resp = client.get("/api/tree/data?person_id=child-1&depth=1")
        data = resp.json()
        ids = [n["id"] for n in data["nodes"]]
        # child-1's parents and child should be included
        assert "father-1" in ids
        assert "mother-1" in ids
        assert "grandchild-1" in ids

    def test_depth_0_returns_only_focal(self, client, mock_tree_data):
        resp = client.get("/api/tree/data?person_id=child-1&depth=0")
        data = resp.json()
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["id"] == "child-1"

    def test_default_person_selection(self, client, mock_tree_data):
        resp = client.get("/api/tree/data?depth=1")
        data = resp.json()
        assert data["focal_person"] != ""
        assert len(data["nodes"]) > 0

    def test_nodes_have_required_fields(self, client, mock_tree_data):
        resp = client.get("/api/tree/data?person_id=father-1&depth=1")
        data = resp.json()
        node = data["nodes"][0]
        assert "id" in node
        assert "data" in node
        assert "rels" in node
        assert "first name" in node["data"]
        assert "last name" in node["data"]
        assert "gender" in node["data"]

    def test_expansion_flags_present(self, client, mock_tree_data):
        resp = client.get("/api/tree/data?person_id=father-1&depth=0")
        data = resp.json()
        node = data["nodes"][0]
        assert "has_more_children" in node["data"]


class TestTreeExpandEndpoint:
    def test_expand_children(self, client, mock_tree_data):
        resp = client.get("/api/tree/expand?person_id=father-1&direction=children")
        assert resp.status_code == 200
        data = resp.json()
        ids = [n["id"] for n in data["nodes"]]
        assert "child-1" in ids
        assert "child-2" in ids

    def test_expand_parents(self, client, mock_tree_data):
        resp = client.get("/api/tree/expand?person_id=child-1&direction=parents")
        data = resp.json()
        ids = [n["id"] for n in data["nodes"]]
        assert "father-1" in ids
        assert "mother-1" in ids

    def test_expand_siblings(self, client, mock_tree_data):
        resp = client.get("/api/tree/expand?person_id=child-1&direction=siblings")
        data = resp.json()
        ids = [n["id"] for n in data["nodes"]]
        assert "child-2" in ids


class TestTreeSearchEndpoint:
    def test_search_by_name(self, client, mock_tree_data):
        resp = client.get("/api/tree/search?q=Leon")
        assert resp.status_code == 200
        data = resp.json()
        names = [r["name"] for r in data["results"]]
        assert any("Leon" in n for n in names)

    def test_search_min_length(self, client, mock_tree_data):
        resp = client.get("/api/tree/search?q=L")
        data = resp.json()
        assert data["results"] == []

    def test_search_case_insensitive(self, client, mock_tree_data):
        resp = client.get("/api/tree/search?q=leon")
        data = resp.json()
        assert len(data["results"]) > 0

    def test_search_results_have_fields(self, client, mock_tree_data):
        resp = client.get("/api/tree/search?q=Capeluto")
        data = resp.json()
        assert len(data["results"]) > 0
        result = data["results"][0]
        assert "id" in result
        assert "name" in result
        assert "has_photo" in result


class TestTreePageRendering:
    def test_tree_page_returns_200(self, client, mock_tree_data):
        resp = client.get("/tree")
        assert resp.status_code == 200

    def test_tree_page_has_search_input(self, client, mock_tree_data):
        resp = client.get("/tree")
        assert "tree-search-input" in resp.text

    def test_tree_page_has_zoom_controls(self, client, mock_tree_data):
        resp = client.get("/tree")
        assert "tree-zoom-in" in resp.text
        assert "tree-zoom-out" in resp.text

    def test_tree_page_loads_js(self, client, mock_tree_data):
        resp = client.get("/tree")
        assert "family-tree.js" in resp.text
        assert "initRhodesliTree" in resp.text
