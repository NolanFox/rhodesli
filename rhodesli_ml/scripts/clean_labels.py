"""Validate and clean date_labels.json.

Strips invalid controlled_tags, flags suspicious decades, invalid ages,
people_count mismatches, and missing scene descriptions.

Usage:
    python -m rhodesli_ml.scripts.clean_labels --dry-run
    python rhodesli_ml/scripts/clean_labels.py --dry-run
    python rhodesli_ml/scripts/clean_labels.py              # modifies in place
    python rhodesli_ml/scripts/clean_labels.py --path /alt/path/date_labels.json
"""

import argparse
import json
import sys
from pathlib import Path

# Allow direct invocation: python rhodesli_ml/scripts/clean_labels.py
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from rhodesli_ml.data.date_labels import VALID_CONTROLLED_TAGS

# Local copy for explicitness and quick reference
VALID_TAGS = {
    "Studio", "Outdoor", "Beach", "Street", "Home_Interior",
    "Synagogue", "Cemetery", "Wedding", "Funeral", "Religious_Ceremony",
    "School", "Military", "Formal_Event", "Casual", "Group_Portrait",
    "Document", "Postcard",
}

# Sanity check: our local set matches the canonical source
assert VALID_TAGS == set(VALID_CONTROLLED_TAGS), (
    f"VALID_TAGS mismatch with VALID_CONTROLLED_TAGS: "
    f"extra={VALID_TAGS - set(VALID_CONTROLLED_TAGS)}, "
    f"missing={set(VALID_CONTROLLED_TAGS) - VALID_TAGS}"
)

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "date_labels.json"


def _green(text: str) -> str:
    return f"{GREEN}{text}{RESET}"


def _yellow(text: str) -> str:
    return f"{YELLOW}{text}{RESET}"


def _red(text: str) -> str:
    return f"{RED}{text}{RESET}"


def clean_labels(labels_path: str | Path, dry_run: bool = False) -> dict:
    """Validate and clean date_labels.json.

    Args:
        labels_path: Path to date_labels.json.
        dry_run: If True, print issues without modifying the file.

    Returns:
        Summary dict with counts and lists of flagged items.
    """
    labels_path = Path(labels_path)
    if not labels_path.exists():
        print(_red(f"ERROR: {labels_path} not found"))
        return {
            "total_labels": 0,
            "invalid_tags_removed": 0,
            "suspicious_decades": [],
            "invalid_ages": [],
            "people_count_mismatches": [],
            "missing_scene_descriptions": 0,
            "modified": False,
        }

    with open(labels_path) as f:
        data = json.load(f)

    labels = data.get("labels", [])
    total = len(labels)

    invalid_tags_removed = 0
    suspicious_decades: list[tuple[str, int]] = []
    invalid_ages: list[tuple[str, list[int]]] = []
    people_count_mismatches: list[tuple[str, int, int]] = []
    missing_scene_descriptions = 0
    modified = False

    for entry in labels:
        photo_id = entry.get("photo_id", "<unknown>")

        # 1. Strip invalid controlled_tags
        tags = entry.get("controlled_tags", [])
        if tags:
            clean_tags = [t for t in tags if t in VALID_TAGS]
            removed = [t for t in tags if t not in VALID_TAGS]
            if removed:
                invalid_tags_removed += len(removed)
                print(_red(f"  REMOVE tags {removed} from {photo_id}"))
                if not dry_run:
                    entry["controlled_tags"] = clean_tags
                    modified = True

        # 2. Flag suspicious decades
        decade = entry.get("estimated_decade", entry.get("decade"))
        if decade is not None and (decade < 1870 or decade > 2020):
            suspicious_decades.append((photo_id, decade))
            print(_yellow(f"  WARN suspicious decade {decade} for {photo_id}"))

        # 3. Flag subject_ages outside 0-110
        ages = entry.get("subject_ages", [])
        if ages:
            bad_ages = [a for a in ages if a < 0 or a > 110]
            if bad_ages:
                invalid_ages.append((photo_id, ages))
                print(_yellow(f"  WARN invalid ages {ages} for {photo_id}"))

        # 4. Flag people_count vs subject_ages mismatch
        people_count = entry.get("people_count")
        if people_count is not None and ages:
            if abs(people_count - len(ages)) > 1:
                people_count_mismatches.append((photo_id, people_count, len(ages)))
                print(_yellow(
                    f"  WARN people_count={people_count} but "
                    f"{len(ages)} subject_ages for {photo_id}"
                ))

        # 5. Flag missing scene_description
        scene = entry.get("scene_description")
        if not scene:
            missing_scene_descriptions += 1

    # Save if modified and not dry_run
    if modified and not dry_run:
        with open(labels_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(_green(f"\nSaved cleaned labels to {labels_path}"))
    elif dry_run and (invalid_tags_removed > 0):
        print(_yellow(f"\nDry run: {invalid_tags_removed} tags would be removed"))

    summary = {
        "total_labels": total,
        "invalid_tags_removed": invalid_tags_removed,
        "suspicious_decades": suspicious_decades,
        "invalid_ages": invalid_ages,
        "people_count_mismatches": people_count_mismatches,
        "missing_scene_descriptions": missing_scene_descriptions,
        "modified": modified and not dry_run,
    }

    # Print summary
    print(f"\n{'=' * 50}")
    print(f"  Date Labels Cleaning Summary")
    print(f"{'=' * 50}")
    print(f"  Total labels:              {total}")

    if invalid_tags_removed == 0:
        print(_green(f"  Invalid tags removed:      0"))
    else:
        print(_red(f"  Invalid tags removed:      {invalid_tags_removed}"))

    if suspicious_decades:
        print(_red(f"  Suspicious decades:        {len(suspicious_decades)}"))
        for pid, dec in suspicious_decades:
            print(f"    - {pid}: {dec}")
    else:
        print(_green(f"  Suspicious decades:        0"))

    if invalid_ages:
        print(_red(f"  Invalid ages:              {len(invalid_ages)}"))
        for pid, ages_val in invalid_ages:
            print(f"    - {pid}: {ages_val}")
    else:
        print(_green(f"  Invalid ages:              0"))

    if people_count_mismatches:
        print(_yellow(f"  People count mismatches:   {len(people_count_mismatches)}"))
        for pid, pc, ac in people_count_mismatches:
            print(f"    - {pid}: people_count={pc}, ages_count={ac}")
    else:
        print(_green(f"  People count mismatches:   0"))

    if missing_scene_descriptions > 0:
        print(_yellow(f"  Missing scene descriptions: {missing_scene_descriptions}"))
    else:
        print(_green(f"  Missing scene descriptions: 0"))

    if dry_run:
        print(_yellow(f"\n  Mode: DRY RUN (no changes written)"))
    elif modified:
        print(_green(f"\n  File modified and saved."))
    else:
        print(_green(f"\n  Already clean. No changes needed."))

    print(f"{'=' * 50}")

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Validate and clean date_labels.json"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print issues without modifying the file",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=str(DEFAULT_PATH),
        help=f"Path to date_labels.json (default: {DEFAULT_PATH})",
    )
    args = parser.parse_args()

    summary = clean_labels(args.path, dry_run=args.dry_run)

    # Exit with non-zero if there were issues flagged
    has_issues = (
        summary["invalid_tags_removed"] > 0
        or len(summary["suspicious_decades"]) > 0
        or len(summary["invalid_ages"]) > 0
        or len(summary["people_count_mismatches"]) > 0
    )
    sys.exit(1 if has_issues else 0)


if __name__ == "__main__":
    main()
