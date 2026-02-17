"""Tests for family tree data structure builder."""

import pytest

from rhodesli_ml.graph.relationship_graph import (
    build_family_tree,
    find_root_couples,
)


# --- Test data fixtures ---

_EMPTY_GRAPH = {"schema_version": 1, "relationships": [], "gedcom_imports": []}

_SINGLE_COUPLE_GRAPH = {
    "schema_version": 1,
    "relationships": [
        {"person_a": "father", "person_b": "child1", "type": "parent_child", "source": "gedcom"},
        {"person_a": "father", "person_b": "child2", "type": "parent_child", "source": "gedcom"},
        {"person_a": "mother", "person_b": "child1", "type": "parent_child", "source": "gedcom"},
        {"person_a": "mother", "person_b": "child2", "type": "parent_child", "source": "gedcom"},
        {"person_a": "father", "person_b": "mother", "type": "spouse", "source": "gedcom"},
    ],
    "gedcom_imports": [],
}

_MULTI_GEN_GRAPH = {
    "schema_version": 1,
    "relationships": [
        # Grandparents -> Parents
        {"person_a": "grandpa", "person_b": "father", "type": "parent_child", "source": "gedcom"},
        {"person_a": "grandma", "person_b": "father", "type": "parent_child", "source": "gedcom"},
        {"person_a": "grandpa", "person_b": "grandma", "type": "spouse", "source": "gedcom"},
        # Parents -> Children
        {"person_a": "father", "person_b": "child1", "type": "parent_child", "source": "gedcom"},
        {"person_a": "mother", "person_b": "child1", "type": "parent_child", "source": "gedcom"},
        {"person_a": "father", "person_b": "mother", "type": "spouse", "source": "gedcom"},
    ],
    "gedcom_imports": [],
}

_DISCONNECTED_GRAPH = {
    "schema_version": 1,
    "relationships": [
        # Family A
        {"person_a": "dad-a", "person_b": "kid-a", "type": "parent_child", "source": "gedcom"},
        {"person_a": "mom-a", "person_b": "kid-a", "type": "parent_child", "source": "gedcom"},
        {"person_a": "dad-a", "person_b": "mom-a", "type": "spouse", "source": "gedcom"},
        # Family B (disconnected)
        {"person_a": "dad-b", "person_b": "kid-b", "type": "parent_child", "source": "gedcom"},
        {"person_a": "mom-b", "person_b": "kid-b", "type": "parent_child", "source": "gedcom"},
        {"person_a": "dad-b", "person_b": "mom-b", "type": "spouse", "source": "gedcom"},
    ],
    "gedcom_imports": [],
}

_IDENTITIES = {
    "grandpa": {"identity_id": "grandpa", "name": "Rahamin Capeluto", "state": "CONFIRMED"},
    "grandma": {"identity_id": "grandma", "name": "Hanula Capeluto", "state": "CONFIRMED"},
    "father": {"identity_id": "father", "name": "Leon Capeluto", "state": "CONFIRMED"},
    "mother": {"identity_id": "mother", "name": "Vida Capeluto", "state": "CONFIRMED"},
    "child1": {"identity_id": "child1", "name": "Moise Capeluto", "state": "CONFIRMED"},
    "child2": {"identity_id": "child2", "name": "Selma Capeluto", "state": "CONFIRMED"},
    "dad-a": {"identity_id": "dad-a", "name": "Dad A", "state": "CONFIRMED"},
    "mom-a": {"identity_id": "mom-a", "name": "Mom A", "state": "CONFIRMED"},
    "kid-a": {"identity_id": "kid-a", "name": "Kid A", "state": "CONFIRMED"},
    "dad-b": {"identity_id": "dad-b", "name": "Dad B", "state": "CONFIRMED"},
    "mom-b": {"identity_id": "mom-b", "name": "Mom B", "state": "CONFIRMED"},
    "kid-b": {"identity_id": "kid-b", "name": "Kid B", "state": "CONFIRMED"},
}


class TestFindRootCouples:

    def test_empty_graph(self):
        """Empty graph has no root couples."""
        roots = find_root_couples(_EMPTY_GRAPH)
        assert roots == []

    def test_single_couple_is_root(self):
        """A couple with no parents is a root couple."""
        roots = find_root_couples(_SINGLE_COUPLE_GRAPH)
        assert len(roots) == 1
        couple = roots[0]
        assert set(couple) == {"father", "mother"}

    def test_multi_gen_grandparents_are_root(self):
        """Grandparents (no parents in graph) are a root couple.
        Mother also has no parents in graph, so she's a root too.
        Tree builder handles this via visited tracking."""
        roots = find_root_couples(_MULTI_GEN_GRAPH)
        # grandpa+grandma are root couple, mother is root single (no parents in graph)
        root_ids = set()
        for couple in roots:
            root_ids.update(c for c in couple if c is not None)
        assert "grandpa" in root_ids
        assert "grandma" in root_ids

    def test_disconnected_families_have_two_roots(self):
        """Two disconnected families produce two root couples."""
        roots = find_root_couples(_DISCONNECTED_GRAPH)
        assert len(roots) == 2
        root_sets = [set(r) for r in roots]
        assert {"dad-a", "mom-a"} in root_sets
        assert {"dad-b", "mom-b"} in root_sets


class TestBuildFamilyTree:

    def test_empty_graph_returns_empty(self):
        """Empty graph produces empty tree."""
        tree = build_family_tree(_EMPTY_GRAPH, _IDENTITIES)
        assert tree == []

    def test_single_couple_with_children(self):
        """Single couple with 2 children produces correct 2-level hierarchy."""
        tree = build_family_tree(_SINGLE_COUPLE_GRAPH, _IDENTITIES)
        assert len(tree) == 1
        root = tree[0]
        assert root["type"] == "couple"
        member_ids = {m["id"] for m in root["members"]}
        assert member_ids == {"father", "mother"}
        assert len(root["children"]) == 2
        child_ids = set()
        for child_node in root["children"]:
            # Children without spouses are "single" type
            if child_node["type"] == "single":
                child_ids.add(child_node["id"])
            elif child_node["type"] == "couple":
                for m in child_node["members"]:
                    child_ids.add(m["id"])
        assert {"child1", "child2"} == child_ids

    def test_multi_generation_hierarchy(self):
        """3-level tree: grandparents -> parents -> children."""
        tree = build_family_tree(_MULTI_GEN_GRAPH, _IDENTITIES)
        assert len(tree) == 1
        root = tree[0]
        # Root should be grandparents
        root_ids = {m["id"] for m in root["members"]}
        assert root_ids == {"grandpa", "grandma"}
        # Should have at least one child subtree
        assert len(root["children"]) >= 1
        # Find the father's subtree (should be a couple with mother)
        father_subtree = None
        for child in root["children"]:
            if child["type"] == "couple":
                ids = {m["id"] for m in child["members"]}
                if "father" in ids:
                    father_subtree = child
                    break
        assert father_subtree is not None, "Father should be in a couple node"
        assert {m["id"] for m in father_subtree["members"]} == {"father", "mother"}
        # Father+mother should have child1
        assert len(father_subtree["children"]) == 1
        child_node = father_subtree["children"][0]
        if child_node["type"] == "single":
            assert child_node["id"] == "child1"
        else:
            assert "child1" in {m["id"] for m in child_node["members"]}

    def test_root_person_focuses_subtree(self):
        """root_person parameter centers tree on a specific person."""
        tree = build_family_tree(_MULTI_GEN_GRAPH, _IDENTITIES, root_person="father")
        assert len(tree) == 1
        root = tree[0]
        # Root should contain father
        all_ids = set()
        if root["type"] == "couple":
            all_ids = {m["id"] for m in root["members"]}
        else:
            all_ids = {root["id"]}
        assert "father" in all_ids

    def test_disconnected_families_separate_trees(self):
        """Two disconnected families produce two separate sub-trees."""
        tree = build_family_tree(_DISCONNECTED_GRAPH, _IDENTITIES)
        assert len(tree) == 2

    def test_cycle_prevention(self):
        """Graph with a cycle doesn't recurse infinitely."""
        cycle_graph = {
            "schema_version": 1,
            "relationships": [
                {"person_a": "a", "person_b": "b", "type": "parent_child", "source": "gedcom"},
                {"person_a": "b", "person_b": "a", "type": "parent_child", "source": "gedcom"},
                {"person_a": "a", "person_b": "spouse-a", "type": "spouse", "source": "gedcom"},
            ],
            "gedcom_imports": [],
        }
        ids = {
            "a": {"identity_id": "a", "name": "Person A", "state": "CONFIRMED"},
            "b": {"identity_id": "b", "name": "Person B", "state": "CONFIRMED"},
            "spouse-a": {"identity_id": "spouse-a", "name": "Spouse A", "state": "CONFIRMED"},
        }
        # Should not hang or raise
        tree = build_family_tree(cycle_graph, ids)
        assert isinstance(tree, list)
