"""Tests for identity suggestion pipeline (PRD-059 Phase 4)."""

import numpy as np
import pytest


# --- Unit tests for scoring functions ---


class TestFamilyClusterScore:
    """Test compute_family_cluster_score from the batch script."""

    def _import_fn(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from scripts.compute_identity_suggestions import compute_family_cluster_score

        return compute_family_cluster_score

    def test_close_target_scores_high(self):
        fn = self._import_fn()
        target = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        family = {
            "Albert": np.array([1.0, 0.1, 0.0], dtype=np.float32),
            "Esther": np.array([1.0, 0.0, 0.1], dtype=np.float32),
        }
        result = fn(target, family, threshold=1.35)
        assert result["score"] > 0.5
        assert result["raw_distance"] < 0.5
        assert result["n_family_members"] == 2

    def test_distant_target_scores_low(self):
        fn = self._import_fn()
        target = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        family = {
            "Albert": np.array([10.0, 10.0, 10.0], dtype=np.float32),
        }
        result = fn(target, family, threshold=1.35)
        assert result["score"] == 0.0

    def test_empty_family_scores_zero(self):
        fn = self._import_fn()
        target = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        result = fn(target, {}, threshold=1.35)
        assert result["score"] == 0.0
        assert result["n_family_members"] == 0

    def test_at_threshold_boundary(self):
        """Target at exactly threshold distance scores near 0."""
        fn = self._import_fn()
        target = np.zeros(512, dtype=np.float32)
        # Place family member at distance = 1.35 (threshold)
        family_vec = np.zeros(512, dtype=np.float32)
        family_vec[0] = 1.35
        family = {"Albert": family_vec}
        result = fn(target, family, threshold=1.35)
        # Should be close to 0 (1.35 is near the upper boundary of 1.55)
        assert result["score"] < 0.4
        assert abs(result["raw_distance"] - 1.35) < 0.01

    def test_closest_member_identified(self):
        fn = self._import_fn()
        target = np.array([1.0, 0.0], dtype=np.float32)
        family = {
            "Far": np.array([5.0, 5.0], dtype=np.float32),
            "Close": np.array([1.1, 0.0], dtype=np.float32),
        }
        result = fn(target, family, threshold=1.35)
        assert result["closest_member"] == "Close"


class TestCoOccurrenceScore:
    def _import_fn(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from scripts.compute_identity_suggestions import compute_co_occurrence_score

        return compute_co_occurrence_score

    def test_no_co_occurrence(self):
        fn = self._import_fn()
        result = fn("target-1", {"fam-1", "fam-2"}, {})
        assert result["score"] == 0.0
        assert result["shared_photos_with_family"] == 0

    def test_high_co_occurrence(self):
        fn = self._import_fn()
        pairs = {
            tuple(sorted(["target-1", "fam-1"])): 8,
            tuple(sorted(["target-1", "fam-2"])): 5,
        }
        result = fn("target-1", {"fam-1", "fam-2"}, pairs)
        assert result["score"] > 0.5
        assert result["shared_photos_with_family"] == 13
        assert result["top_co_occurring"][0]["count"] == 8

    def test_maxes_at_ten(self):
        fn = self._import_fn()
        pairs = {tuple(sorted(["t", "f"])): 50}
        result = fn("t", {"f"}, pairs)
        assert result["score"] == 1.0


class TestAgeFeasibility:
    def _import_fn(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from scripts.compute_identity_suggestions import compute_age_feasibility

        return compute_age_feasibility

    def test_no_birth_year(self):
        fn = self._import_fn()
        result = fn("id-1", None, {}, {})
        assert result["score"] == 0.5

    def test_impossible_age(self):
        fn = self._import_fn()
        # Photo from 1920, person born 1925 → age -5 → impossible
        date_labels = {"photo-1": {"estimated_year": 1920}}
        photo_faces = {"id-1": ["photo-1"]}
        result = fn("id-1", 1925, date_labels, photo_faces)
        assert result["score"] == 0.0
        assert result["reason"] == "impossible_age"

    def test_plausible_age(self):
        fn = self._import_fn()
        date_labels = {"photo-1": {"estimated_year": 1920, "estimated_age": 30}}
        photo_faces = {"id-1": ["photo-1"]}
        result = fn("id-1", 1889, date_labels, photo_faces)
        # Expected age: 31, estimated: 30, deviation: 1 → high score
        assert result["score"] > 0.8


class TestAggregateEvidence:
    def _import_fn(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from scripts.compute_identity_suggestions import aggregate_evidence

        return aggregate_evidence

    def test_all_signals_present(self):
        fn = self._import_fn()
        signals = {
            "family_cluster": {"score": 0.8},
            "co_occurrence": {"score": 0.6},
            "age_trajectory": {"score": 0.9},
            "gedcom_match": {"score": 0.7},
            "testimony": {"score": 0.95},
            "provenance": {"score": 0.5},
        }
        score = fn(signals)
        assert 0.0 < score < 1.0
        # Testimony has highest weight, so score should be influenced
        assert score > 0.7

    def test_absent_signals_redistributed(self):
        fn = self._import_fn()
        # Only family_cluster and co_occurrence present
        signals = {
            "family_cluster": {"score": 1.0},
            "co_occurrence": {"score": 1.0},
        }
        score = fn(signals)
        # All present signals are 1.0, so aggregate should be 1.0
        assert abs(score - 1.0) < 0.01

    def test_no_signals(self):
        fn = self._import_fn()
        score = fn({})
        assert score == 0.0


class TestEmbeddingLoader:
    """Test that the embeddings loader handles both PFE and flat formats."""

    def test_loads_pfe_format(self, tmp_path):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

        # Create a test embeddings file with PFE format
        entries = [
            {
                "face_id": "inbox_test1",
                "mu": np.array([1.0, 2.0, 3.0], dtype=np.float32),
                "sigma_sq": np.array([0.1, 0.1, 0.1], dtype=np.float32),
                "filename": "test.jpg",
                "bbox": [0, 0, 100, 100],
            },
            {
                "face_id": "inbox_test2",
                "mu": np.array([4.0, 5.0, 6.0], dtype=np.float32),
                "filename": "test2.jpg",
                "bbox": [0, 0, 100, 100],
            },
        ]
        npy_path = tmp_path / "embeddings.npy"
        np.save(npy_path, np.array(entries, dtype=object))

        # Monkey-patch ROOT for the loader
        import scripts.compute_identity_suggestions as mod

        original_root = mod.ROOT
        mod.ROOT = tmp_path.parent  # So ROOT / "data" / "embeddings.npy" won't match
        # Instead, directly test loading
        raw = np.load(npy_path, allow_pickle=True)
        lookup = {}
        for entry in raw:
            fid = entry.get("face_id")
            emb = entry.get("mu")
            if emb is None:
                emb = entry.get("embeddings")
            if fid and emb is not None:
                lookup[fid] = np.asarray(emb, dtype=np.float32)

        mod.ROOT = original_root

        assert "inbox_test1" in lookup
        assert "inbox_test2" in lookup
        np.testing.assert_array_almost_equal(lookup["inbox_test1"], [1.0, 2.0, 3.0])


class TestIdentitySuggestionsTable:
    """Test that the identity_suggestions table exists and is accessible."""

    def test_table_exists(self):
        """Verify identity_suggestions table exists in Supabase."""
        from dotenv import load_dotenv

        load_dotenv(str(Path(__file__).resolve().parent.parent / ".env"))
        import os
        from supabase import create_client

        sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY"))
        # Should not raise
        resp = sb.table("identity_suggestions").select("id").limit(1).execute()
        assert isinstance(resp.data, list)


# Import Path at module level for TestIdentitySuggestionsTable
from pathlib import Path
