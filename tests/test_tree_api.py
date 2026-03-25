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
        "father-1": {
            "identity_id": "father-1",
            "name": "Big Leon Capeluto",
            "state": "CONFIRMED",
            "metadata": {"gender": "M", "birth_year": "1902"},
            "anchor_ids": [],
            "candidate_ids": [],
        },
        "mother-1": {
            "identity_id": "mother-1",
            "name": "Rachel Capeluto",
            "state": "CONFIRMED",
            "metadata": {"gender": "F", "birth_year": "1905"},
            "anchor_ids": [],
            "candidate_ids": [],
        },
        "child-1": {
            "identity_id": "child-1",
            "name": "Nace Capeluto",
            "state": "CONFIRMED",
            "metadata": {"gender": "M", "birth_year": "1930"},
            "anchor_ids": [],
            "candidate_ids": [],
        },
        "child-2": {
            "identity_id": "child-2",
            "name": "Betty Capeluto",
            "state": "CONFIRMED",
            "metadata": {"gender": "F", "birth_year": "1933"},
            "anchor_ids": [],
            "candidate_ids": [],
        },
        "grandchild-1": {
            "identity_id": "grandchild-1",
            "name": "Leon Capeluto Jr",
            "state": "CONFIRMED",
            "metadata": {"gender": "M", "birth_year": "1955"},
            "anchor_ids": [],
            "candidate_ids": [],
        },
    },
    "schema_version": 1,
}


@pytest.fixture
def mock_tree_data():
    """Mock data loading for tree API tests."""
    with (
        patch("app.main._load_relationship_graph", return_value=_TEST_GRAPH),
        patch("app.main._load_current_gedcom_relationship_edges", return_value=[]),
        patch("app.main._load_gedcom_individuals", return_value=[]),
        patch("app.main._load_gedcom_face_links", return_value={}),
        patch("app.main.get_crop_files", return_value=set()),
    ):
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

    def test_linked_identity_expand_avoids_full_gedcom_mirror_loads(self, client):
        mock_registry = MagicMock()
        mock_registry.get_identity = lambda pid: (
            {
                "child-1": {
                    "identity_id": "child-1",
                    "name": "Child One",
                    "state": "CONFIRMED",
                    "metadata": {"gender": "M", "birth_year": "1930"},
                    "anchor_ids": [],
                    "candidate_ids": [],
                }
            }.get(pid)
            or (_ for _ in ()).throw(KeyError(pid))
        )

        def mock_targeted_edges(gedcom_ids):
            ids = set(gedcom_ids)
            if ids == {"@I1@"}:
                return [
                    {"person_a": "@P1@", "person_b": "@I1@", "type": "parent_child", "source": "gedcom_current"},
                    {"person_a": "@P2@", "person_b": "@I1@", "type": "parent_child", "source": "gedcom_current"},
                ]
            if "@P1@" in ids or "@P2@" in ids:
                return [
                    {"person_a": "@P1@", "person_b": "@I1@", "type": "parent_child", "source": "gedcom_current"},
                    {"person_a": "@P2@", "person_b": "@I1@", "type": "parent_child", "source": "gedcom_current"},
                    {"person_a": "@P1@", "person_b": "@S1@", "type": "parent_child", "source": "gedcom_current"},
                    {"person_a": "@P2@", "person_b": "@S1@", "type": "parent_child", "source": "gedcom_current"},
                ]
            return []

        with (
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main.get_crop_files", return_value=set()),
            patch(
                "app.main._load_relationship_graph",
                return_value={"schema_version": 1, "relationships": [], "gedcom_imports": []},
            ),
            patch("app.main._load_gedcom_face_links", return_value={"child-1": {"gedcom_id": "@I1@"}}),
            patch("app.main._load_gedcom_matches", return_value={"matches": []}),
            patch("app.main._load_gedcom_relationship_edges_for_ids", side_effect=mock_targeted_edges),
            patch(
                "app.main._load_gedcom_individuals_by_ids",
                return_value=[
                    {"gedcom_id": "@P1@", "name": "Parent One", "gender": "M", "birth_date": "1900", "death_date": ""},
                    {"gedcom_id": "@P2@", "name": "Parent Two", "gender": "F", "birth_date": "1905", "death_date": ""},
                    {"gedcom_id": "@S1@", "name": "Sibling One", "gender": "F", "birth_date": "1932", "death_date": ""},
                ],
            ),
            patch(
                "app.main._load_current_gedcom_relationship_edges",
                side_effect=AssertionError("full tree edge load should not run"),
            ),
            patch(
                "app.main._load_gedcom_individuals",
                side_effect=AssertionError("full GEDCOM individual load should not run"),
            ),
        ):
            resp = client.get("/api/tree/expand?person_id=child-1&direction=siblings")

        assert resp.status_code == 200
        data = resp.json()
        ids = {n["id"] for n in data["nodes"]}
        assert ids == {"child-1", "@S1@"}


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


class TestTargetedTreeLoading:
    def test_linked_identity_data_avoids_full_gedcom_mirror_loads(self, client):
        identities = {
            "child-1": {
                "identity_id": "child-1",
                "name": "Child One",
                "state": "CONFIRMED",
                "metadata": {"gender": "M", "birth_year": "1930"},
                "anchor_ids": [],
                "candidate_ids": [],
            }
        }

        mock_registry = MagicMock()

        def mock_get_identity(pid):
            ident = identities.get(pid)
            if not ident:
                raise KeyError(pid)
            return ident

        mock_registry.get_identity = mock_get_identity

        def mock_targeted_edges(gedcom_ids):
            if set(gedcom_ids) == {"@I1@"}:
                return [
                    {"person_a": "@P1@", "person_b": "@I1@", "type": "parent_child", "source": "gedcom_current"},
                    {"person_a": "@P2@", "person_b": "@I1@", "type": "parent_child", "source": "gedcom_current"},
                ]
            return []

        with (
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main.get_crop_files", return_value=set()),
            patch(
                "app.main._load_relationship_graph",
                return_value={"schema_version": 1, "relationships": [], "gedcom_imports": []},
            ),
            patch("app.main._load_gedcom_face_links", return_value={"child-1": {"gedcom_id": "@I1@"}}),
            patch("app.main._load_gedcom_matches", return_value={"matches": []}),
            patch("app.main._load_gedcom_relationship_edges_for_ids", side_effect=mock_targeted_edges),
            patch(
                "app.main._load_gedcom_individuals_by_ids",
                return_value=[
                    {"gedcom_id": "@P1@", "name": "Parent One", "gender": "M", "birth_date": "1900", "death_date": ""},
                    {"gedcom_id": "@P2@", "name": "Parent Two", "gender": "F", "birth_date": "1905", "death_date": ""},
                ],
            ),
            patch(
                "app.main._load_current_gedcom_relationship_edges",
                side_effect=AssertionError("full tree edge load should not run"),
            ),
            patch(
                "app.main._load_gedcom_individuals",
                side_effect=AssertionError("full GEDCOM individual load should not run"),
            ),
        ):
            resp = client.get("/api/tree/data?person_id=child-1&depth=1")

        assert resp.status_code == 200
        data = resp.json()
        ids = {n["id"] for n in data["nodes"]}
        assert ids == {"child-1", "@P1@", "@P2@"}


class TestSharedPhotosInTree:
    """Tests for shared_photos field in tree node data."""

    def test_shared_photos_field_present(self, client, mock_tree_data):
        """Every tree node should include shared_photos in data."""
        resp = client.get("/api/tree/data?person_id=father-1&depth=1")
        data = resp.json()
        for node in data["nodes"]:
            assert "shared_photos" in node["data"], f"Node {node['id']} missing shared_photos"

    def test_shared_photos_empty_when_no_face_data(self, client, mock_tree_data):
        """With no face data, shared_photos should be empty dict."""
        resp = client.get("/api/tree/data?person_id=father-1&depth=1")
        data = resp.json()
        for node in data["nodes"]:
            assert node["data"]["shared_photos"] == {}, (
                f"Node {node['id']} has unexpected shared_photos: {node['data']['shared_photos']}"
            )

    def test_shared_photos_with_face_data(self, client):
        """When two people share photos, shared_photos should reflect the count."""
        # Create identities with overlapping face IDs in the same photos
        test_identities = {
            "identities": {
                "person-a": {
                    "identity_id": "person-a",
                    "name": "Person A",
                    "state": "CONFIRMED",
                    "metadata": {"gender": "M"},
                    "anchor_ids": ["face-a1", "face-a2"],
                    "candidate_ids": [],
                },
                "person-b": {
                    "identity_id": "person-b",
                    "name": "Person B",
                    "state": "CONFIRMED",
                    "metadata": {"gender": "F"},
                    "anchor_ids": ["face-b1"],
                    "candidate_ids": [],
                },
            },
            "schema_version": 1,
        }
        test_graph = {
            "schema_version": 1,
            "relationships": [
                {"person_a": "person-a", "person_b": "person-b", "type": "spouse", "source": "gedcom"},
            ],
            "gedcom_imports": [],
        }

        mock_registry = MagicMock()
        mock_registry.list_identities.return_value = list(test_identities["identities"].values())
        mock_registry.get_identity = lambda pid: test_identities["identities"].get(pid)

        # face-a1 and face-b1 are in photo-1 (shared), face-a2 is in photo-2 (not shared)
        mock_f2p = {"face-a1": "photo-1", "face-a2": "photo-2", "face-b1": "photo-1"}

        with (
            patch("app.main._load_relationship_graph", return_value=test_graph),
            patch("app.main._load_current_gedcom_relationship_edges", return_value=[]),
            patch("app.main._load_gedcom_individuals", return_value=[]),
            patch("app.main._load_gedcom_face_links", return_value={}),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main._build_caches"),
            patch("app.main._face_to_photo_cache", mock_f2p),
            patch("app.main._photo_cache", {}),
        ):
            resp = client.get("/api/tree/data?person_id=person-a&depth=1")
            data = resp.json()
            node_a = next(n for n in data["nodes"] if n["id"] == "person-a")
            node_b = next(n for n in data["nodes"] if n["id"] == "person-b")
            # Person A and Person B share 1 photo (photo-1)
            assert node_a["data"]["shared_photos"].get("person-b") == 1
            assert node_b["data"]["shared_photos"].get("person-a") == 1

    def test_shared_photos_in_expand_response(self, client):
        """Expand endpoint should also include shared_photos."""
        test_identities = {
            "identities": {
                "parent-x": {
                    "identity_id": "parent-x",
                    "name": "Parent X",
                    "state": "CONFIRMED",
                    "metadata": {"gender": "M"},
                    "anchor_ids": [],
                    "candidate_ids": [],
                },
                "child-x": {
                    "identity_id": "child-x",
                    "name": "Child X",
                    "state": "CONFIRMED",
                    "metadata": {"gender": "M"},
                    "anchor_ids": [],
                    "candidate_ids": [],
                },
            },
            "schema_version": 1,
        }
        test_graph = {
            "schema_version": 1,
            "relationships": [
                {"person_a": "parent-x", "person_b": "child-x", "type": "parent_child", "source": "gedcom"},
            ],
            "gedcom_imports": [],
        }

        mock_registry = MagicMock()
        mock_registry.list_identities.return_value = list(test_identities["identities"].values())
        mock_registry.get_identity = lambda pid: test_identities["identities"].get(pid)

        with (
            patch("app.main._load_relationship_graph", return_value=test_graph),
            patch("app.main._load_current_gedcom_relationship_edges", return_value=[]),
            patch("app.main._load_gedcom_individuals", return_value=[]),
            patch("app.main._load_gedcom_face_links", return_value={}),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main._build_caches"),
            patch("app.main._face_to_photo_cache", {}),
            patch("app.main._photo_cache", {}),
        ):
            resp = client.get("/api/tree/expand?person_id=parent-x&direction=children")
            data = resp.json()
            for node in data["nodes"]:
                assert "shared_photos" in node["data"]


class TestComputeSharedPhotos:
    """Unit tests for _compute_shared_photos helper."""

    def test_no_faces_returns_empty(self):
        """People with no face IDs should have no shared photos."""
        mock_registry = MagicMock()
        mock_registry.get_identity.return_value = {"anchor_ids": [], "candidate_ids": []}

        with patch("app.main._build_caches"), patch("app.main._face_to_photo_cache", {}):
            from app.main import _compute_shared_photos

            result = _compute_shared_photos({"p1", "p2"}, mock_registry)
            assert result == {}

    def test_shared_photo_detected(self):
        """Two people with faces in the same photo should show shared count."""
        mock_registry = MagicMock()

        def get_ident(pid):
            if pid == "p1":
                return {"anchor_ids": ["f1"], "candidate_ids": []}
            elif pid == "p2":
                return {"anchor_ids": ["f2"], "candidate_ids": []}
            return None

        mock_registry.get_identity = get_ident

        mock_f2p = {"f1": "photo-shared", "f2": "photo-shared"}

        with patch("app.main._build_caches"), patch("app.main._face_to_photo_cache", mock_f2p):
            from app.main import _compute_shared_photos

            result = _compute_shared_photos({"p1", "p2"}, mock_registry)
            assert result.get("p1", {}).get("p2") == 1
            assert result.get("p2", {}).get("p1") == 1

    def test_multiple_shared_photos(self):
        """Count should reflect number of shared photos, not faces."""
        mock_registry = MagicMock()

        def get_ident(pid):
            if pid == "p1":
                return {"anchor_ids": ["f1a", "f1b"], "candidate_ids": []}
            elif pid == "p2":
                return {"anchor_ids": ["f2a", "f2b"], "candidate_ids": []}
            return None

        mock_registry.get_identity = get_ident

        # f1a and f2a in photo-1, f1b and f2b in photo-2 = 2 shared photos
        mock_f2p = {"f1a": "photo-1", "f1b": "photo-2", "f2a": "photo-1", "f2b": "photo-2"}

        with patch("app.main._build_caches"), patch("app.main._face_to_photo_cache", mock_f2p):
            from app.main import _compute_shared_photos

            result = _compute_shared_photos({"p1", "p2"}, mock_registry)
            assert result.get("p1", {}).get("p2") == 2

    def test_no_overlap_returns_empty(self):
        """Two people in different photos should have no shared photos."""
        mock_registry = MagicMock()

        def get_ident(pid):
            if pid == "p1":
                return {"anchor_ids": ["f1"], "candidate_ids": []}
            elif pid == "p2":
                return {"anchor_ids": ["f2"], "candidate_ids": []}
            return None

        mock_registry.get_identity = get_ident

        mock_f2p = {"f1": "photo-1", "f2": "photo-2"}

        with patch("app.main._build_caches"), patch("app.main._face_to_photo_cache", mock_f2p):
            from app.main import _compute_shared_photos

            result = _compute_shared_photos({"p1", "p2"}, mock_registry)
            assert result == {}

    def test_identity_not_found_handled(self):
        """If registry.get_identity raises KeyError, it should be handled gracefully."""
        mock_registry = MagicMock()
        mock_registry.get_identity.side_effect = KeyError("not found")

        with patch("app.main._build_caches"), patch("app.main._face_to_photo_cache", {}):
            from app.main import _compute_shared_photos

            result = _compute_shared_photos({"p1", "p2"}, mock_registry)
            assert result == {}


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
