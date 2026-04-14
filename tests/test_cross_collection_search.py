"""Tests for GET /api/admin/search-person-in-collection (TOOLS-007).

Admin-only endpoint that searches for a person across collections by
computing the centroid of their anchor embeddings and ranking faces in
the target community by L2 distance.
"""

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from core.registry import IdentityRegistry, IdentityState

HTMX_HEADERS = {"HX-Request": "true"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_face_embeddings(face_ids: list[str], dim: int = 512) -> dict:
    """Build a fake face_embeddings dict with random unit vectors."""
    rng = np.random.RandomState(42)
    result = {}
    for fid in face_ids:
        vec = rng.randn(dim).astype(np.float32)
        vec /= np.linalg.norm(vec)
        result[fid] = {
            "mu": vec,
            "sigma_sq": np.full(dim, 0.55, dtype=np.float32),
            "bbox": [0, 0, 100, 100],
            "det_score": 0.99,
            "quality": 0.8,
            "filename": f"{fid}.jpg",
        }
    return result


def _url(identity_id: str, community_id: str, limit: int = 20) -> str:
    return f"/api/admin/search-person-in-collection?identity_id={identity_id}&community_id={community_id}&limit={limit}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_search_requires_admin_auth(client, auth_enabled, no_user):
    """Anonymous users get 401."""
    response = client.get(_url("id-1", "comm-1"), headers=HTMX_HEADERS)
    assert response.status_code == 401


def test_search_rejects_non_admin(client, auth_enabled, regular_user):
    """Non-admin users get 403."""
    response = client.get(_url("id-1", "comm-1"), headers=HTMX_HEADERS)
    assert response.status_code == 403


def test_search_returns_ranked_results(client, auth_enabled, admin_user):
    """Returns faces sorted by distance for a known identity."""
    # Set up identity with 1 anchor face
    registry = IdentityRegistry()
    identity_id = registry.create_identity(
        anchor_ids=["anchor_face_1"],
        user_source="test",
        state=IdentityState.CONFIRMED,
        name="Test Person",
    )

    # Create embeddings: 1 anchor + 3 community faces
    all_face_ids = ["anchor_face_1", "comm_face_a", "comm_face_b", "comm_face_c"]
    face_embeddings = _make_face_embeddings(all_face_ids)

    # Make comm_face_a very similar to anchor (copy with small noise)
    anchor_vec = face_embeddings["anchor_face_1"]["mu"].copy()
    face_embeddings["comm_face_a"]["mu"] = anchor_vec + np.random.RandomState(1).randn(512).astype(np.float32) * 0.01
    face_embeddings["comm_face_a"]["mu"] /= np.linalg.norm(face_embeddings["comm_face_a"]["mu"])

    # Face-to-photo mapping: community faces map to community photos
    face_to_photo = {
        "anchor_face_1": "photo_anchor",
        "comm_face_a": "photo_comm_1",
        "comm_face_b": "photo_comm_2",
        "comm_face_c": "photo_comm_3",
    }
    photo_cache = {
        "photo_comm_1": {"filename": "comm1.jpg"},
        "photo_comm_2": {"filename": "comm2.jpg"},
        "photo_comm_3": {"filename": "comm3.jpg"},
    }

    community_photo_ids = ["photo_comm_1", "photo_comm_2", "photo_comm_3"]

    with (
        patch("app.identity_routes._main_mod.load_registry", return_value=registry),
        patch("app.identity_routes._main_mod.load_face_embeddings", return_value=face_embeddings),
        patch("app.identity_routes._main_mod._build_caches"),
        patch("app.identity_routes._main_mod._face_to_photo_cache", face_to_photo),
        patch("app.identity_routes._main_mod._photo_cache", photo_cache),
        patch("app.identity_routes.load_photos_for_community", return_value=community_photo_ids),
    ):
        response = client.get(_url(identity_id, "test-community"), headers=HTMX_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3

    # comm_face_a should be closest (we made it very similar)
    assert data[0]["face_id"] == "comm_face_a"
    assert data[0]["distance"] < data[1]["distance"]

    # All results have required fields
    for item in data:
        assert "face_id" in item
        assert "photo_id" in item
        assert "distance" in item
        assert "photo_path" in item
        assert item["photo_path"].startswith("raw_photos/")


def test_search_returns_empty_when_no_matches(client, auth_enabled, admin_user):
    """Returns empty list when community has no photos."""
    registry = IdentityRegistry()
    identity_id = registry.create_identity(
        anchor_ids=["anchor_face_1"],
        user_source="test",
        state=IdentityState.CONFIRMED,
    )

    face_embeddings = _make_face_embeddings(["anchor_face_1"])

    with (
        patch("app.identity_routes._main_mod.load_registry", return_value=registry),
        patch("app.identity_routes._main_mod.load_face_embeddings", return_value=face_embeddings),
        patch("app.identity_routes.load_photos_for_community", return_value=[]),
    ):
        response = client.get(_url(identity_id, "empty-community"), headers=HTMX_HEADERS)

    assert response.status_code == 200
    assert response.json() == []


def test_search_respects_limit(client, auth_enabled, admin_user):
    """Limit parameter caps the number of results."""
    registry = IdentityRegistry()
    identity_id = registry.create_identity(
        anchor_ids=["anchor_face_1"],
        user_source="test",
        state=IdentityState.CONFIRMED,
    )

    # Create 10 community faces
    comm_faces = [f"comm_face_{i}" for i in range(10)]
    all_faces = ["anchor_face_1"] + comm_faces
    face_embeddings = _make_face_embeddings(all_faces)

    face_to_photo = {"anchor_face_1": "photo_anchor"}
    photo_cache = {}
    community_photo_ids = []
    for i, fid in enumerate(comm_faces):
        pid = f"photo_{i}"
        face_to_photo[fid] = pid
        photo_cache[pid] = {"filename": f"photo_{i}.jpg"}
        community_photo_ids.append(pid)

    with (
        patch("app.identity_routes._main_mod.load_registry", return_value=registry),
        patch("app.identity_routes._main_mod.load_face_embeddings", return_value=face_embeddings),
        patch("app.identity_routes._main_mod._build_caches"),
        patch("app.identity_routes._main_mod._face_to_photo_cache", face_to_photo),
        patch("app.identity_routes._main_mod._photo_cache", photo_cache),
        patch("app.identity_routes.load_photos_for_community", return_value=community_photo_ids),
    ):
        response = client.get(_url(identity_id, "test-community", limit=3), headers=HTMX_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


def test_search_returns_404_for_unknown_identity(client, auth_enabled, admin_user):
    """Returns 404 when identity doesn't exist."""
    registry = IdentityRegistry()

    with patch("app.identity_routes._main_mod.load_registry", return_value=registry):
        response = client.get(_url("nonexistent-id", "comm-1"), headers=HTMX_HEADERS)

    assert response.status_code == 404
    assert "not found" in response.json()["error"].lower()


def test_search_returns_404_for_no_anchor_embeddings(client, auth_enabled, admin_user):
    """Returns 404 when identity has anchors but no embeddings for them."""
    registry = IdentityRegistry()
    identity_id = registry.create_identity(
        anchor_ids=["missing_face"],
        user_source="test",
        state=IdentityState.CONFIRMED,
    )

    # Empty embeddings — anchor face not found
    face_embeddings = {}

    with (
        patch("app.identity_routes._main_mod.load_registry", return_value=registry),
        patch("app.identity_routes._main_mod.load_face_embeddings", return_value=face_embeddings),
    ):
        response = client.get(_url(identity_id, "comm-1"), headers=HTMX_HEADERS)

    assert response.status_code == 404
    assert "embeddings" in response.json()["error"].lower()


def test_search_returns_400_for_missing_params(client, auth_enabled, admin_user):
    """Returns 400 when required parameters are missing."""
    response = client.get(
        "/api/admin/search-person-in-collection",
        headers=HTMX_HEADERS,
    )
    assert response.status_code == 400
