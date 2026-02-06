#!/usr/bin/env python3
"""
Upload photos and crops to Cloudflare R2.

This script uploads local photos and face crops to a Cloudflare R2 bucket
for production use. By default, it runs in dry-run mode to show what would
be uploaded without making changes.

Usage:
    # Preview what would be uploaded (default)
    python scripts/upload_to_r2.py --dry-run

    # Actually upload
    python scripts/upload_to_r2.py --execute

Required environment variables:
    R2_ACCOUNT_ID       - Cloudflare account ID
    R2_ACCESS_KEY_ID    - R2 API token access key
    R2_SECRET_ACCESS_KEY - R2 API token secret
    R2_BUCKET_NAME      - Name of the R2 bucket

Optional:
    R2_PUBLIC_URL       - Public URL for verification (not used for upload)
"""

import argparse
import mimetypes
import os
import sys
from pathlib import Path

# Add project root for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


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
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        print("\nSet these before running:")
        print("  export R2_ACCOUNT_ID=your-account-id")
        print("  export R2_ACCESS_KEY_ID=your-access-key")
        print("  export R2_SECRET_ACCESS_KEY=your-secret-key")
        print("  export R2_BUCKET_NAME=your-bucket-name")
        sys.exit(1)

    # R2 uses S3-compatible API with a custom endpoint
    endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def get_content_type(filepath: Path) -> str:
    """Get MIME type for a file."""
    mime_type, _ = mimetypes.guess_type(str(filepath))
    return mime_type or "application/octet-stream"


def list_files_to_upload(directory: Path, prefix: str) -> list[tuple[Path, str]]:
    """
    List files in directory and their R2 keys.

    Returns list of (local_path, r2_key) tuples.
    """
    if not directory.exists():
        print(f"WARNING: Directory does not exist: {directory}")
        return []

    files = []
    for filepath in directory.glob("**/*"):
        if filepath.is_file() and not filepath.name.startswith("."):
            # R2 key is prefix + filename (flat structure)
            r2_key = f"{prefix}/{filepath.name}"
            files.append((filepath, r2_key))

    return files


def upload_file(client, bucket: str, filepath: Path, r2_key: str, dry_run: bool) -> bool:
    """Upload a single file to R2."""
    content_type = get_content_type(filepath)
    size_kb = filepath.stat().st_size / 1024

    if dry_run:
        print(f"  [DRY-RUN] Would upload: {filepath.name} ({size_kb:.1f} KB) -> {r2_key}")
        return True

    try:
        with open(filepath, "rb") as f:
            client.put_object(
                Bucket=bucket,
                Key=r2_key,
                Body=f,
                ContentType=content_type,
            )
        print(f"  Uploaded: {filepath.name} ({size_kb:.1f} KB) -> {r2_key}")
        return True
    except Exception as e:
        print(f"  ERROR uploading {filepath.name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Upload photos and crops to Cloudflare R2"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview what would be uploaded (default)",
    )
    group.add_argument(
        "--execute",
        action="store_true",
        help="Actually upload files to R2",
    )
    parser.add_argument(
        "--photos-only",
        action="store_true",
        help="Only upload raw photos, skip crops",
    )
    parser.add_argument(
        "--crops-only",
        action="store_true",
        help="Only upload crops, skip raw photos",
    )

    args = parser.parse_args()
    dry_run = not args.execute

    # Get bucket name
    bucket_name = os.getenv("R2_BUCKET_NAME")
    if not bucket_name:
        print("ERROR: R2_BUCKET_NAME environment variable is required")
        sys.exit(1)

    # Paths
    raw_photos_dir = project_root / "raw_photos"
    crops_dir = project_root / "app" / "static" / "crops"

    # Build upload list
    files_to_upload = []

    if not args.crops_only:
        photos = list_files_to_upload(raw_photos_dir, "raw_photos")
        files_to_upload.extend(photos)
        print(f"Found {len(photos)} photos in raw_photos/")

    if not args.photos_only:
        crops = list_files_to_upload(crops_dir, "crops")
        files_to_upload.extend(crops)
        print(f"Found {len(crops)} crops in app/static/crops/")

    if not files_to_upload:
        print("\nNo files to upload.")
        return

    # Calculate total size
    total_size_mb = sum(f[0].stat().st_size for f in files_to_upload) / (1024 * 1024)
    print(f"\nTotal: {len(files_to_upload)} files ({total_size_mb:.1f} MB)")

    if dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN MODE - No files will be uploaded")
        print("Run with --execute to actually upload")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("EXECUTING - Files will be uploaded to R2")
        print(f"Bucket: {bucket_name}")
        print("=" * 60)

    # Connect to R2
    print("\nConnecting to R2...")
    client = get_r2_client()

    # Verify bucket exists (will fail if credentials are wrong)
    if not dry_run:
        try:
            client.head_bucket(Bucket=bucket_name)
            print(f"Connected to bucket: {bucket_name}")
        except Exception as e:
            print(f"ERROR: Could not access bucket '{bucket_name}': {e}")
            sys.exit(1)

    # Upload files
    print("\nUploading files...")
    success_count = 0
    error_count = 0

    for filepath, r2_key in files_to_upload:
        if upload_file(client, bucket_name, filepath, r2_key, dry_run):
            success_count += 1
        else:
            error_count += 1

    # Summary
    print("\n" + "=" * 60)
    if dry_run:
        print(f"DRY RUN COMPLETE: Would upload {success_count} files")
        print("\nTo actually upload, run:")
        print("  python scripts/upload_to_r2.py --execute")
    else:
        print(f"UPLOAD COMPLETE: {success_count} succeeded, {error_count} failed")
        if error_count == 0:
            r2_public_url = os.getenv("R2_PUBLIC_URL", "https://pub-xxx.r2.dev")
            print(f"\nPhotos should now be accessible at:")
            print(f"  {r2_public_url}/raw_photos/<filename>")
            print(f"  {r2_public_url}/crops/<filename>")
    print("=" * 60)


if __name__ == "__main__":
    main()
