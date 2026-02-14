"""Tests for the temporal consistency audit script.

Tests cover:
- Temporal impossibility detection (photo before birth, after death)
- Age discrepancy detection (Gemini ages vs expected ages)
- People count discrepancy detection (Gemini count vs detected faces)
- Identity-photo mapping from face_to_photo
- Edge cases: missing metadata, merged identities, no labels
"""

import json
from pathlib import Path

import pytest

from rhodesli_ml.scripts.audit_temporal_consistency import (
    AGE_DISCREPANCY_THRESHOLD,
    audit_people_count,
    audit_temporal_consistency,
    build_identity_photo_map,
    load_date_labels,
    load_identities,
    load_photo_index,
)


# ============================================================
# Fixtures
# ============================================================

def _make_identity(
    identity_id="id-001",
    name="Test Person",
    state="CONFIRMED",
    anchor_ids=None,
    candidate_ids=None,
    birth_year=None,
    death_year=None,
    merged_into=None,
):
    """Build a test identity entry."""
    entry = {
        "identity_id": identity_id,
        "name": name,
        "state": state,
        "anchor_ids": anchor_ids or [],
        "candidate_ids": candidate_ids or [],
        "negative_ids": [],
        "version_id": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "metadata": {},
        "history": [],
    }
    if birth_year is not None:
        entry["metadata"]["birth_year"] = birth_year
    if death_year is not None:
        entry["metadata"]["death_year"] = death_year
    if merged_into is not None:
        entry["merged_into"] = merged_into
    return entry


def _make_label(
    photo_id="photo-001",
    estimated_decade=1940,
    best_year_estimate=1942,
    people_count=3,
    subject_ages=None,
):
    """Build a test date label entry."""
    return {
        "photo_id": photo_id,
        "estimated_decade": estimated_decade,
        "best_year_estimate": best_year_estimate,
        "people_count": people_count,
        "subject_ages": subject_ages or [],
        "source": "gemini",
        "confidence": "medium",
    }


def _make_photo(photo_id="photo-001", face_ids=None, path="test.jpg"):
    """Build a test photo entry."""
    return {
        "path": path,
        "face_ids": face_ids or [],
    }


def _write_json(path, data):
    """Write a JSON file."""
    with open(path, "w") as f:
        json.dump(data, f)


# ============================================================
# File Loading Tests
# ============================================================

class TestFileLoading:
    def test_load_date_labels(self, tmp_path):
        """Loads labels keyed by photo_id."""
        path = tmp_path / "labels.json"
        _write_json(path, {
            "labels": [
                {"photo_id": "p1", "estimated_decade": 1940},
                {"photo_id": "p2", "estimated_decade": 1950},
            ]
        })
        result = load_date_labels(path)
        assert len(result) == 2
        assert "p1" in result
        assert result["p1"]["estimated_decade"] == 1940

    def test_load_date_labels_nonexistent(self, tmp_path):
        """Returns empty dict for missing file."""
        result = load_date_labels(tmp_path / "missing.json")
        assert result == {}

    def test_load_identities(self, tmp_path):
        """Loads identities dict."""
        path = tmp_path / "identities.json"
        _write_json(path, {
            "identities": {
                "id-001": _make_identity("id-001", "Alice"),
            }
        })
        result = load_identities(path)
        assert len(result) == 1
        assert result["id-001"]["name"] == "Alice"

    def test_load_identities_nonexistent(self, tmp_path):
        """Returns empty dict for missing file."""
        result = load_identities(tmp_path / "missing.json")
        assert result == {}

    def test_load_photo_index(self, tmp_path):
        """Loads photos and face_to_photo."""
        path = tmp_path / "photo_index.json"
        _write_json(path, {
            "photos": {"p1": {"face_ids": ["f1", "f2"], "path": "img.jpg"}},
            "face_to_photo": {"f1": "p1", "f2": "p1"},
        })
        photos, f2p = load_photo_index(path)
        assert len(photos) == 1
        assert len(f2p) == 2
        assert f2p["f1"] == "p1"

    def test_load_photo_index_nonexistent(self, tmp_path):
        """Returns empty dicts for missing file."""
        photos, f2p = load_photo_index(tmp_path / "missing.json")
        assert photos == {}
        assert f2p == {}


# ============================================================
# Identity-Photo Mapping Tests
# ============================================================

class TestBuildIdentityPhotoMap:
    def test_basic_mapping(self):
        """Maps identity to photos via anchor_ids."""
        identities = {
            "id-001": _make_identity(
                "id-001", "Alice", anchor_ids=["f1", "f2"],
            ),
        }
        f2p = {"f1": "photo-001", "f2": "photo-002"}
        result = build_identity_photo_map(identities, f2p)
        assert "id-001" in result
        assert result["id-001"] == {"photo-001", "photo-002"}

    def test_includes_candidate_ids(self):
        """Maps identity to photos via candidate_ids too."""
        identities = {
            "id-001": _make_identity(
                "id-001", "Alice",
                anchor_ids=["f1"],
                candidate_ids=["f2"],
            ),
        }
        f2p = {"f1": "photo-001", "f2": "photo-002"}
        result = build_identity_photo_map(identities, f2p)
        assert result["id-001"] == {"photo-001", "photo-002"}

    def test_skips_merged_identities(self):
        """Merged identities are excluded."""
        identities = {
            "id-001": _make_identity(
                "id-001", "Alice",
                anchor_ids=["f1"],
                merged_into="id-002",
            ),
            "id-002": _make_identity(
                "id-002", "Alice (merged)",
                anchor_ids=["f1", "f2"],
            ),
        }
        f2p = {"f1": "photo-001", "f2": "photo-002"}
        result = build_identity_photo_map(identities, f2p)
        assert "id-001" not in result
        assert "id-002" in result

    def test_skips_unmapped_faces(self):
        """Faces not in face_to_photo are silently skipped."""
        identities = {
            "id-001": _make_identity(
                "id-001", "Alice", anchor_ids=["f1", "f_missing"],
            ),
        }
        f2p = {"f1": "photo-001"}
        result = build_identity_photo_map(identities, f2p)
        assert result["id-001"] == {"photo-001"}

    def test_empty_identities(self):
        """Empty identities returns empty map."""
        result = build_identity_photo_map({}, {"f1": "p1"})
        assert result == {}


# ============================================================
# Temporal Consistency Tests
# ============================================================

class TestAuditTemporalConsistency:
    def test_no_flags_when_dates_consistent(self):
        """No flags when photo date is within birth-death range."""
        identities = {
            "id-001": _make_identity(
                "id-001", "Alice",
                anchor_ids=["f1"],
                birth_year=1900,
                death_year=1970,
            ),
        }
        f2p = {"f1": "photo-001"}
        labels = {"photo-001": _make_label("photo-001", best_year_estimate=1940)}

        result = audit_temporal_consistency(labels, identities, f2p)
        assert result["checked"] == 1
        assert len(result["impossible"]) == 0
        assert len(result["suspicious"]) == 0

    def test_flags_photo_before_birth(self):
        """Flags IMPOSSIBLE when photo is dated before person's birth."""
        identities = {
            "id-001": _make_identity(
                "id-001", "Alice",
                anchor_ids=["f1"],
                birth_year=1950,
            ),
        }
        f2p = {"f1": "photo-001"}
        labels = {"photo-001": _make_label("photo-001", best_year_estimate=1940)}

        result = audit_temporal_consistency(labels, identities, f2p)
        assert len(result["impossible"]) == 1
        assert result["impossible"][0]["type"] == "BEFORE_BIRTH"
        assert result["impossible"][0]["name"] == "Alice"

    def test_flags_photo_after_death(self):
        """Flags IMPOSSIBLE when photo is dated after person's death."""
        identities = {
            "id-001": _make_identity(
                "id-001", "Bob",
                anchor_ids=["f1"],
                birth_year=1900,
                death_year=1944,
            ),
        }
        f2p = {"f1": "photo-001"}
        labels = {"photo-001": _make_label("photo-001", best_year_estimate=1960)}

        result = audit_temporal_consistency(labels, identities, f2p)
        assert len(result["impossible"]) == 1
        assert result["impossible"][0]["type"] == "AFTER_DEATH"
        assert result["impossible"][0]["death_year"] == 1944

    def test_flags_both_before_birth_and_after_death(self):
        """Can flag multiple identities for the same photo."""
        identities = {
            "id-001": _make_identity(
                "id-001", "Young Person",
                anchor_ids=["f1"],
                birth_year=1960,  # Photo before birth
            ),
            "id-002": _make_identity(
                "id-002", "Old Person",
                anchor_ids=["f2"],
                death_year=1930,  # Photo after death
            ),
        }
        f2p = {"f1": "photo-001", "f2": "photo-001"}
        labels = {"photo-001": _make_label("photo-001", best_year_estimate=1945)}

        result = audit_temporal_consistency(labels, identities, f2p)
        assert len(result["impossible"]) == 2
        types = {f["type"] for f in result["impossible"]}
        assert "BEFORE_BIRTH" in types
        assert "AFTER_DEATH" in types

    def test_flags_age_mismatch(self):
        """Flags SUSPICIOUS when subject ages diverge from expected."""
        identities = {
            "id-001": _make_identity(
                "id-001", "Alice",
                anchor_ids=["f1"],
                birth_year=1900,
            ),
        }
        f2p = {"f1": "photo-001"}
        # Photo year 1940, birth 1900 -> expected age 40
        # Subject ages [10, 8] -> closest diff is 30 > 20 threshold
        labels = {
            "photo-001": _make_label(
                "photo-001",
                best_year_estimate=1940,
                subject_ages=[10, 8],
            ),
        }

        result = audit_temporal_consistency(labels, identities, f2p)
        assert len(result["suspicious"]) == 1
        assert result["suspicious"][0]["type"] == "AGE_MISMATCH"
        assert result["suspicious"][0]["expected_age"] == 40

    def test_no_age_flag_when_close_match(self):
        """No age flag when a subject age is within threshold."""
        identities = {
            "id-001": _make_identity(
                "id-001", "Alice",
                anchor_ids=["f1"],
                birth_year=1900,
            ),
        }
        f2p = {"f1": "photo-001"}
        # Photo year 1940, birth 1900 -> expected age 40
        # Subject ages [35, 12] -> closest diff is 5 < 20 threshold
        labels = {
            "photo-001": _make_label(
                "photo-001",
                best_year_estimate=1940,
                subject_ages=[35, 12],
            ),
        }

        result = audit_temporal_consistency(labels, identities, f2p)
        assert len(result["suspicious"]) == 0

    def test_custom_age_threshold(self):
        """Custom age threshold changes sensitivity."""
        identities = {
            "id-001": _make_identity(
                "id-001", "Alice",
                anchor_ids=["f1"],
                birth_year=1900,
            ),
        }
        f2p = {"f1": "photo-001"}
        # Expected age 40, subject ages [30] -> diff 10
        labels = {
            "photo-001": _make_label(
                "photo-001",
                best_year_estimate=1940,
                subject_ages=[30],
            ),
        }

        # Default threshold (20) -> no flag
        result = audit_temporal_consistency(labels, identities, f2p)
        assert len(result["suspicious"]) == 0

        # Stricter threshold (5) -> flag
        result = audit_temporal_consistency(
            labels, identities, f2p, age_threshold=5,
        )
        assert len(result["suspicious"]) == 1

    def test_skips_identities_without_temporal_metadata(self):
        """Identities without birth/death year are skipped."""
        identities = {
            "id-001": _make_identity(
                "id-001", "No Dates Person",
                anchor_ids=["f1"],
            ),
        }
        f2p = {"f1": "photo-001"}
        labels = {"photo-001": _make_label("photo-001", best_year_estimate=1940)}

        result = audit_temporal_consistency(labels, identities, f2p)
        assert result["checked"] == 0

    def test_skips_photos_without_labels(self):
        """Photos not in date_labels are skipped."""
        identities = {
            "id-001": _make_identity(
                "id-001", "Alice",
                anchor_ids=["f1"],
                birth_year=1900,
            ),
        }
        f2p = {"f1": "photo-001"}
        labels = {}  # No labels at all

        result = audit_temporal_consistency(labels, identities, f2p)
        assert result["checked"] == 0

    def test_falls_back_to_estimated_decade(self):
        """Uses estimated_decade when best_year_estimate is missing."""
        identities = {
            "id-001": _make_identity(
                "id-001", "Alice",
                anchor_ids=["f1"],
                birth_year=1960,  # Photo decade before birth
            ),
        }
        f2p = {"f1": "photo-001"}
        labels = {
            "photo-001": {
                "photo_id": "photo-001",
                "estimated_decade": 1940,
                # No best_year_estimate
            },
        }

        result = audit_temporal_consistency(labels, identities, f2p)
        assert len(result["impossible"]) == 1
        assert result["impossible"][0]["estimated_year"] == 1940

    def test_no_age_flag_when_subject_ages_empty(self):
        """No age flag when label has no subject_ages."""
        identities = {
            "id-001": _make_identity(
                "id-001", "Alice",
                anchor_ids=["f1"],
                birth_year=1900,
            ),
        }
        f2p = {"f1": "photo-001"}
        labels = {
            "photo-001": _make_label(
                "photo-001",
                best_year_estimate=1940,
                subject_ages=[],
            ),
        }

        result = audit_temporal_consistency(labels, identities, f2p)
        assert len(result["suspicious"]) == 0

    def test_no_age_flag_when_photo_before_birth(self):
        """Age check skipped when estimated_year < birth_year (expected_age < 0)."""
        identities = {
            "id-001": _make_identity(
                "id-001", "Alice",
                anchor_ids=["f1"],
                birth_year=1950,
            ),
        }
        f2p = {"f1": "photo-001"}
        labels = {
            "photo-001": _make_label(
                "photo-001",
                best_year_estimate=1940,
                subject_ages=[10],
            ),
        }

        result = audit_temporal_consistency(labels, identities, f2p)
        # Should have IMPOSSIBLE flag but NOT suspicious age flag
        assert len(result["impossible"]) == 1
        assert len(result["suspicious"]) == 0


# ============================================================
# People Count Discrepancy Tests
# ============================================================

class TestAuditPeopleCount:
    def test_no_discrepancy(self):
        """No flags when Gemini count matches detected count."""
        labels = {"p1": _make_label("p1", people_count=3)}
        photos = {"p1": _make_photo("p1", face_ids=["f1", "f2", "f3"])}
        result = audit_people_count(labels, photos)
        assert result["checked"] == 1
        assert len(result["potentially_missed"]) == 0

    def test_flags_missed_faces(self):
        """Flags when Gemini sees more people than detected faces."""
        labels = {"p1": _make_label("p1", people_count=5)}
        photos = {"p1": _make_photo("p1", face_ids=["f1", "f2"])}
        result = audit_people_count(labels, photos)
        assert len(result["potentially_missed"]) == 1
        entry = result["potentially_missed"][0]
        assert entry["gemini_count"] == 5
        assert entry["detected_count"] == 2
        assert entry["diff"] == 3

    def test_no_flag_when_detected_greater(self):
        """No flag when detected faces >= Gemini count."""
        labels = {"p1": _make_label("p1", people_count=2)}
        photos = {"p1": _make_photo("p1", face_ids=["f1", "f2", "f3"])}
        result = audit_people_count(labels, photos)
        assert len(result["potentially_missed"]) == 0

    def test_skips_when_no_people_count(self):
        """Skips labels without people_count."""
        labels = {"p1": {"photo_id": "p1", "estimated_decade": 1940}}
        photos = {"p1": _make_photo("p1", face_ids=["f1"])}
        result = audit_people_count(labels, photos)
        assert result["checked"] == 0

    def test_skips_when_photo_not_found(self):
        """Skips labels whose photo_id is not in photos."""
        labels = {"p_missing": _make_label("p_missing", people_count=3)}
        photos = {"p1": _make_photo("p1", face_ids=["f1"])}
        result = audit_people_count(labels, photos)
        assert result["checked"] == 0

    def test_sorted_by_descending_diff(self):
        """Results are sorted by descending diff (most missed first)."""
        labels = {
            "p1": _make_label("p1", people_count=3),
            "p2": _make_label("p2", people_count=10),
            "p3": _make_label("p3", people_count=5),
        }
        photos = {
            "p1": _make_photo("p1", face_ids=["f1"]),        # diff=2
            "p2": _make_photo("p2", face_ids=["f1", "f2"]),  # diff=8
            "p3": _make_photo("p3", face_ids=["f1"]),         # diff=4
        }
        result = audit_people_count(labels, photos)
        assert len(result["potentially_missed"]) == 3
        diffs = [e["diff"] for e in result["potentially_missed"]]
        assert diffs == [8, 4, 2]

    def test_handles_empty_face_ids(self):
        """Handles photos with no face_ids at all."""
        labels = {"p1": _make_label("p1", people_count=2)}
        photos = {"p1": _make_photo("p1", face_ids=[])}
        result = audit_people_count(labels, photos)
        assert len(result["potentially_missed"]) == 1
        assert result["potentially_missed"][0]["diff"] == 2

    def test_multiple_photos(self):
        """Processes multiple photos correctly."""
        labels = {
            "p1": _make_label("p1", people_count=3),
            "p2": _make_label("p2", people_count=1),
            "p3": _make_label("p3", people_count=2),
        }
        photos = {
            "p1": _make_photo("p1", face_ids=["f1", "f2", "f3"]),  # OK
            "p2": _make_photo("p2", face_ids=["f1"]),               # OK
            "p3": _make_photo("p3", face_ids=["f1"]),               # diff=1
        }
        result = audit_people_count(labels, photos)
        assert result["checked"] == 3
        assert len(result["potentially_missed"]) == 1
        assert result["potentially_missed"][0]["photo_id"] == "p3"
