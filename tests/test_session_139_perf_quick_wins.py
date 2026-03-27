"""Tests for Session 139 Track E performance quick wins.

E1: Dict lookup for _global_identity_info in perf_cache.py
E2: Precomputed best_face_id cache in main.py
"""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock


class TestGlobalIdentityInfoDictLookup:
    """E1: Verify dict lookup returns same results as linear scan would."""

    def _build_mock_data(self, n_identities=5):
        """Create mock registry, face data, and photo registry for testing."""
        identities = {}
        face_data = {}
        for i in range(n_identities):
            iid = f"id-{i}"
            fid = f"face-{i}"
            emb = np.random.randn(512).astype(np.float32)
            identities[iid] = {
                "state": "CONFIRMED",
                "name": f"Person {i}",
                "anchor_ids": [fid],
                "candidate_ids": [],
            }
            face_data[fid] = {"mu": emb}

        mock_registry = MagicMock()
        mock_registry._identities = identities

        mock_photo_registry = MagicMock()
        mock_photo_registry.get_photos_for_faces = MagicMock(return_value=set())

        return mock_registry, face_data, mock_photo_registry

    def test_dict_lookup_returns_correct_neighbors(self):
        """get_all_neighbors with dict lookup returns valid results."""
        from app.perf_cache import get_all_neighbors, mark_global_dirty

        mark_global_dirty()

        mock_registry, face_data, mock_photo_registry = self._build_mock_data(5)

        with (
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main.get_face_data", return_value=face_data),
            patch("app.main.load_photo_registry", return_value=mock_photo_registry),
        ):
            results = get_all_neighbors("id-0", limit=10)

        # Should return 4 neighbors (all except id-0 itself)
        assert len(results) == 4
        result_ids = {r["identity_id"] for r in results}
        assert "id-0" not in result_ids
        for i in range(1, 5):
            assert f"id-{i}" in result_ids

    def test_dict_lookup_preserves_name_and_face_count(self):
        """Dict lookup returns correct name and face_count for each neighbor."""
        from app.perf_cache import get_all_neighbors, mark_global_dirty

        mark_global_dirty()

        mock_registry, face_data, mock_photo_registry = self._build_mock_data(3)

        with (
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main.get_face_data", return_value=face_data),
            patch("app.main.load_photo_registry", return_value=mock_photo_registry),
        ):
            results = get_all_neighbors("id-0", limit=10)

        for r in results:
            idx = int(r["identity_id"].split("-")[1])
            assert r["name"] == f"Person {idx}"
            assert r["face_count"] == 1

    def test_dict_lookup_for_nonexistent_target(self):
        """get_all_neighbors returns empty for unknown target_id."""
        from app.perf_cache import get_all_neighbors, mark_global_dirty

        mark_global_dirty()

        mock_registry, face_data, mock_photo_registry = self._build_mock_data(3)

        with (
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main.get_face_data", return_value=face_data),
            patch("app.main.load_photo_registry", return_value=mock_photo_registry),
        ):
            results = get_all_neighbors("nonexistent-id", limit=10)

        assert results == []

    def test_identity_info_by_id_dict_built_on_rebuild(self):
        """_global_identity_info_by_id is populated after matrix rebuild."""
        from app import perf_cache
        from app.perf_cache import mark_global_dirty

        mark_global_dirty()

        mock_registry, face_data, mock_photo_registry = self._build_mock_data(3)

        with (
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main.get_face_data", return_value=face_data),
            patch("app.main.load_photo_registry", return_value=mock_photo_registry),
        ):
            # Trigger rebuild
            perf_cache._rebuild_global_matrix()

        # Verify dict was built
        assert perf_cache._global_identity_info_by_id is not None
        assert len(perf_cache._global_identity_info_by_id) == 3
        for i in range(3):
            info = perf_cache._global_identity_info_by_id[f"id-{i}"]
            assert info[0] == f"id-{i}"
            assert info[1] == f"Person {i}"

    def test_identity_info_by_id_cleared_on_error(self):
        """_global_identity_info_by_id is empty dict after rebuild error."""
        from app import perf_cache
        from app.perf_cache import mark_global_dirty

        mark_global_dirty()

        with patch("app.main.load_registry", side_effect=Exception("test error")):
            perf_cache._rebuild_global_matrix()

        assert perf_cache._global_identity_info_by_id == {}


class TestBestFaceCache:
    """E2: Verify best_face_id cache returns consistent results."""

    def test_cache_returns_same_result(self):
        """get_best_face_id returns same result on second call (cached)."""
        import app.main as main_mod

        main_mod._best_face_cache.clear()

        face_ids = ["face-a", "face-b", "face-c"]

        with patch.object(main_mod, "compute_face_quality_score", side_effect=[0.5, 0.9, 0.3]) as mock_score:
            result1 = main_mod.get_best_face_id(face_ids)

        # Second call should use cache (no compute_face_quality_score calls)
        with patch.object(
            main_mod, "compute_face_quality_score", side_effect=Exception("should not be called")
        ) as mock_score:
            result2 = main_mod.get_best_face_id(face_ids)

        assert result1 == result2
        assert result1 == "face-b"

    def test_cache_cleared_by_save_registry(self):
        """save_registry clears the best_face_cache."""
        import app.main as main_mod

        main_mod._best_face_cache[("face-x",)] = "face-x"
        assert len(main_mod._best_face_cache) > 0

        mock_registry = MagicMock()
        mock_registry._identities = {}
        mock_registry._history = []

        with (
            patch("app.supabase_data.shadow_write_identities_batch"),
            patch("app.main.DATA_SOURCE", "postgres"),
        ):
            main_mod.save_registry(mock_registry)

        assert len(main_mod._best_face_cache) == 0

    def test_cache_cleared_by_invalidate_all_caches(self):
        """_invalidate_all_caches clears the best_face_cache."""
        import app.main as main_mod

        main_mod._best_face_cache[("face-y",)] = "face-y"
        assert len(main_mod._best_face_cache) > 0

        main_mod._invalidate_all_caches()

        assert len(main_mod._best_face_cache) == 0

    def test_single_face_not_cached(self):
        """Single-element face_ids lists return early without caching."""
        import app.main as main_mod

        main_mod._best_face_cache.clear()
        result = main_mod.get_best_face_id(["only-face"])
        assert result == "only-face"
        # Single-face shortcut doesn't populate cache (no quality scoring needed)
        assert len(main_mod._best_face_cache) == 0

    def test_empty_face_ids(self):
        """Empty list returns None."""
        import app.main as main_mod

        result = main_mod.get_best_face_id([])
        assert result is None

    def test_dict_face_ids_normalized(self):
        """Dict-style face_ids are normalized before cache key."""
        import app.main as main_mod

        main_mod._best_face_cache.clear()

        dict_ids = [{"face_id": "face-a"}, {"face_id": "face-b"}]

        with patch.object(main_mod, "compute_face_quality_score", side_effect=[0.5, 0.9]):
            result = main_mod.get_best_face_id(dict_ids)

        assert result == "face-b"
        # Cache key should use normalized string IDs
        assert ("face-a", "face-b") in main_mod._best_face_cache
