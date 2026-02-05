"""
Add source attribution to existing photos.

Usage:
  python scripts/migrate_photo_sources.py --dry-run   # Preview changes (default)
  python scripts/migrate_photo_sources.py --execute   # Apply changes

This script classifies existing photos based on filename and path patterns,
then updates their source field in photo_index.json.
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# Classification rules for existing files
# Each rule has a match function and a source label
SOURCE_RULES = [
    # data/uploads/b5e8a89e/* → Betty Capeluto Miami Collection
    {
        "match": lambda path, filename: "b5e8a89e" in str(path),
        "source": "Betty Capeluto Miami Collection"
    },
    # Image NNN_compress* → Vida Capeluto NYC Collection
    {
        "match": lambda path, filename: re.match(r"Image \d+_compress", filename),
        "source": "Vida Capeluto NYC Collection"
    },
    # Brass_Rail_Restaurant* → Newspapers.com
    {
        "match": lambda path, filename: "Brass_Rail" in filename,
        "source": "Newspapers.com"
    },
    # 603569530.803296* → Betty Capeluto Miami Collection
    {
        "match": lambda path, filename: filename.startswith("603569530"),
        "source": "Betty Capeluto Miami Collection"
    },
    # 596771324.500867* or 757557325.971675* → Nace Capeluto Tampa Collection
    {
        "match": lambda path, filename: (
            filename.startswith("596771324") or filename.startswith("757557325")
        ),
        "source": "Nace Capeluto Tampa Collection"
    },
]


def classify_photo(path: str, filename: str) -> str:
    """Determine source for a photo based on path and filename."""
    for rule in SOURCE_RULES:
        if rule["match"](path, filename):
            return rule["source"]
    return ""  # Unknown source


def migrate(dry_run: bool = True) -> None:
    """
    Run the migration to add source attribution to photos.

    Args:
        dry_run: If True, show changes without applying. If False, apply changes.
    """
    project_root = Path(__file__).resolve().parent.parent
    photo_index_path = project_root / "data" / "photo_index.json"

    if not photo_index_path.exists():
        print(f"ERROR: {photo_index_path} does not exist")
        sys.exit(1)

    with open(photo_index_path) as f:
        data = json.load(f)

    if data.get("schema_version") != 1:
        print(f"ERROR: Unexpected schema version: {data.get('schema_version')}")
        sys.exit(1)

    photos = data.get("photos", {})

    changes = []
    already_have_source = []
    unclassified = []

    for photo_id, photo in photos.items():
        path = photo.get("path", "")
        # Extract filename from path
        filename = Path(path).name if path else ""

        current_source = photo.get("source", "")
        if current_source:
            already_have_source.append({
                "id": photo_id,
                "filename": filename,
                "source": current_source
            })
            continue

        new_source = classify_photo(path, filename)
        if new_source:
            changes.append({
                "id": photo_id,
                "filename": filename,
                "source": new_source
            })
            if not dry_run:
                photo["source"] = new_source
        else:
            unclassified.append({
                "id": photo_id,
                "filename": filename
            })

    # Report
    print(f"\n{'DRY RUN' if dry_run else 'EXECUTING'}")
    print("=" * 60)
    print(f"Total photos: {len(photos)}")
    print(f"Will classify: {len(changes)}")
    print(f"Already have source: {len(already_have_source)}")
    print(f"Unclassified: {len(unclassified)}")

    print(f"\nClassifications:")
    sources = Counter(c["source"] for c in changes)
    for source, count in sources.most_common():
        print(f"  {source}: {count} photos")

    if changes:
        print(f"\nSample changes:")
        for c in changes[:10]:
            print(f"  {c['filename'][:45]:45s} -> {c['source']}")
        if len(changes) > 10:
            print(f"  ... and {len(changes) - 10} more")

    if unclassified:
        print(f"\nUnclassified photos ({len(unclassified)}):")
        for u in unclassified[:10]:
            print(f"  {u['filename']}")
        if len(unclassified) > 10:
            print(f"  ... and {len(unclassified) - 10} more")

    if not dry_run:
        # Ensure all photos have the source field (even if empty)
        for photo_id, photo in photos.items():
            if "source" not in photo:
                photo["source"] = ""

        with open(photo_index_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\n✓ Migration applied to {photo_index_path}")
    else:
        print(f"\nDry run complete. Use --execute to apply changes.")


def main():
    parser = argparse.ArgumentParser(
        description="Add source attribution to existing photos"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply changes (default: dry-run)"
    )
    args = parser.parse_args()

    migrate(dry_run=not args.execute)


if __name__ == "__main__":
    main()
