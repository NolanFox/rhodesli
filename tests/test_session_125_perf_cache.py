"""Tests for Session 125 PERF #8: perf_cache metadata caching.

Verifies that _confirmed_metadata is populated during _rebuild_matrix()
and that get_confirmed_distances() uses it instead of calling load_registry() again.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def reset_perf_cache():
    """Reset perf_cache global state before each test."""
    import app.perf_cache as pc

    pc._confirmed_matrix = None
    pc._confirmed_face_map = None
    pc._confirmed_identity_ids = None
    pc._confirmed_metadata = None
    pc._confirmed_dirty = True
    yield
    pc._confirmed_matrix = None
    pc._confirmed_face_map = None
    pc._confirmed_identity_ids = None
    pc._confirmed_metadata = None
    pc._confirmed_dirty = True


def _make_mock_registry():
    """Create a mock registry with two confirmed identities."""
    registry = MagicMock()
    registry._identities = {
        "id-1": {
            "state": "CONFIRMED",
            "name": "Alice",
            "anchor_ids": ["face-a", "face-b"],
            "candidate_ids": [],
        },
        "id-2": {
            "state": "CONFIRMED",
            "name": "Bob",
            "anchor_ids": ["face-c"],
            "candidate_ids": ["face-d"],
        },
        "id-merged": {
            "state": "CONFIRMED",
            "name": "Merged Person",
            "merged_into": "id-1",
            "anchor_ids": ["face-e"],
            "candidate_ids": [],
        },
        "id-proposed": {
            "state": "PROPOSED",
            "name": "Proposed Person",
            "anchor_ids": ["face-f"],
            "candidate_ids": [],
        },
    }
    return registry


def _make_face_data():
    """Create face data with 512-dim embeddings for each face."""
    rng = np.random.RandomState(42)
    return {
        "face-a": {"embeddings": rng.randn(512).tolist()},
        "face-b": {"embeddings": rng.randn(512).tolist()},
        "face-c": {"embeddings": rng.randn(512).tolist()},
        "face-d": {"embeddings": rng.randn(512).tolist()},
        "face-e": {"embeddings": rng.randn(512).tolist()},
        "face-f": {"embeddings": rng.randn(512).tolist()},
    }


def test_confirmed_metadata_populated_after_rebuild():
    """_confirmed_metadata should be populated with name and face_count after _rebuild_matrix()."""
    import app.perf_cache as pc

    registry = _make_mock_registry()
    face_data = _make_face_data()

    with (
        patch("app.main.load_registry", return_value=registry),
        patch("app.main.get_face_data", return_value=face_data),
    ):
        pc._rebuild_matrix()

    assert pc._confirmed_metadata is not None
    assert "id-1" in pc._confirmed_metadata
    assert "id-2" in pc._confirmed_metadata

    # Alice has 2 anchor faces
    assert pc._confirmed_metadata["id-1"]["name"] == "Alice"
    assert pc._confirmed_metadata["id-1"]["face_count"] == 2

    # Bob has 1 anchor + 1 candidate = 2 faces
    assert pc._confirmed_metadata["id-2"]["name"] == "Bob"
    assert pc._confirmed_metadata["id-2"]["face_count"] == 2

    # Merged and proposed identities should NOT be in metadata
    assert "id-merged" not in pc._confirmed_metadata
    assert "id-proposed" not in pc._confirmed_metadata


def test_get_confirmed_distances_does_not_reload_registry():
    """get_confirmed_distances() should NOT call load_registry() when metadata is cached."""
    import app.perf_cache as pc

    registry = _make_mock_registry()
    face_data = _make_face_data()

    # First call: rebuild populates everything
    with (
        patch("app.main.load_registry", return_value=registry) as mock_load,
        patch("app.main.get_face_data", return_value=face_data),
    ):
        pc._rebuild_matrix()

    # load_registry was called once during rebuild
    assert mock_load.call_count == 1

    # Now call get_confirmed_distances — it should NOT call load_registry again
    pc._confirmed_dirty = False  # ensure no rebuild
    target_emb = np.random.RandomState(99).randn(512)

    with patch("app.main.load_registry") as mock_load2, patch("app.main.get_face_data"):
        results = pc.get_confirmed_distances(target_emb)

    # load_registry should NOT have been called
    assert mock_load2.call_count == 0

    # Results should still have correct names from cached metadata
    names = {r["name"] for r in results}
    assert "Alice" in names
    assert "Bob" in names

    # face_count should be correct
    for r in results:
        if r["name"] == "Alice":
            assert r["face_count"] == 2
        elif r["name"] == "Bob":
            assert r["face_count"] == 2


def test_metadata_empty_dict_on_rebuild_error():
    """_confirmed_metadata should be empty dict (not None) when rebuild fails."""
    import app.perf_cache as pc

    with (
        patch("app.main.load_registry", side_effect=Exception("boom")),
        patch("app.main.get_face_data", side_effect=Exception("boom")),
    ):
        pc._rebuild_matrix()

    assert pc._confirmed_metadata == {}
    assert pc._confirmed_dirty is False
