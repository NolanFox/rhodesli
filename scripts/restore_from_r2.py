#!/usr/bin/env python3
"""
Restore data files from Cloudflare R2 backup.

Lists available backup dates and restores a specific backup to the data directory.

Usage:
    # List available backups
    python scripts/restore_from_r2.py --list

    # Restore a specific backup
    python scripts/restore_from_r2.py --date 2026-03-07

    # Restore without confirmation prompt
    python scripts/restore_from_r2.py --date 2026-03-07 --yes

    # Restore to custom directory
    python scripts/restore_from_r2.py --date 2026-03-07 --data-dir /data

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
from pathlib import Path

# Add project root for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Reuse R2 client setup from backup script
from scripts.backup_to_r2 import get_bucket_name, get_r2_client, list_backup_dates


def restore_backup(client, bucket: str, date_str: str, data_dir: Path) -> int:
    """
    Download all files from a backup date to the data directory.

    Returns count of files restored.
    """
    prefix = f"backups/{date_str}/"
    paginator = client.get_paginator("list_objects_v2")
    restored = 0

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            # Extract filename from key (e.g., "backups/2026-03-07/identities.json" -> "identities.json")
            filename = key.split("/")[-1]
            if not filename:
                continue

            dest = data_dir / filename
            size_kb = obj["Size"] / 1024

            try:
                response = client.get_object(Bucket=bucket, Key=key)
                data_dir.mkdir(parents=True, exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(response["Body"].read())
                print(f"  Restored: {filename} ({size_kb:.1f} KB) -> {dest}")
                restored += 1
            except Exception as e:
                print(f"  ERROR restoring {filename}: {e}")

    return restored


def main():
    parser = argparse.ArgumentParser(description="Restore data files from Cloudflare R2 backup")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available backup dates without restoring",
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Backup date to restore (YYYY-MM-DD format)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Path to data directory (default: DATA_DIR env var or data/)",
    )

    args = parser.parse_args()

    if not args.list and not args.date:
        parser.error("Either --list or --date is required")

    try:
        bucket = get_bucket_name()
        client = get_r2_client()
    except EnvironmentError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    if args.list:
        dates = list_backup_dates(client, bucket)
        if not dates:
            print("No backups found.")
        else:
            print(f"Available backups ({len(dates)}):")
            for d in dates:
                print(f"  {d}")
        return

    # Restore mode
    date_str = args.date

    # Verify backup exists
    dates = list_backup_dates(client, bucket)
    if date_str not in dates:
        print(f"ERROR: No backup found for date {date_str}")
        if dates:
            print(f"Available dates: {', '.join(dates[-5:])}")
        sys.exit(1)

    # Resolve data directory
    data_dir_str = args.data_dir or os.getenv("DATA_DIR", "data/")
    data_dir = Path(data_dir_str)
    if not data_dir.is_absolute():
        data_dir = project_root / data_dir

    print(f"Restoring backup from {date_str} to {data_dir}")

    if not args.yes:
        confirm = input("This will overwrite existing files. Continue? [y/N] ")
        if confirm.lower() != "y":
            print("Aborted.")
            return

    restored = restore_backup(client, bucket, date_str, data_dir)
    print(f"\nRestored {restored} file(s).")


if __name__ == "__main__":
    main()
