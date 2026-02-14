"""Manually add a Gemini date label from a web UI paste or JSON file.

Accepts a photo_id and a JSON string (or file path) containing the raw
Gemini output, validates it against the label schema, and adds/replaces
the entry in date_labels.json.

Usage:
    # From a JSON string (paste from Gemini web UI)
    python -m rhodesli_ml.scripts.add_manual_label PHOTO_ID '{"date_estimation": {...}, ...}'

    # From a JSON file
    python -m rhodesli_ml.scripts.add_manual_label PHOTO_ID /path/to/response.json

    # With custom model name
    python -m rhodesli_ml.scripts.add_manual_label PHOTO_ID '...' --model gemini-3-pro-preview

    # Skip archiving the old label
    python -m rhodesli_ml.scripts.add_manual_label PHOTO_ID '...' --no-archive
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from rhodesli_ml.scripts.generate_date_labels import load_existing_labels, save_labels

# Valid values for schema validation
VALID_CONFIDENCES = {"high", "medium", "low"}
VALID_SETTINGS = {
    "indoor_studio", "outdoor_urban", "outdoor_rural",
    "indoor_home", "indoor_other", "outdoor_other", "unknown",
}
VALID_PHOTO_TYPES = {
    "formal_portrait", "group_photo", "candid", "document", "postcard",
    "wedding", "funeral", "school", "military", "religious_ceremony", "other",
}
VALID_CONDITIONS = {"excellent", "good", "fair", "poor"}
VALID_CONTROLLED_TAGS = {
    "Studio", "Outdoor", "Beach", "Street", "Home_Interior", "Synagogue",
    "Cemetery", "Wedding", "Funeral", "Religious_Ceremony", "School",
    "Military", "Formal_Event", "Casual", "Group_Portrait", "Document", "Postcard",
}


def parse_json_input(json_input: str) -> dict:
    """Parse JSON from either a string or a file path.

    Tries JSON string parsing first (most common for web UI paste),
    then falls back to reading from a file path.
    """
    # Try as raw JSON string first (handles long pasted strings that
    # would cause OSError if treated as a file path)
    try:
        return json.loads(json_input)
    except (json.JSONDecodeError, ValueError):
        pass

    # Try as file path
    try:
        path = Path(json_input)
        if path.exists() and path.is_file():
            with open(path) as f:
                return json.load(f)
    except OSError:
        pass

    print(f"ERROR: Could not parse JSON input.")
    print("Input must be either a valid JSON string or a path to a JSON file.")
    sys.exit(1)


def flatten_gemini_response(parsed: dict) -> dict:
    """Flatten a Gemini response with nested date_estimation into a flat dict.

    Mirrors the flattening logic in generate_date_labels.call_gemini().
    """
    if "date_estimation" in parsed:
        date_est = dict(parsed["date_estimation"])
        # Merge rich metadata fields from top level
        for key in ("scene_description", "visible_text", "keywords",
                     "controlled_tags", "setting", "photo_type",
                     "people_count", "condition", "clothing_notes",
                     "subject_ages"):
            if key in parsed:
                date_est[key] = parsed[key]
        return date_est
    return dict(parsed)


def validate_label(result: dict) -> list[str]:
    """Validate the flattened label dict against the schema.

    Returns a list of error messages. Empty list means valid.
    """
    errors = []

    # Required: estimated_decade (int, 1900-2020)
    decade = result.get("estimated_decade")
    if decade is None:
        errors.append("Missing required field: estimated_decade")
    elif not isinstance(decade, int):
        errors.append(f"estimated_decade must be an integer, got {type(decade).__name__}")
    elif decade < 1900 or decade > 2020:
        errors.append(f"estimated_decade must be between 1900 and 2020, got {decade}")

    # Required: confidence (high/medium/low)
    confidence = result.get("confidence")
    if confidence is None:
        errors.append("Missing required field: confidence")
    elif confidence not in VALID_CONFIDENCES:
        errors.append(f"confidence must be one of {VALID_CONFIDENCES}, got '{confidence}'")

    # Required: decade_probabilities (dict, values sum to ~1.0)
    probs = result.get("decade_probabilities")
    if probs is None:
        errors.append("Missing required field: decade_probabilities")
    elif not isinstance(probs, dict):
        errors.append(f"decade_probabilities must be a dict, got {type(probs).__name__}")
    elif probs:
        prob_sum = sum(probs.values())
        if abs(prob_sum - 1.0) > 0.10:
            errors.append(
                f"decade_probabilities must sum to ~1.0, got {prob_sum:.3f}"
            )
        # Check all values are numeric
        for k, v in probs.items():
            if not isinstance(v, (int, float)):
                errors.append(f"decade_probabilities['{k}'] must be numeric, got {type(v).__name__}")

    # Optional field validation
    setting = result.get("setting")
    if setting is not None and setting not in VALID_SETTINGS:
        errors.append(f"setting must be one of {VALID_SETTINGS}, got '{setting}'")

    photo_type = result.get("photo_type")
    if photo_type is not None and photo_type not in VALID_PHOTO_TYPES:
        errors.append(f"photo_type must be one of {VALID_PHOTO_TYPES}, got '{photo_type}'")

    condition = result.get("condition")
    if condition is not None and condition not in VALID_CONDITIONS:
        errors.append(f"condition must be one of {VALID_CONDITIONS}, got '{condition}'")

    controlled_tags = result.get("controlled_tags")
    if controlled_tags is not None:
        if not isinstance(controlled_tags, list):
            errors.append(f"controlled_tags must be a list, got {type(controlled_tags).__name__}")
        else:
            invalid_tags = set(controlled_tags) - VALID_CONTROLLED_TAGS
            if invalid_tags:
                errors.append(f"Invalid controlled_tags: {invalid_tags}")

    people_count = result.get("people_count")
    if people_count is not None and not isinstance(people_count, int):
        errors.append(f"people_count must be an integer, got {type(people_count).__name__}")

    best_year = result.get("best_year_estimate")
    if best_year is not None:
        if not isinstance(best_year, int):
            errors.append(f"best_year_estimate must be an integer, got {type(best_year).__name__}")
        elif best_year < 1880 or best_year > 2025:
            errors.append(f"best_year_estimate must be between 1880 and 2025, got {best_year}")

    probable_range = result.get("probable_range")
    if probable_range is not None:
        if not isinstance(probable_range, list) or len(probable_range) != 2:
            errors.append("probable_range must be a list of [start_year, end_year]")
        elif not all(isinstance(y, int) for y in probable_range):
            errors.append("probable_range values must be integers")

    subject_ages = result.get("subject_ages")
    if subject_ages is not None:
        if not isinstance(subject_ages, list):
            errors.append(f"subject_ages must be a list, got {type(subject_ages).__name__}")
        elif not all(isinstance(a, int) for a in subject_ages):
            errors.append("subject_ages values must be integers")

    return errors


def archive_old_label(old_label: dict, photo_id: str, archive_dir: str):
    """Save the old label to model_comparisons/ with a timestamp."""
    archive_path = Path(archive_dir)
    archive_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"replaced_{photo_id}_{timestamp}.json"
    filepath = archive_path / filename

    with open(filepath, "w") as f:
        json.dump(old_label, f, indent=2)

    print(f"Archived old label to {filepath}")


def build_label(photo_id: str, result: dict, model: str) -> dict:
    """Build the label dict from the flattened Gemini result."""
    # Normalize decade_probabilities: if sum is off, normalize
    probs = result.get("decade_probabilities", {})
    if probs:
        prob_sum = sum(probs.values())
        if abs(prob_sum - 1.0) > 0.05:
            probs = {k: v / prob_sum for k, v in probs.items()}

    return {
        "photo_id": photo_id,
        "source": "gemini",
        "model": model,
        "source_method": "web_manual",
        # Date estimation fields
        "estimated_decade": result.get("estimated_decade"),
        "best_year_estimate": result.get("best_year_estimate"),
        "confidence": result.get("confidence", "medium"),
        "probable_range": result.get("probable_range"),
        "decade_probabilities": probs,
        "location_estimate": result.get("location_estimate", ""),
        "is_color": result.get("is_color", False),
        "evidence": result.get("evidence", {}),
        "cultural_lag_applied": result.get("cultural_lag_applied", False),
        "cultural_lag_note": result.get("cultural_lag_note", ""),
        "capture_vs_print": result.get("capture_vs_print", ""),
        "reasoning_summary": result.get("reasoning_summary", ""),
        # Rich metadata fields (AD-048)
        "scene_description": result.get("scene_description"),
        "visible_text": result.get("visible_text"),
        "keywords": result.get("keywords", []),
        "setting": result.get("setting"),
        "photo_type": result.get("photo_type"),
        "people_count": result.get("people_count"),
        "condition": result.get("condition"),
        "clothing_notes": result.get("clothing_notes"),
        # AD-049 fields
        "controlled_tags": result.get("controlled_tags", []),
        "subject_ages": result.get("subject_ages", []),
        "prompt_version": "v2_rich_metadata",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Manually add a Gemini date label from a web UI paste or JSON file",
        epilog=(
            "Example: python -m rhodesli_ml.scripts.add_manual_label "
            'abc123 \'{"date_estimation": {"estimated_decade": 1940, ...}}\''
        ),
    )
    parser.add_argument(
        "photo_id",
        help="The photo ID to label",
    )
    parser.add_argument(
        "json_input",
        help="Either a JSON string or a path to a JSON file containing the Gemini response",
    )
    parser.add_argument(
        "--model",
        default="gemini-3-flash-preview",
        help="Model name to record (default: gemini-3-flash-preview)",
    )
    parser.add_argument(
        "--labels-path",
        default="rhodesli_ml/data/date_labels.json",
        help="Path to date_labels.json (default: rhodesli_ml/data/date_labels.json)",
    )
    parser.add_argument(
        "--no-archive",
        action="store_true",
        help="Skip archiving the old label if one exists",
    )
    args = parser.parse_args()

    # Parse input JSON
    parsed = parse_json_input(args.json_input)

    # Flatten nested date_estimation if present
    result = flatten_gemini_response(parsed)

    # Validate against schema
    errors = validate_label(result)
    if errors:
        print(f"ERROR: Validation failed for photo {args.photo_id}:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    # Load existing labels
    existing = load_existing_labels(args.labels_path)

    # Archive old label if one exists
    old_label = existing.get(args.photo_id)
    if old_label:
        if not args.no_archive:
            archive_dir = str(
                Path(args.labels_path).parent / "model_comparisons"
            )
            archive_old_label(old_label, args.photo_id, archive_dir)
        print(f"Replacing existing label for {args.photo_id} "
              f"(was: {old_label.get('model', '?')}, "
              f"decade={old_label.get('estimated_decade', '?')})")
    else:
        print(f"Adding new label for {args.photo_id}")

    # Build the label
    label = build_label(args.photo_id, result, args.model)

    # Replace or add in the labels list
    existing[args.photo_id] = label
    all_labels = list(existing.values())

    # Save
    save_labels(all_labels, args.labels_path)

    # Print confirmation
    decade = label["estimated_decade"]
    year = label.get("best_year_estimate", "?")
    conf = label["confidence"]
    loc = label.get("location_estimate", "?")
    print(f"\nLabel saved for {args.photo_id}:")
    print(f"  Decade: {decade}s (best year: {year})")
    print(f"  Confidence: {conf}")
    print(f"  Location: {loc}")
    print(f"  Model: {args.model}")
    print(f"  Source method: web_manual")

    scene = label.get("scene_description")
    if scene:
        print(f"  Scene: {scene[:120]}")
    keywords = label.get("keywords", [])
    if keywords:
        print(f"  Keywords: {', '.join(keywords[:10])}")
    controlled = label.get("controlled_tags", [])
    if controlled:
        print(f"  Controlled tags: {', '.join(controlled)}")
    text = label.get("visible_text")
    if text:
        print(f"  Visible text: \"{text[:80]}\"")

    print(f"\nTotal labels in {args.labels_path}: {len(all_labels)}")


if __name__ == "__main__":
    main()
