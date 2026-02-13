#!/usr/bin/env python3
"""Associate back images with front photos based on filename patterns.

Scans raw_photos/ for files matching a pattern (e.g., {name}_back.jpg) and
associates them with the corresponding front photo in photo_index.json.

Usage:
    python scripts/associate_backs.py                    # Dry run (default)
    python scripts/associate_backs.py --execute          # Actually update records
    python scripts/associate_backs.py --pattern custom   # Custom pattern
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Resolve paths
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.photo_registry import PhotoRegistry


def find_back_images(raw_photos_dir: Path, pattern: str = "default") -> list:
    """Find files that look like back images based on the pattern.

    Returns list of (back_filename, front_filename) tuples.
    """
    matches = []

    for f in sorted(raw_photos_dir.iterdir()):
        if not f.is_file():
            continue
        stem = f.stem
        ext = f.suffix.lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue

        # Check if filename ends with _back
        if stem.endswith("_back"):
            front_stem = stem[:-5]  # Remove "_back"
            # Look for matching front image with any supported extension
            for front_ext in [".jpg", ".jpeg", ".png", ".webp"]:
                front_file = raw_photos_dir / f"{front_stem}{front_ext}"
                if front_file.exists():
                    matches.append((f.name, front_file.name))
                    break
            else:
                # Also try the compress pattern
                for front_ext in [".jpg", ".jpeg", ".png", ".webp"]:
                    front_file = raw_photos_dir / f"{front_stem}_compress{front_ext}"
                    if front_file.exists():
                        matches.append((f.name, front_file.name))
                        break

    return matches


def main():
    parser = argparse.ArgumentParser(description="Associate back images with front photos")
    parser.add_argument("--execute", action="store_true", help="Actually update records (default: dry run)")
    parser.add_argument("--pattern", default="default", help="Filename pattern (default: {name}_back.{ext})")
    parser.add_argument("--dir", default="raw_photos", help="Directory to scan")
    args = parser.parse_args()

    raw_photos_dir = ROOT / args.dir
    if not raw_photos_dir.exists():
        print(f"Directory not found: {raw_photos_dir}")
        sys.exit(1)

    photo_index_path = ROOT / "data" / "photo_index.json"
    if not photo_index_path.exists():
        print(f"Photo index not found: {photo_index_path}")
        sys.exit(1)

    # Find matching back images
    matches = find_back_images(raw_photos_dir, args.pattern)

    if not matches:
        print("No back images found matching the pattern.")
        print(f"  Pattern: {{name}}_back.{{ext}}")
        print(f"  Directory: {raw_photos_dir}")
        sys.exit(0)

    print(f"Found {len(matches)} back image{'s' if len(matches) != 1 else ''}:\n")

    # Load photo registry
    registry = PhotoRegistry.load(photo_index_path)

    updated = 0
    for back_filename, front_filename in matches:
        # Find the photo ID for the front image
        photo_id = None
        for pid, photo in registry._photos.items():
            p = photo.get("path", photo.get("filename", ""))
            if Path(p).name == front_filename:
                photo_id = pid
                break

        if photo_id:
            existing_back = registry.get_metadata(photo_id).get("back_image", "")
            status = "ALREADY SET" if existing_back else "WILL SET"
            print(f"  {back_filename} -> {front_filename} (photo_id: {photo_id}) [{status}]")

            if args.execute and not existing_back:
                registry.set_metadata(photo_id, {"back_image": back_filename})
                updated += 1
        else:
            print(f"  {back_filename} -> {front_filename} (NOT FOUND in registry)")

    print()
    if args.execute:
        if updated > 0:
            registry.save(photo_index_path)
            print(f"Updated {updated} photo record{'s' if updated != 1 else ''}.")
        else:
            print("No records needed updating.")
    else:
        print("DRY RUN — no changes made. Use --execute to apply.")


if __name__ == "__main__":
    main()
