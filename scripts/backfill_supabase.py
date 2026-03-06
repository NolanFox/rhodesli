#!/usr/bin/env python3
"""Backfill Supabase shadow tables from JSON source files.

Reads photo_index.json and identities.json, then batch-upserts
all records into the corresponding Supabase tables.

Usage:
    python scripts/backfill_supabase.py --dry-run    # Preview only
    python scripts/backfill_supabase.py --execute     # Actually write

Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY env vars.
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def load_photo_index(data_dir: Path) -> dict:
    """Load photo_index.json and return photos dict with photo_id injected."""
    path = data_dir / "photo_index.json"
    if not path.exists():
        print(f"  [SKIP] {path} not found")
        return {}
    with open(path) as f:
        data = json.load(f)
    photos = data.get("photos", {})
    # Inject photo_id into each record
    for photo_id, photo_data in photos.items():
        photo_data["photo_id"] = photo_id
    return photos


def load_identities(data_dir: Path) -> dict:
    """Load identities.json and return identities dict with identity_id injected."""
    path = data_dir / "identities.json"
    if not path.exists():
        print(f"  [SKIP] {path} not found")
        return {}
    with open(path) as f:
        data = json.load(f)
    identities = data.get("identities", {})
    # Inject identity_id into each record
    for identity_id, identity_data in identities.items():
        identity_data["identity_id"] = identity_id
    return identities


def main():
    parser = argparse.ArgumentParser(description="Backfill Supabase shadow tables from JSON")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview without writing")
    group.add_argument("--execute", action="store_true", help="Actually write to Supabase")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=project_root / "data",
        help="Path to data directory (default: data/)",
    )
    args = parser.parse_args()

    data_dir = args.data_dir
    print(f"Data directory: {data_dir}")

    # Load data
    print("\n--- Loading photo_index.json ---")
    photos = load_photo_index(data_dir)
    print(f"  Found {len(photos)} photos")

    print("\n--- Loading identities.json ---")
    identities = load_identities(data_dir)
    print(f"  Found {len(identities)} identities")

    if args.dry_run:
        print("\n--- DRY RUN ---")
        print(f"  Would upsert {len(photos)} photos to Supabase 'photos' table")
        print(f"  Would upsert {len(identities)} identities to Supabase 'identities' table")

        # Show sample data
        if photos:
            sample_id = next(iter(photos))
            sample = photos[sample_id]
            print(f"\n  Sample photo ({sample_id}):")
            print(f"    path: {sample.get('path', 'N/A')}")
            print(f"    collection: {sample.get('collection', 'N/A')}")
            print(f"    face_ids: {len(sample.get('face_ids', []))} faces")

        if identities:
            sample_id = next(iter(identities))
            sample = identities[sample_id]
            print(f"\n  Sample identity ({sample_id}):")
            print(f"    name: {sample.get('name', 'N/A')}")
            print(f"    state: {sample.get('state', 'N/A')}")
            print(f"    anchors: {len(sample.get('anchor_ids', []))}")

        print("\nRun with --execute to write to Supabase.")
        return

    # Execute
    from app.supabase_data import shadow_write_identities_batch, shadow_write_photos_batch

    print("\n--- Writing photos to Supabase ---")
    photos_list = list(photos.values())
    photo_count = shadow_write_photos_batch(photos_list)
    print(f"  Wrote {photo_count}/{len(photos_list)} photos")

    print("\n--- Writing identities to Supabase ---")
    identities_list = list(identities.values())
    identity_count = shadow_write_identities_batch(identities_list)
    print(f"  Wrote {identity_count}/{len(identities_list)} identities")

    print("\n--- Backfill complete ---")
    print(f"  Photos: {photo_count}")
    print(f"  Identities: {identity_count}")


if __name__ == "__main__":
    main()
