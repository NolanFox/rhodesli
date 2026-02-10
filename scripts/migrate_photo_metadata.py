#!/usr/bin/env python3
"""
Migrate photo_index.json to add separate collection and source_url fields.

Currently, the `source` field does double duty as both provenance (where the photo
came from) and classification (how the archive organizes it). This migration:

1. Keeps existing `source` values unchanged (provenance/origin)
2. Copies `source` → `collection` for initial classification
3. Adds `source_url: ""` for citation links

Usage:
    python scripts/migrate_photo_metadata.py --dry-run    # Preview changes
    python scripts/migrate_photo_metadata.py --execute    # Apply changes
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "photo_index.json"


def migrate(dry_run: bool = True) -> dict:
    """Run the migration. Returns stats dict."""
    with open(DATA_PATH) as f:
        data = json.load(f)

    photos = data.get("photos", {})
    stats = {
        "total": len(photos),
        "collection_added": 0,
        "source_url_added": 0,
        "already_had_collection": 0,
        "already_had_source_url": 0,
    }

    for photo_id, photo in photos.items():
        # Add collection from source if missing
        if "collection" not in photo or not photo["collection"]:
            source = photo.get("source", "")
            photo["collection"] = source or "Uncategorized"
            stats["collection_added"] += 1
            if not dry_run:
                pass  # Will be written below
            else:
                print(f"  + collection: {photo_id[:12]}... → \"{photo['collection']}\"")
        else:
            stats["already_had_collection"] += 1

        # Add source_url if missing
        if "source_url" not in photo:
            photo["source_url"] = ""
            stats["source_url_added"] += 1
        else:
            stats["already_had_source_url"] += 1

    print(f"\nMigration summary:")
    print(f"  Total photos: {stats['total']}")
    print(f"  Collection added: {stats['collection_added']}")
    print(f"  Already had collection: {stats['already_had_collection']}")
    print(f"  Source URL added: {stats['source_url_added']}")
    print(f"  Already had source_url: {stats['already_had_source_url']}")

    if not dry_run:
        with open(DATA_PATH, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\n  Written to {DATA_PATH}")
    else:
        print(f"\n  DRY RUN — no changes written. Use --execute to apply.")

    return stats


def main():
    if "--execute" in sys.argv:
        migrate(dry_run=False)
    elif "--dry-run" in sys.argv or len(sys.argv) == 1:
        migrate(dry_run=True)
    else:
        print("Usage: python scripts/migrate_photo_metadata.py [--dry-run|--execute]")
        sys.exit(1)


if __name__ == "__main__":
    main()
