"""
Backup critical Railway volume data files to Cloudflare R2.

Uploads data files to R2 under backups/YYYY-MM-DD/ prefix.
Keeps last 7 days of backups, pruning older ones.

Can be called from Railway startup or cron.
Dry-run by default; pass --execute to actually upload.

Usage:
    python scripts/backup_volume_to_r2.py           # dry-run
    python scripts/backup_volume_to_r2.py --execute  # upload for real
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.storage import (
    R2_BUCKET_NAME,
    _get_r2_client,
    can_write_r2,
)

logger = logging.getLogger(__name__)

# Storage configuration (mirrors init_railway_volume.py)
STORAGE_DIR = os.getenv("STORAGE_DIR")
if STORAGE_DIR:
    DATA_DIR = Path(os.path.join(STORAGE_DIR, "data"))
else:
    DATA_DIR = Path(os.getenv("DATA_DIR", "data"))

# Files to back up — critical data that lives on the Railway volume
BACKUP_FILES = [
    "identities.json",
    "photo_index.json",
    "embeddings.npy",
    "date_labels.json",
    "photo_locations.json",
]

# R2 prefix for backups
BACKUP_PREFIX = "backups"

# Number of days of backups to keep
RETENTION_DAYS = 7


def get_backup_key(date_str: str, filename: str) -> str:
    """Generate R2 object key for a backup file.

    Args:
        date_str: Date string in YYYY-MM-DD format
        filename: Name of the file being backed up

    Returns:
        R2 key like "backups/2026-03-05/identities.json"
    """
    return f"{BACKUP_PREFIX}/{date_str}/{filename}"


def get_files_to_backup(data_dir: Path | None = None) -> list[tuple[Path, str]]:
    """Get list of (path, filename) pairs for files that exist and should be backed up.

    Args:
        data_dir: Directory containing data files. Defaults to DATA_DIR.

    Returns:
        List of (full_path, filename) tuples for files that exist.
    """
    if data_dir is None:
        data_dir = DATA_DIR

    result = []
    for filename in BACKUP_FILES:
        filepath = data_dir / filename
        if filepath.exists():
            result.append((filepath, filename))
    return result


def list_backup_dates(client, bucket: str) -> list[str]:
    """List all backup date prefixes in R2.

    Args:
        client: boto3 S3 client
        bucket: R2 bucket name

    Returns:
        Sorted list of date strings like ["2026-02-26", "2026-02-27", ...]
    """
    try:
        response = client.list_objects_v2(
            Bucket=bucket,
            Prefix=f"{BACKUP_PREFIX}/",
            Delimiter="/",
        )
    except Exception as e:
        logger.warning("Failed to list backup prefixes: %s", e)
        return []

    dates = []
    for prefix_info in response.get("CommonPrefixes", []):
        # prefix looks like "backups/2026-03-05/"
        prefix = prefix_info["Prefix"]
        date_part = prefix.rstrip("/").split("/")[-1]
        # Validate it looks like a date
        try:
            datetime.strptime(date_part, "%Y-%m-%d")
            dates.append(date_part)
        except ValueError:
            continue

    return sorted(dates)


def delete_backup_date(client, bucket: str, date_str: str, dry_run: bool = True) -> int:
    """Delete all objects under a backup date prefix.

    Args:
        client: boto3 S3 client
        bucket: R2 bucket name
        date_str: Date string like "2026-02-26"
        dry_run: If True, only log what would be deleted

    Returns:
        Number of objects deleted (or would be deleted in dry-run)
    """
    prefix = f"{BACKUP_PREFIX}/{date_str}/"
    try:
        response = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    except Exception as e:
        logger.warning("Failed to list objects for %s: %s", prefix, e)
        return 0

    objects = response.get("Contents", [])
    if not objects:
        return 0

    if dry_run:
        for obj in objects:
            print(f"  [dry-run] Would delete: {obj['Key']}")
        return len(objects)

    # Delete in batch
    delete_keys = [{"Key": obj["Key"]} for obj in objects]
    try:
        client.delete_objects(
            Bucket=bucket,
            Delete={"Objects": delete_keys, "Quiet": True},
        )
    except Exception as e:
        logger.warning("Failed to delete objects for %s: %s", date_str, e)
        return 0

    return len(objects)


def prune_old_backups(client, bucket: str, retention_days: int = RETENTION_DAYS, dry_run: bool = True) -> int:
    """Remove backup dates older than retention_days.

    Args:
        client: boto3 S3 client
        bucket: R2 bucket name
        retention_days: Number of days to keep
        dry_run: If True, only log what would be deleted

    Returns:
        Number of date prefixes pruned
    """
    dates = list_backup_dates(client, bucket)
    if not dates:
        return 0

    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).strftime("%Y-%m-%d")
    pruned = 0

    for date_str in dates:
        if date_str < cutoff:
            action = "Would prune" if dry_run else "Pruning"
            print(f"  [{action}] backup date: {date_str}")
            deleted = delete_backup_date(client, bucket, date_str, dry_run=dry_run)
            if deleted > 0:
                pruned += 1
                print(f"    {'Would delete' if dry_run else 'Deleted'} {deleted} object(s)")

    return pruned


def run_backup(dry_run: bool = True, data_dir: Path | None = None) -> dict:
    """Run the full backup: upload today's files, then prune old backups.

    Args:
        dry_run: If True, only log what would happen
        data_dir: Override data directory (for testing)

    Returns:
        Dict with keys: uploaded, pruned, errors, skipped
    """
    result = {"uploaded": 0, "pruned": 0, "errors": [], "skipped": []}

    if not can_write_r2():
        print("[backup] R2 write credentials not configured, skipping backup")
        result["errors"].append("R2 write credentials not configured")
        return result

    files = get_files_to_backup(data_dir)
    if not files:
        print("[backup] No data files found to back up")
        result["errors"].append("No data files found")
        return result

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    mode = "DRY-RUN" if dry_run else "LIVE"
    print(f"[backup] {mode} — Backing up {len(files)} file(s) to R2 under {BACKUP_PREFIX}/{date_str}/")

    client = _get_r2_client()

    # Upload files
    for filepath, filename in files:
        key = get_backup_key(date_str, filename)
        size_kb = filepath.stat().st_size / 1024

        if dry_run:
            print(f"  [dry-run] Would upload: {filename} ({size_kb:.1f} KB) -> {key}")
            result["uploaded"] += 1
        else:
            try:
                data = filepath.read_bytes()
                content_type = "application/json" if filename.endswith(".json") else "application/octet-stream"
                client.put_object(
                    Bucket=R2_BUCKET_NAME,
                    Key=key,
                    Body=data,
                    ContentType=content_type,
                )
                print(f"  Uploaded: {filename} ({size_kb:.1f} KB) -> {key}")
                result["uploaded"] += 1
            except Exception as e:
                print(f"  ERROR uploading {filename}: {e}")
                result["errors"].append(f"Upload failed: {filename}: {e}")

    # Prune old backups
    print(f"\n[backup] Pruning backups older than {RETENTION_DAYS} days...")
    result["pruned"] = prune_old_backups(client, R2_BUCKET_NAME, dry_run=dry_run)

    if result["pruned"] == 0:
        print("  No old backups to prune")

    print(f"\n[backup] Done. Uploaded: {result['uploaded']}, Pruned: {result['pruned']} date(s)")
    return result


def main():
    parser = argparse.ArgumentParser(description="Backup Railway volume data to R2")
    parser.add_argument("--execute", action="store_true", help="Actually upload (default is dry-run)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    run_backup(dry_run=not args.execute)


if __name__ == "__main__":
    main()
