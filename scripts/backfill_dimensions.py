"""
Backfill missing width/height dimensions in photo_index.json.

Photos without dimensions don't get face overlay boxes in the UI
(critical for R2/production mode where filesystem is unavailable).

Usage:
    python scripts/backfill_dimensions.py --dry-run     # Preview changes
    python scripts/backfill_dimensions.py --execute      # Apply changes
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure project root is on path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def backfill_dimensions(photo_index_path: Path, photos_dir: Path, dry_run: bool = True) -> int:
    """
    Read local image files to fill in missing width/height fields.

    Args:
        photo_index_path: Path to photo_index.json
        photos_dir: Path to raw_photos/ directory
        dry_run: If True, only print what would change

    Returns:
        Number of photos that were (or would be) updated
    """
    from PIL import Image

    with open(photo_index_path) as f:
        data = json.load(f)

    photos = data.get("photos", {})
    fixed = 0

    for pid, p in photos.items():
        if not isinstance(p, dict):
            continue
        if p.get("width") and p.get("height"):
            continue

        # Try to find the file locally
        path = p.get("path", "")
        basename = os.path.basename(path) if path else ""

        local_path = photos_dir / basename
        if not local_path.exists():
            print(f"  SKIP {pid}: file not found at {local_path}")
            continue

        try:
            with Image.open(local_path) as img:
                width, height = img.size
        except Exception as e:
            print(f"  ERROR {pid}: {e}")
            continue

        if dry_run:
            print(f"  WOULD FIX {pid}: {width}x{height} ({basename})")
        else:
            p["width"] = width
            p["height"] = height
            print(f"  FIXED {pid}: {width}x{height} ({basename})")

        fixed += 1

    if not dry_run and fixed > 0:
        with open(photo_index_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\nSaved {photo_index_path}")

    return fixed


def main():
    parser = argparse.ArgumentParser(description="Backfill photo dimensions")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview changes")
    group.add_argument("--execute", action="store_true", help="Apply changes")
    args = parser.parse_args()

    photo_index_path = project_root / "data" / "photo_index.json"
    photos_dir = project_root / "raw_photos"

    if not photo_index_path.exists():
        print(f"ERROR: {photo_index_path} not found")
        sys.exit(1)

    dry_run = not args.execute
    mode = "DRY RUN" if dry_run else "EXECUTING"
    print(f"Backfill dimensions ({mode})")
    print(f"  Photo index: {photo_index_path}")
    print(f"  Photos dir: {photos_dir}")
    print()

    fixed = backfill_dimensions(photo_index_path, photos_dir, dry_run=dry_run)

    print(f"\n{'Would fix' if dry_run else 'Fixed'} {fixed} photos")


if __name__ == "__main__":
    main()
