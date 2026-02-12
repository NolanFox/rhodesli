"""Tests for face quality scoring system.

Tests the composite quality score (0-100), best-face selection,
and integration with identity card rendering.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestComputeFaceQualityScore:
    """Tests for compute_face_quality_score()."""

    def test_high_quality_face_scores_high(self):
        """A face with good detection, large area, high norm scores near 100."""
        from app.main import compute_face_quality_score

        mock_face = {
            "face_id": "test_face_1",
            "det_score": 0.99,
            "quality": 30.0,  # High embedding norm
            "bbox": [0, 0, 200, 200],  # Large face (200×200 = 40000 px²)
        }

        with patch("app.main._get_face_cache_entry", return_value=mock_face):
            score = compute_face_quality_score("test_face_1")

        # det: 0.99*30=29.7, area: min(40000/22500,1)*35=35, norm: (30-15)/15*35=35
        assert score >= 90, f"High quality face should score >=90, got {score}"

    def test_low_quality_face_scores_low(self):
        """A face with poor detection, tiny area, low norm scores low."""
        from app.main import compute_face_quality_score

        mock_face = {
            "face_id": "test_face_2",
            "det_score": 0.3,
            "quality": 16.0,  # Low norm
            "bbox": [0, 0, 30, 30],  # Tiny face (900 px²)
        }

        with patch("app.main._get_face_cache_entry", return_value=mock_face):
            score = compute_face_quality_score("test_face_2")

        # det: 0.3*30=9, area: 900/22500*35=1.4, norm: 1/15*35=2.3
        assert score < 20, f"Low quality face should score <20, got {score}"

    def test_missing_face_returns_zero(self):
        """Face not in cache returns 0."""
        from app.main import compute_face_quality_score

        with patch("app.main._get_face_cache_entry", return_value=None):
            score = compute_face_quality_score("nonexistent")

        assert score == 0.0

    def test_missing_quality_field_degrades_gracefully(self):
        """If quality (norm) is 0 or missing, other factors still contribute."""
        from app.main import compute_face_quality_score

        mock_face = {
            "face_id": "test_face_3",
            "det_score": 0.95,
            "quality": 0,  # Missing/zero
            "bbox": [0, 0, 150, 150],
        }

        with patch("app.main._get_face_cache_entry", return_value=mock_face):
            score = compute_face_quality_score("test_face_3")

        # Should still have det + area scores, just no norm
        assert score > 0, "Should still score >0 from other factors"
        assert score < 70, "Without norm, shouldn't max out"

    def test_score_range_is_0_to_100(self):
        """Score is always in [0, 100] range."""
        from app.main import compute_face_quality_score

        # Extreme high values
        mock_face = {
            "face_id": "extreme",
            "det_score": 1.0,
            "quality": 50.0,  # Very high norm
            "bbox": [0, 0, 500, 500],  # Very large
        }

        with patch("app.main._get_face_cache_entry", return_value=mock_face):
            score = compute_face_quality_score("extreme")

        assert 0 <= score <= 100, f"Score {score} out of range"

    def test_area_factor_caps_at_1(self):
        """Very large faces don't get bonus beyond cap."""
        from app.main import compute_face_quality_score

        mock_small = {
            "face_id": "small",
            "det_score": 0.9,
            "quality": 25.0,
            "bbox": [0, 0, 150, 150],  # 22500 px² (at cap)
        }
        mock_huge = {
            "face_id": "huge",
            "det_score": 0.9,
            "quality": 25.0,
            "bbox": [0, 0, 500, 500],  # 250000 px² (way above cap)
        }

        with patch("app.main._get_face_cache_entry", return_value=mock_small):
            small_score = compute_face_quality_score("small")
        with patch("app.main._get_face_cache_entry", return_value=mock_huge):
            huge_score = compute_face_quality_score("huge")

        assert small_score == huge_score, "Both should cap at same area score"


class TestGetBestFaceId:
    """Tests for get_best_face_id()."""

    def test_returns_none_for_empty_list(self):
        """Empty face list returns None."""
        from app.main import get_best_face_id
        assert get_best_face_id([]) is None

    def test_single_face_returns_it(self):
        """Single face is returned without computing quality."""
        from app.main import get_best_face_id
        assert get_best_face_id(["face_1"]) == "face_1"

    def test_picks_highest_quality(self):
        """Returns the face with the highest composite score."""
        from app.main import get_best_face_id

        scores = {"face_low": 20.0, "face_high": 80.0, "face_mid": 50.0}

        with patch("app.main.compute_face_quality_score", side_effect=lambda fid: scores.get(fid, 0)):
            best = get_best_face_id(["face_low", "face_high", "face_mid"])

        assert best == "face_high"

    def test_handles_dict_format(self):
        """Handles face entries that are dicts with 'face_id' key."""
        from app.main import get_best_face_id

        face_entries = [
            {"face_id": "dict_face_1"},
            {"face_id": "dict_face_2"},
        ]
        scores = {"dict_face_1": 30.0, "dict_face_2": 70.0}

        with patch("app.main.compute_face_quality_score", side_effect=lambda fid: scores.get(fid, 0)):
            best = get_best_face_id(face_entries)

        assert best == "dict_face_2"

    def test_falls_back_to_first_when_all_zero(self):
        """When all scores are 0 (no cache data), returns first face."""
        from app.main import get_best_face_id

        with patch("app.main.compute_face_quality_score", return_value=0.0):
            best = get_best_face_id(["face_a", "face_b", "face_c"])

        # When all are tied at 0, the first face with score > best_score(-1) wins
        assert best == "face_a"


class TestQualityIntegration:
    """Integration tests: quality scoring affects identity card rendering."""

    def test_identity_card_uses_best_face(self):
        """identity_card_mini shows best-quality face, not first in list."""
        from app.main import identity_card_mini

        identity = {
            "identity_id": "test-id",
            "name": "Test Person",
            "state": "CONFIRMED",
            "anchor_ids": ["low_face", "high_face"],
            "candidate_ids": [],
        }

        scores = {"low_face": 20.0, "high_face": 80.0}

        with patch("app.main.compute_face_quality_score", side_effect=lambda fid: scores.get(fid, 0)):
            with patch("app.main.resolve_face_image_url", side_effect=lambda fid, _: f"/crops/{fid}.jpg") as mock_resolve:
                card = identity_card_mini(identity, set())

        # The best face (high_face) should be used for the thumbnail
        mock_resolve.assert_called_with("high_face", set())

    def test_get_first_anchor_uses_quality(self):
        """get_first_anchor_face_id returns best quality anchor."""
        from app.main import get_first_anchor_face_id

        mock_registry = MagicMock()
        mock_registry.get_anchor_face_ids.return_value = ["low_face", "high_face"]

        scores = {"low_face": 20.0, "high_face": 80.0}

        with patch("app.main.compute_face_quality_score", side_effect=lambda fid: scores.get(fid, 0)):
            result = get_first_anchor_face_id("test-id", mock_registry)

        assert result == "high_face"
