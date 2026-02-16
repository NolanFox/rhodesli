"""Tests for relationship graph and co-occurrence graph."""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from rhodesli_ml.importers.gedcom_parser import parse_gedcom
from rhodesli_ml.importers.identity_matcher import MatchProposal, match_gedcom_to_identities
from rhodesli_ml.graph.relationship_graph import (
    build_relationship_graph,
    get_relationships_for_person,
    load_relationship_graph,
    save_relationship_graph,
)
from rhodesli_ml.graph.co_occurrence_graph import (
    build_co_occurrence_graph,
    get_co_occurrences_for_person,
    load_co_occurrence_graph,
    save_co_occurrence_graph,
)

FIXTURE_PATH = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "test_capeluto.ged"


class TestRelationshipGraph:
    """TEST 7: Relationship graph created from GEDCOM + confirmed matches."""

    @pytest.fixture
    def parsed(self):
        return parse_gedcom(str(FIXTURE_PATH))

    @pytest.fixture
    def confirmed_matches(self, parsed):
        """Simulated confirmed matches."""
        identities = {
            "id-rahamin": {"name": "Rahamin Capeluto", "state": "CONFIRMED", "identity_id": "id-rahamin"},
            "id-hanula": {"name": "Hanula Mosafir Capuano", "state": "CONFIRMED", "identity_id": "id-hanula"},
            "id-leon": {"name": "Big Leon Capeluto", "state": "CONFIRMED", "identity_id": "id-leon"},
            "id-moise": {"name": "Moise Capeluto", "state": "CONFIRMED", "identity_id": "id-moise"},
            "id-nace": {"name": "Nace Capeluto", "state": "CONFIRMED", "identity_id": "id-nace"},
        }
        result = match_gedcom_to_identities(parsed, identities)
        # Mark all as confirmed
        for p in result.proposals:
            p.status = "confirmed"
        return result.proposals

    def test_builds_graph(self, parsed, confirmed_matches):
        graph = build_relationship_graph(parsed, confirmed_matches)
        assert "relationships" in graph
        assert "gedcom_imports" in graph

    def test_parent_child_relationships(self, parsed, confirmed_matches):
        graph = build_relationship_graph(parsed, confirmed_matches)
        parent_child = [r for r in graph["relationships"] if r["type"] == "parent_child"]
        assert len(parent_child) > 0

        # Rahamin is parent of Leon, Moise, Nace
        rahamin_children = [
            r["person_b"] for r in parent_child if r["person_a"] == "id-rahamin"
        ]
        assert "id-leon" in rahamin_children
        assert "id-moise" in rahamin_children
        assert "id-nace" in rahamin_children

    def test_spouse_relationships(self, parsed, confirmed_matches):
        graph = build_relationship_graph(parsed, confirmed_matches)
        spouses = [r for r in graph["relationships"] if r["type"] == "spouse"]
        assert len(spouses) > 0

        # Rahamin and Hanula are spouses
        spouse_pairs = [(r["person_a"], r["person_b"]) for r in spouses]
        assert ("id-rahamin", "id-hanula") in spouse_pairs or ("id-hanula", "id-rahamin") in spouse_pairs

    def test_import_recorded(self, parsed, confirmed_matches):
        graph = build_relationship_graph(parsed, confirmed_matches)
        assert len(graph["gedcom_imports"]) == 1
        assert graph["gedcom_imports"][0]["individuals_count"] == 14
        assert graph["gedcom_imports"][0]["families_count"] == 6

    def test_no_duplicate_relationships(self, parsed, confirmed_matches):
        graph = build_relationship_graph(parsed, confirmed_matches)
        keys = set()
        for r in graph["relationships"]:
            key = (r["type"], r["person_a"], r["person_b"])
            assert key not in keys, f"Duplicate relationship: {key}"
            keys.add(key)

    def test_get_relationships_for_person(self, parsed, confirmed_matches):
        graph = build_relationship_graph(parsed, confirmed_matches)
        rels = get_relationships_for_person(graph, "id-leon")
        assert "id-rahamin" in rels["parents"]
        assert "id-hanula" in rels["parents"]
        # Leon's siblings should include Moise and Nace
        assert "id-moise" in rels["siblings"]
        assert "id-nace" in rels["siblings"]

    def test_merge_with_existing(self, parsed, confirmed_matches):
        """Merging into existing graph doesn't duplicate."""
        graph1 = build_relationship_graph(parsed, confirmed_matches)
        count1 = len(graph1["relationships"])

        graph2 = build_relationship_graph(parsed, confirmed_matches, existing_graph=graph1)
        count2 = len(graph2["relationships"])
        assert count2 == count1  # No duplicates

    def test_only_matched_individuals(self, parsed):
        """Only individuals with confirmed matches create relationships."""
        # Only match Leon
        matches = [MatchProposal(
            gedcom_individual=parsed.individuals["@I3@"],
            identity_id="id-leon",
            identity_name="Leon",
            match_score=0.9,
            match_reason="test",
            match_layer=1,
            status="confirmed",
        )]
        graph = build_relationship_graph(parsed, matches)
        # No relationships because both endpoints must be matched
        assert len(graph["relationships"]) == 0


class TestRelationshipGraphPersistence:
    def test_save_and_load(self, tmp_path):
        graph = {"schema_version": 1, "relationships": [{"type": "test"}], "gedcom_imports": []}
        filepath = str(tmp_path / "relationships.json")
        save_relationship_graph(graph, filepath)
        loaded = load_relationship_graph(filepath)
        assert loaded["relationships"][0]["type"] == "test"

    def test_load_nonexistent(self, tmp_path):
        result = load_relationship_graph(str(tmp_path / "nonexistent.json"))
        assert result["relationships"] == []


class TestCoOccurrenceGraph:
    """TEST 8: Co-occurrence graph created from photo data."""

    @pytest.fixture
    def mock_data(self):
        identities = {
            "id-a": {
                "name": "Person A", "state": "CONFIRMED",
                "anchor_ids": ["face1", "face3"],
            },
            "id-b": {
                "name": "Person B", "state": "CONFIRMED",
                "anchor_ids": ["face2", "face4"],
            },
            "id-c": {
                "name": "Person C", "state": "CONFIRMED",
                "anchor_ids": ["face5"],
            },
        }
        photo_index = {
            "photos": {
                "photo1": {"face_ids": ["face1", "face2"]},  # A and B
                "photo2": {"face_ids": ["face1", "face2", "face5"]},  # A, B, C
                "photo3": {"face_ids": ["face3"]},  # Only A
            },
            "face_to_photo": {
                "face1": "photo1",
                "face2": "photo1",
                "face3": "photo3",
                "face4": "photo2",
                "face5": "photo2",
            },
        }
        return identities, photo_index

    def test_builds_edges(self, mock_data):
        identities, photo_index = mock_data
        graph = build_co_occurrence_graph(identities, photo_index)
        assert len(graph["edges"]) > 0

    def test_edge_counts(self, mock_data):
        identities, photo_index = mock_data
        graph = build_co_occurrence_graph(identities, photo_index)

        # A and B appear together in photo1 (face1+face2) and photo2 (via face4+face1... hmm)
        # Actually face4 maps to photo2, and face1 maps to photo1
        # Let me recalculate: face1->photo1, face2->photo1, face3->photo3, face4->photo2, face5->photo2
        # photo1 has A(face1) and B(face2) → edge A-B
        # photo2 has B(face4) and C(face5) → edge B-C
        # photo3 has A(face3) only → no edge

        ab_edge = [e for e in graph["edges"]
                   if set([e["person_a"], e["person_b"]]) == {"id-a", "id-b"}]
        assert len(ab_edge) == 1
        assert ab_edge[0]["count"] == 1

    def test_stats(self, mock_data):
        identities, photo_index = mock_data
        graph = build_co_occurrence_graph(identities, photo_index)
        assert "stats" in graph
        assert graph["stats"]["total_edges"] > 0

    def test_get_co_occurrences(self, mock_data):
        identities, photo_index = mock_data
        graph = build_co_occurrence_graph(identities, photo_index)
        co = get_co_occurrences_for_person(graph, "id-a")
        assert len(co) > 0
        assert co[0]["person_id"] in ("id-b", "id-c")

    def test_empty_data(self):
        graph = build_co_occurrence_graph({}, {"photos": {}, "face_to_photo": {}})
        assert graph["edges"] == []
        assert graph["stats"]["total_edges"] == 0

    def test_skips_merged(self):
        identities = {
            "id-a": {"name": "A", "state": "CONFIRMED", "anchor_ids": ["f1"], "merged_into": "id-b"},
            "id-b": {"name": "B", "state": "CONFIRMED", "anchor_ids": ["f2"]},
        }
        photo_index = {
            "photos": {"p1": {"face_ids": ["f1", "f2"]}},
            "face_to_photo": {"f1": "p1", "f2": "p1"},
        }
        graph = build_co_occurrence_graph(identities, photo_index)
        # Merged identity should be skipped
        assert graph["edges"] == []


class TestCoOccurrenceGraphPersistence:
    def test_save_and_load(self, tmp_path):
        graph = {"schema_version": 1, "edges": [{"person_a": "a", "person_b": "b", "count": 1}], "generated_at": "now", "stats": {}}
        filepath = str(tmp_path / "co_occurrence_graph.json")
        save_co_occurrence_graph(graph, filepath)
        loaded = load_co_occurrence_graph(filepath)
        assert loaded["edges"][0]["count"] == 1

    def test_load_nonexistent(self, tmp_path):
        result = load_co_occurrence_graph(str(tmp_path / "nonexistent.json"))
        assert result["edges"] == []
