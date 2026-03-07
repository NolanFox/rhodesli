#!/usr/bin/env python3
"""
Backup critical data files to Cloudflare R2.

Uploads identities.json, photo_index.json, embeddings.npy, date_labels.json,
and photo_locations.json to r2://rhodesli-photos/backups/YYYY-MM-DD/.

Prunes backups older than 30 days (keeps max 30 snapshots).

Usage:
    # Preview what would be uploaded (default)
    python scripts/backup_to_r2.py --dry-run

    # Actually upload
    python scripts/backup_to_r2.py

    # Custom data directory (e.g., Railway volume)
    python scripts/backup_to_r2.py --data-dir /data

Required environment variables:
    R2_ACCOUNT_ID        - Cloudflare account ID
    R2_ACCESS_KEY_ID     - R2 API token access key
    R2_SECRET_ACCESS_KEY - R2 API token secret
    R2_BUCKET_NAME       - Name of the R2 bucket

Optional:
    DATA_DIR             - Path to data directory (default: data/)
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Files to back up (relative to data directory)
BACKUP_FILES = [
    "identities.json",
    "photo_index.json",
    "embeddings.npy",
    "date_labels.json",
    "photo_locations.json",
]

MAX_BACKUP_AGE_DAYS = 30


def get_r2_client():
    """Create boto3 client for R2."""
    try:
        import boto3
    except ImportError:
        print("ERROR: boto3 is required. Install with: pip install boto3")
        sys.exit(1)

    account_id = os.getenv("R2_ACCOUNT_ID")
    access_key = os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")

    missing = []
    if not account_id:
        missing.append("R2_ACCOUNT_ID")
    if not access_key:
        missing.append("R2_ACCESS_KEY_ID")
    if not secret_key:
        missing.append("R2_SECRET_ACCESS_KEY")

    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")

    endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def get_bucket_name():
    """Get R2 bucket name from environment."""
    bucket_name = os.getenv("R2_BUCKET_NAME")
    if not bucket_name:
        raise EnvironmentError("Missing required environment variable: R2_BUCKET_NAME")
    return bucket_name


def backup_files(client, bucket: str, data_dir: Path, dry_run: bool) -> tuple[int, int]:
    """
    Upload data files to R2 under backups/YYYY-MM-DD/.

    Returns (success_count, skip_count).
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prefix = f"backups/{today}"

    success = 0
    skipped = 0

    for filename in BACKUP_FILES:
        filepath = data_dir / filename
        if not filepath.exists():
            print(f"  WARNING: {filename} not found in {data_dir}, skipping")
            skipped += 1
            continue

        r2_key = f"{prefix}/{filename}"
        size_kb = filepath.stat().st_size / 1024

        if dry_run:
            print(f"  [DRY-RUN] Would upload: {filename} ({size_kb:.1f} KB) -> {r2_key}")
            success += 1
            continue

        try:
            with open(filepath, "rb") as f:
                client.put_object(
                    Bucket=bucket,
                    Key=r2_key,
                    Body=f,
                )
            print(f"  Uploaded: {filename} ({size_kb:.1f} KB) -> {r2_key}")
            success += 1
        except Exception as e:
            print(f"  ERROR uploading {filename}: {e}")

    return success, skipped


def list_backup_dates(client, bucket: str) -> list[str]:
    """
    List all backup dates in R2 (YYYY-MM-DD format).

    Returns sorted list of date strings.
    """
    dates = set()
    paginator = client.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix="backups/", Delimiter="/"):
        for prefix_info in page.get("CommonPrefixes", []):
            # prefix_info["Prefix"] is like "backups/2026-03-07/"
            prefix = prefix_info["Prefix"]
            parts = prefix.strip("/").split("/")
            if len(parts) == 2:
                dates.add(parts[1])

    return sorted(dates)


def prune_old_backups(client, bucket: str, dry_run: bool) -> int:
    """
    Delete backups older than MAX_BACKUP_AGE_DAYS.

    Returns count of dates pruned.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=MAX_BACKUP_AGE_DAYS)).strftime("%Y-%m-%d")
    dates = list_backup_dates(client, bucket)
    pruned = 0

    for date_str in dates:
        if date_str < cutoff:
            if dry_run:
                print(f"  [DRY-RUN] Would prune backup: {date_str}")
                pruned += 1
                continue

            # List all objects under this date prefix
            prefix = f"backups/{date_str}/"
            paginator = client.get_paginator("list_objects_v2")
            objects_to_delete = []

            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    objects_to_delete.append({"Key": obj["Key"]})

            if objects_to_delete:
                # Delete in batches of 1000 (S3/R2 limit)
                for i in range(0, len(objects_to_delete), 1000):
                    batch = objects_to_delete[i : i + 1000]
                    client.delete_objects(
                        Bucket=bucket,
                        Delete={"Objects": batch},
                    )
                print(f"  Pruned backup: {date_str} ({len(objects_to_delete)} files)")
                pruned += 1

    return pruned


def main():
    parser = argparse.ArgumentParser(description="Backup critical data files to Cloudflare R2")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview what would be uploaded without making changes",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Path to data directory (default: DATA_DIR env var or data/)",
    )

    args = parser.parse_args()
    dry_run = args.dry_run

    # Resolve data directory
    data_dir_str = args.data_dir or os.getenv("DATA_DIR", "data/")
    data_dir = Path(data_dir_str)
    if not data_dir.is_absolute():
        data_dir = project_root / data_dir

    print(f"Data directory: {data_dir}")
    print(f"Mode: {'DRY-RUN' if dry_run else 'EXECUTE'}")
    print()

    try:
        bucket = get_bucket_name()
        client = get_r2_client()
    except EnvironmentError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Backup
    print("Backing up files...")
    success, skipped = backup_files(client, bucket, data_dir, dry_run)
    print(f"\nBackup: {success} uploaded, {skipped} skipped")

    # Prune
    print("\nChecking for old backups to prune...")
    pruned = prune_old_backups(client, bucket, dry_run)
    if pruned:
        print(f"Pruned {pruned} old backup(s)")
    else:
        print("No old backups to prune")

    print("\nDone.")


if __name__ == "__main__":
    main()
