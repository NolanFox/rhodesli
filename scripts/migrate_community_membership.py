"""Migrate existing photos and identities to Rhodes community membership tables.

Creates photo_communities and identity_communities rows for all existing
photos and identities, tagging them with the Rhodes community.

Usage:
    python scripts/migrate_community_membership.py --dry-run
    python scripts/migrate_community_membership.py --execute
"""

import argparse
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def get_client():
    from app.supabase_data import get_supabase_client

    client = get_supabase_client()
    if not client:
        logger.error("Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        sys.exit(1)
    return client


def get_rhodes_community_id(client):
    result = client.table("communities").select("id").eq("slug", "rhodes").execute()
    if not result.data:
        logger.error("Rhodes community not found in communities table")
        sys.exit(1)
    return result.data[0]["id"]


def migrate_photos(client, community_id, dry_run=True):
    """Insert photo_communities rows for all existing photos."""
    # Get all photo IDs from photos table
    all_photos = []
    offset = 0
    page_size = 1000
    while True:
        result = client.table("photos").select("photo_id").range(offset, offset + page_size - 1).execute()
        if not result.data:
            break
        all_photos.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size

    photo_ids = [p["photo_id"] for p in all_photos]
    logger.info(f"Found {len(photo_ids)} photos to tag with Rhodes community")

    if dry_run:
        logger.info("[DRY RUN] Would insert %d photo_communities rows", len(photo_ids))
        return len(photo_ids)

    # Insert in batches
    inserted = 0
    batch_size = 100
    for i in range(0, len(photo_ids), batch_size):
        batch = photo_ids[i : i + batch_size]
        rows = [{"photo_id": pid, "community_id": community_id} for pid in batch]
        try:
            client.table("photo_communities").upsert(rows).execute()
            inserted += len(rows)
        except Exception as e:
            logger.warning(f"Batch insert failed at offset {i}: {e}")

    logger.info(f"Inserted {inserted} photo_communities rows")
    return inserted


def migrate_identities(client, community_id, dry_run=True):
    """Insert identity_communities rows for all existing identities."""
    all_identities = []
    offset = 0
    page_size = 1000
    while True:
        result = client.table("identities").select("identity_id").range(offset, offset + page_size - 1).execute()
        if not result.data:
            break
        all_identities.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size

    identity_ids = [i["identity_id"] for i in all_identities]
    logger.info(f"Found {len(identity_ids)} identities to tag with Rhodes community")

    if dry_run:
        logger.info("[DRY RUN] Would insert %d identity_communities rows", len(identity_ids))
        return len(identity_ids)

    # Insert in batches
    inserted = 0
    batch_size = 100
    for i in range(0, len(identity_ids), batch_size):
        batch = identity_ids[i : i + batch_size]
        rows = [{"identity_id": iid, "community_id": community_id, "is_primary": True} for iid in batch]
        try:
            client.table("identity_communities").upsert(rows).execute()
            inserted += len(rows)
        except Exception as e:
            logger.warning(f"Batch insert failed at offset {i}: {e}")

    logger.info(f"Inserted {inserted} identity_communities rows")
    return inserted


def main():
    parser = argparse.ArgumentParser(description="Migrate existing data to Rhodes community")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview without changes")
    group.add_argument("--execute", action="store_true", help="Execute migration")
    args = parser.parse_args()

    client = get_client()
    community_id = get_rhodes_community_id(client)
    logger.info(f"Rhodes community ID: {community_id}")

    dry_run = args.dry_run
    photo_count = migrate_photos(client, community_id, dry_run=dry_run)
    identity_count = migrate_identities(client, community_id, dry_run=dry_run)

    logger.info(
        f"{'[DRY RUN] ' if dry_run else ''}Migration complete: {photo_count} photos, {identity_count} identities"
    )


if __name__ == "__main__":
    main()
