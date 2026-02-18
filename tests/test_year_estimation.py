"""
Unit tests for core/year_estimation.py — year estimation engine.

Tests cover:
- estimate_photo_year() with faces that have known birth years
- Weighted aggregation (confirmed vs ML birth years)
- Fallback to scene estimate when no identified faces
- Returns None when no data available
- Single face → correct margin and confidence
- Multiple faces with spread → wider margin
- Face-to-age matching by left-to-right bbox ordering
- Scene evidence extraction from Gemini labels
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from core.year_estimation import estimate_photo_year


# ---------------------------------------------------------------------------
# Helpers — build mock data
# ---------------------------------------------------------------------------

def _make_photo(face_ids, faces=None, path="test_photo.jpg"):
    """Build a mock photo_cache entry."""
    photo = {
        "path": path,
        "face_ids": face_ids,
    }
    if faces is not None:
        photo["faces"] = faces
    return photo


def _make_label(subject_ages, estimated_decade=None, best_year_estimate=None,
                confidence="medium", metadata=None):
    """Build a mock date_labels entry."""
    label = {
        "subject_ages": subject_ages,
        "confidence": confidence,
    }
    if estimated_decade is not None:
        label["estimated_decade"] = estimated_decade
    if best_year_estimate is not None:
        label["best_year_estimate"] = best_year_estimate
    if metadata is not None:
        label["metadata"] = metadata
    return label


def _make_identity(identity_id, name, state="CONFIRMED", anchor_ids=None):
    """Build a mock identity dict."""
    return {
        "identity_id": identity_id,
        "name": name,
        "state": state,
        "anchor_ids": anchor_ids or [],
        "candidate_ids": [],
        "negative_ids": [],
        "metadata": {},
    }


def _birth_year_fn_factory(birth_years: dict):
    """Create a birth_year_fn that returns values from a dict.

    birth_years: {identity_id: (year, source, confidence)}
    """
    def _fn(identity_id, identity):
        if identity_id in birth_years:
            return birth_years[identity_id]
        return (None, None, None)
    return _fn


def _face_to_identity_fn_factory(face_map: dict):
    """Create a face_to_identity_fn that returns identities from a dict.

    face_map: {face_id: identity_dict_or_None}
    """
    def _fn(registry, face_id):
        return face_map.get(face_id)
    return _fn


# ---------------------------------------------------------------------------
# Test: estimate_photo_year with identified faces and known birth years
# ---------------------------------------------------------------------------

class TestEstimateWithKnownBirthYears:
    """Tests where faces have known (confirmed) birth years."""

    def test_single_face_confirmed_birth_year(self):
        """One face with confirmed birth_year → year = birth_year + apparent_age."""
        photo_id = "photo-1"
        face_id = "face-a"
        identity = _make_identity("id-a", "Leon Capeluto")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_id],
                faces=[{"face_id": face_id, "bbox": [100, 50, 200, 200]}],
            ),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=[{"age": 35}]),
        }
        birth_years = {"id-a": (1900, "confirmed", "high")}

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({face_id: identity}),
        )

        assert result is not None
        assert result["year"] == 1935  # 1900 + 35
        assert result["method"] == "facial_age_aggregation"
        assert result["face_count"] == 1

    def test_two_faces_confirmed_birth_years(self):
        """Two faces with confirmed birth years → weighted average year."""
        photo_id = "photo-2"
        face_a = "face-a"
        face_b = "face-b"
        identity_a = _make_identity("id-a", "Person A")
        identity_b = _make_identity("id-b", "Person B")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_a, face_b],
                faces=[
                    {"face_id": face_a, "bbox": [50, 50, 150, 200]},
                    {"face_id": face_b, "bbox": [200, 50, 300, 200]},
                ],
            ),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=[{"age": 30}, {"age": 25}]),
        }
        # Both confirmed: person A born 1910 (age 30 → 1940), person B born 1915 (age 25 → 1940)
        birth_years = {
            "id-a": (1910, "confirmed", "high"),
            "id-b": (1915, "confirmed", "high"),
        }

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({
                face_a: identity_a,
                face_b: identity_b,
            }),
        )

        assert result is not None
        # Both faces estimate 1940, so aggregated should be 1940
        assert result["year"] == 1940
        assert result["face_count"] == 2
        assert result["confidence"] == "high"  # 2 confirmed faces


# ---------------------------------------------------------------------------
# Test: weighted aggregation — confirmed vs ML birth years
# ---------------------------------------------------------------------------

class TestWeightedAggregation:
    """Tests that confirmed birth years are weighted higher than ML-inferred."""

    def test_confirmed_weighted_double(self):
        """Confirmed sources get weight 2.0, ML gets 1.0."""
        photo_id = "photo-w"
        face_a = "face-a"
        face_b = "face-b"
        identity_a = _make_identity("id-a", "Confirmed Person")
        identity_b = _make_identity("id-b", "ML Person")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_a, face_b],
                faces=[
                    {"face_id": face_a, "bbox": [50, 50, 150, 200]},
                    {"face_id": face_b, "bbox": [200, 50, 300, 200]},
                ],
            ),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=[{"age": 40}, {"age": 30}]),
        }
        # Confirmed person born 1900 (age 40 → 1940) with weight 2.0
        # ML person born 1920 (age 30 → 1950) with weight 1.0
        # Weighted avg = (1940*2 + 1950*1) / 3 = 5830 / 3 ≈ 1943
        birth_years = {
            "id-a": (1900, "confirmed", "high"),
            "id-b": (1920, "ml_inferred", "medium"),
        }

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({
                face_a: identity_a,
                face_b: identity_b,
            }),
        )

        assert result is not None
        # Weighted: (1940*2 + 1950*1) / 3 = 1943.33 → rounds to 1943
        assert result["year"] == 1943
        assert result["confidence"] == "medium"  # 1 confirmed, total 2

    def test_all_ml_inferred_weight_one(self):
        """When all birth years are ML-inferred, equal weighting (1.0 each)."""
        photo_id = "photo-ml"
        face_a = "face-a"
        face_b = "face-b"
        identity_a = _make_identity("id-a", "ML Person A")
        identity_b = _make_identity("id-b", "ML Person B")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_a, face_b],
                faces=[
                    {"face_id": face_a, "bbox": [50, 50, 150, 200]},
                    {"face_id": face_b, "bbox": [200, 50, 300, 200]},
                ],
            ),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=[{"age": 20}, {"age": 30}]),
        }
        # Both ML: A born 1920 (age 20 → 1940), B born 1910 (age 30 → 1940)
        birth_years = {
            "id-a": (1920, "ml_inferred", "medium"),
            "id-b": (1910, "ml_inferred", "low"),
        }

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({
                face_a: identity_a,
                face_b: identity_b,
            }),
        )

        assert result is not None
        # Equal weight: (1940 + 1940) / 2 = 1940
        assert result["year"] == 1940
        # 0 confirmed, 2 ML faces → medium
        assert result["confidence"] == "medium"


# ---------------------------------------------------------------------------
# Test: fallback to scene estimate when no identified faces
# ---------------------------------------------------------------------------

class TestSceneFallback:
    """Tests scene analysis fallback when no faces have birth years."""

    def test_no_identified_faces_uses_scene_year(self):
        """When no face has a birth year, falls back to scene best_year_estimate."""
        photo_id = "photo-scene"

        photo_cache = {
            photo_id: _make_photo(face_ids=[], faces=[]),
        }
        date_labels = {
            photo_id: _make_label(
                subject_ages=[],
                estimated_decade=1930,
                best_year_estimate=1935,
                metadata={"photo_type": "group_portrait", "setting": "outdoor"},
            ),
        }

        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
        )

        assert result is not None
        assert result["year"] == 1935
        assert result["method"] == "scene_analysis"
        assert result["confidence"] == "low"
        assert result["margin"] == 10

    def test_scene_fallback_with_decade_only(self):
        """Scene with estimated_decade but no best_year_estimate → no result
        (best_year_estimate is required for fallback)."""
        photo_id = "photo-decade"

        photo_cache = {
            photo_id: _make_photo(face_ids=[], faces=[]),
        }
        date_labels = {
            photo_id: _make_label(
                subject_ages=[],
                estimated_decade=1940,
                best_year_estimate=None,
            ),
        }

        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
        )

        # No best_year_estimate means aggregated_year stays None → returns None
        assert result is None

    def test_faces_without_identities_still_try_scene(self):
        """Faces exist but none are identified → still falls back to scene."""
        photo_id = "photo-unid"

        photo_cache = {
            photo_id: _make_photo(
                face_ids=["face-x"],
                faces=[{"face_id": "face-x", "bbox": [50, 50, 150, 200]}],
            ),
        }
        date_labels = {
            photo_id: _make_label(
                subject_ages=[{"age": 25}],
                best_year_estimate=1945,
                metadata={"photo_type": "portrait"},
            ),
        }

        # face_to_identity returns None for all faces (nobody identified)
        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory({}),
            face_to_identity_fn=_face_to_identity_fn_factory({"face-x": None}),
        )

        assert result is not None
        assert result["year"] == 1945
        assert result["method"] == "scene_analysis"


# ---------------------------------------------------------------------------
# Test: returns None when insufficient data
# ---------------------------------------------------------------------------

class TestReturnsNone:
    """Tests that estimate_photo_year returns None when data is insufficient."""

    def test_no_date_labels(self):
        """Returns None when date_labels is None."""
        result = estimate_photo_year(
            photo_id="photo-1",
            date_labels=None,
            photo_cache={"photo-1": _make_photo(face_ids=[])},
        )
        assert result is None

    def test_no_photo_cache(self):
        """Returns None when photo_cache is None."""
        result = estimate_photo_year(
            photo_id="photo-1",
            date_labels={"photo-1": _make_label(subject_ages=[])},
            photo_cache=None,
        )
        assert result is None

    def test_empty_date_labels(self):
        """Returns None when date_labels is empty dict."""
        result = estimate_photo_year(
            photo_id="photo-1",
            date_labels={},
            photo_cache={"photo-1": _make_photo(face_ids=[])},
        )
        assert result is None

    def test_photo_not_in_cache(self):
        """Returns None when photo_id not found in photo_cache."""
        result = estimate_photo_year(
            photo_id="nonexistent",
            date_labels={"nonexistent": _make_label(subject_ages=[])},
            photo_cache={},
        )
        assert result is None

    def test_no_faces_no_scene_estimate(self):
        """Returns None when no faces and no scene estimate available."""
        photo_id = "photo-empty"

        photo_cache = {
            photo_id: _make_photo(face_ids=[], faces=[]),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=[]),
        }

        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
        )

        assert result is None

    def test_both_none(self):
        """Returns None when both date_labels and photo_cache are None."""
        result = estimate_photo_year(
            photo_id="anything",
            date_labels=None,
            photo_cache=None,
        )
        assert result is None


# ---------------------------------------------------------------------------
# Test: single face margin and confidence
# ---------------------------------------------------------------------------

class TestSingleFaceMarginConfidence:
    """Tests margin and confidence calculations for a single face."""

    def test_single_face_margin_is_at_least_3(self):
        """Single face with no spread → margin = max(3, min(15, 10/2 + 3)) = 8."""
        photo_id = "photo-single"
        face_id = "face-a"
        identity = _make_identity("id-a", "Solo Person")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_id],
                faces=[{"face_id": face_id, "bbox": [100, 50, 200, 200]}],
            ),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=[{"age": 50}]),
        }
        birth_years = {"id-a": (1890, "confirmed", "high")}

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({face_id: identity}),
        )

        assert result is not None
        # Single face: spread = 10 (default for len == 1)
        # margin = max(3, min(15, round(10/2) + 3)) = max(3, min(15, 8)) = 8
        assert result["margin"] == 8
        assert result["margin"] >= 3

    def test_single_confirmed_face_confidence_medium(self):
        """Single confirmed face gives medium confidence (1 confirmed, not 2)."""
        photo_id = "photo-s"
        face_id = "face-a"
        identity = _make_identity("id-a", "Person X")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_id],
                faces=[{"face_id": face_id, "bbox": [100, 50, 200, 200]}],
            ),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=[{"age": 30}]),
        }
        birth_years = {"id-a": (1900, "confirmed", "high")}

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({face_id: identity}),
        )

        assert result is not None
        assert result["confidence"] == "medium"  # 1 confirmed = medium

    def test_single_ml_face_confidence_low(self):
        """Single ML-inferred face gives low confidence."""
        photo_id = "photo-ml-single"
        face_id = "face-a"
        identity = _make_identity("id-a", "ML Person")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_id],
                faces=[{"face_id": face_id, "bbox": [100, 50, 200, 200]}],
            ),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=[{"age": 40}]),
        }
        birth_years = {"id-a": (1905, "ml_inferred", "low")}

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({face_id: identity}),
        )

        assert result is not None
        assert result["confidence"] == "low"  # 1 ML face = low


# ---------------------------------------------------------------------------
# Test: multiple faces with spread → wider margin
# ---------------------------------------------------------------------------

class TestMultipleFaceSpread:
    """Tests that disagreeing faces produce wider margins."""

    def test_wide_spread_increases_margin(self):
        """Faces that disagree (e.g., 1930 vs 1950) produce wider margin."""
        photo_id = "photo-spread"
        face_a = "face-a"
        face_b = "face-b"
        identity_a = _make_identity("id-a", "Person A")
        identity_b = _make_identity("id-b", "Person B")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_a, face_b],
                faces=[
                    {"face_id": face_a, "bbox": [50, 50, 150, 200]},
                    {"face_id": face_b, "bbox": [200, 50, 300, 200]},
                ],
            ),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=[{"age": 30}, {"age": 50}]),
        }
        # A born 1900 (age 30 → 1930), B born 1900 (age 50 → 1950)
        # Spread = 20
        birth_years = {
            "id-a": (1900, "confirmed", "high"),
            "id-b": (1900, "confirmed", "high"),
        }

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({
                face_a: identity_a,
                face_b: identity_b,
            }),
        )

        assert result is not None
        # spread = 20, margin = max(3, min(15, round(20/2) + 3)) = max(3, min(15, 13)) = 13
        assert result["margin"] == 13
        assert result["margin"] > 8  # wider than single-face default

    def test_close_agreement_keeps_margin_small(self):
        """Faces that agree closely produce smaller margin."""
        photo_id = "photo-agree"
        face_a = "face-a"
        face_b = "face-b"
        identity_a = _make_identity("id-a", "Person A")
        identity_b = _make_identity("id-b", "Person B")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_a, face_b],
                faces=[
                    {"face_id": face_a, "bbox": [50, 50, 150, 200]},
                    {"face_id": face_b, "bbox": [200, 50, 300, 200]},
                ],
            ),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=[{"age": 30}, {"age": 25}]),
        }
        # A born 1910 (age 30 → 1940), B born 1915 (age 25 → 1940)
        # Spread = 0
        birth_years = {
            "id-a": (1910, "confirmed", "high"),
            "id-b": (1915, "confirmed", "high"),
        }

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({
                face_a: identity_a,
                face_b: identity_b,
            }),
        )

        assert result is not None
        # spread = 0, margin = max(3, min(15, round(0/2) + 3)) = max(3, 3) = 3
        assert result["margin"] == 3

    def test_margin_caps_at_15(self):
        """Margin never exceeds 15 regardless of spread."""
        photo_id = "photo-cap"
        face_a = "face-a"
        face_b = "face-b"
        identity_a = _make_identity("id-a", "Person A")
        identity_b = _make_identity("id-b", "Person B")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_a, face_b],
                faces=[
                    {"face_id": face_a, "bbox": [50, 50, 150, 200]},
                    {"face_id": face_b, "bbox": [200, 50, 300, 200]},
                ],
            ),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=[{"age": 10}, {"age": 70}]),
        }
        # A born 1900 (age 10 → 1910), B born 1900 (age 70 → 1970)
        # Spread = 60
        birth_years = {
            "id-a": (1900, "confirmed", "high"),
            "id-b": (1900, "confirmed", "high"),
        }

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({
                face_a: identity_a,
                face_b: identity_b,
            }),
        )

        assert result is not None
        # spread = 60, margin = max(3, min(15, round(60/2) + 3)) = max(3, min(15, 33)) = 15
        assert result["margin"] == 15


# ---------------------------------------------------------------------------
# Test: face-to-age matching by left-to-right bbox ordering
# ---------------------------------------------------------------------------

class TestLeftToRightBboxOrdering:
    """Tests that faces are matched to ages by left-to-right x-coordinate."""

    def test_faces_sorted_by_x_coordinate(self):
        """Face with lower x1 bbox gets the first age entry."""
        photo_id = "photo-lr"
        # face-right has x1=300, face-left has x1=50
        face_left = "face-left"
        face_right = "face-right"
        identity_left = _make_identity("id-left", "Left Person")
        identity_right = _make_identity("id-right", "Right Person")

        photo_cache = {
            photo_id: _make_photo(
                # Intentionally list right face first — sorting should fix order
                face_ids=[face_right, face_left],
                faces=[
                    {"face_id": face_right, "bbox": [300, 50, 400, 200]},
                    {"face_id": face_left, "bbox": [50, 50, 150, 200]},
                ],
            ),
        }
        date_labels = {
            photo_id: _make_label(
                # First age entry should go to leftmost face
                subject_ages=[{"age": 20}, {"age": 50}],
            ),
        }
        # Left person born 1920 (age 20 → 1940)
        # Right person born 1890 (age 50 → 1940)
        birth_years = {
            "id-left": (1920, "confirmed", "high"),
            "id-right": (1890, "confirmed", "high"),
        }

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({
                face_left: identity_left,
                face_right: identity_right,
            }),
        )

        assert result is not None
        assert result["face_count"] == 2

        # Verify that face-left got age 20 and face-right got age 50
        evidence_by_id = {e["face_id"]: e for e in result["face_evidence"]}
        assert evidence_by_id[face_left]["apparent_age"] == 20
        assert evidence_by_id[face_right]["apparent_age"] == 50

    def test_faces_without_bbox_get_x0(self):
        """Faces without bbox data default to x=0 (sorted first)."""
        photo_id = "photo-nobbox"
        face_no_bbox = "face-no-bbox"
        face_with_bbox = "face-with-bbox"
        identity = _make_identity("id-a", "Person A")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_with_bbox, face_no_bbox],
                faces=[
                    {"face_id": face_with_bbox, "bbox": [200, 50, 300, 200]},
                    # face_no_bbox not in faces list — gets default x=0
                ],
            ),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=[{"age": 30}, {"age": 40}]),
        }
        birth_years = {"id-a": (1900, "confirmed", "high")}

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({
                face_no_bbox: identity,
                face_with_bbox: None,
            }),
        )

        assert result is not None
        # face_no_bbox sorted to x=0 (first position) → gets age 30
        evidence_by_id = {e["face_id"]: e for e in result["face_evidence"]}
        assert evidence_by_id[face_no_bbox]["apparent_age"] == 30

    def test_more_faces_than_ages(self):
        """When there are more faces than age entries, extras are skipped."""
        photo_id = "photo-extra"
        face_a = "face-a"
        face_b = "face-b"
        face_c = "face-c"
        identity_a = _make_identity("id-a", "Person A")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_a, face_b, face_c],
                faces=[
                    {"face_id": face_a, "bbox": [50, 50, 150, 200]},
                    {"face_id": face_b, "bbox": [200, 50, 300, 200]},
                    {"face_id": face_c, "bbox": [350, 50, 450, 200]},
                ],
            ),
        }
        date_labels = {
            # Only 2 ages for 3 faces
            photo_id: _make_label(subject_ages=[{"age": 25}, {"age": 35}]),
        }
        birth_years = {"id-a": (1910, "confirmed", "high")}

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({
                face_a: identity_a,
                face_b: None,
                face_c: None,
            }),
        )

        assert result is not None
        # face_a got age 25 (first position), face_c gets nothing (only 2 ages)
        assert len(result["face_evidence"]) == 2  # only 2 matched


# ---------------------------------------------------------------------------
# Test: scene evidence extraction from Gemini labels
# ---------------------------------------------------------------------------

class TestSceneEvidence:
    """Tests for scene evidence extraction from Gemini label metadata."""

    def test_scene_clues_extracted(self):
        """Scene evidence includes photo_type, setting, condition, clothing_notes."""
        photo_id = "photo-clues"

        photo_cache = {
            photo_id: _make_photo(face_ids=[], faces=[]),
        }
        date_labels = {
            photo_id: _make_label(
                subject_ages=[],
                estimated_decade=1940,
                best_year_estimate=1945,
                metadata={
                    "photo_type": "group_portrait",
                    "setting": "outdoor_garden",
                    "condition": "fair",
                    "clothing_notes": "Women in 1940s-style dresses with padded shoulders",
                },
            ),
        }

        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
        )

        assert result is not None
        scene = result["scene_evidence"]
        assert scene is not None
        assert "Group Portrait" in scene["clues"]
        assert "Outdoor Garden" in scene["clues"]
        assert "Condition: fair" in scene["clues"]
        # clothing_notes truncated to 80 chars
        assert any("1940s-style" in c for c in scene["clues"])
        assert scene["scene_estimate"] == "1940s"
        assert scene["scene_year"] == 1945

    def test_scene_decade_formatted_as_string(self):
        """Scene estimate shows decade as '1930s' string."""
        photo_id = "photo-decade"

        photo_cache = {
            photo_id: _make_photo(face_ids=[], faces=[]),
        }
        date_labels = {
            photo_id: _make_label(
                subject_ages=[],
                estimated_decade=1930,
                best_year_estimate=1935,
            ),
        }

        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
        )

        assert result is not None
        assert result["scene_evidence"]["scene_estimate"] == "1930s"

    def test_no_metadata_no_clues(self):
        """Label without metadata produces empty clues list."""
        photo_id = "photo-noclues"

        photo_cache = {
            photo_id: _make_photo(face_ids=[], faces=[]),
        }
        date_labels = {
            photo_id: _make_label(
                subject_ages=[],
                best_year_estimate=1950,
            ),
        }

        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
        )

        assert result is not None
        scene = result["scene_evidence"]
        assert scene is not None
        assert scene["clues"] == []

    def test_scene_evidence_included_alongside_face_evidence(self):
        """Scene evidence is present even when face-based estimate dominates."""
        photo_id = "photo-both"
        face_id = "face-a"
        identity = _make_identity("id-a", "Person A")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_id],
                faces=[{"face_id": face_id, "bbox": [100, 50, 200, 200]}],
            ),
        }
        date_labels = {
            photo_id: _make_label(
                subject_ages=[{"age": 30}],
                estimated_decade=1930,
                best_year_estimate=1935,
                metadata={"photo_type": "portrait"},
            ),
        }
        birth_years = {"id-a": (1910, "confirmed", "high")}

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({face_id: identity}),
        )

        assert result is not None
        # Face-based estimate wins (method = facial_age_aggregation)
        assert result["method"] == "facial_age_aggregation"
        assert result["year"] == 1940  # 1910 + 30
        # But scene evidence is still included
        assert result["scene_evidence"] is not None
        assert result["scene_evidence"]["scene_estimate"] == "1930s"


# ---------------------------------------------------------------------------
# Test: subject_ages format variations
# ---------------------------------------------------------------------------

class TestSubjectAgeFormats:
    """Tests handling of various subject_ages entry formats."""

    def test_integer_age_entries(self):
        """subject_ages as bare integers (not dicts) work."""
        photo_id = "photo-int"
        face_id = "face-a"
        identity = _make_identity("id-a", "Person A")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_id],
                faces=[{"face_id": face_id, "bbox": [100, 50, 200, 200]}],
            ),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=[25]),
        }
        birth_years = {"id-a": (1910, "confirmed", "high")}

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({face_id: identity}),
        )

        assert result is not None
        assert result["year"] == 1935

    def test_string_age_entries(self):
        """subject_ages as strings (e.g., "30") are parsed."""
        photo_id = "photo-str"
        face_id = "face-a"
        identity = _make_identity("id-a", "Person A")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_id],
                faces=[{"face_id": face_id, "bbox": [100, 50, 200, 200]}],
            ),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=["30"]),
        }
        birth_years = {"id-a": (1910, "confirmed", "high")}

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({face_id: identity}),
        )

        assert result is not None
        assert result["year"] == 1940

    def test_invalid_string_age_skipped(self):
        """Non-numeric string ages are safely skipped."""
        photo_id = "photo-bad"
        face_id = "face-a"
        identity = _make_identity("id-a", "Person A")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_id],
                faces=[{"face_id": face_id, "bbox": [100, 50, 200, 200]}],
            ),
        }
        date_labels = {
            photo_id: _make_label(
                subject_ages=["unknown"],
                best_year_estimate=1940,
            ),
        }
        birth_years = {"id-a": (1910, "confirmed", "high")}

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({face_id: identity}),
        )

        # Face has no valid age → falls back to scene
        assert result is not None
        assert result["year"] == 1940
        assert result["method"] == "scene_analysis"

    def test_dict_with_estimated_age_key(self):
        """subject_ages dict with 'estimated_age' key (alternative to 'age')."""
        photo_id = "photo-est"
        face_id = "face-a"
        identity = _make_identity("id-a", "Person A")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_id],
                faces=[{"face_id": face_id, "bbox": [100, 50, 200, 200]}],
            ),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=[{"estimated_age": 45}]),
        }
        birth_years = {"id-a": (1900, "confirmed", "high")}

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({face_id: identity}),
        )

        assert result is not None
        assert result["year"] == 1945  # 1900 + 45


# ---------------------------------------------------------------------------
# Test: reasoning text and face_evidence structure
# ---------------------------------------------------------------------------

class TestReasoningAndEvidence:
    """Tests for the reasoning text and face_evidence structure."""

    def test_reasoning_includes_person_name(self):
        """Reasoning text mentions the person name and birth year."""
        photo_id = "photo-r"
        face_id = "face-a"
        identity = _make_identity("id-a", "Leon Capeluto")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_id],
                faces=[{"face_id": face_id, "bbox": [100, 50, 200, 200]}],
            ),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=[{"age": 35}]),
        }
        birth_years = {"id-a": (1905, "confirmed", "high")}

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({face_id: identity}),
        )

        assert result is not None
        assert "Leon Capeluto" in result["reasoning"]
        assert "1905" in result["reasoning"]
        assert "35" in result["reasoning"]

    def test_face_evidence_structure(self):
        """Each face evidence entry has the expected keys."""
        photo_id = "photo-ev"
        face_id = "face-a"
        identity = _make_identity("id-a", "Test Person")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_id],
                faces=[{"face_id": face_id, "bbox": [100, 50, 200, 200]}],
            ),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=[{"age": 30}]),
        }
        birth_years = {"id-a": (1910, "confirmed", "high")}

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({face_id: identity}),
        )

        assert result is not None
        assert len(result["face_evidence"]) == 1
        ev = result["face_evidence"][0]
        assert ev["face_id"] == face_id
        assert ev["identity_id"] == "id-a"
        assert ev["person_name"] == "Test Person"
        assert ev["apparent_age"] == 30
        assert ev["birth_year"] == 1910
        assert ev["birth_year_source"] == "confirmed"
        assert ev["estimated_year"] == 1940
        assert ev["has_identity"] is True

    def test_unidentified_face_evidence(self):
        """Faces without identities have has_identity=False and no identity fields."""
        photo_id = "photo-unid2"
        face_id = "face-a"

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_id],
                faces=[{"face_id": face_id, "bbox": [100, 50, 200, 200]}],
            ),
        }
        date_labels = {
            photo_id: _make_label(
                subject_ages=[{"age": 25}],
                best_year_estimate=1950,
            ),
        }

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory({}),
            face_to_identity_fn=_face_to_identity_fn_factory({face_id: None}),
        )

        assert result is not None
        assert len(result["face_evidence"]) == 1
        ev = result["face_evidence"][0]
        assert ev["has_identity"] is False
        assert ev["apparent_age"] == 25

    def test_unidentified_person_name_cleared(self):
        """Identities with 'Unidentified Person' name have person_name set to None."""
        photo_id = "photo-unid-name"
        face_id = "face-a"
        identity = _make_identity("id-a", "Unidentified Person 042")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_id],
                faces=[{"face_id": face_id, "bbox": [100, 50, 200, 200]}],
            ),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=[{"age": 30}]),
        }
        birth_years = {"id-a": (1910, "ml_inferred", "low")}

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({face_id: identity}),
        )

        assert result is not None
        ev = result["face_evidence"][0]
        assert ev["person_name"] is None  # Cleared because starts with "Unidentified"


# ---------------------------------------------------------------------------
# Test: confidence levels
# ---------------------------------------------------------------------------

class TestConfidenceLevels:
    """Tests for confidence level assignment."""

    def test_two_confirmed_gives_high(self):
        """Two or more confirmed birth year faces → high confidence."""
        photo_id = "photo-hi"
        face_a = "face-a"
        face_b = "face-b"
        identity_a = _make_identity("id-a", "Person A")
        identity_b = _make_identity("id-b", "Person B")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_a, face_b],
                faces=[
                    {"face_id": face_a, "bbox": [50, 50, 150, 200]},
                    {"face_id": face_b, "bbox": [200, 50, 300, 200]},
                ],
            ),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=[{"age": 30}, {"age": 25}]),
        }
        birth_years = {
            "id-a": (1910, "confirmed", "high"),
            "id-b": (1915, "confirmed", "high"),
        }

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({
                face_a: identity_a,
                face_b: identity_b,
            }),
        )

        assert result["confidence"] == "high"

    def test_one_confirmed_one_ml_gives_medium(self):
        """One confirmed + one ML → medium confidence."""
        photo_id = "photo-med"
        face_a = "face-a"
        face_b = "face-b"
        identity_a = _make_identity("id-a", "Person A")
        identity_b = _make_identity("id-b", "Person B")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_a, face_b],
                faces=[
                    {"face_id": face_a, "bbox": [50, 50, 150, 200]},
                    {"face_id": face_b, "bbox": [200, 50, 300, 200]},
                ],
            ),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=[{"age": 30}, {"age": 25}]),
        }
        birth_years = {
            "id-a": (1910, "confirmed", "high"),
            "id-b": (1915, "ml_inferred", "medium"),
        }

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({
                face_a: identity_a,
                face_b: identity_b,
            }),
        )

        assert result["confidence"] == "medium"

    def test_two_ml_faces_gives_medium(self):
        """Two ML-inferred faces (no confirmed) → medium confidence."""
        photo_id = "photo-2ml"
        face_a = "face-a"
        face_b = "face-b"
        identity_a = _make_identity("id-a", "Person A")
        identity_b = _make_identity("id-b", "Person B")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_a, face_b],
                faces=[
                    {"face_id": face_a, "bbox": [50, 50, 150, 200]},
                    {"face_id": face_b, "bbox": [200, 50, 300, 200]},
                ],
            ),
        }
        date_labels = {
            photo_id: _make_label(subject_ages=[{"age": 30}, {"age": 25}]),
        }
        birth_years = {
            "id-a": (1910, "ml_inferred", "low"),
            "id-b": (1915, "ml_inferred", "low"),
        }

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({
                face_a: identity_a,
                face_b: identity_b,
            }),
        )

        assert result["confidence"] == "medium"

    def test_scene_only_gives_low(self):
        """Scene-only estimate is always low confidence."""
        photo_id = "photo-scene-low"

        photo_cache = {
            photo_id: _make_photo(face_ids=[], faces=[]),
        }
        date_labels = {
            photo_id: _make_label(
                subject_ages=[],
                best_year_estimate=1945,
            ),
        }

        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
        )

        assert result is not None
        assert result["confidence"] == "low"


# ---------------------------------------------------------------------------
# Test: subject_ages in metadata sub-key
# ---------------------------------------------------------------------------

class TestSubjectAgesInMetadata:
    """Tests that subject_ages can be found in label.metadata.subject_ages."""

    def test_subject_ages_in_metadata_key(self):
        """When subject_ages is in metadata dict, still extracted."""
        photo_id = "photo-meta-ages"
        face_id = "face-a"
        identity = _make_identity("id-a", "Person A")

        photo_cache = {
            photo_id: _make_photo(
                face_ids=[face_id],
                faces=[{"face_id": face_id, "bbox": [100, 50, 200, 200]}],
            ),
        }
        # subject_ages at top level is None, but exists in metadata
        date_labels = {
            photo_id: {
                "subject_ages": None,
                "metadata": {"subject_ages": [{"age": 35}]},
                "confidence": "medium",
            },
        }
        birth_years = {"id-a": (1900, "confirmed", "high")}

        registry = MagicMock()
        result = estimate_photo_year(
            photo_id=photo_id,
            date_labels=date_labels,
            photo_cache=photo_cache,
            identity_registry=registry,
            birth_year_fn=_birth_year_fn_factory(birth_years),
            face_to_identity_fn=_face_to_identity_fn_factory({face_id: identity}),
        )

        assert result is not None
        assert result["year"] == 1935
