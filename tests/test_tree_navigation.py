"""Tests for photo->tree smart navigation (Session 81 Act 1).

Tests cover:
- Nuclear family detection (parents + children in one photo)
- Single person -> immediate family
- Unrelated people -> side-by-side families
- Connected people -> path union
- No GEDCOM data -> graceful fallback
- Person page tree link present
- Tree page with people param
- API /api/tree/data with people param
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import (
    app,
    _bfs_immediate_family,
    _bfs_shortest_path,
    _is_nuclear_family,
    compute_subtree_for_photo,
)


@pytest.fixture
def client():
    return TestClient(app)


# --- Adjacency data for tests ---

def _build_adjacency():
    """Build ptc, ctp, pts for a multi-generation family.

    Family structure:
        grandpa + grandma (spouses)
            -> father
            -> uncle
        father + mother (spouses)
            -> child1
            -> child2
        uncle + aunt (spouses)
            -> cousin

    Disconnected family:
        dad-b + mom-b
            -> kid-b
    """
    ptc = {  # parent_to_children
        "grandpa": {"father", "uncle"},
        "grandma": {"father", "uncle"},
        "father": {"child1", "child2"},
        "mother": {"child1", "child2"},
        "uncle": {"cousin"},
        "aunt": {"cousin"},
        "dad-b": {"kid-b"},
        "mom-b": {"kid-b"},
    }
    ctp = {  # child_to_parents
        "father": {"grandpa", "grandma"},
        "uncle": {"grandpa", "grandma"},
        "child1": {"father", "mother"},
        "child2": {"father", "mother"},
        "cousin": {"uncle", "aunt"},
        "kid-b": {"dad-b", "mom-b"},
    }
    pts = {  # person_to_spouses
        "grandpa": {"grandma"},
        "grandma": {"grandpa"},
        "father": {"mother"},
        "mother": {"father"},
        "uncle": {"aunt"},
        "aunt": {"uncle"},
        "dad-b": {"mom-b"},
        "mom-b": {"dad-b"},
    }
    return ptc, ctp, pts


class TestBfsImmediateFamily:
    """Test _bfs_immediate_family returns the correct immediate family."""

    def test_single_person_with_family(self):
        ptc, ctp, pts = _build_adjacency()
        family = _bfs_immediate_family("father", ptc, ctp, pts)
        # father's immediate family: parents (grandpa, grandma), spouse (mother),
        # children (child1, child2), siblings (uncle)
        assert "father" in family
        assert "grandpa" in family
        assert "grandma" in family
        assert "mother" in family
        assert "child1" in family
        assert "child2" in family
        assert "uncle" in family  # sibling

    def test_leaf_person(self):
        ptc, ctp, pts = _build_adjacency()
        family = _bfs_immediate_family("child1", ptc, ctp, pts)
        assert "child1" in family
        assert "father" in family
        assert "mother" in family
        assert "child2" in family  # sibling

    def test_no_relationships(self):
        """Person with no relationships returns just themselves."""
        family = _bfs_immediate_family("loner", {}, {}, {})
        assert family == {"loner"}


class TestIsNuclearFamily:
    """Test _is_nuclear_family detection."""

    def test_parent_and_child(self):
        ptc, ctp, pts = _build_adjacency()
        assert _is_nuclear_family(["father", "child1"], ptc, ctp, pts) is True

    def test_parent_and_children(self):
        ptc, ctp, pts = _build_adjacency()
        assert _is_nuclear_family(["father", "child1", "child2"], ptc, ctp, pts) is True

    def test_both_parents_and_children(self):
        ptc, ctp, pts = _build_adjacency()
        assert _is_nuclear_family(
            ["father", "mother", "child1", "child2"], ptc, ctp, pts
        ) is True

    def test_siblings_only_not_nuclear(self):
        """Two siblings without parents present are NOT a nuclear family.

        They are connected but the nuclear family detection requires
        a parent-child relationship within the group.
        """
        ptc, ctp, pts = _build_adjacency()
        # child1 and child2 share parents but parents aren't in the group
        assert _is_nuclear_family(["child1", "child2"], ptc, ctp, pts) is False

    def test_grandparent_and_grandchild_not_nuclear(self):
        """Grandparent-grandchild is NOT a nuclear family (no direct parent-child)."""
        ptc, ctp, pts = _build_adjacency()
        assert _is_nuclear_family(["grandpa", "child1"], ptc, ctp, pts) is False

    def test_unrelated_people_not_nuclear(self):
        ptc, ctp, pts = _build_adjacency()
        assert _is_nuclear_family(["father", "dad-b"], ptc, ctp, pts) is False

    def test_single_person_not_nuclear(self):
        ptc, ctp, pts = _build_adjacency()
        assert _is_nuclear_family(["father"], ptc, ctp, pts) is False

    def test_spouse_pair(self):
        """Spouses without children in the set: not nuclear (no parent-child link)."""
        ptc, ctp, pts = _build_adjacency()
        assert _is_nuclear_family(["father", "mother"], ptc, ctp, pts) is False

    def test_parent_spouse_and_child(self):
        """Parent + spouse + child = nuclear family."""
        ptc, ctp, pts = _build_adjacency()
        assert _is_nuclear_family(
            ["father", "mother", "child1"], ptc, ctp, pts
        ) is True


class TestBfsShortestPath:
    """Test _bfs_shortest_path."""

    def test_same_person(self):
        ptc, ctp, pts = _build_adjacency()
        path = _bfs_shortest_path("father", "father", ptc, ctp, pts)
        assert path == ["father"]

    def test_parent_child_direct(self):
        ptc, ctp, pts = _build_adjacency()
        path = _bfs_shortest_path("father", "child1", ptc, ctp, pts)
        assert path is not None
        assert len(path) == 2
        assert path[0] == "father"
        assert path[-1] == "child1"

    def test_grandparent_to_grandchild(self):
        ptc, ctp, pts = _build_adjacency()
        path = _bfs_shortest_path("grandpa", "child1", ptc, ctp, pts)
        assert path is not None
        assert path[0] == "grandpa"
        assert path[-1] == "child1"
        assert len(path) == 3  # grandpa -> father -> child1

    def test_cousins(self):
        ptc, ctp, pts = _build_adjacency()
        path = _bfs_shortest_path("child1", "cousin", ptc, ctp, pts)
        assert path is not None
        assert path[0] == "child1"
        assert path[-1] == "cousin"

    def test_disconnected(self):
        ptc, ctp, pts = _build_adjacency()
        path = _bfs_shortest_path("father", "kid-b", ptc, ctp, pts)
        assert path is None

    def test_respects_max_depth(self):
        ptc, ctp, pts = _build_adjacency()
        # grandpa->father->child1 is 3 hops, so max_depth=1 should fail
        path = _bfs_shortest_path("grandpa", "child1", ptc, ctp, pts, max_depth=1)
        assert path is None


class TestComputeSubtreeForPhoto:
    """Test compute_subtree_for_photo smart subtree computation."""

    def test_empty_list(self):
        ptc, ctp, pts = _build_adjacency()
        result = compute_subtree_for_photo([], ptc, ctp, pts)
        assert result == set()

    def test_single_person(self):
        """Single person returns immediate family."""
        ptc, ctp, pts = _build_adjacency()
        result = compute_subtree_for_photo(["father"], ptc, ctp, pts)
        assert "father" in result
        assert "mother" in result  # spouse
        assert "grandpa" in result  # parent
        assert "grandma" in result  # parent
        assert "child1" in result  # child
        assert "child2" in result  # child

    def test_nuclear_family_photo(self):
        """Parents + children in one photo returns nuclear family subtree."""
        ptc, ctp, pts = _build_adjacency()
        result = compute_subtree_for_photo(
            ["father", "mother", "child1", "child2"], ptc, ctp, pts
        )
        assert "father" in result
        assert "mother" in result
        assert "child1" in result
        assert "child2" in result

    def test_connected_people_path(self):
        """Two connected but not nuclear people -> path union."""
        ptc, ctp, pts = _build_adjacency()
        # child1 and cousin are connected through father->grandpa->uncle->cousin
        result = compute_subtree_for_photo(["child1", "cousin"], ptc, ctp, pts)
        assert "child1" in result
        assert "cousin" in result
        # Path should include intermediate people
        assert len(result) > 2

    def test_unrelated_people_fallback(self):
        """Unrelated people -> side-by-side immediate families."""
        ptc, ctp, pts = _build_adjacency()
        result = compute_subtree_for_photo(["father", "kid-b"], ptc, ctp, pts)
        # Should include both families
        assert "father" in result
        assert "kid-b" in result
        # father's family
        assert "mother" in result or "child1" in result or "grandpa" in result
        # kid-b's family
        assert "dad-b" in result or "mom-b" in result

    def test_no_gedcom_data_graceful(self):
        """People with no GEDCOM relationships -> returns each person's (empty) family."""
        result = compute_subtree_for_photo(["person-a", "person-b"], {}, {}, {})
        # Should still return both people
        assert "person-a" in result
        assert "person-b" in result

    def test_partial_nuclear_family(self):
        """Parent + one child = nuclear family detection."""
        ptc, ctp, pts = _build_adjacency()
        result = compute_subtree_for_photo(["father", "child1"], ptc, ctp, pts)
        assert "father" in result
        assert "child1" in result
        # Nuclear family detection should also include the other child and mother
        assert "child2" in result
        assert "mother" in result

    def test_single_person_no_relationships(self):
        """Single person with no relationships returns just them."""
        result = compute_subtree_for_photo(["loner"], {}, {}, {})
        assert result == {"loner"}


# --- Integration tests (route-level) ---

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
        "id-mother": {
            "identity_id": "id-mother",
            "name": "Vida Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face-m"],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        },
        "id-child": {
            "identity_id": "id-child",
            "name": "Moise Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face-c"],
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
        {"person_a": "id-grandpa", "person_b": "id-father", "type": "parent_child",
         "source": "gedcom"},
        {"person_a": "id-grandma", "person_b": "id-father", "type": "parent_child",
         "source": "gedcom"},
        {"person_a": "id-grandpa", "person_b": "id-grandma", "type": "spouse",
         "source": "gedcom"},
        {"person_a": "id-father", "person_b": "id-child", "type": "parent_child",
         "source": "gedcom"},
        {"person_a": "id-mother", "person_b": "id-child", "type": "parent_child",
         "source": "gedcom"},
        {"person_a": "id-father", "person_b": "id-mother", "type": "spouse",
         "source": "gedcom"},
    ],
    "gedcom_imports": [],
}

_MOCK_PHOTO_INDEX = {
    "schema_version": 1,
    "photos": {
        "photo-1": {
            "path": "Image_001.jpg",
            "face_ids": ["face-f", "face-m", "face-c"],
            "filename": "Image_001.jpg",
        },
    },
    "face_to_photo": {
        "face-f": "photo-1",
        "face-m": "photo-1",
        "face-c": "photo-1",
        "face-gp": "photo-2",
        "face-gm": "photo-2",
    },
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
    mock_photo_reg.get_photos_for_faces = MagicMock(return_value=["photo-1"])
    mock_photo_reg._photos = _MOCK_PHOTO_INDEX["photos"]

    patches = [
        patch("app.main.is_auth_enabled", return_value=False),
        patch("app.main.load_registry", return_value=mock_registry),
        patch("app.main.load_photo_registry", return_value=mock_photo_reg),
        patch("app.main._build_caches"),
        patch("app.main.get_crop_files", return_value={}),
        patch("app.main._load_relationship_graph", return_value=_MOCK_REL_GRAPH),
        patch("app.main._load_current_gedcom_relationship_edges", return_value=[]),
        patch("app.main._load_gedcom_face_links", return_value={}),
        patch("app.main._load_gedcom_individuals", return_value=[]),
        patch("app.main._face_to_photo_cache", _MOCK_PHOTO_INDEX["face_to_photo"]),
        patch("app.main._photo_cache", _MOCK_PHOTO_INDEX["photos"]),
    ]
    return patches


class TestTreePageWithPeople:
    """Test /tree route with people query param."""

    def test_tree_with_people_param(self, client):
        """GET /tree?people=id1,id2 renders tree page and passes people to JS."""
        patches = _patch_data()
        for p in patches:
            p.start()
        try:
            resp = client.get("/tree?people=id-father,id-child")
            assert resp.status_code == 200
            assert "tree-container" in resp.text
            # JS init should include the people list
            assert "id-father" in resp.text
            assert "id-child" in resp.text
            assert "initRhodesliTree" in resp.text
        finally:
            for p in patches:
                p.stop()

    def test_tree_people_param_picks_first_as_focal(self, client):
        """When people param is provided, first person becomes focal person."""
        patches = _patch_data()
        for p in patches:
            p.start()
        try:
            resp = client.get("/tree?people=id-father,id-child")
            assert resp.status_code == 200
            # The first person in the list should be the focal person
            assert "Leon Capeluto" in resp.text  # id-father's name in the title
        finally:
            for p in patches:
                p.stop()

    def test_tree_people_param_with_photo_id(self, client):
        """Both photo_id and people params accepted."""
        patches = _patch_data()
        for p in patches:
            p.start()
        try:
            resp = client.get("/tree?photo_id=photo-1&people=id-father,id-child")
            assert resp.status_code == 200
            assert "tree-container" in resp.text
        finally:
            for p in patches:
                p.stop()


class TestTreeApiWithPeople:
    """Test /api/tree/data with people query param for smart subtree."""

    def test_api_tree_data_with_people(self, client):
        """API returns smart subtree when people param provided."""
        patches = _patch_data()
        for p in patches:
            p.start()
        try:
            resp = client.get(
                "/api/tree/data?person_id=id-father&people=id-father,id-child"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "nodes" in data
            assert "focal_person" in data
            assert data["focal_person"] == "id-father"
            # Should include photo_people in the response
            assert "photo_people" in data
            assert "id-father" in data["photo_people"]
            assert "id-child" in data["photo_people"]
            # Nodes should include the people and their family
            node_ids = {n["id"] for n in data["nodes"]}
            assert "id-father" in node_ids
            assert "id-child" in node_ids
        finally:
            for p in patches:
                p.stop()

    def test_api_tree_data_single_person_no_people_param(self, client):
        """API works normally without people param."""
        patches = _patch_data()
        for p in patches:
            p.start()
        try:
            resp = client.get("/api/tree/data?person_id=id-father&depth=1")
            assert resp.status_code == 200
            data = resp.json()
            assert data["focal_person"] == "id-father"
            assert "photo_people" not in data
        finally:
            for p in patches:
                p.stop()

    def test_api_tree_data_nuclear_family(self, client):
        """Nuclear family (parent+child) returns nuclear subtree."""
        patches = _patch_data()
        for p in patches:
            p.start()
        try:
            resp = client.get(
                "/api/tree/data?person_id=id-father&people=id-father,id-mother,id-child"
            )
            assert resp.status_code == 200
            data = resp.json()
            node_ids = {n["id"] for n in data["nodes"]}
            # Nuclear family should include parents, children, and their connections
            assert "id-father" in node_ids
            assert "id-mother" in node_ids
            assert "id-child" in node_ids
        finally:
            for p in patches:
                p.stop()


class TestPersonPageTreeLink:
    """Test that person pages have tree links for both admin and public users."""

    def test_person_page_has_tree_link_in_action_bar(self, client):
        """Person page action bar includes Family Tree link."""
        patches = _patch_data()
        extra_patches = [
            patch("app.main._load_social_graph", return_value={"nodes": {}, "edges": {}}),
            patch("app.main._load_annotations", return_value={"annotations": {}}),
            patch("app.main._load_date_labels", return_value={}),
            patch("app.main._load_birth_year_estimates", return_value={}),
            patch("app.main.get_photo_metadata", return_value=None),
            patch("app.main.get_photo_id_for_face", return_value=None),
            patch("app.main.resolve_face_image_url", return_value=None),
            patch("app.main.get_best_face_id", return_value=None),
        ]
        for p in patches + extra_patches:
            p.start()
        try:
            resp = client.get("/person/id-father")
            assert resp.status_code == 200
            assert "person-action-bar" in resp.text
            assert 'href="/tree?person=id-father"' in resp.text
            assert "Family Tree" in resp.text
        finally:
            for p in patches + extra_patches:
                p.stop()

    def test_person_page_tree_link_for_non_admin(self, client):
        """Tree link appears for non-admin users too."""
        from app.main import User

        patches = _patch_data()
        extra_patches = [
            patch("app.main._load_social_graph", return_value={"nodes": {}, "edges": {}}),
            patch("app.main._load_annotations", return_value={"annotations": {}}),
            patch("app.main._load_date_labels", return_value={}),
            patch("app.main._load_birth_year_estimates", return_value={}),
            patch("app.main.get_photo_metadata", return_value=None),
            patch("app.main.get_photo_id_for_face", return_value=None),
            patch("app.main.resolve_face_image_url", return_value=None),
            patch("app.main.get_best_face_id", return_value=None),
            patch("app.main.is_auth_enabled", return_value=True),
            patch("app.main.get_current_user", return_value=User(
                id="user-1", email="viewer@test.com", is_admin=False)),
        ]
        for p in patches:
            p.start()
        # Override is_auth_enabled to True (patched as False in _patch_data)
        for p in extra_patches:
            p.start()
        try:
            resp = client.get("/person/id-father")
            assert resp.status_code == 200
            # Action bar with tree link should be present even for non-admin
            assert "person-action-bar" in resp.text
            assert 'href="/tree?person=id-father"' in resp.text
        finally:
            for p in extra_patches:
                p.stop()
            for p in patches:
                p.stop()
