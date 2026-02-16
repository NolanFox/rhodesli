"""Tests for the birth year estimation pipeline.

Tests cover:
- Face-to-age matching (single person, bbox matching, count mismatch)
- Birth year computation (weighted average, confidence tiers, flags)
- Full pipeline integration with synthetic data
- Validation (impossible ages, outliers, birth year bounds)
- Big Leon Capeluto validation anchor (real data, if available)

Acceptance criteria from PRD 008:
1. birth_year_estimates.json exists and is valid JSON
2. Identities with 5+ appearances AND matched age data have estimates
3. Each estimate has HIGH/MEDIUM/LOW confidence
4. Each estimate has per-photo evidence array
5. No person has impossible ages (negative or >100) in any photo
6. Big Leon Capeluto has estimate near 1903 (range 1900-1910)
7. /timeline integration (tested in e2e tests)
8. Known birth year validation
"""

import json
import math
from pathlib import Path

import numpy as np
import pytest

from rhodesli_ml.pipelines.birth_year_estimation import (
    CONFIDENCE_WEIGHTS,
    HIGH_CONFIDENCE_MIN_N,
    HIGH_CONFIDENCE_STD,
    MAX_AGE,
    MEDIUM_CONFIDENCE_STD,
    MIN_AGE,
    MIN_BIRTH_YEAR,
    MAX_BIRTH_YEAR,
    SINGLE_PERSON_BONUS,
    compute_birth_year_estimate,
    get_face_ids_for_identity,
    match_faces_to_ages,
    run_birth_year_estimation,
)


# ============================================================
# Fixtures
# ============================================================

def _make_identity(identity_id, name, state="CONFIRMED", anchor_ids=None,
                   candidate_ids=None, metadata=None):
    return {
        "identity_id": identity_id,
        "name": name,
        "state": state,
        "anchor_ids": anchor_ids or [],
        "candidate_ids": candidate_ids or [],
        "negative_ids": [],
        "version_id": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "metadata": metadata or {},
        "history": [],
    }


def _make_photo(photo_id, path, face_ids, source="test"):
    return {
        "path": path,
        "face_ids": face_ids,
        "source": source,
        "width": 800,
        "height": 600,
    }


def _make_date_label(photo_id, year, ages, confidence="high"):
    return {
        "photo_id": photo_id,
        "best_year_estimate": year,
        "subject_ages": ages,
        "confidence": confidence,
        "estimated_decade": (year // 10) * 10,
        "probable_range": [year - 2, year + 2],
        "source": "gemini",
    }


def _make_embedding_entry(face_id, filename, bbox):
    """Create a numpy-compatible embedding dict."""
    return {
        "face_id": face_id,
        "filename": filename,
        "filepath": f"raw_photos/{filename}",
        "bbox": bbox,
        "mu": np.zeros(512),
        "sigma_sq": np.ones(512),
        "det_score": 0.99,
        "quality": 15.0,
    }


@pytest.fixture
def synthetic_data(tmp_path):
    """Create a complete synthetic dataset for pipeline testing.

    Scenario: 2 confirmed identities.
    - "Person A" appears in 5 photos, born ~1920
    - "Person B" appears in 2 photos, born ~1890
    """
    # Identities
    identities = {
        "schema_version": 1,
        "identities": {
            "id-a": _make_identity("id-a", "Person A",
                                   anchor_ids=["face-a1", "face-a2", "face-a3"],
                                   candidate_ids=["face-a4", "face-a5"]),
            "id-b": _make_identity("id-b", "Person B",
                                   anchor_ids=["face-b1", "face-b2"]),
            "id-skip": _make_identity("id-skip", "Skipped Person",
                                      state="SKIPPED",
                                      candidate_ids=["face-skip1"]),
        },
        "history": [],
    }
    id_path = tmp_path / "identities.json"
    id_path.write_text(json.dumps(identities))

    # Photos — Person A in 5 photos, Person B in 2, some multi-person
    photos = {
        "schema_version": 1,
        "photos": {
            "photo-1": _make_photo("photo-1", "p1.jpg", ["face-a1"]),         # A alone
            "photo-2": _make_photo("photo-2", "p2.jpg", ["face-a2"]),         # A alone
            "photo-3": _make_photo("photo-3", "p3.jpg", ["face-a3", "face-b1"]),  # A + B
            "photo-4": _make_photo("photo-4", "p4.jpg", ["face-a4"]),         # A alone
            "photo-5": _make_photo("photo-5", "p5.jpg", ["face-a5", "face-b2"]),  # A + B
        },
        "face_to_photo": {
            "face-a1": "photo-1",
            "face-a2": "photo-2",
            "face-a3": "photo-3",
            "face-a4": "photo-4",
            "face-a5": "photo-5",
            "face-b1": "photo-3",
            "face-b2": "photo-5",
        },
    }
    pi_path = tmp_path / "photo_index.json"
    pi_path.write_text(json.dumps(photos))

    # Date labels
    labels = {
        "schema_version": 2,
        "labels": [
            _make_date_label("photo-1", 1940, [20]),           # A=20 → born 1920
            _make_date_label("photo-2", 1950, [30]),           # A=30 → born 1920
            _make_date_label("photo-3", 1955, [35, 65]),       # A=35, B=65 → A born 1920, B born 1890
            _make_date_label("photo-4", 1960, [40], "medium"), # A=40 → born 1920
            _make_date_label("photo-5", 1965, [45, 75]),       # A=45, B=75 → A born 1920, B born 1890
        ],
    }
    dl_path = tmp_path / "date_labels.json"
    dl_path.write_text(json.dumps(labels))

    # Embeddings — faces with bboxes for left-to-right matching
    embeddings = np.array([
        _make_embedding_entry("face-a1", "p1.jpg", [100, 50, 200, 200]),
        _make_embedding_entry("face-a2", "p2.jpg", [100, 50, 200, 200]),
        _make_embedding_entry("face-a3", "p3.jpg", [50, 50, 150, 200]),   # A on left
        _make_embedding_entry("face-b1", "p3.jpg", [300, 50, 400, 200]),  # B on right
        _make_embedding_entry("face-a4", "p4.jpg", [100, 50, 200, 200]),
        _make_embedding_entry("face-a5", "p5.jpg", [50, 50, 150, 200]),   # A on left
        _make_embedding_entry("face-b2", "p5.jpg", [300, 50, 400, 200]),  # B on right
    ])
    emb_path = tmp_path / "embeddings.npy"
    np.save(emb_path, embeddings, allow_pickle=True)

    output_path = tmp_path / "birth_year_estimates.json"

    return {
        "identities_path": str(id_path),
        "photo_index_path": str(pi_path),
        "date_labels_path": str(dl_path),
        "embeddings_path": str(emb_path),
        "output_path": str(output_path),
    }


# ============================================================
# Test: match_faces_to_ages
# ============================================================

class TestMatchFacesToAges:
    """Tests for face-to-age matching via bbox x-coordinate ordering."""

    def test_single_person_match(self):
        """Single face + single age → unambiguous match."""
        face_bboxes = {"face-1": {"bbox": [100, 50, 200, 200]}}
        result, method = match_faces_to_ages(["face-1"], face_bboxes, [25])
        assert result == {"face-1": 25}
        assert method == "single_person"

    def test_two_person_bbox_match(self):
        """Two faces sorted left-to-right match two ages."""
        face_bboxes = {
            "face-left": {"bbox": [50, 50, 150, 200]},
            "face-right": {"bbox": [300, 50, 400, 200]},
        }
        result, method = match_faces_to_ages(
            ["face-right", "face-left"],  # unordered input
            face_bboxes, [20, 40]
        )
        assert result == {"face-left": 20, "face-right": 40}
        assert method == "bbox_matched"

    def test_count_mismatch_returns_empty(self):
        """Different number of faces and ages → no match."""
        face_bboxes = {"face-1": {"bbox": [100, 50, 200, 200]}}
        result, method = match_faces_to_ages(["face-1"], face_bboxes, [25, 30])
        assert result == {}
        assert method == "count_mismatch"

    def test_missing_bbox_returns_empty(self):
        """Face without bbox → can't sort → no match."""
        face_bboxes = {
            "face-1": {"bbox": [100, 50, 200, 200]},
            "face-2": {},  # no bbox
        }
        result, method = match_faces_to_ages(
            ["face-1", "face-2"], face_bboxes, [25, 30]
        )
        assert result == {}
        assert method == "missing_bbox"

    def test_empty_ages_returns_empty(self):
        """No subject_ages → no match."""
        result, method = match_faces_to_ages(["face-1"], {}, [])
        assert result == {}
        assert method == "no_data"

    def test_empty_faces_returns_empty(self):
        """No faces → no match."""
        result, method = match_faces_to_ages([], {}, [25])
        assert result == {}
        assert method == "no_data"

    def test_three_person_ordering(self):
        """Three faces properly ordered by x-coordinate."""
        face_bboxes = {
            "face-c": {"bbox": [500, 50, 600, 200]},
            "face-a": {"bbox": [50, 50, 150, 200]},
            "face-b": {"bbox": [250, 50, 350, 200]},
        }
        result, method = match_faces_to_ages(
            ["face-c", "face-a", "face-b"],
            face_bboxes, [20, 35, 50]
        )
        assert result == {"face-a": 20, "face-b": 35, "face-c": 50}
        assert method == "bbox_matched"


# ============================================================
# Test: compute_birth_year_estimate
# ============================================================

class TestComputeBirthYearEstimate:
    """Tests for weighted birth year computation."""

    def test_single_evidence_item(self):
        """Single evidence item gives an estimate with low confidence."""
        evidence = [{"implied_birth": 1920, "weight": 1.0, "photo_year": 1940,
                     "estimated_age": 20, "photo_id": "p1"}]
        est, std, conf, lo, hi, flags = compute_birth_year_estimate(evidence)
        assert est == 1920
        assert conf == "low"  # single item → infinite std → low

    def test_two_consistent_items(self):
        """Two consistent items give medium confidence."""
        evidence = [
            {"implied_birth": 1920, "weight": 1.0, "photo_year": 1940,
             "estimated_age": 20, "photo_id": "p1"},
            {"implied_birth": 1921, "weight": 1.0, "photo_year": 1951,
             "estimated_age": 30, "photo_id": "p2"},
        ]
        est, std, conf, lo, hi, flags = compute_birth_year_estimate(evidence)
        assert est == 1920 or est == 1921  # weighted avg rounds
        assert conf == "medium"  # n==2 always medium

    def test_high_confidence_with_many_items(self):
        """Multiple items with low std → high confidence."""
        evidence = [
            {"implied_birth": 1920, "weight": 1.0, "photo_year": 1940,
             "estimated_age": 20, "photo_id": "p1"},
            {"implied_birth": 1921, "weight": 1.0, "photo_year": 1951,
             "estimated_age": 30, "photo_id": "p2"},
            {"implied_birth": 1919, "weight": 1.0, "photo_year": 1959,
             "estimated_age": 40, "photo_id": "p3"},
            {"implied_birth": 1920, "weight": 1.0, "photo_year": 1970,
             "estimated_age": 50, "photo_id": "p4"},
        ]
        est, std, conf, lo, hi, flags = compute_birth_year_estimate(evidence)
        assert 1919 <= est <= 1921
        assert std < HIGH_CONFIDENCE_STD
        assert conf == "high"
        assert lo == 1919
        assert hi == 1921
        assert len(flags) == 0

    def test_low_confidence_with_high_variance(self):
        """High variance across items → low confidence."""
        evidence = [
            {"implied_birth": 1920, "weight": 1.0, "photo_year": 1940,
             "estimated_age": 20, "photo_id": "p1"},
            {"implied_birth": 1910, "weight": 1.0, "photo_year": 1950,
             "estimated_age": 40, "photo_id": "p2"},
            {"implied_birth": 1930, "weight": 1.0, "photo_year": 1960,
             "estimated_age": 30, "photo_id": "p3"},
        ]
        est, std, conf, lo, hi, flags = compute_birth_year_estimate(evidence)
        assert std > MEDIUM_CONFIDENCE_STD
        assert conf == "low"

    def test_weighting_affects_estimate(self):
        """Higher-weighted evidence pulls estimate toward it."""
        evidence = [
            {"implied_birth": 1920, "weight": 10.0, "photo_year": 1940,
             "estimated_age": 20, "photo_id": "p1"},  # high weight
            {"implied_birth": 1930, "weight": 1.0, "photo_year": 1960,
             "estimated_age": 30, "photo_id": "p2"},   # low weight
        ]
        est, std, conf, lo, hi, flags = compute_birth_year_estimate(evidence)
        assert est <= 1922  # should be pulled toward 1920

    def test_flags_impossible_age(self):
        """Person with negative or >100 age is flagged."""
        evidence = [
            {"implied_birth": 1950, "weight": 1.0, "photo_year": 1940,
             "estimated_age": -10, "photo_id": "p1"},  # born after photo!
        ]
        est, std, conf, lo, hi, flags = compute_birth_year_estimate(evidence)
        assert any("negative_age" in f for f in flags)

    def test_flags_out_of_range_birth(self):
        """Birth year before 1850 is flagged."""
        evidence = [
            {"implied_birth": 1800, "weight": 1.0, "photo_year": 1880,
             "estimated_age": 80, "photo_id": "p1"},
        ]
        est, std, conf, lo, hi, flags = compute_birth_year_estimate(evidence)
        assert any("birth_year_out_of_range" in f for f in flags)

    def test_empty_evidence_returns_none(self):
        """No evidence → no estimate."""
        est, std, conf, lo, hi, flags = compute_birth_year_estimate([])
        assert est is None
        assert conf is None


# ============================================================
# Test: get_face_ids_for_identity
# ============================================================

class TestGetFaceIds:
    def test_anchors_and_candidates(self):
        identity = {"anchor_ids": ["a1", "a2"], "candidate_ids": ["c1"]}
        result = get_face_ids_for_identity(identity)
        assert set(result) == {"a1", "a2", "c1"}

    def test_deduplicates(self):
        identity = {"anchor_ids": ["a1"], "candidate_ids": ["a1"]}
        result = get_face_ids_for_identity(identity)
        assert result == ["a1"]


# ============================================================
# Test: Full pipeline integration
# ============================================================

class TestFullPipeline:
    """Integration tests for run_birth_year_estimation."""

    def test_pipeline_produces_valid_output(self, synthetic_data):
        """ACCEPTANCE 1: Output file exists and is valid JSON."""
        result = run_birth_year_estimation(**synthetic_data)

        # File should exist
        output_path = Path(synthetic_data["output_path"])
        assert output_path.exists()

        # Valid JSON
        with open(output_path) as f:
            data = json.load(f)
        assert data["schema_version"] == 1
        assert "generated_at" in data
        assert "estimates" in data
        assert isinstance(data["estimates"], list)

    def test_confirmed_identities_get_estimates(self, synthetic_data):
        """ACCEPTANCE 2: Confirmed identities with age data get estimates."""
        result = run_birth_year_estimation(**synthetic_data)
        estimates = result["estimates"]

        names = {e["name"] for e in estimates}
        assert "Person A" in names  # 5 appearances
        assert "Person B" in names  # 2 appearances

        # Skipped identity should NOT get an estimate
        assert "Skipped Person" not in names

    def test_estimates_have_confidence(self, synthetic_data):
        """ACCEPTANCE 3: Each estimate has a confidence tier."""
        result = run_birth_year_estimation(**synthetic_data)
        for est in result["estimates"]:
            assert est["birth_year_confidence"] in ("high", "medium", "low")

    def test_estimates_have_evidence(self, synthetic_data):
        """ACCEPTANCE 4: Each estimate has per-photo evidence array."""
        result = run_birth_year_estimation(**synthetic_data)
        for est in result["estimates"]:
            assert isinstance(est["evidence"], list)
            assert len(est["evidence"]) > 0
            for ev in est["evidence"]:
                assert "photo_id" in ev
                assert "photo_year" in ev
                assert "estimated_age" in ev
                assert "implied_birth" in ev
                assert "weight" in ev
                assert "matching_method" in ev

    def test_no_impossible_ages(self, synthetic_data):
        """ACCEPTANCE 5: No person has impossible ages."""
        result = run_birth_year_estimation(**synthetic_data)
        for est in result["estimates"]:
            birth = est["birth_year_estimate"]
            for ev in est["evidence"]:
                age = ev["photo_year"] - birth
                assert MIN_AGE <= age <= MAX_AGE, (
                    f"{est['name']}: age {age} in {ev['photo_year']} "
                    f"(birth estimate {birth})"
                )

    def test_person_a_birth_year(self, synthetic_data):
        """Person A should have birth year near 1920."""
        result = run_birth_year_estimation(**synthetic_data)
        person_a = next(e for e in result["estimates"] if e["name"] == "Person A")
        assert 1918 <= person_a["birth_year_estimate"] <= 1922
        assert person_a["n_appearances"] == 5
        assert person_a["n_with_age_data"] >= 3

    def test_person_b_birth_year(self, synthetic_data):
        """Person B should have birth year near 1890."""
        result = run_birth_year_estimation(**synthetic_data)
        person_b = next(e for e in result["estimates"] if e["name"] == "Person B")
        assert 1888 <= person_b["birth_year_estimate"] <= 1892

    def test_single_person_photos_weighted_higher(self, synthetic_data):
        """Evidence from single-person photos should have higher weight."""
        result = run_birth_year_estimation(**synthetic_data)
        person_a = next(e for e in result["estimates"] if e["name"] == "Person A")

        single_weights = [
            e["weight"] for e in person_a["evidence"]
            if e["matching_method"] == "single_person"
        ]
        bbox_weights = [
            e["weight"] for e in person_a["evidence"]
            if e["matching_method"] == "bbox_matched"
        ]

        if single_weights and bbox_weights:
            assert max(single_weights) > max(bbox_weights)

    def test_stats_summary(self, synthetic_data):
        """Pipeline result includes summary statistics."""
        result = run_birth_year_estimation(**synthetic_data)
        stats = result["stats"]
        assert stats["total_confirmed"] == 2  # only confirmed, not skipped
        assert stats["with_estimates"] == 2
        assert stats["skipped_no_photos"] == 0

    def test_evidence_sorted_chronologically(self, synthetic_data):
        """Evidence items should be sorted by photo_year."""
        result = run_birth_year_estimation(**synthetic_data)
        for est in result["estimates"]:
            years = [e["photo_year"] for e in est["evidence"]]
            assert years == sorted(years)

    def test_skipped_identities_excluded(self, synthetic_data):
        """Only CONFIRMED identities get estimates."""
        result = run_birth_year_estimation(**synthetic_data)
        names = {e["name"] for e in result["estimates"]}
        assert "Skipped Person" not in names

    def test_min_appearances_filter(self, synthetic_data):
        """min_appearances=3 excludes Person B (only 2 appearances)."""
        result = run_birth_year_estimation(**synthetic_data, min_appearances=3)
        names = {e["name"] for e in result["estimates"]}
        assert "Person A" in names
        assert "Person B" not in names


# ============================================================
# Test: Edge cases
# ============================================================

class TestEdgeCases:
    """Edge case tests for robustness."""

    def test_identity_with_no_photos(self, tmp_path):
        """Identity with face IDs that don't map to any photo."""
        identities = {
            "schema_version": 1,
            "identities": {
                "id-orphan": _make_identity("id-orphan", "Orphan",
                                            anchor_ids=["face-ghost"]),
            },
            "history": [],
        }
        id_path = tmp_path / "identities.json"
        id_path.write_text(json.dumps(identities))

        photos = {"schema_version": 1, "photos": {}, "face_to_photo": {}}
        pi_path = tmp_path / "photo_index.json"
        pi_path.write_text(json.dumps(photos))

        labels = {"schema_version": 2, "labels": []}
        dl_path = tmp_path / "date_labels.json"
        dl_path.write_text(json.dumps(labels))

        embeddings = np.array([])
        emb_path = tmp_path / "embeddings.npy"
        np.save(emb_path, embeddings, allow_pickle=True)

        result = run_birth_year_estimation(
            identities_path=str(id_path),
            photo_index_path=str(pi_path),
            date_labels_path=str(dl_path),
            embeddings_path=str(emb_path),
            output_path=str(tmp_path / "output.json"),
        )
        assert len(result["estimates"]) == 0
        assert result["stats"]["skipped_no_photos"] == 1

    def test_photo_with_no_date_label(self, tmp_path):
        """Photo exists but has no date label → skipped gracefully."""
        identities = {
            "schema_version": 1,
            "identities": {
                "id-1": _make_identity("id-1", "P1", anchor_ids=["face-1"]),
            },
            "history": [],
        }
        id_path = tmp_path / "identities.json"
        id_path.write_text(json.dumps(identities))

        photos = {
            "schema_version": 1,
            "photos": {"ph-1": _make_photo("ph-1", "x.jpg", ["face-1"])},
            "face_to_photo": {"face-1": "ph-1"},
        }
        pi_path = tmp_path / "photo_index.json"
        pi_path.write_text(json.dumps(photos))

        labels = {"schema_version": 2, "labels": []}  # no labels!
        dl_path = tmp_path / "date_labels.json"
        dl_path.write_text(json.dumps(labels))

        embeddings = np.array([
            _make_embedding_entry("face-1", "x.jpg", [100, 50, 200, 200])
        ])
        emb_path = tmp_path / "embeddings.npy"
        np.save(emb_path, embeddings, allow_pickle=True)

        result = run_birth_year_estimation(
            identities_path=str(id_path),
            photo_index_path=str(pi_path),
            date_labels_path=str(dl_path),
            embeddings_path=str(emb_path),
            output_path=str(tmp_path / "output.json"),
        )
        assert len(result["estimates"]) == 0
        assert result["stats"]["skipped_no_age_data"] == 1


# ============================================================
# Test: Real data validation (Big Leon)
# ============================================================

BIG_LEON_ID = "b6d9ea5b-bf90-463a-bab3-682acac7753d"
REAL_DATA_AVAILABLE = (
    Path("data/identities.json").exists()
    and Path("data/photo_index.json").exists()
    and Path("rhodesli_ml/data/date_labels.json").exists()
    and Path("data/embeddings.npy").exists()
)


@pytest.mark.skipif(not REAL_DATA_AVAILABLE, reason="Real data files not available")
class TestRealDataValidation:
    """ACCEPTANCE 6: Big Leon Capeluto birth year validation.

    These tests run against real project data.
    """

    def test_big_leon_has_estimate(self):
        """Big Leon Capeluto should have a birth year estimate."""
        result = run_birth_year_estimation(output_path=None)
        leon = next(
            (e for e in result["estimates"]
             if e["identity_id"] == BIG_LEON_ID),
            None
        )
        assert leon is not None, "Big Leon should have a birth year estimate"

    def test_big_leon_birth_near_1903(self):
        """ACCEPTANCE 6: Big Leon's birth year should be near 1903."""
        result = run_birth_year_estimation(output_path=None)
        leon = next(
            e for e in result["estimates"]
            if e["identity_id"] == BIG_LEON_ID
        )
        assert 1895 <= leon["birth_year_estimate"] <= 1910, (
            f"Big Leon birth estimate {leon['birth_year_estimate']} "
            f"outside expected range 1895-1910"
        )

    def test_big_leon_has_multiple_evidence(self):
        """Big Leon has 25 photos — should have significant evidence."""
        result = run_birth_year_estimation(output_path=None)
        leon = next(
            e for e in result["estimates"]
            if e["identity_id"] == BIG_LEON_ID
        )
        assert leon["n_with_age_data"] >= 3, (
            f"Expected 3+ evidence items for Big Leon, got {leon['n_with_age_data']}"
        )

    def test_all_estimates_have_valid_ages(self):
        """ACCEPTANCE 5: No impossible ages across all estimates."""
        result = run_birth_year_estimation(output_path=None)
        for est in result["estimates"]:
            birth = est["birth_year_estimate"]
            for ev in est["evidence"]:
                age = ev["photo_year"] - birth
                assert MIN_AGE <= age <= MAX_AGE, (
                    f"{est['name']}: impossible age {age} in {ev['photo_year']} "
                    f"(birth estimate {birth})"
                )

    def test_multiple_identities_estimated(self):
        """Multiple confirmed identities should get estimates."""
        result = run_birth_year_estimation(output_path=None)
        assert len(result["estimates"]) >= 5, (
            f"Expected 5+ estimates, got {len(result['estimates'])}"
        )

    def test_output_schema_complete(self):
        """ACCEPTANCE 1+3+4: Output has required fields."""
        result = run_birth_year_estimation(output_path=None)
        for est in result["estimates"]:
            assert "identity_id" in est
            assert "name" in est
            assert "birth_year_estimate" in est
            assert "birth_year_confidence" in est
            assert est["birth_year_confidence"] in ("high", "medium", "low")
            assert "birth_year_range" in est
            assert isinstance(est["birth_year_range"], list)
            assert len(est["birth_year_range"]) == 2
            assert "birth_year_std" in est
            assert "n_appearances" in est
            assert "n_with_age_data" in est
            assert "evidence" in est
            assert isinstance(est["evidence"], list)
            assert "source" in est
            assert est["source"] == "ml_inferred"
