"""Tests for family tree data building.

Loads real data from data/ files and validates the output of
build_family_tree() matches the family-chart library contract.
"""
import json
from pathlib import Path

import pytest

from rhodesli_ml.graph.relationship_graph import (
    build_family_tree,
    load_relationship_graph,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(scope="module")
def tree_data():
    """Build tree from real data files."""
    identities_path = DATA_DIR / "identities.json"
    if not identities_path.exists():
        pytest.skip("data/identities.json not found")

    with open(identities_path) as f:
        identities = json.load(f).get("identities", {})

    rel_graph = load_relationship_graph()
    return build_family_tree(rel_graph, identities)


class TestTreeDataStructure:
    """Validate tree output matches family-chart library contract."""

    def test_returns_list(self, tree_data):
        assert isinstance(tree_data, list)
        assert len(tree_data) > 0

    def test_person_has_required_fields(self, tree_data):
        for person in tree_data[:10]:
            assert "id" in person
            assert "data" in person
            assert "rels" in person
            assert "first name" in person["data"]
            assert "last name" in person["data"]
            assert "gender" in person["data"]

    def test_rels_has_valid_structure(self, tree_data):
        for person in tree_data[:20]:
            rels = person["rels"]
            if "spouses" in rels:
                assert isinstance(rels["spouses"], list)
            if "children" in rels:
                assert isinstance(rels["children"], list)
            if "father" in rels:
                assert isinstance(rels["father"], str)
            if "mother" in rels:
                assert isinstance(rels["mother"], str)

    def test_siblings_exist(self, tree_data):
        """At least one parent should have 2+ children (sibling rendering)."""
        parents_with_multiple = [
            p for p in tree_data
            if len(p["rels"].get("children", [])) >= 2
        ]
        assert len(parents_with_multiple) > 0, "No parents with multiple children found"

    def test_no_broken_dates(self, tree_data):
        """No "21 S", "ABT ", "AFT ", "BEF " in any date field."""
        for person in tree_data:
            birthday = person["data"].get("birthday", "")
            lifespan = person["data"].get("lifespan", "")
            for field_val in (birthday, lifespan):
                assert "21 S" not in field_val, f"Broken date '21 S' found for {person['id']}"
                assert "ABT " not in field_val, f"Broken date 'ABT ' found for {person['id']}"
                assert "AFT " not in field_val, f"Broken date 'AFT ' found for {person['id']}"
                assert "BEF " not in field_val, f"Broken date 'BEF ' found for {person['id']}"

    def test_ids_are_unique(self, tree_data):
        ids = [p["id"] for p in tree_data]
        assert len(ids) == len(set(ids)), "Duplicate IDs found"

    def test_relationship_ids_reference_existing_people(self, tree_data):
        """All relationship references must point to real IDs in the tree."""
        all_ids = {p["id"] for p in tree_data}
        for person in tree_data:
            rels = person["rels"]
            if "father" in rels:
                assert rels["father"] in all_ids, f"Father {rels['father']} not in tree for {person['id']}"
            if "mother" in rels:
                assert rels["mother"] in all_ids, f"Mother {rels['mother']} not in tree for {person['id']}"
            for spouse_id in rels.get("spouses", []):
                assert spouse_id in all_ids, f"Spouse {spouse_id} not in tree for {person['id']}"
            for child_id in rels.get("children", []):
                assert child_id in all_ids, f"Child {child_id} not in tree for {person['id']}"

    def test_data_has_lifespan_field(self, tree_data):
        """Every person should have a lifespan field (may be empty)."""
        for person in tree_data[:20]:
            assert "lifespan" in person["data"]

    def test_confirmed_identities_have_names(self, tree_data):
        """UUID-based identities should have non-Unknown names."""
        uuid_nodes = [p for p in tree_data if not p["id"].startswith("@")]
        named = [p for p in uuid_nodes if p["data"]["first name"] != "Unknown"]
        assert len(named) > 0, "No confirmed identities with real names found"
