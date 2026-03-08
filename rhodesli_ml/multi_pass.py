"""Multi-pass Gemini re-analysis foundation (ML-053).

Identifies low-confidence photo analyses and builds targeted prompts
for re-analysis with additional context. Foundation only — no batch
execution in this module.

Session: 92 | AD-210
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Confidence threshold below which a photo is a candidate for re-analysis
LOW_CONFIDENCE_THRESHOLD = 0.6


def identify_low_confidence_photos(
    date_labels: dict,
    threshold: float = LOW_CONFIDENCE_THRESHOLD,
) -> list[dict]:
    """Find photos with Gemini confidence below threshold.

    Args:
        date_labels: Dict of photo_id -> label data (from date_labels.json).
            Each entry may have 'confidence' (float 0-1) and 'estimated_year'.
        threshold: Confidence threshold (default 0.6). Photos below this
            are candidates for re-analysis.

    Returns:
        List of dicts with photo_id, confidence, estimated_year, sorted by
        confidence ascending (lowest confidence first).
    """
    candidates = []
    for photo_id, label in date_labels.items():
        confidence = label.get("confidence")
        if confidence is None:
            # No confidence = never analyzed or failed, always include
            candidates.append(
                {
                    "photo_id": photo_id,
                    "confidence": None,
                    "estimated_year": label.get("estimated_year") or label.get("best_year_estimate"),
                    "estimated_decade": label.get("estimated_decade"),
                    "reason": "no_confidence_score",
                }
            )
        elif isinstance(confidence, (int, float)) and confidence < threshold:
            candidates.append(
                {
                    "photo_id": photo_id,
                    "confidence": confidence,
                    "estimated_year": label.get("estimated_year") or label.get("best_year_estimate"),
                    "estimated_decade": label.get("estimated_decade"),
                    "reason": "below_threshold",
                }
            )

    # Sort by confidence ascending (None first, then lowest)
    candidates.sort(key=lambda x: (x["confidence"] is not None, x["confidence"] or 0))
    return candidates


def build_reanalysis_prompt(
    photo_id: str,
    previous_result: dict,
    gedcom_context: Optional[str] = None,
    visible_text: Optional[str] = None,
) -> str:
    """Build a targeted prompt for re-analyzing a low-confidence photo.

    Includes the previous analysis result so Gemini can refine rather than
    start from scratch.

    Args:
        photo_id: Photo being re-analyzed.
        previous_result: Previous Gemini analysis result dict.
        gedcom_context: Optional GEDCOM context string.
        visible_text: Optional text detected in the photo.

    Returns:
        Prompt string for re-analysis.
    """
    parts = [
        "You are re-analyzing this historical photograph. A previous analysis",
        "produced low confidence results. Please look more carefully at all",
        "available evidence.\n",
    ]

    # Include previous result for context
    prev_year = previous_result.get("estimated_year") or previous_result.get("best_year_estimate")
    prev_decade = previous_result.get("estimated_decade")
    prev_confidence = previous_result.get("confidence")
    prev_location = previous_result.get("location", {})

    parts.append("## Previous Analysis (low confidence)")
    if prev_year:
        parts.append(f"- Estimated year: {prev_year}")
    if prev_decade:
        parts.append(f"- Estimated decade: {prev_decade}")
    if prev_confidence is not None:
        parts.append(f"- Confidence: {prev_confidence}")
    if isinstance(prev_location, dict) and prev_location.get("place"):
        parts.append(f"- Location: {prev_location['place']}")
    parts.append("")

    parts.append("## Instructions for Re-Analysis")
    parts.append("Look for evidence the previous analysis may have missed:")
    parts.append("- Clothing styles and fashion details")
    parts.append("- Architecture and building materials")
    parts.append("- Vehicle models visible")
    parts.append("- Hairstyles and grooming")
    parts.append("- Photo processing characteristics (sepia, format)")
    parts.append("- Any text, signage, or written materials")
    parts.append("")

    if visible_text:
        parts.append(f"## Text Detected in Photo\n{visible_text}\n")

    if gedcom_context:
        parts.append(f"\n{gedcom_context}\n")

    parts.append(
        "Provide your best estimate with confidence level. If you disagree with the previous analysis, explain why."
    )

    return "\n".join(parts)
