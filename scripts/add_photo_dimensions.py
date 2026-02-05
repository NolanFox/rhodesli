#!/usr/bin/env python3
"""
Add image dimensions to photo_index.json.

In R2 mode, photos are stored in Cloudflare R2 and can't be read locally.
This script pre-computes dimensions and stores them in photo_index.json
so the web app can display photos without needing filesystem access.

Usage:
    python -m scripts.add_photo_dimensions --dry-run  # Preview changes
    python -m scripts.add_photo_dimensions --execute  # Apply changes
"""

import argparse
import json
from pathlib import Path

# Defer PIL import to avoid issues on servers without PIL
def get_image_dimensions(filepath: str) -> tuple[int, int]:
    """Get image dimensions from a file."""
    from PIL import Image
    try:
        with Image.open(filepath) as img:
            return img.size  # (width, height)
    except Exception as e:
        print(f"  WARNING: Could not read {filepath}: {e}")
        return (0, 0)


def main():
    parser = argparse.ArgumentParser(description="Add dimensions to photo_index.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without modifying files (default)")
    parser.add_argument("--execute", action="store_true",
                        help="Actually modify photo_index.json")
    args = parser.parse_args()

    # Default to dry-run if neither flag specified
    if not args.execute:
        args.dry_run = True

    data_dir = Path(__file__).resolve().parent.parent / "data"
    raw_photos_dir = Path(__file__).resolve().parent.parent / "raw_photos"
    uploads_dir = data_dir / "uploads"
    photo_index_path = data_dir / "photo_index.json"

    if not photo_index_path.exists():
        print(f"ERROR: photo_index.json not found at {photo_index_path}")
        return 1

    with open(photo_index_path, "r") as f:
        photo_index = json.load(f)

    photos = photo_index.get("photos", {})
    modified_count = 0
    skipped_count = 0
    missing_count = 0

    print(f"Processing {len(photos)} photos...")
    print()

    for photo_id, photo_data in photos.items():
        # Skip if already has dimensions
        if "width" in photo_data and "height" in photo_data:
            if photo_data["width"] > 0 and photo_data["height"] > 0:
                skipped_count += 1
                continue

        # Get the photo path
        photo_path = photo_data.get("path", "")
        if not photo_path:
            print(f"  WARNING: No path for photo {photo_id}")
            missing_count += 1
            continue

        # Try to find the file
        filepath = None

        # First, try the path as given (relative to project root)
        project_root = Path(__file__).resolve().parent.parent
        relative_path = project_root / photo_path
        if relative_path.exists():
            filepath = relative_path

        # Try in raw_photos directory
        if not filepath:
            filepath = raw_photos_dir / photo_path
            if not filepath.exists():
                filepath = raw_photos_dir / Path(photo_path).name
                if not filepath.exists():
                    filepath = None

        # Try in uploads directory (for inbox photos)
        if not filepath and "uploads" in photo_path:
            filepath = project_root / photo_path
            if not filepath.exists():
                filepath = None

        if not filepath or not filepath.exists():
            print(f"  WARNING: File not found for {photo_path}")
            missing_count += 1
            continue

        # Get dimensions
        width, height = get_image_dimensions(str(filepath))
        if width == 0 or height == 0:
            missing_count += 1
            continue

        if args.dry_run:
            print(f"  Would add: {photo_path} -> {width}x{height}")
        else:
            photo_data["width"] = width
            photo_data["height"] = height

        modified_count += 1

    print()
    print(f"Summary:")
    print(f"  Already had dimensions: {skipped_count}")
    print(f"  Would add dimensions: {modified_count}")
    print(f"  Missing/failed: {missing_count}")

    if args.dry_run:
        print()
        print("DRY RUN - No changes made.")
        print("Run with --execute to apply changes.")
    else:
        # Write back
        with open(photo_index_path, "w") as f:
            json.dump(photo_index, f, indent=2)
        print()
        print(f"Updated {photo_index_path}")

    return 0


if __name__ == "__main__":
    exit(main())
