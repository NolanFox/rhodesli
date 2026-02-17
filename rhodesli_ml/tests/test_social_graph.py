"""Tests for unified social graph — merges relationships + co-occurrence.

Tests BFS pathfinding, proximity scoring, D3 export, and graph merging.
"""

import pytest

from rhodesli_ml.graph.social_graph import (
    build_social_graph,
    find_shortest_path,
    find_all_paths,
    compute_proximity,
    get_closest_connections,
    export_for_d3,
    compute_all_proximities,
)


# ─── Test Fixtures ───────────────────────────────────────────────


def _make_relationship_graph():
    """3-generation family: grandpa→parent→child, with spouse edges."""
    return {
        "schema_version": 1,
        "relationships": [
            # Grandpa (A) is parent of Parent (B)
            {"person_a": "A", "person_b": "B", "type": "parent_child", "source": "gedcom"},
            # Grandpa (A) is parent of Uncle (C)
            {"person_a": "A", "person_b": "C", "type": "parent_child", "source": "gedcom"},
            # Grandma (G) is parent of Parent (B) and Uncle (C)
            {"person_a": "G", "person_b": "B", "type": "parent_child", "source": "gedcom"},
            {"person_a": "G", "person_b": "C", "type": "parent_child", "source": "gedcom"},
            # Parent (B) is parent of Child (D)
            {"person_a": "B", "person_b": "D", "type": "parent_child", "source": "gedcom"},
            # Spouse: A married G
            {"person_a": "A", "person_b": "G", "type": "spouse", "source": "gedcom"},
            # Spouse: B married E
            {"person_a": "B", "person_b": "E", "type": "spouse", "source": "gedcom"},
        ],
        "gedcom_imports": [],
    }


def _make_co_occurrence_graph():
    """Photo co-occurrence edges — some overlap with family, some not."""
    return {
        "schema_version": 1,
        "edges": [
            # B and D appear in 3 photos together (family + photo)
            {"person_a": "B", "person_b": "D", "shared_photos": ["p1", "p2", "p3"], "count": 3},
            # D and F appear in 1 photo (photo only — F has no family edges)
            {"person_a": "D", "person_b": "F", "shared_photos": ["p4"], "count": 1},
            # A and C appear in 6 photos (family + strong photo)
            {"person_a": "A", "person_b": "C", "shared_photos": ["p5", "p6", "p7", "p8", "p9", "p10"], "count": 6},
        ],
    }


@pytest.fixture
def rel_graph():
    return _make_relationship_graph()


@pytest.fixture
def cooc_graph():
    return _make_co_occurrence_graph()


@pytest.fixture
def social_graph(rel_graph, cooc_graph):
    return build_social_graph(rel_graph, cooc_graph)


# ─── Build Social Graph ────────────────────────────────────────


class TestBuildSocialGraph:

    def test_nodes_include_all_people(self, social_graph):
        """All people from both graphs appear as nodes."""
        assert set(social_graph["nodes"]) == {"A", "B", "C", "D", "E", "F", "G"}

    def test_family_edges_created(self, social_graph):
        """Parent-child, child-of, spouse-of, sibling-of edges all present."""
        edge_types = {e["type"] for e in social_graph["edges"]}
        assert "parent_child" in edge_types
        assert "child_of" in edge_types
        assert "spouse_of" in edge_types
        assert "sibling_of" in edge_types

    def test_photo_edges_created(self, social_graph):
        """Photographed_with edges present from co-occurrence data."""
        photo_edges = [e for e in social_graph["edges"] if e["type"] == "photographed_with"]
        assert len(photo_edges) > 0

    def test_sibling_edges_derived(self, social_graph):
        """B and C are siblings (shared parents A and G)."""
        sibling_edges = [
            e for e in social_graph["edges"]
            if e["type"] == "sibling_of" and {e["source"], e["target"]} == {"B", "C"}
        ]
        assert len(sibling_edges) == 2  # Bidirectional

    def test_edges_are_bidirectional(self, social_graph):
        """Each relationship has both forward and reverse edges."""
        for edge in social_graph["edges"]:
            if edge["type"] == "parent_child":
                # Should have a corresponding child_of
                reverse = [e for e in social_graph["edges"]
                           if e["source"] == edge["target"] and e["target"] == edge["source"]
                           and e["type"] == "child_of"]
                assert len(reverse) == 1

    def test_photo_weight_by_count(self, social_graph):
        """Photo edges weighted by co-occurrence count."""
        # 6 photos → weight 0.8
        six_photo = [e for e in social_graph["edges"]
                     if e["type"] == "photographed_with" and e.get("photo_count") == 6]
        assert len(six_photo) > 0
        assert six_photo[0]["weight"] == 0.8

        # 1 photo → weight 0.3
        one_photo = [e for e in social_graph["edges"]
                     if e["type"] == "photographed_with" and e.get("photo_count") == 1]
        assert len(one_photo) > 0
        assert one_photo[0]["weight"] == 0.3

    def test_empty_graphs(self):
        """Empty inputs produce empty social graph."""
        graph = build_social_graph(
            {"relationships": []},
            {"edges": []},
        )
        assert graph["nodes"] == []
        assert graph["edges"] == []


# ─── BFS Pathfinding ───────────────────────────────────────────


class TestFindShortestPath:

    def test_direct_connection(self, social_graph):
        """A→B is direct (parent_child)."""
        path = find_shortest_path(social_graph, "A", "B")
        assert path is not None
        assert len(path) == 1
        assert path[0]["edge"]["type"] == "parent_child"

    def test_two_hop_connection(self, social_graph):
        """A→D is 2 hops (A→B→D via parent_child)."""
        path = find_shortest_path(social_graph, "A", "D")
        assert path is not None
        assert len(path) == 2

    def test_spouse_connection(self, social_graph):
        """B→E is direct (spouse)."""
        path = find_shortest_path(social_graph, "B", "E")
        assert path is not None
        assert len(path) == 1
        assert path[0]["edge"]["type"] == "spouse_of"

    def test_photo_only_connection(self, social_graph):
        """D→F is only connected through photos."""
        path = find_shortest_path(social_graph, "D", "F")
        assert path is not None
        assert len(path) == 1
        assert path[0]["edge"]["type"] == "photographed_with"

    def test_mixed_path(self, social_graph):
        """A→F requires family + photo edges."""
        path = find_shortest_path(social_graph, "A", "F")
        assert path is not None
        categories = {step["edge"]["category"] for step in path}
        assert "family" in categories
        assert "photo" in categories

    def test_no_connection(self, social_graph):
        """Unconnected node returns None."""
        # Add an isolated node
        social_graph["nodes"].append("Z")
        path = find_shortest_path(social_graph, "A", "Z")
        assert path is None

    def test_same_person(self, social_graph):
        """Same person returns empty path."""
        path = find_shortest_path(social_graph, "A", "A")
        assert path == []

    def test_nonexistent_person(self, social_graph):
        """Non-existent person returns None."""
        path = find_shortest_path(social_graph, "A", "NOBODY")
        assert path is None

    def test_family_only_filter(self, social_graph):
        """Family-only path excludes photo edges."""
        path = find_shortest_path(social_graph, "D", "F", category_filter="family")
        assert path is None  # No family path to F

    def test_photo_only_filter(self, social_graph):
        """Photo-only path uses only photo edges."""
        path = find_shortest_path(social_graph, "D", "F", category_filter="photo")
        assert path is not None
        assert all(step["edge"]["category"] == "photo" for step in path)

    def test_sibling_path(self, social_graph):
        """B→C through sibling edge (1 hop)."""
        path = find_shortest_path(social_graph, "B", "C")
        assert path is not None
        assert len(path) == 1
        assert path[0]["edge"]["type"] == "sibling_of"


# ─── Find All Paths ────────────────────────────────────────────


class TestFindAllPaths:

    def test_returns_all_three_types(self, social_graph):
        """Returns any, family, and photo path types."""
        result = find_all_paths(social_graph, "A", "D")
        assert "any" in result
        assert "family" in result
        assert "photo" in result

    def test_mixed_connection_has_all(self, social_graph):
        """A→F has any path but no family-only path."""
        result = find_all_paths(social_graph, "A", "F")
        assert result["any"] is not None
        assert result["family"] is None  # F only connected via photos


# ─── Proximity Scoring ─────────────────────────────────────────


class TestComputeProximity:

    def test_direct_family_connection(self, social_graph):
        """Direct family = highest proximity (1.0)."""
        prox = compute_proximity(social_graph, "A", "B")
        assert prox == 1.0

    def test_two_hop_lower_than_one_hop(self, social_graph):
        """2-hop connection has lower proximity than 1-hop."""
        prox_1 = compute_proximity(social_graph, "A", "B")
        prox_2 = compute_proximity(social_graph, "A", "D")
        assert prox_1 > prox_2

    def test_no_connection_zero(self, social_graph):
        """No connection = 0 proximity."""
        social_graph["nodes"].append("Z")
        prox = compute_proximity(social_graph, "A", "Z")
        assert prox == 0.0

    def test_photo_weight_affects_proximity(self, social_graph):
        """Photo-only connection has lower weight."""
        prox = compute_proximity(social_graph, "D", "F")
        assert 0 < prox < 1.0  # Photo weight = 0.3


# ─── Closest Connections ───────────────────────────────────────


class TestGetClosestConnections:

    def test_returns_sorted_by_proximity(self, social_graph):
        """Results sorted descending by proximity."""
        connections = get_closest_connections(social_graph, "A", n=10)
        assert len(connections) > 0
        proximities = [c["proximity"] for c in connections]
        assert proximities == sorted(proximities, reverse=True)

    def test_n_limit(self, social_graph):
        """Respects the n limit."""
        connections = get_closest_connections(social_graph, "A", n=2)
        assert len(connections) == 2

    def test_includes_path_length(self, social_graph):
        """Each result has path_length."""
        connections = get_closest_connections(social_graph, "A", n=3)
        for c in connections:
            assert "path_length" in c
            assert c["path_length"] >= 1

    def test_nonexistent_person(self, social_graph):
        """Non-existent person returns empty list."""
        connections = get_closest_connections(social_graph, "NOBODY")
        assert connections == []


# ─── D3 Export ─────────────────────────────────────────────────


class TestExportForD3:

    def test_d3_nodes_have_names(self, social_graph):
        """Exported nodes include names from identities."""
        identities = {
            "A": {"name": "Grandpa"},
            "B": {"name": "Parent"},
            "C": {"name": "Uncle"},
        }
        result = export_for_d3(social_graph, identities)
        a_node = next(n for n in result["nodes"] if n["id"] == "A")
        assert a_node["name"] == "Grandpa"

    def test_d3_links_deduplicated(self, social_graph):
        """Bidirectional edges collapsed into single links."""
        identities = {nid: {"name": nid} for nid in social_graph["nodes"]}
        result = export_for_d3(social_graph, identities)
        # Edges are bidirectional in social_graph but should be deduplicated in D3
        assert len(result["links"]) < len(social_graph["edges"])

    def test_d3_links_have_category(self, social_graph):
        """Each link has a category (family or photo)."""
        identities = {nid: {"name": nid} for nid in social_graph["nodes"]}
        result = export_for_d3(social_graph, identities)
        for link in result["links"]:
            assert link["category"] in ("family", "photo", "unknown")

    def test_d3_photo_counts(self, social_graph):
        """Photo count passed through for node sizing."""
        identities = {"A": {"name": "Grandpa"}}
        photo_counts = {"A": 15, "B": 8}
        result = export_for_d3(social_graph, identities, photo_counts)
        a_node = next(n for n in result["nodes"] if n["id"] == "A")
        assert a_node["photo_count"] == 15


# ─── All Proximities ──────────────────────────────────────────


class TestComputeAllProximities:

    def test_returns_dict_of_pairs(self, social_graph):
        """Returns dict with tuple keys and float values."""
        prox = compute_all_proximities(social_graph)
        assert isinstance(prox, dict)
        for key, val in prox.items():
            assert len(key) == 2
            assert isinstance(val, float)

    def test_only_connected_pairs(self, social_graph):
        """Only includes pairs with non-zero proximity."""
        social_graph["nodes"].append("Z")
        prox = compute_all_proximities(social_graph)
        for key, val in prox.items():
            assert val > 0
            assert "Z" not in key
