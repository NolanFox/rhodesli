"""Tests for Session 135b: Global embedding matrix in perf_cache.

Verifies that get_all_neighbors() returns correct results using the precomputed
global matrix (all identities, not just confirmed).
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def reset_perf_cache():
    """Reset perf_cache global state before each test."""
    import app.perf_cache as pc

    pc._global_matrix = None
    pc._global_face_map = None
    pc._global_identity_map = None
    pc._global_identity_info = None
    pc._global_identity_photos = None
    pc._global_dirty = True
    yield
    pc._global_matrix = None
    pc._global_face_map = None
    pc._global_identity_map = None
    pc._global_identity_info = None
    pc._global_identity_photos = None
    pc._global_dirty = True


def _make_embedding(seed=42):
    """Create a deterministic 512-dim embedding."""
    rng = np.random.RandomState(seed)
    emb = rng.randn(512).astype(np.float32)
    return emb


def _setup_global_cache():
    """Directly populate the global cache with test data (bypasses _rebuild_global_matrix)."""
    import app.perf_cache as pc

    # 3 identities: id-confirmed (face-a), id-proposed (face-b), id-inbox (face-c)
    emb_a = _make_embedding(seed=1)
    emb_c = emb_a + np.random.RandomState(99).randn(512).astype(np.float32) * 0.01  # very close to a
    emb_b = _make_embedding(seed=42)  # different

    embeddings = np.vstack([emb_a, emb_b, emb_c]).astype(np.float32)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    embeddings = embeddings / norms

    pc._global_matrix = embeddings
    pc._global_face_map = [
        ("id-confirmed", "face-a"),
        ("id-proposed", "face-b"),
        ("id-inbox", "face-c"),
    ]
    pc._global_identity_map = np.array([0, 1, 2], dtype=np.int32)
    pc._global_identity_info = [
        ("id-confirmed", "Alice", ["face-a"], 1),
        ("id-proposed", "Bob Proposed", ["face-b"], 1),
        ("id-inbox", "Unidentified Person 123", ["face-c"], 1),
    ]
    pc._global_identity_info_by_id = {item[0]: item for item in pc._global_identity_info}
    pc._global_identity_photos = {
        "id-confirmed": set(),
        "id-proposed": set(),
        "id-inbox": set(),
    }
    pc._global_dirty = False


def test_get_all_neighbors_returns_sorted_by_distance():
    """get_all_neighbors returns neighbors sorted by distance, closest first."""
    import app.perf_cache as pc

    _setup_global_cache()
    results = pc.get_all_neighbors("id-inbox", limit=10)

    assert len(results) == 2  # id-confirmed and id-proposed (not self)
    # id-confirmed (face-a) should be closer to id-inbox (face-c) than id-proposed (face-b)
    assert results[0]["identity_id"] == "id-confirmed"
    assert results[0]["distance"] < results[1]["distance"]


def test_get_all_neighbors_excludes_self():
    """get_all_neighbors does not include the target identity."""
    import app.perf_cache as pc

    _setup_global_cache()
    results = pc.get_all_neighbors("id-confirmed", limit=10)

    identity_ids = [r["identity_id"] for r in results]
    assert "id-confirmed" not in identity_ids
    assert len(results) == 2


def test_get_all_neighbors_respects_limit():
    """get_all_neighbors returns at most `limit` results."""
    import app.perf_cache as pc

    _setup_global_cache()
    results = pc.get_all_neighbors("id-inbox", limit=1)

    assert len(results) == 1
    assert results[0]["identity_id"] == "id-confirmed"


def test_get_all_neighbors_co_occurrence_blocks_merge():
    """get_all_neighbors marks can_merge=False for co-occurring identities."""
    import app.perf_cache as pc

    _setup_global_cache()
    # Make id-confirmed and id-inbox share a photo
    pc._global_identity_photos["id-confirmed"] = {"photo-1"}
    pc._global_identity_photos["id-inbox"] = {"photo-1"}

    results = pc.get_all_neighbors("id-inbox", limit=10)

    confirmed_result = next(r for r in results if r["identity_id"] == "id-confirmed")
    assert confirmed_result["can_merge"] is False
    assert confirmed_result["merge_blocked_reason"] == "co_occurrence"

    proposed_result = next(r for r in results if r["identity_id"] == "id-proposed")
    assert proposed_result["can_merge"] is True


def test_get_all_neighbors_returns_empty_for_unknown_target():
    """get_all_neighbors returns empty list for target not in matrix."""
    import app.perf_cache as pc

    _setup_global_cache()
    results = pc.get_all_neighbors("nonexistent-id", limit=10)
    assert results == []


def test_mark_global_dirty():
    """mark_global_dirty sets the dirty flag."""
    import app.perf_cache as pc

    pc._global_dirty = False
    pc.mark_global_dirty()
    assert pc._global_dirty is True


def test_get_all_neighbors_result_structure():
    """get_all_neighbors returns dicts with expected keys."""
    import app.perf_cache as pc

    _setup_global_cache()
    results = pc.get_all_neighbors("id-inbox", limit=10)

    assert len(results) > 0
    result = results[0]
    assert "identity_id" in result
    assert "name" in result
    assert "distance" in result
    assert "face_count" in result
    assert "can_merge" in result
    assert "merge_blocked_reason" in result
    assert isinstance(result["distance"], float)
    assert result["distance"] >= 0
