"""Unified confidence scoring for face similarity distances.

Single source of truth for converting Euclidean face distances
to confidence percentages, tiers, labels, and colors.

Replaces 6+ divergent scoring paths (AD-200).
Fixed in Session 88: isotonic too coarse for continuous display,
sigmoid CDF with empirical stats gives proper granularity.

Priority chain:
  1. Sigmoid CDF with empirical same_person stats (best granularity)
  2. Linear fallback
"""

import json
import numpy as np
from pathlib import Path
from typing import Optional

# Tier boundaries based on confidence_pct (AD-091)
TIER_STRONG = 85
TIER_POSSIBLE = 70
TIER_SIMILAR = 50

# Cached same_person stats from kinship thresholds
_same_person_stats = None
_same_person_stats_loaded = False


def _get_same_person_stats() -> Optional[dict]:
    """Lazy-load same_person distribution stats from kinship thresholds."""
    global _same_person_stats, _same_person_stats_loaded
    if _same_person_stats_loaded:
        return _same_person_stats
    _same_person_stats_loaded = True
    try:
        thresholds_path = (
            Path(__file__).resolve().parent.parent
            / "rhodesli_ml"
            / "data"
            / "model_comparisons"
            / "kinship_thresholds.json"
        )
        if thresholds_path.exists():
            with open(thresholds_path) as f:
                data = json.load(f)
            sp = data.get("same_person")
            if sp and sp.get("n", 0) > 0 and sp.get("std", 0) > 0:
                _same_person_stats = sp
    except Exception:
        pass
    return _same_person_stats


def distance_to_cosine_sim(distance: float) -> float:
    """Convert Euclidean distance to cosine similarity."""
    return max(0.0, 1.0 - (distance**2) / 2.0)


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
    """Core percentage computation with priority chain.

    Session 88: Sigmoid CDF with empirical stats gives best granularity
    for continuous display. Isotonic calibrator (10 breakpoints) was too
    coarse — gave 99% for everything above distance ~1.22.
    """
    # Ensure distance is a plain float (callers may pass numpy scalars/arrays)
    distance = float(distance)

    # Use caller-provided stats or load from kinship thresholds
    stats = same_person_stats
    if stats is None:
        stats = _get_same_person_stats()

    # 1. Sigmoid CDF with empirical same_person distribution
    if stats and stats.get("n", 0) > 0:
        mean = stats.get("mean", 0)
        std = stats.get("std", 0)
        if std > 0:
            z = (distance - mean) / (std * 1.5)
            prob = 1.0 / (1.0 + np.exp(z))
            return max(1, min(99, int(prob * 100)))

    # 2. Linear fallback
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
