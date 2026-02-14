"""Date label and photo metadata loading for the ML pipeline.

Loads silver labels (Gemini API estimates) and gold labels (user corrections)
from date_labels.json. Merges them with gold-overrides-silver semantics.

Schema v2 labels include structured evidence, decade probabilities, and
year-level estimates alongside decade classifications.

Rich metadata fields (AD-048) are optional — older labels without them
load correctly with None/empty defaults.
"""

import json
from pathlib import Path
from typing import NamedTuple


class DateLabel(NamedTuple):
    """A date label for a photo."""
    photo_id: str
    decade: int  # e.g., 1940
    best_year: int | None  # e.g., 1937
    confidence: str  # "high", "medium", "low"
    source: str  # "gemini", "user", "newspaper_date"
    probable_range: tuple[int, int] | None  # e.g., (1935, 1955)
    decade_probabilities: dict[str, float]  # e.g., {"1930": 0.15, "1940": 0.55}
    reasoning: str  # Summary reasoning


class PhotoMetadata(NamedTuple):
    """Rich metadata extracted from a photo via Gemini Vision (AD-048, AD-049).

    All fields are Optional — older labels without metadata still load fine.
    """
    photo_id: str
    scene_description: str | None  # 2-3 sentence description
    visible_text: str | None  # OCR of inscriptions/captions, or None
    keywords: list[str]  # 5-15 searchable tags
    controlled_tags: list[str]  # Values from VALID_CONTROLLED_TAGS only (AD-049)
    setting: str | None  # indoor_studio, outdoor_urban, etc.
    photo_type: str | None  # formal_portrait, group_photo, etc.
    people_count: int | None  # Number of visible people
    condition: str | None  # excellent, good, fair, poor
    clothing_notes: str | None  # Brief clothing/accessory description
    subject_ages: list[int]  # Estimated ages left-to-right (AD-049)
    prompt_version: str | None  # Prompt version for reproducibility (AD-049)


# Valid enum values for validation
VALID_CONTROLLED_TAGS = frozenset({
    "Studio", "Outdoor", "Beach", "Street", "Home_Interior",
    "Synagogue", "Cemetery", "Wedding", "Funeral", "Religious_Ceremony",
    "School", "Military", "Formal_Event", "Casual", "Group_Portrait",
    "Document", "Postcard",
})
VALID_SETTINGS = frozenset({
    "indoor_studio", "outdoor_urban", "outdoor_rural",
    "indoor_home", "indoor_other", "outdoor_other", "unknown",
})
VALID_PHOTO_TYPES = frozenset({
    "formal_portrait", "group_photo", "candid", "document",
    "postcard", "wedding", "funeral", "school", "military",
    "religious_ceremony", "other",
})
VALID_CONDITIONS = frozenset({"excellent", "good", "fair", "poor"})


def load_date_labels(path: str = "rhodesli_ml/data/date_labels.json") -> list[DateLabel]:
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
        probable_range = entry.get("probable_range")
        if isinstance(probable_range, list) and len(probable_range) == 2:
            probable_range = tuple(probable_range)
        else:
            probable_range = None

        label = DateLabel(
            photo_id=entry["photo_id"],
            decade=entry.get("estimated_decade", entry.get("decade", 0)),
            best_year=entry.get("best_year_estimate"),
            confidence=entry.get("confidence", "medium"),
            source=entry.get("source", "gemini"),
            probable_range=probable_range,
            decade_probabilities=entry.get("decade_probabilities", {}),
            reasoning=entry.get("reasoning_summary", entry.get("reasoning", "")),
        )
        existing = by_photo.get(label.photo_id)
        if existing is None or label.source == "user":
            by_photo[label.photo_id] = label

    return list(by_photo.values())


def load_photo_metadata(path: str = "rhodesli_ml/data/date_labels.json") -> list[PhotoMetadata]:
    """Load rich photo metadata from labels file (AD-048).

    Returns PhotoMetadata for labels that have metadata fields.
    Labels without metadata fields are silently skipped.
    """
    labels_path = Path(path)
    if not labels_path.exists():
        return []

    with open(labels_path) as f:
        data = json.load(f)

    raw_labels = data.get("labels", [])
    metadata_list = []

    for entry in raw_labels:
        # Skip entries without any metadata fields
        has_metadata = any(
            entry.get(k) is not None
            for k in ("scene_description", "visible_text", "keywords",
                       "setting", "photo_type", "people_count",
                       "condition", "clothing_notes")
        )
        if not has_metadata:
            continue

        metadata_list.append(PhotoMetadata(
            photo_id=entry["photo_id"],
            scene_description=entry.get("scene_description"),
            visible_text=entry.get("visible_text"),
            keywords=entry.get("keywords", []),
            controlled_tags=entry.get("controlled_tags", []),
            setting=entry.get("setting"),
            photo_type=entry.get("photo_type"),
            people_count=entry.get("people_count"),
            condition=entry.get("condition"),
            clothing_notes=entry.get("clothing_notes"),
            subject_ages=entry.get("subject_ages", []),
            prompt_version=entry.get("prompt_version"),
        ))

    return metadata_list


def decade_to_ordinal(decade: int) -> int:
    """Convert decade (e.g. 1940) to ordinal index for CORAL regression.

    Decades: 1900=0, 1910=1, ..., 2000=10
    """
    return max(0, min(10, (decade - 1900) // 10))


def ordinal_to_decade(ordinal: int) -> int:
    """Convert ordinal index back to decade."""
    return 1900 + ordinal * 10
