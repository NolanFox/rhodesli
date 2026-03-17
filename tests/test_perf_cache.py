"""Tests for app/perf_cache.py — vectorized confirmed identity distance computation."""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock


class TestPerfCache:
    """Test the precomputed confirmed identity matrix."""

    def test_empty_confirmed_list(self):
        """Handle 0 confirmed identities gracefully."""
        from app.perf_cache import get_confirmed_distances, mark_confirmed_dirty

        mark_confirmed_dirty()

        mock_registry = MagicMock()
        mock_registry._identities = {}

        with (
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main.get_face_data", return_value={}),
        ):
            result = get_confirmed_distances(np.random.randn(512))

        assert result == []

    def test_vectorized_matches_loop(self):
        """Vectorized distances match loop-based distances within tolerance."""
        from app.perf_cache import get_confirmed_distances, mark_confirmed_dirty
        from scipy.spatial.distance import cdist

        mark_confirmed_dirty()

        # Create 3 confirmed identities with known embeddings
        emb1 = np.random.randn(512).astype(np.float32)
        emb2 = np.random.randn(512).astype(np.float32)
        emb3 = np.random.randn(512).astype(np.float32)
        target = np.random.randn(512).astype(np.float32)

        mock_registry = MagicMock()
        mock_registry._identities = {
            "id1": {
                "state": "CONFIRMED",
                "anchor_ids": ["face1"],
                "candidate_ids": [],
                "name": "Person 1",
            },
            "id2": {
                "state": "CONFIRMED",
                "anchor_ids": ["face2"],
                "candidate_ids": [],
                "name": "Person 2",
            },
            "id3": {
                "state": "CONFIRMED",
                "anchor_ids": ["face3"],
                "candidate_ids": [],
                "name": "Person 3",
            },
        }

        mock_face_data = {
            "face1": {"embeddings": emb1},
            "face2": {"embeddings": emb2},
            "face3": {"embeddings": emb3},
        }

        with (
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main.get_face_data", return_value=mock_face_data),
        ):
            vectorized = get_confirmed_distances(target)

        # Compute loop-based distances for comparison
        for result in vectorized:
            iid = result["identity_id"]
            emb = mock_face_data[f"face{iid[-1]}"]["embeddings"]
            loop_dist = float(cdist([target], [emb], metric="cosine")[0][0])
            assert abs(result["distance"] - loop_dist) < 1e-5, (
                f"Distance mismatch for {iid}: vectorized={result['distance']:.6f} vs loop={loop_dist:.6f}"
            )

    def test_results_sorted_by_distance(self):
        """Results should be sorted by ascending distance."""
        from app.perf_cache import get_confirmed_distances, mark_confirmed_dirty

        mark_confirmed_dirty()

        target = np.random.randn(512).astype(np.float32)

        mock_registry = MagicMock()
        mock_registry._identities = {
            f"id{i}": {
                "state": "CONFIRMED",
                "anchor_ids": [f"face{i}"],
                "candidate_ids": [],
                "name": f"P{i}",
            }
            for i in range(5)
        }
        mock_face_data = {f"face{i}": {"embeddings": np.random.randn(512).astype(np.float32)} for i in range(5)}

        with (
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main.get_face_data", return_value=mock_face_data),
        ):
            results = get_confirmed_distances(target)

        distances = [r["distance"] for r in results]
        assert distances == sorted(distances)

    def test_mark_dirty_triggers_rebuild(self):
        """Marking dirty should trigger a rebuild on next access."""
        from app.perf_cache import mark_confirmed_dirty, get_confirmed_distances
        import app.perf_cache as pc

        mark_confirmed_dirty()
        assert pc._confirmed_dirty is True

        mock_registry = MagicMock()
        mock_registry._identities = {}

        with (
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main.get_face_data", return_value={}),
        ):
            get_confirmed_distances(np.random.randn(512))

        assert pc._confirmed_dirty is False

    def test_merged_identities_excluded(self):
        """Merged identities should not appear in results."""
        from app.perf_cache import get_confirmed_distances, mark_confirmed_dirty

        mark_confirmed_dirty()

        mock_registry = MagicMock()
        mock_registry._identities = {
            "id1": {
                "state": "CONFIRMED",
                "anchor_ids": ["f1"],
                "candidate_ids": [],
                "name": "Active",
                "merged_into": None,
            },
            "id2": {
                "state": "CONFIRMED",
                "anchor_ids": ["f2"],
                "candidate_ids": [],
                "name": "Merged",
                "merged_into": "id1",
            },
        }
        mock_face_data = {
            "f1": {"embeddings": np.random.randn(512)},
            "f2": {"embeddings": np.random.randn(512)},
        }

        with (
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main.get_face_data", return_value=mock_face_data),
        ):
            results = get_confirmed_distances(np.random.randn(512))

        result_ids = {r["identity_id"] for r in results}
        assert "id1" in result_ids
        assert "id2" not in result_ids

    def test_non_confirmed_excluded(self):
        """Only CONFIRMED identities should be in the matrix."""
        from app.perf_cache import get_confirmed_distances, mark_confirmed_dirty

        mark_confirmed_dirty()

        mock_registry = MagicMock()
        mock_registry._identities = {
            "id1": {
                "state": "CONFIRMED",
                "anchor_ids": ["f1"],
                "candidate_ids": [],
                "name": "Confirmed",
            },
            "id2": {
                "state": "PROPOSED",
                "anchor_ids": ["f2"],
                "candidate_ids": [],
                "name": "Proposed",
            },
            "id3": {
                "state": "INBOX",
                "anchor_ids": ["f3"],
                "candidate_ids": [],
                "name": "Inbox",
            },
        }
        mock_face_data = {f"f{i}": {"embeddings": np.random.randn(512)} for i in range(1, 4)}

        with (
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main.get_face_data", return_value=mock_face_data),
        ):
            results = get_confirmed_distances(np.random.randn(512))

        result_ids = {r["identity_id"] for r in results}
        assert result_ids == {"id1"}
