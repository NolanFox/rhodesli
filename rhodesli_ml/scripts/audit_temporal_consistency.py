"""Audit temporal consistency between photo dates and identity metadata.

Checks for impossible/suspicious date-person combinations:
- Photo estimated year vs person birth/death year
- Gemini subject ages vs expected ages from birth year
- Gemini people count vs detected face count

Usage:
    python -m rhodesli_ml.scripts.audit_temporal_consistency
    python rhodesli_ml/scripts/audit_temporal_consistency.py
"""

import argparse
import json
import sys
from pathlib import Path

# Allow direct invocation: python rhodesli_ml/scripts/audit_temporal_consistency.py
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Default file paths (relative to project root)
DEFAULT_DATE_LABELS = Path(__file__).resolve().parent.parent / "data" / "date_labels.json"
DEFAULT_IDENTITIES = Path(__file__).resolve().parent.parent.parent / "data" / "identities.json"
DEFAULT_PHOTO_INDEX = Path(__file__).resolve().parent.parent.parent / "data" / "photo_index.json"

# Age discrepancy threshold (years) for flagging as SUSPICIOUS
AGE_DISCREPANCY_THRESHOLD = 20


def _green(text: str) -> str:
    return f"{GREEN}{text}{RESET}"


def _yellow(text: str) -> str:
    return f"{YELLOW}{text}{RESET}"


def _red(text: str) -> str:
    return f"{RED}{text}{RESET}"


def _cyan(text: str) -> str:
    return f"{CYAN}{text}{RESET}"


def _bold(text: str) -> str:
    return f"{BOLD}{text}{RESET}"


def load_date_labels(path: str | Path) -> dict[str, dict]:
    """Load date labels and return a dict keyed by photo_id."""
    path = Path(path)
    if not path.exists():
        print(_red(f"ERROR: {path} not found"))
        return {}
    with open(path) as f:
        data = json.load(f)
    return {entry["photo_id"]: entry for entry in data.get("labels", [])}


def load_identities(path: str | Path) -> dict[str, dict]:
    """Load identities.json and return the identities dict."""
    path = Path(path)
    if not path.exists():
        print(_red(f"ERROR: {path} not found"))
        return {}
    with open(path) as f:
        data = json.load(f)
    return data.get("identities", {})


def load_photo_index(path: str | Path) -> tuple[dict[str, dict], dict[str, str]]:
    """Load photo_index.json and return (photos, face_to_photo)."""
    path = Path(path)
    if not path.exists():
        print(_red(f"ERROR: {path} not found"))
        return {}, {}
    with open(path) as f:
        data = json.load(f)
    photos = data.get("photos", {})
    face_to_photo = data.get("face_to_photo", {})
    return photos, face_to_photo


def build_identity_photo_map(
    identities: dict[str, dict],
    face_to_photo: dict[str, str],
) -> dict[str, set[str]]:
    """Build a mapping from identity_id -> set of photo_ids they appear in.

    Uses anchor_ids + candidate_ids to find face IDs, then looks up
    the photo for each face via face_to_photo.
    """
    identity_photos: dict[str, set[str]] = {}
    for identity_id, identity in identities.items():
        if identity.get("merged_into"):
            continue
        face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
        photo_ids = set()
        for face_id in face_ids:
            photo_id = face_to_photo.get(face_id)
            if photo_id:
                photo_ids.add(photo_id)
        if photo_ids:
            identity_photos[identity_id] = photo_ids
    return identity_photos


def audit_temporal_consistency(
    date_labels: dict[str, dict],
    identities: dict[str, dict],
    face_to_photo: dict[str, str],
    age_threshold: int = AGE_DISCREPANCY_THRESHOLD,
) -> dict:
    """Check for temporal impossibilities between photo dates and identity metadata.

    Args:
        date_labels: Dict of photo_id -> label entry.
        identities: Dict of identity_id -> identity entry.
        face_to_photo: Dict of face_id -> photo_id.
        age_threshold: Maximum acceptable age discrepancy in years.

    Returns:
        Summary dict with impossible, suspicious, and checked counts.
    """
    impossible: list[dict] = []
    suspicious: list[dict] = []
    checked = 0

    identity_photos = build_identity_photo_map(identities, face_to_photo)

    for identity_id, photo_ids in identity_photos.items():
        identity = identities[identity_id]
        name = identity.get("name", "Unknown")
        metadata = identity.get("metadata", {})
        birth_year = metadata.get("birth_year")
        death_year = metadata.get("death_year")

        # Skip identities without temporal metadata
        if birth_year is None and death_year is None:
            continue

        for photo_id in photo_ids:
            label = date_labels.get(photo_id)
            if not label:
                continue

            estimated_year = label.get("best_year_estimate")
            if estimated_year is None:
                estimated_year = label.get("estimated_decade")
            if estimated_year is None:
                continue

            checked += 1

            # Check: photo before birth
            if birth_year is not None and estimated_year < birth_year:
                impossible.append({
                    "type": "BEFORE_BIRTH",
                    "identity_id": identity_id,
                    "name": name,
                    "photo_id": photo_id,
                    "estimated_year": estimated_year,
                    "birth_year": birth_year,
                    "detail": (
                        f"Photo dated ~{estimated_year} but {name} "
                        f"born in {birth_year}"
                    ),
                })

            # Check: photo after death
            if death_year is not None and estimated_year > death_year:
                impossible.append({
                    "type": "AFTER_DEATH",
                    "identity_id": identity_id,
                    "name": name,
                    "photo_id": photo_id,
                    "estimated_year": estimated_year,
                    "death_year": death_year,
                    "detail": (
                        f"Photo dated ~{estimated_year} but {name} "
                        f"died in {death_year}"
                    ),
                })

            # Check: subject age vs expected age
            if birth_year is not None:
                subject_ages = label.get("subject_ages", [])
                expected_age = estimated_year - birth_year
                if expected_age >= 0 and subject_ages:
                    # Check if ANY subject age is close to expected
                    closest_diff = min(abs(age - expected_age) for age in subject_ages)
                    if closest_diff > age_threshold:
                        suspicious.append({
                            "type": "AGE_MISMATCH",
                            "identity_id": identity_id,
                            "name": name,
                            "photo_id": photo_id,
                            "estimated_year": estimated_year,
                            "birth_year": birth_year,
                            "expected_age": expected_age,
                            "subject_ages": subject_ages,
                            "closest_diff": closest_diff,
                            "detail": (
                                f"{name} expected age ~{expected_age} "
                                f"(born {birth_year}, photo ~{estimated_year}) "
                                f"but Gemini ages are {subject_ages} "
                                f"(closest diff: {closest_diff}y)"
                            ),
                        })

    return {
        "checked": checked,
        "impossible": impossible,
        "suspicious": suspicious,
    }


def audit_people_count(
    date_labels: dict[str, dict],
    photos: dict[str, dict],
) -> dict:
    """Compare Gemini people_count vs detected face count for each photo.

    Args:
        date_labels: Dict of photo_id -> label entry.
        photos: Dict of photo_id -> photo entry from photo_index.json.

    Returns:
        Summary dict with potentially_missed list and checked count.
    """
    potentially_missed: list[dict] = []
    checked = 0

    for photo_id, label in date_labels.items():
        gemini_count = label.get("people_count")
        if gemini_count is None:
            continue

        photo = photos.get(photo_id)
        if not photo:
            continue

        face_ids = photo.get("face_ids", [])
        detected_count = len(face_ids)
        checked += 1

        if gemini_count > detected_count:
            diff = gemini_count - detected_count
            potentially_missed.append({
                "photo_id": photo_id,
                "gemini_count": gemini_count,
                "detected_count": detected_count,
                "diff": diff,
                "path": photo.get("path", ""),
                "detail": (
                    f"Gemini sees {gemini_count} people but only "
                    f"{detected_count} faces detected (missing {diff})"
                ),
            })

    # Sort by descending difference (most missed first)
    potentially_missed.sort(key=lambda x: x["diff"], reverse=True)

    return {
        "checked": checked,
        "potentially_missed": potentially_missed,
    }


def print_temporal_report(result: dict) -> None:
    """Print the temporal consistency report."""
    impossible = result["impossible"]
    suspicious = result["suspicious"]
    checked = result["checked"]

    print(f"\n{'=' * 60}")
    print(f"  {_bold('Temporal Consistency Audit')}")
    print(f"{'=' * 60}")
    print(f"  Identity-photo pairs checked: {checked}")

    # Impossible flags
    if impossible:
        print(f"\n  {_red(f'IMPOSSIBLE: {len(impossible)} flags')}")
        for flag in impossible:
            print(f"    {_red('X')} {flag['detail']}")
            print(f"      Photo: {flag['photo_id'][:16]}  Identity: {flag['identity_id'][:8]}")
    else:
        print(f"\n  {_green('IMPOSSIBLE: 0 flags')}")

    # Suspicious flags
    if suspicious:
        print(f"\n  {_yellow(f'SUSPICIOUS: {len(suspicious)} flags')}")
        for flag in suspicious:
            print(f"    {_yellow('?')} {flag['detail']}")
            print(f"      Photo: {flag['photo_id'][:16]}  Identity: {flag['identity_id'][:8]}")
    else:
        print(f"\n  {_green('SUSPICIOUS: 0 flags')}")

    print(f"{'=' * 60}")


def print_people_count_report(result: dict) -> None:
    """Print the people count discrepancy report."""
    potentially_missed = result["potentially_missed"]
    checked = result["checked"]

    print(f"\n{'=' * 60}")
    print(f"  {_bold('People Count Discrepancy Report')}")
    print(f"{'=' * 60}")
    print(f"  Photos with people_count checked: {checked}")

    if potentially_missed:
        print(f"\n  {_cyan(f'Potentially missed faces: {len(potentially_missed)} photos')}")
        print(f"  {'Photo ID':<20} {'Gemini':>7} {'Detected':>9} {'Missing':>8} Path")
        print(f"  {'-' * 70}")
        for entry in potentially_missed:
            pid = entry["photo_id"][:18]
            path = Path(entry["path"]).name if entry["path"] else "?"
            print(
                f"  {pid:<20} {entry['gemini_count']:>7} "
                f"{entry['detected_count']:>9} "
                f"{_yellow(str(entry['diff'])):>17} {path}"
            )
    else:
        print(f"\n  {_green('No people count discrepancies found.')}")

    print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(
        description="Audit temporal consistency between photo dates and identity metadata",
    )
    parser.add_argument(
        "--date-labels",
        type=str,
        default=str(DEFAULT_DATE_LABELS),
        help=f"Path to date_labels.json (default: {DEFAULT_DATE_LABELS})",
    )
    parser.add_argument(
        "--identities",
        type=str,
        default=str(DEFAULT_IDENTITIES),
        help=f"Path to identities.json (default: {DEFAULT_IDENTITIES})",
    )
    parser.add_argument(
        "--photo-index",
        type=str,
        default=str(DEFAULT_PHOTO_INDEX),
        help=f"Path to photo_index.json (default: {DEFAULT_PHOTO_INDEX})",
    )
    parser.add_argument(
        "--age-threshold",
        type=int,
        default=AGE_DISCREPANCY_THRESHOLD,
        help=f"Max acceptable age discrepancy in years (default: {AGE_DISCREPANCY_THRESHOLD})",
    )
    args = parser.parse_args()

    print(_bold("Loading data files..."))

    # Load all data
    date_labels = load_date_labels(args.date_labels)
    if not date_labels:
        print(_red("No date labels found. Exiting."))
        sys.exit(1)
    print(f"  Date labels: {len(date_labels)}")

    identities = load_identities(args.identities)
    if not identities:
        print(_red("No identities found. Exiting."))
        sys.exit(1)
    print(f"  Identities: {len(identities)}")

    photos, face_to_photo = load_photo_index(args.photo_index)
    if not photos:
        print(_red("No photos found. Exiting."))
        sys.exit(1)
    print(f"  Photos: {len(photos)}")
    print(f"  Face-to-photo mappings: {len(face_to_photo)}")

    # Count identities with temporal metadata
    with_birth = sum(
        1 for i in identities.values()
        if i.get("metadata", {}).get("birth_year") is not None
        and not i.get("merged_into")
    )
    with_death = sum(
        1 for i in identities.values()
        if i.get("metadata", {}).get("death_year") is not None
        and not i.get("merged_into")
    )
    print(f"  Identities with birth_year: {with_birth}")
    print(f"  Identities with death_year: {with_death}")

    # Run temporal audit
    temporal_result = audit_temporal_consistency(
        date_labels, identities, face_to_photo,
        age_threshold=args.age_threshold,
    )
    print_temporal_report(temporal_result)

    # Run people count audit
    people_result = audit_people_count(date_labels, photos)
    print_people_count_report(people_result)

    # Summary
    total_flags = (
        len(temporal_result["impossible"])
        + len(temporal_result["suspicious"])
        + len(people_result["potentially_missed"])
    )
    if total_flags == 0:
        print(_green(f"\nAll checks passed. No issues found."))
    else:
        print(_yellow(
            f"\nTotal flags: {total_flags} "
            f"({len(temporal_result['impossible'])} impossible, "
            f"{len(temporal_result['suspicious'])} suspicious, "
            f"{len(people_result['potentially_missed'])} missed faces)"
        ))

    sys.exit(1 if temporal_result["impossible"] else 0)


if __name__ == "__main__":
    main()
