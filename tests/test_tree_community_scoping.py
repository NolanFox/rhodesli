"""Regression tests for community scoping of the family-tree API."""

from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

from app.main import app
import app.page_routes as page_routes


RHODES_ID = "rhodes-identity"
FOX_ONLY_ID = "fox-only-identity"
FOX_XREF = "@I132506612777@"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mocked_tree(monkeypatch):
    """Provide a small deterministic tree without loading registry or GEDCOM data."""
    ptc = {FOX_ONLY_ID: {RHODES_ID, FOX_XREF}}
    ctp = {RHODES_ID: {FOX_ONLY_ID}, FOX_XREF: {FOX_ONLY_ID}}

    monkeypatch.setattr(page_routes._main_mod, "load_registry", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr(page_routes._main_mod, "get_crop_files", MagicMock(return_value={}))
    monkeypatch.setattr(page_routes._main_mod, "_compute_shared_photos", MagicMock(return_value={}))
    monkeypatch.setattr(page_routes, "_build_tree_link_maps", MagicMock(return_value=({}, {})))
    monkeypatch.setattr(page_routes, "_build_tree_adjacency", MagicMock(return_value=(ptc, ctp, {})))
    monkeypatch.setattr(page_routes, "_build_tree_person_lookup", MagicMock(return_value={}))
    monkeypatch.setattr(
        page_routes,
        "_make_tree_node",
        MagicMock(side_effect=lambda pid, *args, **kwargs: {"id": pid, "data": {}, "rels": {}}),
    )


def test_rhodes_tree_does_not_leak_fox_gedcom_nodes(client, mocked_tree, monkeypatch):
    monkeypatch.setattr("app.supabase_data.get_community_by_slug", lambda slug: {"slug": slug})
    monkeypatch.setattr(page_routes._main_mod, "_get_community_identity_ids", lambda community: {RHODES_ID})

    response = client.get(f"/api/tree/data?person_id={FOX_ONLY_ID}")

    assert response.status_code == 200
    payload = response.json()
    node_ids = {node["id"] for node in payload["nodes"]}
    assert node_ids == {RHODES_ID}
    assert not any(node_id.startswith("@") for node_id in node_ids)
    assert FOX_ONLY_ID not in node_ids
    assert payload["focal_person"] == RHODES_ID


def test_rhodes_tree_scrubs_cross_community_node_references(client, mocked_tree, monkeypatch):
    monkeypatch.setattr("app.supabase_data.get_community_by_slug", lambda slug: {"slug": slug})
    monkeypatch.setattr(page_routes._main_mod, "_get_community_identity_ids", lambda community: {RHODES_ID})
    monkeypatch.setattr(
        page_routes,
        "_make_tree_node",
        MagicMock(
            side_effect=lambda pid, *args, **kwargs: {
                "id": pid,
                "data": {"shared_photos": {FOX_ONLY_ID: 3, RHODES_ID: 1}},
                "rels": {
                    "father": "@FOXPRIVATE@",
                    "mother": FOX_ONLY_ID,
                    "children": [RHODES_ID, FOX_ONLY_ID],
                },
            }
        ),
    )

    response = client.get(f"/api/tree/data?person_id={FOX_ONLY_ID}")

    assert response.status_code == 200
    node = response.json()["nodes"][0]
    assert "@FOXPRIVATE@" not in node["rels"].values()
    assert FOX_ONLY_ID not in node["rels"].values()
    assert "father" not in node["rels"]
    assert "mother" not in node["rels"]
    assert node["rels"]["children"] == [RHODES_ID]
    assert FOX_ONLY_ID not in node["data"]["shared_photos"]


def test_fox_family_owner_tree_is_not_filtered(client, mocked_tree, monkeypatch):
    monkeypatch.setattr("app.supabase_data.get_community_by_slug", lambda slug: {"slug": slug})
    identity_scope = MagicMock(side_effect=AssertionError("owner tree must not be scoped"))
    monkeypatch.setattr(page_routes._main_mod, "_get_community_identity_ids", identity_scope)

    response = client.get(f"/c/fox-family/api/tree/data?person_id={FOX_ONLY_ID}")

    assert response.status_code == 200
    payload = response.json()
    assert {node["id"] for node in payload["nodes"]} == {RHODES_ID, FOX_ONLY_ID, FOX_XREF}
    assert payload["focal_person"] == FOX_ONLY_ID
    identity_scope.assert_not_called()


def test_non_owner_tree_fails_closed_when_identity_scope_is_unknown(client, mocked_tree, monkeypatch):
    monkeypatch.setattr("app.supabase_data.get_community_by_slug", lambda slug: {"slug": slug})
    monkeypatch.setattr(page_routes._main_mod, "_get_community_identity_ids", lambda community: None)

    response = client.get(f"/api/tree/data?person_id={FOX_ONLY_ID}")

    assert response.status_code == 200
    assert response.json()["nodes"] == []
    assert response.json()["focal_person"] == ""


def test_non_owner_tree_expand_filters_returned_nodes(client, mocked_tree, monkeypatch):
    monkeypatch.setattr("app.supabase_data.get_community_by_slug", lambda slug: {"slug": slug})
    monkeypatch.setattr(page_routes._main_mod, "_get_community_identity_ids", lambda community: {RHODES_ID})

    response = client.get(f"/api/tree/expand?person_id={FOX_ONLY_ID}&direction=children")

    assert response.status_code == 200
    assert {node["id"] for node in response.json()["nodes"]} == {RHODES_ID}
