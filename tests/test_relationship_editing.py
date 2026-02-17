"""Tests for relationship schema extension + editing API."""

import json
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app
from rhodesli_ml.graph.relationship_graph import (
    add_relationship,
    get_relationships_for_person,
    remove_relationship,
    update_relationship_confidence,
)


@pytest.fixture
def client():
    return TestClient(app)


# --- Schema extension tests ---

_BASE_GRAPH = {
    "schema_version": 1,
    "relationships": [
        {"person_a": "id-a", "person_b": "id-b", "type": "parent_child", "source": "gedcom"},
        {"person_a": "id-a", "person_b": "id-c", "type": "spouse", "source": "gedcom"},
    ],
    "gedcom_imports": [],
}


class TestAddRelationship:

    def test_adds_new_relationship(self):
        """add_relationship creates new entry."""
        graph = {"schema_version": 1, "relationships": [], "gedcom_imports": []}
        result = add_relationship(graph, "id-x", "id-y", "parent_child", "manual", "confirmed")
        assert len(result["relationships"]) == 1
        rel = result["relationships"][0]
        assert rel["person_a"] == "id-x"
        assert rel["person_b"] == "id-y"
        assert rel["type"] == "parent_child"
        assert rel["confidence"] == "confirmed"
        assert rel["source"] == "manual"

    def test_deduplicates(self):
        """add_relationship does not create duplicate."""
        graph = {"schema_version": 1, "relationships": [
            {"person_a": "id-x", "person_b": "id-y", "type": "parent_child", "source": "gedcom"},
        ], "gedcom_imports": []}
        result = add_relationship(graph, "id-x", "id-y", "parent_child", "manual", "confirmed")
        assert len(result["relationships"]) == 1  # Not duplicated

    def test_fan_types_accepted(self):
        """FAN relationship types are valid."""
        graph = {"schema_version": 1, "relationships": [], "gedcom_imports": []}
        for fan_type in ["fan_friend", "fan_associate", "fan_neighbor"]:
            result = add_relationship(graph, "id-a", "id-b", fan_type, "manual", "theory")
        assert len(result["relationships"]) == 3

    def test_add_with_label(self):
        """Relationships can have an optional label."""
        graph = {"schema_version": 1, "relationships": [], "gedcom_imports": []}
        result = add_relationship(graph, "id-a", "id-b", "fan_friend", "manual", "theory", label="Childhood friends")
        assert result["relationships"][0]["label"] == "Childhood friends"


class TestUpdateRelationshipConfidence:

    def test_updates_confidence(self):
        """update_relationship_confidence changes the confidence field."""
        graph = {"schema_version": 1, "relationships": [
            {"person_a": "id-a", "person_b": "id-b", "type": "parent_child", "source": "gedcom"},
        ], "gedcom_imports": []}
        result = update_relationship_confidence(graph, "id-a", "id-b", "parent_child", "theory")
        assert result["relationships"][0]["confidence"] == "theory"

    def test_no_match_returns_unchanged(self):
        """update_relationship_confidence with no match returns graph unchanged."""
        graph = {"schema_version": 1, "relationships": [
            {"person_a": "id-a", "person_b": "id-b", "type": "parent_child", "source": "gedcom"},
        ], "gedcom_imports": []}
        result = update_relationship_confidence(graph, "id-x", "id-y", "parent_child", "theory")
        assert "confidence" not in result["relationships"][0]


class TestRemoveRelationship:

    def test_marks_as_removed(self):
        """remove_relationship marks relationship as removed (non-destructive)."""
        graph = {"schema_version": 1, "relationships": [
            {"person_a": "id-a", "person_b": "id-b", "type": "parent_child", "source": "gedcom"},
        ], "gedcom_imports": []}
        result = remove_relationship(graph, "id-a", "id-b", "parent_child")
        assert result["relationships"][0].get("removed") is True

    def test_removed_filtered_from_get(self):
        """get_relationships_for_person excludes removed relationships."""
        graph = {"schema_version": 1, "relationships": [
            {"person_a": "id-a", "person_b": "id-b", "type": "parent_child", "source": "gedcom", "removed": True},
            {"person_a": "id-a", "person_b": "id-c", "type": "spouse", "source": "gedcom"},
        ], "gedcom_imports": []}
        rels = get_relationships_for_person(graph, "id-a")
        assert len(rels["children"]) == 0  # id-b removed
        assert len(rels["spouses"]) == 1   # id-c still there


class TestGetRelationshipsTheoryFilter:

    def test_include_theory_true_returns_all(self):
        """include_theory=True returns both confirmed and theory."""
        graph = {"schema_version": 1, "relationships": [
            {"person_a": "id-a", "person_b": "id-b", "type": "parent_child", "source": "gedcom", "confidence": "confirmed"},
            {"person_a": "id-a", "person_b": "id-c", "type": "parent_child", "source": "manual", "confidence": "theory"},
        ], "gedcom_imports": []}
        rels = get_relationships_for_person(graph, "id-a", include_theory=True)
        assert len(rels["children"]) == 2

    def test_include_theory_false_excludes_theory(self):
        """include_theory=False excludes theory relationships."""
        graph = {"schema_version": 1, "relationships": [
            {"person_a": "id-a", "person_b": "id-b", "type": "parent_child", "source": "gedcom", "confidence": "confirmed"},
            {"person_a": "id-a", "person_b": "id-c", "type": "parent_child", "source": "manual", "confidence": "theory"},
        ], "gedcom_imports": []}
        rels = get_relationships_for_person(graph, "id-a", include_theory=False)
        assert len(rels["children"]) == 1
        assert rels["children"][0] == "id-b"

    def test_fan_types_returned(self):
        """FAN relationships returned in fan key."""
        graph = {"schema_version": 1, "relationships": [
            {"person_a": "id-a", "person_b": "id-b", "type": "fan_friend", "source": "manual", "confidence": "theory"},
            {"person_a": "id-a", "person_b": "id-c", "type": "fan_associate", "source": "manual"},
        ], "gedcom_imports": []}
        rels = get_relationships_for_person(graph, "id-a")
        assert len(rels["fan"]) == 2


# --- API endpoint tests ---

_MOCK_IDENTITIES = {
    "identities": {
        "id-a": {
            "identity_id": "id-a",
            "name": "Person A",
            "state": "CONFIRMED",
            "anchor_ids": [],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        },
        "id-b": {
            "identity_id": "id-b",
            "name": "Person B",
            "state": "CONFIRMED",
            "anchor_ids": [],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        },
    },
    "history": [],
}


def _patch_for_api():
    """Patches for relationship API tests."""
    from core.registry import IdentityRegistry

    mock_registry = IdentityRegistry.__new__(IdentityRegistry)
    mock_registry._identities = _MOCK_IDENTITIES["identities"]
    mock_registry._history = []
    mock_registry._path = None

    graph = {"schema_version": 1, "relationships": [
        {"person_a": "id-a", "person_b": "id-b", "type": "parent_child", "source": "gedcom"},
    ], "gedcom_imports": []}

    patches = [
        patch("app.main.is_auth_enabled", return_value=False),
        patch("app.main.load_registry", return_value=mock_registry),
        patch("app.main._load_relationship_graph", return_value=graph),
        patch("app.main._save_relationship_graph"),
    ]
    return patches


class TestRelationshipAPI:

    def test_add_relationship_admin(self, client):
        """POST /api/relationship/add returns 200 for admin."""
        patches = _patch_for_api()
        for p in patches:
            p.start()
        resp = client.post("/api/relationship/add", data={
            "person_a": "id-a",
            "person_b": "id-b",
            "type": "fan_friend",
            "confidence": "theory",
        })
        for p in patches:
            p.stop()
        assert resp.status_code == 200

    def test_add_relationship_requires_auth(self, client):
        """POST /api/relationship/add returns 401 for unauthenticated."""
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            resp = client.post("/api/relationship/add", data={
                "person_a": "id-a",
                "person_b": "id-b",
                "type": "parent_child",
                "confidence": "confirmed",
            })
        assert resp.status_code == 401

    def test_update_confidence(self, client):
        """POST /api/relationship/update changes confidence."""
        patches = _patch_for_api()
        for p in patches:
            p.start()
        resp = client.post("/api/relationship/update", data={
            "person_a": "id-a",
            "person_b": "id-b",
            "type": "parent_child",
            "confidence": "theory",
        })
        for p in patches:
            p.stop()
        assert resp.status_code == 200

    def test_remove_relationship(self, client):
        """POST /api/relationship/remove marks as removed."""
        patches = _patch_for_api()
        for p in patches:
            p.start()
        resp = client.post("/api/relationship/remove", data={
            "person_a": "id-a",
            "person_b": "id-b",
            "type": "parent_child",
        })
        for p in patches:
            p.stop()
        assert resp.status_code == 200
