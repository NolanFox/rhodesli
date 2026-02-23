"""Tests for SimilarityCalibrator — raw cosine → P(match) calibration.

Tests use synthetic calibration pairs so no Supabase connection is needed.
"""

import numpy as np
import pytest

from rhodesli_ml.similarity_calibration import SimilarityCalibrator


def _make_synthetic_pairs(n_match=30, n_nonmatch=30, seed=42):
    """Generate synthetic calibration pairs.

    Matches get high similarity scores (0.5-0.9),
    non-matches get low scores (0.0-0.4). Realistic overlap zone included.
    """
    rng = np.random.RandomState(seed)
    pairs = []
    for _ in range(n_match):
        pairs.append({
            "similarity_score": float(rng.uniform(0.5, 0.9)),
            "is_match": True,
            "weight": 1.0,
        })
    for _ in range(n_nonmatch):
        pairs.append({
            "similarity_score": float(rng.uniform(0.0, 0.4)),
            "is_match": False,
            "weight": 1.0,
        })
    return pairs


class TestFit:
    """Tests for fit() — isotonic regression training."""

    def test_fit_produces_valid_model(self, tmp_path):
        """fit() with synthetic pairs returns a CalibrationModel with expected fields."""
        cal = SimilarityCalibrator(model_dir=tmp_path / "cal")
        pairs = _make_synthetic_pairs()
        model = cal.fit(pairs)

        assert model.version == 1
        assert model.pair_count == 60
        assert model.match_count == 30
        assert model.nonmatch_count == 30
        assert 0.0 <= model.auc <= 1.0
        assert len(model.iso_X) > 0
        assert len(model.iso_y) > 0
        assert model.created_at  # non-empty timestamp

    def test_fit_too_few_pairs_raises(self, tmp_path):
        """fit() with fewer than 10 pairs raises ValueError."""
        cal = SimilarityCalibrator(model_dir=tmp_path / "cal")
        pairs = _make_synthetic_pairs(n_match=3, n_nonmatch=3)
        assert len(pairs) == 6

        with pytest.raises(ValueError, match="at least 10"):
            cal.fit(pairs)

    def test_fit_increments_version(self, tmp_path):
        """Successive fit() calls increment the model version."""
        cal = SimilarityCalibrator(model_dir=tmp_path / "cal")
        pairs = _make_synthetic_pairs()
        m1 = cal.fit(pairs)
        m2 = cal.fit(pairs)
        assert m2.version == m1.version + 1


class TestPredict:
    """Tests for predict() and predict_batch()."""

    def test_predict_returns_between_0_and_1(self, tmp_path):
        """predict() output is always in [0, 1]."""
        cal = SimilarityCalibrator(model_dir=tmp_path / "cal")
        cal.fit(_make_synthetic_pairs())

        test_scores = [-0.5, 0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0, 1.5]
        for score in test_scores:
            prob = cal.predict(score)
            assert 0.0 <= prob <= 1.0, f"predict({score}) = {prob}, out of range"

    def test_predict_is_monotonic(self, tmp_path):
        """Higher raw similarity should yield higher or equal P(match)."""
        cal = SimilarityCalibrator(model_dir=tmp_path / "cal")
        cal.fit(_make_synthetic_pairs())

        scores = np.linspace(0.0, 1.0, 50)
        probs = [cal.predict(float(s)) for s in scores]

        for i in range(1, len(probs)):
            assert probs[i] >= probs[i - 1] - 1e-9, (
                f"Monotonicity violated: predict({scores[i-1]:.3f})={probs[i-1]:.4f} > "
                f"predict({scores[i]:.3f})={probs[i]:.4f}"
            )

    def test_predict_no_model_returns_clamped(self, tmp_path):
        """predict() with no fitted model returns raw score clamped to [0, 1]."""
        cal = SimilarityCalibrator(model_dir=tmp_path / "empty")

        assert cal.predict(0.75) == 0.75
        assert cal.predict(-0.3) == 0.0
        assert cal.predict(1.5) == 1.0

    def test_predict_batch_matches_individual(self, tmp_path):
        """predict_batch() results match individual predict() calls."""
        cal = SimilarityCalibrator(model_dir=tmp_path / "cal")
        cal.fit(_make_synthetic_pairs())

        scores = [0.1, 0.3, 0.5, 0.7, 0.9]
        batch_results = cal.predict_batch(scores)
        individual_results = [cal.predict(s) for s in scores]

        for batch_val, indiv_val in zip(batch_results, individual_results):
            assert abs(batch_val - indiv_val) < 1e-9


class TestConfidenceLabels:
    """Tests for get_confidence_label()."""

    def test_confidence_label_boundaries(self):
        """Boundary values produce correct labels."""
        cal = SimilarityCalibrator()

        # Exact boundaries
        assert cal.get_confidence_label(0.9) == "High"
        assert cal.get_confidence_label(0.7) == "Medium"
        assert cal.get_confidence_label(0.5) == "Low"

        # Interior values
        assert cal.get_confidence_label(0.95) == "High"
        assert cal.get_confidence_label(0.8) == "Medium"
        assert cal.get_confidence_label(0.6) == "Low"
        assert cal.get_confidence_label(0.3) == "Unlikely"
        assert cal.get_confidence_label(0.0) == "Unlikely"


class TestCalibrationReport:
    """Tests for calibration_report()."""

    def test_report_no_model(self, tmp_path):
        """Report with no model returns status: no_model."""
        cal = SimilarityCalibrator(model_dir=tmp_path / "empty")
        report = cal.calibration_report()
        assert report == {"status": "no_model"}

    def test_report_has_expected_keys(self, tmp_path):
        """Report after fit() contains all expected keys."""
        cal = SimilarityCalibrator(model_dir=tmp_path / "cal")
        cal.fit(_make_synthetic_pairs())
        report = cal.calibration_report()

        expected_keys = {
            "version",
            "created_at",
            "pair_count",
            "match_count",
            "nonmatch_count",
            "auc",
            "threshold_at_90_precision",
            "threshold_at_95_precision",
        }
        assert set(report.keys()) == expected_keys
        assert report["version"] == 1
        assert report["pair_count"] == 60


class TestShouldRecalibrate:
    """Tests for should_recalibrate()."""

    def test_no_model_triggers_recalibrate(self, tmp_path):
        """With no model fitted, should_recalibrate returns True."""
        cal = SimilarityCalibrator(model_dir=tmp_path / "empty")
        should, reason = cal.should_recalibrate()
        assert should is True
        assert "no model exists" in reason

    def test_fresh_model_does_not_trigger(self, tmp_path):
        """Immediately after fit(), no recalibration is needed."""
        cal = SimilarityCalibrator(model_dir=tmp_path / "cal")
        cal.fit(_make_synthetic_pairs())
        should, reason = cal.should_recalibrate()
        assert should is False
        assert "no trigger met" in reason
