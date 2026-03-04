"""Tests for core.confidence — unified confidence scoring (AD-200).

Session 88: Updated to match sigmoid CDF priority chain.
Isotonic calibrator removed from continuous scoring path.
"""

import pytest
from unittest.mock import patch, MagicMock
import numpy as np

from core.confidence import (
    compute_face_confidence,
    compute_confidence_pct,
    confidence_tier_from_distance,
    confidence_tier_with_dots,
    distance_to_cosine_sim,
    _build_result,
    _compute_pct,
    TIER_STRONG,
    TIER_POSSIBLE,
    TIER_SIMILAR,
)


class TestDistanceToCosine:
    def test_zero_distance(self):
        assert distance_to_cosine_sim(0.0) == 1.0

    def test_sqrt2_distance(self):
        # d=sqrt(2) → cosine_sim = 0.0
        assert distance_to_cosine_sim(2**0.5) == pytest.approx(0.0, abs=1e-6)

    def test_large_distance_clamped(self):
        # d=2.0 → raw = 1 - 4/2 = -1 → clamped to 0
        assert distance_to_cosine_sim(2.0) == 0.0

    def test_typical_distance(self):
        # d=1.13 → cos = 1 - 1.2769/2 ≈ 0.3616
        result = distance_to_cosine_sim(1.13)
        assert 0.35 < result < 0.37


class TestBuildResult:
    def test_strong_match(self):
        r = _build_result(90)
        assert r["tier"] == "STRONG MATCH"
        assert r["label"] == "Very likely same person"
        assert r["short_label"] == "Very High"
        assert r["dots"] == 5
        assert "emerald" in r["tier_color"]

    def test_possible_match(self):
        r = _build_result(75)
        assert r["tier"] == "POSSIBLE MATCH"
        assert r["short_label"] == "High"
        assert r["dots"] == 4

    def test_similar(self):
        r = _build_result(55)
        assert r["tier"] == "SIMILAR"
        assert r["short_label"] == "Moderate"
        assert r["dots"] == 3

    def test_weak_low(self):
        r = _build_result(35)
        assert r["tier"] == "WEAK"
        assert r["short_label"] == "Low"
        assert r["dots"] == 2

    def test_weak_very_low(self):
        r = _build_result(20)
        assert r["tier"] == "WEAK"
        assert r["short_label"] == "Very Low"
        assert r["dots"] == 1

    def test_boundary_strong(self):
        r = _build_result(TIER_STRONG)
        assert r["tier"] == "STRONG MATCH"

    def test_boundary_possible(self):
        r = _build_result(TIER_POSSIBLE)
        assert r["tier"] == "POSSIBLE MATCH"

    def test_boundary_similar(self):
        r = _build_result(TIER_SIMILAR)
        assert r["tier"] == "SIMILAR"

    def test_below_similar(self):
        r = _build_result(TIER_SIMILAR - 1)
        assert r["tier"] == "WEAK"


class TestComputePctLinearFallback:
    """Test the linear fallback when no stats available."""

    @patch("core.confidence._get_same_person_stats", return_value=None)
    def test_zero_distance(self, _):
        # d=0 → (2-0)/2 * 100 = 100 → clamped to 99
        assert _compute_pct(0.0, None) == 99

    @patch("core.confidence._get_same_person_stats", return_value=None)
    def test_distance_1(self, _):
        # d=1.0 → (2-1)/2 * 100 = 50
        assert _compute_pct(1.0, None) == 50

    @patch("core.confidence._get_same_person_stats", return_value=None)
    def test_distance_1_13(self, _):
        # d=1.13 → (2-1.13)/2 * 100 = 43
        assert _compute_pct(1.13, None) == 43

    @patch("core.confidence._get_same_person_stats", return_value=None)
    def test_distance_2(self, _):
        # d=2.0 → (2-2)/2 * 100 = 0 → clamped to 1
        assert _compute_pct(2.0, None) == 1

    @patch("core.confidence._get_same_person_stats", return_value=None)
    def test_large_distance(self, _):
        assert _compute_pct(3.0, None) == 1


class TestComputePctSigmoidCDF:
    """Test sigmoid CDF when same_person_stats are provided."""

    @patch("core.confidence._get_same_person_stats", return_value=None)
    def test_with_stats_at_mean(self, _):
        stats = {"n": 100, "mean": 0.9, "std": 0.2}
        # At mean: z=0, sigmoid=0.5 → 50%
        result = _compute_pct(0.9, stats)
        assert result == 50

    @patch("core.confidence._get_same_person_stats", return_value=None)
    def test_with_stats_below_mean(self, _):
        stats = {"n": 100, "mean": 0.9, "std": 0.2}
        # Well below mean → high confidence
        result = _compute_pct(0.5, stats)
        assert result > 70

    @patch("core.confidence._get_same_person_stats", return_value=None)
    def test_with_stats_above_mean(self, _):
        stats = {"n": 100, "mean": 0.9, "std": 0.2}
        # Above mean → lower confidence
        result = _compute_pct(1.3, stats)
        assert result < 30

    @patch("core.confidence._get_same_person_stats", return_value=None)
    def test_stats_with_zero_n(self, _):
        # Falls through to linear
        stats = {"n": 0, "mean": 0.9, "std": 0.2}
        result = _compute_pct(1.0, stats)
        assert result == 50  # linear fallback

    @patch("core.confidence._get_same_person_stats", return_value=None)
    def test_stats_with_zero_std(self, _):
        # Falls through to linear
        stats = {"n": 100, "mean": 0.9, "std": 0}
        result = _compute_pct(1.0, stats)
        assert result == 50  # linear fallback


class TestComputePctAutoLoadStats:
    """Test that stats auto-load from kinship_thresholds.json."""

    def test_auto_loaded_stats_give_sigmoid_scores(self):
        """When no explicit stats, auto-loaded same_person_stats should be used."""
        stats = {"n": 959, "mean": 1.0148, "std": 0.187}
        with patch("core.confidence._get_same_person_stats", return_value=stats):
            result = _compute_pct(1.0, None)
        # At ~mean (1.0148), sigmoid → ~50%
        assert 45 <= result <= 55

    def test_auto_loaded_close_distance(self):
        stats = {"n": 959, "mean": 1.0148, "std": 0.187}
        with patch("core.confidence._get_same_person_stats", return_value=stats):
            result = _compute_pct(0.5, None)
        assert result > 80

    def test_auto_loaded_far_distance(self):
        stats = {"n": 959, "mean": 1.0148, "std": 0.187}
        with patch("core.confidence._get_same_person_stats", return_value=stats):
            result = _compute_pct(1.5, None)
        assert result < 20

    def test_explicit_stats_override_auto_loaded(self):
        """Caller-provided stats take precedence over auto-loaded."""
        auto_stats = {"n": 959, "mean": 1.0148, "std": 0.187}
        explicit_stats = {"n": 100, "mean": 0.5, "std": 0.1}
        with patch("core.confidence._get_same_person_stats", return_value=auto_stats):
            # With explicit stats centered at 0.5, distance 1.0 should be very low
            result = _compute_pct(1.0, explicit_stats)
        assert result < 10


class TestComputeFaceConfidence:
    """Integration test for the main entry point."""

    @patch("core.confidence._get_same_person_stats", return_value=None)
    def test_returns_all_fields(self, _):
        result = compute_face_confidence(1.0)
        assert "confidence_pct" in result
        assert "tier" in result
        assert "label" in result
        assert "short_label" in result
        assert "tier_color" in result
        assert "dots" in result

    @patch("core.confidence._get_same_person_stats", return_value=None)
    def test_distance_0_5_linear(self, _):
        result = compute_face_confidence(0.5)
        assert result["confidence_pct"] == 75
        assert result["tier"] == "POSSIBLE MATCH"

    @patch("core.confidence._get_same_person_stats", return_value=None)
    def test_distance_1_13_linear(self, _):
        result = compute_face_confidence(1.13)
        assert result["confidence_pct"] == 43
        assert result["tier"] == "WEAK"

    @patch("core.confidence._get_same_person_stats", return_value=None)
    def test_same_distance_same_result(self, _):
        """The core invariant: same distance ALWAYS produces same confidence."""
        r1 = compute_face_confidence(1.13)
        r2 = compute_face_confidence(1.13)
        assert r1 == r2


class TestConvenienceWrappers:
    @patch("core.confidence._get_same_person_stats", return_value=None)
    def test_confidence_tier_from_distance(self, _):
        label, color = confidence_tier_from_distance(0.5)
        assert label == "High"
        assert "blue" in color or "emerald" in color

    @patch("core.confidence._get_same_person_stats", return_value=None)
    def test_confidence_tier_with_dots(self, _):
        label, color, dots = confidence_tier_with_dots(0.5)
        assert isinstance(dots, int)
        assert 1 <= dots <= 5

    @patch("core.confidence._get_same_person_stats", return_value=None)
    def test_compute_confidence_pct(self, _):
        pct = compute_confidence_pct(1.0)
        assert pct == 50


class TestConsistencyInvariant:
    """The same distance MUST produce identical results everywhere."""

    @patch("core.confidence._get_same_person_stats", return_value=None)
    def test_all_apis_agree_for_distance_1_13(self, _):
        full = compute_face_confidence(1.13)
        pct = compute_confidence_pct(1.13)
        label, color = confidence_tier_from_distance(1.13)
        label_d, color_d, dots = confidence_tier_with_dots(1.13)

        assert full["confidence_pct"] == pct
        assert full["short_label"] == label
        assert full["tier_color"] == color
        assert full["short_label"] == label_d
        assert full["tier_color"] == color_d
        assert full["dots"] == dots

    @patch("core.confidence._get_same_person_stats", return_value=None)
    def test_all_apis_agree_for_distance_0_7(self, _):
        full = compute_face_confidence(0.7)
        pct = compute_confidence_pct(0.7)
        label, color = confidence_tier_from_distance(0.7)
        assert full["confidence_pct"] == pct
        assert full["short_label"] == label


class TestScoringConsistencySession88:
    """Session 88 regression: same distance must give same % everywhere.

    Before fix: neighbors.py batch NN gave 62% while confidence.py gave 43%
    for distance 1.13. Now both use the same sigmoid CDF path.
    """

    def test_monotonically_decreasing(self):
        """Closer distance → higher confidence, always."""
        stats = {"n": 959, "mean": 1.0148, "std": 0.187}
        with patch("core.confidence._get_same_person_stats", return_value=stats):
            distances = [0.3, 0.5, 0.8, 1.0, 1.13, 1.3, 1.5, 1.8]
            pcts = [compute_confidence_pct(d) for d in distances]
            for i in range(len(pcts) - 1):
                assert pcts[i] >= pcts[i + 1], (
                    f"Not monotonic: dist {distances[i]}→{pcts[i]}% "
                    f"but dist {distances[i+1]}→{pcts[i+1]}%"
                )

    def test_clamped_to_1_99(self):
        """All scores must be in [1, 99] range."""
        stats = {"n": 959, "mean": 1.0148, "std": 0.187}
        with patch("core.confidence._get_same_person_stats", return_value=stats):
            for d in [0.0, 0.001, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0]:
                pct = compute_confidence_pct(d)
                assert 1 <= pct <= 99, f"Out of range for dist {d}: {pct}"

    def test_no_calibrated_score_in_result(self):
        """Batch calibrator removed — no calibrated_score field should appear."""
        # This verifies the batch override in neighbors.py is gone
        result = compute_face_confidence(1.13)
        assert "calibrated_score" not in result


class TestMatchInfoBar:
    """Session 88: Tests for the shared match_info_bar component."""

    def test_match_info_bar_renders(self):
        from app.main import match_info_bar
        bar = match_info_bar(distance=0.8, confidence_gap=15.3, co_occurrence=2)
        html = repr(bar)
        assert "match-info-bar" in html
        assert "0.80" in html  # distance
        assert "+15.3% gap" in html
        assert "2 photos" in html

    def test_match_info_bar_no_gap(self):
        from app.main import match_info_bar
        bar = match_info_bar(distance=1.0, confidence_gap=0.0)
        html = repr(bar)
        assert "% gap" not in html

    def test_match_info_bar_hide_distance(self):
        from app.main import match_info_bar
        bar = match_info_bar(distance=1.0, show_distance=False)
        html = repr(bar)
        assert "Dist:" not in html
