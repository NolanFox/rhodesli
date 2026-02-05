"""
Convert absolute paths in photo_index.json to relative paths.

This fixes the issue where inbox uploads were stored with absolute paths
like /Users/nolanfox/rhodesli/data/uploads/... which don't exist in Docker.

Usage:
    python scripts/fix_absolute_paths.py --dry-run   # Preview changes
    python scripts/fix_absolute_paths.py --execute   # Apply changes
"""

import argparse
import json
import shutil
from pathlib import Path

# Project root is parent of scripts/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PHOTO_INDEX_PATH = DATA_DIR / "photo_index.json"


def find_absolute_paths(data: dict) -> list[tuple[str, str, str]]:
    """
    Find all absolute paths in the photo index.

    Returns:
        List of (photo_id, key, absolute_path) tuples
    """
    absolute_paths = []

    for photo_id, photo_data in data.get("photos", {}).items():
        for key, value in photo_data.items():
            if isinstance(value, str) and value.startswith("/Users"):
                absolute_paths.append((photo_id, key, value))

    return absolute_paths


def convert_to_relative(absolute_path: str, project_root: str) -> str:
    """
    Convert an absolute path to a relative path.

    Example:
        /Users/nolanfox/rhodesli/data/uploads/... -> data/uploads/...
    """
    prefix = project_root.rstrip("/") + "/"
    if absolute_path.startswith(prefix):
        return absolute_path[len(prefix):]

    # If it doesn't match our expected prefix, return as-is
    return absolute_path


def check_file_exists(relative_path: str) -> bool:
    """Check if a file exists at the relative path from project root."""
    full_path = PROJECT_ROOT / relative_path
    return full_path.exists()


def main():
    parser = argparse.ArgumentParser(
        description="Convert absolute paths in photo_index.json to relative paths"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview changes without modifying")
    group.add_argument("--execute", action="store_true", help="Apply changes")
    args = parser.parse_args()

    if not PHOTO_INDEX_PATH.exists():
        print(f"ERROR: {PHOTO_INDEX_PATH} does not exist")
        return 1

    # Load the data
    with open(PHOTO_INDEX_PATH) as f:
        data = json.load(f)

    # Find absolute paths
    absolute_paths = find_absolute_paths(data)

    if not absolute_paths:
        print("No absolute paths found. Nothing to do.")
        return 0

    print(f"Found {len(absolute_paths)} absolute paths to convert:\n")

    # Determine the project root prefix from the first path
    # Expected: /Users/nolanfox/rhodesli/...
    first_path = absolute_paths[0][2]
    project_root_prefix = str(PROJECT_ROOT)

    # Show what will be changed
    changes = []
    missing_files = []

    for photo_id, key, abs_path in absolute_paths:
        rel_path = convert_to_relative(abs_path, project_root_prefix)
        exists = check_file_exists(rel_path)

        changes.append((photo_id, key, abs_path, rel_path, exists))

        print(f"  {photo_id}")
        print(f"    OLD: {abs_path}")
        print(f"    NEW: {rel_path}")
        print(f"    EXISTS: {'YES' if exists else 'NO (file missing)'}")
        print()

        if not exists:
            missing_files.append(rel_path)

    print("-" * 60)
    print(f"Summary: {len(changes)} paths to convert")
    if missing_files:
        print(f"WARNING: {len(missing_files)} files do not exist at the new paths:")
        for mf in missing_files[:5]:
            print(f"  - {mf}")
        if len(missing_files) > 5:
            print(f"  ... and {len(missing_files) - 5} more")

    if args.dry_run:
        print("\n[DRY RUN] No changes made. Use --execute to apply.")
        return 0

    # Execute the changes
    print("\n[EXECUTE] Applying changes...")

    # Create backup
    backup_path = PHOTO_INDEX_PATH.with_suffix(".json.bak")
    shutil.copy2(PHOTO_INDEX_PATH, backup_path)
    print(f"Created backup: {backup_path}")

    # Apply changes
    for photo_id, key, abs_path, rel_path, exists in changes:
        data["photos"][photo_id][key] = rel_path

    # Write updated data
    with open(PHOTO_INDEX_PATH, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Updated {PHOTO_INDEX_PATH}")
    print(f"\nSuccessfully converted {len(changes)} absolute paths to relative paths.")

    if missing_files:
        print(f"\nNOTE: {len(missing_files)} files are still missing. These may need to be re-uploaded.")

    return 0


if __name__ == "__main__":
    exit(main())
