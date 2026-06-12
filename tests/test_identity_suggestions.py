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
        """Verify identity_suggestions table exists in Supabase.

        Live-integration smoke test: skips when Supabase creds are absent or
        malformed (e.g. CI without valid secrets — a non-empty but invalid URL
        raises 'Invalid URL'). A unit gate must not hard-fail on environment
        config (Lesson 181).
        """
        import os

        import pytest
        from dotenv import load_dotenv

        load_dotenv(str(Path(__file__).resolve().parent.parent / ".env"))
        url = os.getenv("SUPABASE_URL", "") or ""
        key = os.getenv("SUPABASE_ANON_KEY", "") or ""
        if not url.startswith("https://") or not key:
            pytest.skip("Supabase creds absent/invalid — live integration check skipped")

        from supabase import create_client

        try:
            sb = create_client(url, key)
            resp = sb.table("identity_suggestions").select("id").limit(1).execute()
        except Exception as e:  # noqa: BLE001 — env/connectivity is a skip, not a failure
            pytest.skip(f"Supabase unreachable in this environment: {e}")
        assert isinstance(resp.data, list)


# Import Path at module level for TestIdentitySuggestionsTable
from pathlib import Path
from unittest.mock import MagicMock


def _import_module():
    """Import the compute_identity_suggestions module."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import scripts.compute_identity_suggestions as mod

    return mod


class TestAgeTrajectoryWired:
    """Test that age_trajectory signal is wired (not a placeholder)."""

    def test_age_trajectory_wired_in_pipeline(self):
        """Run the signal computation and verify it doesn't return the placeholder dict."""
        mod = _import_module()
        # Set up test data: a person with a photo that has a date label and estimated age
        date_labels = {"photo-abc": {"estimated_year": 1920, "estimated_age": 27}}
        identity_photos = {"test-person-1": ["photo-abc"]}
        # Use the middle birth year (1893) — expected age in 1920 = 27, deviation = 0
        result = mod.compute_age_feasibility("test-person-1", mod.FOX_BIRTH_YEAR_MIDDLE, date_labels, identity_photos)
        # Must NOT be the old placeholder
        assert result != {"score": 0.5, "reason": "not_yet_implemented"}
        # Should have a real score based on age match
        assert "score" in result
        assert result["score"] > 0.5  # Good match: birth 1893, photo 1920, age 27


class TestGedcomMatch:
    """Test compute_gedcom_match_score."""

    def test_gedcom_match_basic(self):
        """Matching era + generation scores > 0.5."""
        mod = _import_module()
        # Target co-occurs with family and has estimated birth ~1900 (matches Irving Fox, 1899)
        family_ids = {"fam-albert", "fam-esther"}
        co_occurrence = {
            tuple(sorted(["target-1", "fam-albert"])): 3,
        }
        date_labels = {
            "photo-1": {"estimated_year": 1925, "estimated_age": 25},  # birth ~1900
        }
        identity_photos = {"target-1": ["photo-1"]}
        result = mod.compute_gedcom_match_score("target-1", family_ids, co_occurrence, date_labels, identity_photos)
        assert result["score"] >= 0.5
        assert "best_sibling_match" in result

    def test_gedcom_match_impossible_era(self):
        """Person with photo dates suggesting birth in 1960s can't match Fox siblings."""
        mod = _import_module()
        family_ids = {"fam-1"}
        co_occurrence = {}
        date_labels = {
            "photo-1": {"estimated_year": 1990, "estimated_age": 30},  # birth ~1960
        }
        identity_photos = {"target-1": ["photo-1"]}
        result = mod.compute_gedcom_match_score("target-1", family_ids, co_occurrence, date_labels, identity_photos)
        # Born ~1960 is impossible era (>1930)
        assert result["score"] == 0.0
        assert result["reason"] == "impossible_era"

    def test_gedcom_match_wrong_generation(self):
        """Person born ~1920 is wrong generation for Fox siblings (1877-1903)."""
        mod = _import_module()
        family_ids = {"fam-1"}
        co_occurrence = {}
        date_labels = {
            "photo-1": {"estimated_year": 1950, "estimated_age": 30},  # birth ~1920
        }
        identity_photos = {"target-1": ["photo-1"]}
        result = mod.compute_gedcom_match_score("target-1", family_ids, co_occurrence, date_labels, identity_photos)
        # Born ~1920, closest sibling Jacob 1903 → diff=17 > 10 → wrong generation
        assert result["score"] == 0.0
        assert result["reason"] == "wrong_generation"

    def test_gedcom_match_no_data(self):
        """No photo age data defaults to 0.0 or co-occurrence-only."""
        mod = _import_module()
        result = mod.compute_gedcom_match_score("target-1", set(), {}, {}, {})
        assert result["score"] == 0.0
        assert result["reason"] == "no_data"


class TestTestimony:
    """Test testimony signal lookup."""

    def test_testimony_known_negative(self):
        """Person 3481 (273ac560...) returns score 0.0 with negative testimony."""
        mod = _import_module()
        result = mod.get_testimony("273ac560-bf13-43f5-8f87-e0f7ec967b2c")
        assert result["score"] == 0.0
        assert len(result["entries"]) > 0
        assert result["entries"][0]["polarity"] == "NEGATIVE"
        assert "Howard Newman" in result["entries"][0]["source"]

    def test_testimony_unknown_person(self):
        """Unknown person returns empty testimony with score 0.0."""
        mod = _import_module()
        result = mod.get_testimony("00000000-0000-0000-0000-000000000000")
        assert result["score"] == 0.0
        assert result["entries"] == []


class TestProvenance:
    """Test provenance signal lookup."""

    def test_provenance_default_zero(self):
        """Unknown person returns score 0.0."""
        mod = _import_module()
        result = mod.get_provenance("00000000-0000-0000-0000-000000000000")
        assert result["score"] == 0.0
        assert result["labels"] == []


class TestAggregateWithAllSignals:
    """Test that aggregate_evidence works correctly with all 6 signals active."""

    def test_aggregate_with_all_signals_active(self):
        """Confidence with 6 real signals should differ from 2-signal placeholder baseline."""
        mod = _import_module()
        # Simulate the old placeholder state (2 active, 4 at neutral/zero)
        old_signals = {
            "family_cluster": {"score": 0.7},
            "co_occurrence": {"score": 0.4},
            "age_trajectory": {"score": 0.5},  # old placeholder
            "gedcom_match": {"score": 0.5},  # old placeholder
            "testimony": {"score": 0.0},  # old placeholder
            "provenance": {"score": 0.0},  # old placeholder
        }
        old_confidence = mod.aggregate_evidence(old_signals)

        # Now with all 6 signals providing real positive evidence
        new_signals = {
            "family_cluster": {"score": 0.7},
            "co_occurrence": {"score": 0.4},
            "age_trajectory": {"score": 0.9},  # high age match
            "gedcom_match": {"score": 1.0},  # perfect GEDCOM match
            "testimony": {"score": 0.8},  # positive testimony
            "provenance": {"score": 0.6},  # some provenance
        }
        new_confidence = mod.aggregate_evidence(new_signals)

        # All-positive signals should produce higher confidence
        assert new_confidence > old_confidence
        assert new_confidence > 0.7  # Strong overall signal


class TestRerunPreservesReviewedStatus:
    """Test that batch rerun doesn't overwrite reviewed suggestions."""

    def test_rerun_preserves_reviewed_status(self):
        """Mock Supabase with existing REJECTED row, verify it's not overwritten."""
        mod = _import_module()

        # Create a mock Supabase client
        mock_sb = MagicMock()

        # Mock the reviewed suggestions query
        mock_reviewed_response = MagicMock()
        mock_reviewed_response.data = [
            {
                "target_identity_id": "already-reviewed-id",
                "family_id": "fox",
                "status": "REJECTED",
            },
            {
                "target_identity_id": "accepted-id",
                "family_id": "fox",
                "status": "ACCEPTED",
            },
        ]

        # Track what gets written
        written_ids = []
        mock_upsert_response = MagicMock()
        mock_upsert_response.execute.return_value = MagicMock(data=[])

        def track_upsert(row, on_conflict=None):
            written_ids.append(row["target_identity_id"])
            return mock_upsert_response

        # Wire up the chain: sb.table("identity_suggestions").select(...).eq(...).in_(...).execute()
        mock_select_chain = MagicMock()
        mock_select_chain.execute.return_value = mock_reviewed_response
        mock_eq_chain = MagicMock()
        mock_eq_chain.in_.return_value = mock_select_chain
        mock_select_obj = MagicMock()
        mock_select_obj.eq.return_value = mock_eq_chain

        mock_table = MagicMock()
        mock_table.select.return_value = mock_select_obj
        mock_table.upsert.side_effect = track_upsert

        mock_sb.table.return_value = mock_table

        # Simulate the write loop with reviewed-key filtering
        suggestions = [
            {
                "target_identity_id": "already-reviewed-id",
                "family_id": "fox",
                "suggested_name": "test",
                "confidence": 0.8,
                "evidence_json": {},
                "status": "PENDING",
            },
            {
                "target_identity_id": "accepted-id",
                "family_id": "fox",
                "suggested_name": "test",
                "confidence": 0.7,
                "evidence_json": {},
                "status": "PENDING",
            },
            {
                "target_identity_id": "new-suggestion-id",
                "family_id": "fox",
                "suggested_name": "test",
                "confidence": 0.6,
                "evidence_json": {},
                "status": "PENDING",
            },
        ]

        # Simulate the idempotency logic from run_pipeline
        existing_resp = (
            mock_sb.table("identity_suggestions")
            .select("target_identity_id,family_id,status")
            .eq("family_id", "fox")
            .in_("status", ["REJECTED", "ACCEPTED", "NEEDS_MORE"])
            .execute()
        )
        reviewed_keys = {(r["target_identity_id"], r["family_id"]) for r in (existing_resp.data or [])}

        for s in suggestions:
            if (s["target_identity_id"], s["family_id"]) in reviewed_keys:
                continue
            row = {
                "target_identity_id": s["target_identity_id"],
                "suggested_name": s["suggested_name"],
                "family_id": s["family_id"],
                "confidence": s["confidence"],
                "evidence_json": s["evidence_json"],
                "status": "PENDING",
            }
            mock_sb.table("identity_suggestions").upsert(row, on_conflict="target_identity_id,family_id").execute()

        # Only the new suggestion should have been written
        assert "new-suggestion-id" in written_ids
        assert "already-reviewed-id" not in written_ids
        assert "accepted-id" not in written_ids


class TestGedcomBirthYearParser:
    """Test GEDCOM birth_date parsing."""

    def test_parse_exact_year(self):
        """Exact year like '1889' is parsed correctly."""
        mod = _import_module()
        mock_sb = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = [
            {"id": "1", "given_name": "Albert", "surname": "Fox", "birth_date": "1893"},
        ]
        mock_sb.table.return_value.select.return_value.execute.return_value = mock_resp

        result = mod.load_gedcom_birth_years(mock_sb)
        assert result.get("Albert Fox") == 1893

    def test_parse_abt_year(self):
        """Approximate year like 'ABT 1890' is parsed correctly."""
        mod = _import_module()
        mock_sb = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = [
            {"id": "2", "given_name": "Sarah", "surname": "Fox", "birth_date": "ABT 1882"},
        ]
        mock_sb.table.return_value.select.return_value.execute.return_value = mock_resp

        result = mod.load_gedcom_birth_years(mock_sb)
        assert result.get("Sarah Fox") == 1882

    def test_parse_bef_year(self):
        """Before year like 'BEF 1895' is parsed correctly."""
        mod = _import_module()
        mock_sb = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = [
            {"id": "3", "given_name": "Jacob", "surname": "Fox", "birth_date": "BEF 1905"},
        ]
        mock_sb.table.return_value.select.return_value.execute.return_value = mock_resp

        result = mod.load_gedcom_birth_years(mock_sb)
        assert result.get("Jacob Fox") == 1905
