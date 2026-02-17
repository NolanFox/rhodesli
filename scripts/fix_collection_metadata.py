#!/usr/bin/env python3
"""Fix collection/source metadata for community photos.

Session 26 batch-ingested 116 photos as "Community Submissions" / "Community Contributions".
Only Claude Benatar's 2 photos should keep "Community Submissions".
The other 114 should be "Jews of Rhodes: Family Memories & Heritage" / "Facebook".

Usage:
    python scripts/fix_collection_metadata.py --dry-run   # Preview changes
    python scripts/fix_collection_metadata.py --execute    # Apply changes
"""

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PHOTO_INDEX = DATA_DIR / "photo_index.json"

TARGET_COLLECTION = "Jews of Rhodes: Family Memories & Heritage"
TARGET_SOURCE = "Facebook"

KEEP_COLLECTION = "Community Submissions"
KEEP_SOURCES = {"Claude Benatar"}  # These photos keep their current collection


def main():
    parser = argparse.ArgumentParser(description="Fix collection metadata for community photos")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview changes without modifying data")
    group.add_argument("--execute", action="store_true", help="Apply changes to photo_index.json")
    args = parser.parse_args()

    with open(PHOTO_INDEX, encoding="utf-8") as f:
        data = json.load(f)

    changes = []
    for pid, photo in data["photos"].items():
        if photo.get("collection") != "Community Submissions":
            continue
        if photo.get("source") in KEEP_SOURCES:
            continue

        changes.append({
            "photo_id": pid,
            "path": photo.get("path", ""),
            "old_collection": photo.get("collection", ""),
            "old_source": photo.get("source", ""),
            "new_collection": TARGET_COLLECTION,
            "new_source": TARGET_SOURCE,
        })

    print(f"Photos to reassign: {len(changes)}")
    print(f"  From: collection='Community Submissions', source='Community Contributions'")
    print(f"  To:   collection='{TARGET_COLLECTION}', source='{TARGET_SOURCE}'")
    print()

    for c in changes[:5]:
        print(f"  {c['photo_id']}: {c['path']}")
    if len(changes) > 5:
        print(f"  ... and {len(changes) - 5} more")

    if args.dry_run:
        print("\n[DRY RUN] No changes made.")
        return

    # Create backup
    backup_path = PHOTO_INDEX.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    shutil.copy2(PHOTO_INDEX, backup_path)
    print(f"\nBackup created: {backup_path}")

    # Apply changes
    for c in changes:
        pid = c["photo_id"]
        data["photos"][pid]["collection"] = c["new_collection"]
        data["photos"][pid]["source"] = c["new_source"]

    with open(PHOTO_INDEX, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Updated {len(changes)} photos in {PHOTO_INDEX}")

    # Verify
    with open(PHOTO_INDEX, encoding="utf-8") as f:
        verify = json.load(f)
    from collections import Counter
    cols = Counter(p.get("collection", "") for p in verify["photos"].values())
    print("\nCollection counts after fix:")
    for col, count in cols.most_common():
        print(f"  {count:3d}  {col}")


if __name__ == "__main__":
    main()
