"""Unified confidence scoring for face similarity distances.

Single source of truth for converting Euclidean face distances
to confidence percentages, tiers, labels, and colors.

Replaces 6+ divergent scoring paths (AD-200).

Priority chain:
  1. Calibrated similarity (isotonic regression model)
  2. Sigmoid CDF with empirical same_person stats
  3. Linear fallback
"""

import numpy as np
from typing import Optional

# Tier boundaries based on confidence_pct (AD-091)
TIER_STRONG = 85
TIER_POSSIBLE = 70
TIER_SIMILAR = 50

# Cached calibrator instances
_calibrator = None
_calibrator_loaded = False
_batch_calibrator_available = None


def _get_calibrator():
    """Lazy-load the SimilarityCalibrator (isotonic regression)."""
    global _calibrator, _calibrator_loaded
    if _calibrator_loaded:
        return _calibrator
    try:
        from rhodesli_ml.similarity_calibration import SimilarityCalibrator
        cal = SimilarityCalibrator()
        # Verify it can predict
        test_result = cal.predict(0.5)
        if test_result is not None:
            _calibrator = cal
    except Exception:
        pass
    _calibrator_loaded = True
    return _calibrator


def _get_batch_calibrator():
    """Check if batch calibration (ONNX/PyTorch) is available."""
    global _batch_calibrator_available
    if _batch_calibrator_available is not None:
        return _batch_calibrator_available
    try:
        from rhodesli_ml.calibration.inference import is_calibration_available
        _batch_calibrator_available = is_calibration_available()
    except Exception:
        _batch_calibrator_available = False
    return _batch_calibrator_available


def distance_to_cosine_sim(distance: float) -> float:
    """Convert Euclidean distance to cosine similarity."""
    return max(0.0, 1.0 - (distance ** 2) / 2.0)


def compute_face_confidence(
    distance: float,
    same_person_stats: Optional[dict] = None,
) -> dict:
    """Compute confidence for a face similarity distance.

    Returns dict with:
      confidence_pct: int (1-99)
      tier: str (STRONG MATCH / POSSIBLE MATCH / SIMILAR / WEAK)
      label: str (human-readable)
      short_label: str (compact label for badges)
      tier_color: str (Tailwind CSS class)
      dots: int (1-5 for dot displays)
    """
    confidence_pct = _compute_pct(distance, same_person_stats)
    return _build_result(confidence_pct)


def compute_confidence_pct(
    distance: float,
    same_person_stats: Optional[dict] = None,
) -> int:
    """Just the percentage — for callers that only need a number."""
    return _compute_pct(distance, same_person_stats)


def _compute_pct(distance: float, same_person_stats: Optional[dict]) -> int:
    """Core percentage computation with priority chain."""
    # 1. Try isotonic calibrator
    cal = _get_calibrator()
    if cal is not None:
        cosine_sim = distance_to_cosine_sim(distance)
        try:
            prob = cal.predict(cosine_sim)
            if prob is not None:
                return max(1, min(99, int(prob * 100)))
        except Exception:
            pass

    # 2. Try sigmoid CDF with empirical stats
    if same_person_stats and same_person_stats.get("n", 0) > 0:
        mean = same_person_stats.get("mean", 0)
        std = same_person_stats.get("std", 0)
        if std > 0:
            z = (distance - mean) / (std * 1.5)
            prob = 1.0 / (1.0 + np.exp(z))
            return max(1, min(99, int(prob * 100)))

    # 3. Linear fallback
    return max(1, min(99, int((2.0 - distance) / 2.0 * 100)))


def _build_result(confidence_pct: int) -> dict:
    """Build the standard result dict from a confidence percentage."""
    if confidence_pct >= TIER_STRONG:
        tier = "STRONG MATCH"
        label = "Very likely same person"
        short_label = "Very High"
        tier_color = "bg-emerald-600"
        dots = 5
    elif confidence_pct >= TIER_POSSIBLE:
        tier = "POSSIBLE MATCH"
        label = "Strong match"
        short_label = "High"
        tier_color = "bg-blue-600"
        dots = 4
    elif confidence_pct >= TIER_SIMILAR:
        tier = "SIMILAR"
        label = "Possible match"
        short_label = "Moderate"
        tier_color = "bg-amber-500"
        dots = 3
    elif confidence_pct >= 30:
        tier = "WEAK"
        label = "Unlikely match"
        short_label = "Low"
        tier_color = "bg-slate-500"
        dots = 2
    else:
        tier = "WEAK"
        label = "Unlikely match"
        short_label = "Very Low"
        tier_color = "bg-slate-600"
        dots = 1

    return {
        "confidence_pct": confidence_pct,
        "tier": tier,
        "label": label,
        "short_label": short_label,
        "tier_color": tier_color,
        "dots": dots,
    }


def confidence_tier_from_distance(distance: float) -> tuple:
    """Drop-in replacement for _confidence_tier(dist) → (label, color).

    Replaces the 3 local definitions in main.py.
    """
    result = compute_face_confidence(distance)
    return (result["short_label"], result["tier_color"])


def confidence_tier_with_dots(distance: float) -> tuple:
    """Return (short_label, color, dots) for discoveries display."""
    result = compute_face_confidence(distance)
    return (result["short_label"], result["tier_color"], result["dots"])


def calibrated_similarity_batch_unified(query_emb, candidate_embs):
    """Batch calibrated scoring — wraps the ML calibration module.

    Returns (N,) array of probabilities, or None if unavailable.
    Used by neighbors.py for batch scoring.
    """
    if not _get_batch_calibrator():
        return None
    try:
        from rhodesli_ml.calibration.inference import calibrated_similarity_batch
        return calibrated_similarity_batch(query_emb, candidate_embs)
    except Exception:
        return None
