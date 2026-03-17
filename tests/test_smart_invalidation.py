"""Tests for smart cache invalidation and fast neighbor search."""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock

# Bootstrap app.main first to avoid circular imports
import app.main  # noqa: F401


class TestSmartInvalidation:
    """Test surgical cache invalidation."""

    def test_invalidate_specific_identity(self):
        """invalidate_neighbors_cache with identity_id only removes that entry."""
        from app.identity_routes import (
            invalidate_neighbors_cache,
            _set_cached_neighbors,
            _get_cached_neighbors,
        )

        _set_cached_neighbors("id1", [{"distance": 1.0}])
        _set_cached_neighbors("id2", [{"distance": 2.0}])

        invalidate_neighbors_cache(identity_id="id1")

        assert _get_cached_neighbors("id1") is None
        assert _get_cached_neighbors("id2") is not None

        # Clean up
        invalidate_neighbors_cache()

    def test_invalidate_all(self):
        """invalidate_neighbors_cache without identity_id clears all."""
        from app.identity_routes import (
            invalidate_neighbors_cache,
            _set_cached_neighbors,
            _get_cached_neighbors,
        )

        _set_cached_neighbors("id1", [{"distance": 1.0}])
        _set_cached_neighbors("id2", [{"distance": 2.0}])

        invalidate_neighbors_cache()

        assert _get_cached_neighbors("id1") is None
        assert _get_cached_neighbors("id2") is None

    def test_cluster_review_surgical_invalidation(self):
        """invalidate_cluster_review_caches with changed_ids only removes those."""
        from app.cluster_review_routes import (
            invalidate_cluster_review_caches,
            _suggestions_cache,
        )
        import time

        _suggestions_cache[("id1", "")] = (time.time(), [{"name": "P1"}])
        _suggestions_cache[("id2", "")] = (time.time(), [{"name": "P2"}])
        _suggestions_cache[("id3", "")] = (time.time(), [{"name": "P3"}])

        invalidate_cluster_review_caches(changed_ids={"id1", "id2"})

        assert ("id1", "") not in _suggestions_cache
        assert ("id2", "") not in _suggestions_cache
        assert ("id3", "") in _suggestions_cache

        # Clean up
        _suggestions_cache.clear()

    def test_cluster_review_full_flush(self):
        """invalidate_cluster_review_caches without changed_ids clears all."""
        import app.cluster_review_routes as cr_mod
        import time

        # Populate via module-level dicts
        cr_mod._suggestions_cache[("id1", "")] = (time.time(), [{"name": "P1"}])
        cr_mod._speed_run_cache["slug"] = (time.time(), [])

        cr_mod.invalidate_cluster_review_caches()

        # After full flush, module-level dicts are replaced with empty dicts
        assert len(cr_mod._suggestions_cache) == 0
        assert len(cr_mod._speed_run_cache) == 0


class TestFastNeighborSearch:
    """Test find_nearest_neighbors_fast produces same results as original."""

    def test_fast_matches_original(self):
        """Fast neighbor search returns same ordering as original."""
        from core.neighbors import find_nearest_neighbors, find_nearest_neighbors_fast

        # Create a small test registry with deterministic embeddings
        np.random.seed(42)
        embs = {f"face{i}": np.random.randn(512).astype(np.float32) for i in range(10)}

        mock_registry = MagicMock()
        identities = {}
        for i in range(10):
            iid = f"id{i}"
            identities[iid] = {
                "identity_id": iid,
                "name": f"Person {i}",
                "state": "PROPOSED",
                "anchor_ids": [f"face{i}"],
                "candidate_ids": [],
                "negative_ids": [],
            }

        mock_registry.get_identity = lambda iid: identities.get(iid)
        mock_registry.list_identities = lambda: list(identities.values())

        face_data = {f"face{i}": {"mu": embs[f"face{i}"]} for i in range(10)}

        mock_photo_registry = MagicMock()
        mock_photo_registry.get_photos_for_faces = lambda fids: set()

        original = find_nearest_neighbors("id0", mock_registry, mock_photo_registry, face_data, limit=5)
        fast = find_nearest_neighbors_fast("id0", mock_registry, mock_photo_registry, face_data, limit=5)

        # Same identities in same order
        orig_ids = [r["identity_id"] for r in original]
        fast_ids = [r["identity_id"] for r in fast]
        assert orig_ids == fast_ids

        # Distances match within tolerance
        for o, f in zip(original, fast):
            assert abs(o["distance"] - f["distance"]) < 1e-5

    def test_fast_handles_empty(self):
        """Fast search handles target with no embeddings."""
        from core.neighbors import find_nearest_neighbors_fast

        mock_registry = MagicMock()
        mock_registry.get_identity = lambda iid: {
            "identity_id": iid,
            "anchor_ids": [],
            "candidate_ids": [],
            "negative_ids": [],
        }
        mock_registry.list_identities = lambda: []

        mock_photo_registry = MagicMock()

        result = find_nearest_neighbors_fast("id0", mock_registry, mock_photo_registry, {}, limit=5)
        assert result == []

    def test_fast_skips_merged(self):
        """Fast search skips merged identities."""
        from core.neighbors import find_nearest_neighbors_fast

        np.random.seed(123)

        identities = {
            "id0": {
                "identity_id": "id0",
                "name": "Target",
                "anchor_ids": ["face0"],
                "candidate_ids": [],
                "negative_ids": [],
            },
            "id1": {
                "identity_id": "id1",
                "name": "Merged Away",
                "anchor_ids": ["face1"],
                "candidate_ids": [],
                "negative_ids": [],
                "merged_into": "id0",
            },
            "id2": {
                "identity_id": "id2",
                "name": "Active",
                "anchor_ids": ["face2"],
                "candidate_ids": [],
                "negative_ids": [],
            },
        }

        mock_registry = MagicMock()
        mock_registry.get_identity = lambda iid: identities.get(iid)
        mock_registry.list_identities = lambda: list(identities.values())

        face_data = {f"face{i}": {"mu": np.random.randn(512).astype(np.float32)} for i in range(3)}

        mock_photo_registry = MagicMock()
        mock_photo_registry.get_photos_for_faces = lambda fids: set()

        results = find_nearest_neighbors_fast("id0", mock_registry, mock_photo_registry, face_data, limit=5)

        result_ids = [r["identity_id"] for r in results]
        assert "id1" not in result_ids  # merged identity excluded
        assert "id2" in result_ids
