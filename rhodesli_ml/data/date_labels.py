"""Date label loading and management for date estimation model.

Loads silver labels (Gemini API estimates) and gold labels (user corrections)
from data/date_labels.json. Merges them with gold-overrides-silver semantics.
"""

import json
from pathlib import Path
from typing import NamedTuple


class DateLabel(NamedTuple):
    """A date label for a photo."""
    photo_id: str
    decade: int  # e.g., 1940
    confidence: str  # "high", "medium", "low"
    source: str  # "gemini", "user", "newspaper_date"
    reasoning: str  # Why this date was assigned


def load_date_labels(path: str = "data/date_labels.json") -> list[DateLabel]:
    """Load date labels from JSON file.

    Gold labels (source="user") override silver labels (source="gemini")
    for the same photo_id.
    """
    labels_path = Path(path)
    if not labels_path.exists():
        return []

    with open(labels_path) as f:
        data = json.load(f)

    raw_labels = data.get("labels", [])

    # Build lookup: photo_id -> label, gold overrides silver
    by_photo: dict[str, DateLabel] = {}
    for entry in raw_labels:
        label = DateLabel(
            photo_id=entry["photo_id"],
            decade=entry["decade"],
            confidence=entry.get("confidence", "medium"),
            source=entry.get("source", "gemini"),
            reasoning=entry.get("reasoning", ""),
        )
        existing = by_photo.get(label.photo_id)
        if existing is None or label.source == "user":
            by_photo[label.photo_id] = label

    return list(by_photo.values())


def decade_to_ordinal(decade: int) -> int:
    """Convert decade (e.g. 1940) to ordinal index for CORAL regression.

    Decades: 1900=0, 1910=1, ..., 2020=12
    """
    return max(0, min(12, (decade - 1900) // 10))


def ordinal_to_decade(ordinal: int) -> int:
    """Convert ordinal index back to decade."""
    return 1900 + ordinal * 10
