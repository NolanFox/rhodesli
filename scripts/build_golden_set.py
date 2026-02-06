#!/usr/bin/env python3
"""Build golden set from confirmed identities.

Extracts face-to-identity mappings from CONFIRMED identities where
a human has verified the match. This is the ground truth for evaluating
ML clustering accuracy.

Only includes non-merged identities with at least one face. Faces come
from both anchor_ids and candidate_ids (in practice, all current data
uses candidate_ids for confirmed faces).

Usage:
    python scripts/build_golden_set.py --dry-run
    python scripts/build_golden_set.py --execute
"""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path for core imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def load_identities(data_path: Path) -> dict:
    """Load identities.json and return the raw data."""
    identities_path = data_path / "identities.json"
    if not identities_path.exists():
        raise FileNotFoundError(f"Identities not found: {identities_path}")

    with open(identities_path) as f:
        return json.load(f)


def extract_face_ids(identity: dict) -> list[str]:
    """Extract all face IDs from an identity (anchors + candidates).

    Handles both string and dict anchor formats.
    """
    face_ids = []

    for anchor in identity.get("anchor_ids", []):
        if isinstance(anchor, str):
            face_ids.append(anchor)
        elif isinstance(anchor, dict):
            face_ids.append(anchor["face_id"])

    face_ids.extend(identity.get("candidate_ids", []))

    return face_ids


def build_golden_set(data_path: Path) -> dict:
    """Build the golden set from confirmed identities.

    Returns the golden set data structure.
    """
    data = load_identities(data_path)
    identities = data.get("identities", {})

    mappings = []
    unique_identities = set()
    unique_photos = set()

    for identity_id, identity in identities.items():
        # Only CONFIRMED identities
        if identity.get("state") != "CONFIRMED":
            continue

        # Skip merged identities
        if identity.get("merged_into"):
            continue

        face_ids = extract_face_ids(identity)
        if not face_ids:
            continue

        identity_name = identity.get("name", f"Unknown ({identity_id[:8]})")

        for face_id in face_ids:
            # Determine source type
            anchor_ids_flat = []
            for anchor in identity.get("anchor_ids", []):
                if isinstance(anchor, str):
                    anchor_ids_flat.append(anchor)
                elif isinstance(anchor, dict):
                    anchor_ids_flat.append(anchor["face_id"])

            if face_id in anchor_ids_flat:
                source = "confirmed_anchor"
            else:
                source = "confirmed_candidate"

            mappings.append({
                "face_id": face_id,
                "identity_id": identity_id,
                "identity_name": identity_name,
                "source": source,
            })

            unique_identities.add(identity_id)

            # Extract photo from face_id (everything before :faceN)
            if ":" in face_id:
                photo_stem = face_id.rsplit(":", 1)[0]
                unique_photos.add(photo_stem)

    golden_set = {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "description": "Ground truth face-to-identity mappings from confirmed identities",
        "mappings": mappings,
        "stats": {
            "total_mappings": len(mappings),
            "unique_identities": len(unique_identities),
            "unique_photos": len(unique_photos),
        },
    }

    return golden_set


def main():
    parser = argparse.ArgumentParser(
        description="Build golden set from confirmed identities."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview what would be generated (default)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually write the golden set file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path (default: data/golden_set.json)",
    )
    args = parser.parse_args()

    data_path = project_root / "data"
    output_path = args.output or (data_path / "golden_set.json")

    if args.execute:
        args.dry_run = False

    print("=" * 60)
    print("BUILD GOLDEN SET")
    print("=" * 60)
    print(f"Data path: {data_path}")
    print(f"Output path: {output_path}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'EXECUTE'}")
    print()

    # Build golden set
    golden_set = build_golden_set(data_path)
    stats = golden_set["stats"]

    print(f"Total mappings: {stats['total_mappings']}")
    print(f"Unique identities: {stats['unique_identities']}")
    print(f"Unique photos: {stats['unique_photos']}")
    print()

    # Show identity breakdown
    identity_counts = {}
    for mapping in golden_set["mappings"]:
        name = mapping["identity_name"]
        identity_counts[name] = identity_counts.get(name, 0) + 1

    print("Identity breakdown:")
    for name, count in sorted(identity_counts.items(), key=lambda x: -x[1]):
        print(f"  {name}: {count} faces")
    print()

    if args.dry_run:
        print("[DRY RUN] Would write golden set to:")
        print(f"  {output_path}")
        print()
        print("Run with --execute to write the file.")
    else:
        # Atomic write: temp file + rename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fd, temp_path = tempfile.mkstemp(
            suffix=".json",
            dir=output_path.parent,
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(golden_set, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.rename(temp_path, output_path)
            print(f"Golden set written to: {output_path}")
        except Exception:
            # Clean up temp file on failure
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    return golden_set


if __name__ == "__main__":
    main()
