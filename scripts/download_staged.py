#!/usr/bin/env python3
"""
Download staged uploads from production for local ML processing.

Usage:
    # Download all staged photos to raw_photos/pending/
    python scripts/download_staged.py

    # Dry run — list what's staged without downloading
    python scripts/download_staged.py --dry-run

    # Download and clear staging after (only do this after processing)
    python scripts/download_staged.py --clear-after

    # Custom destination
    python scripts/download_staged.py --dest raw_photos/new_uploads/

Requires RHODESLI_SYNC_TOKEN in environment or .env file.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Load .env if it exists
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key not in os.environ:
                os.environ[key] = value

SITE_URL = os.environ.get("RHODESLI_SITE_URL", "https://rhodesli.nolanandrewfox.com")
SYNC_TOKEN = os.environ.get("RHODESLI_SYNC_TOKEN", "")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEST = PROJECT_ROOT / "raw_photos" / "pending"


def _get_ssl_context():
    """Get SSL context, using certifi certs if available (fixes macOS Python)."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch_json(endpoint: str) -> dict:
    """Fetch JSON from sync API endpoint."""
    import urllib.request
    import urllib.error

    url = f"{SITE_URL}{endpoint}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {SYNC_TOKEN}")
    ssl_ctx = _get_ssl_context()

    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("ERROR: Unauthorized. Check RHODESLI_SYNC_TOKEN is set correctly.")
        elif e.code == 503:
            print("ERROR: Sync API not configured on server.")
        elif e.code == 404:
            print(f"ERROR: Endpoint not found: {url}")
            print("  Is the latest code deployed?")
        else:
            print(f"ERROR: HTTP {e.code} from {url}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: Cannot reach {url}: {e.reason}")
        sys.exit(1)


def download_file(rel_path: str, dest_dir: Path) -> bool:
    """Download a single file from staging. Returns True on success."""
    import urllib.request
    import urllib.error
    from urllib.parse import quote

    # URL-encode the path segments (spaces, special chars)
    encoded_path = "/".join(quote(seg, safe="") for seg in rel_path.split("/"))
    url = f"{SITE_URL}/api/sync/staged/download/{encoded_path}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {SYNC_TOKEN}")
    ssl_ctx = _get_ssl_context()

    # Determine local destination — use the filename only (flatten)
    filename = Path(rel_path).name
    local_path = dest_dir / filename

    if local_path.exists():
        print(f"  SKIP (exists): {filename}")
        return False

    try:
        with urllib.request.urlopen(req, timeout=120, context=ssl_ctx) as resp:
            content = resp.read()
        dest_dir.mkdir(parents=True, exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(content)
        size_kb = len(content) / 1024
        print(f"  Downloaded: {filename} ({size_kb:.0f} KB)")
        return True
    except urllib.error.HTTPError as e:
        print(f"  ERROR downloading {rel_path}: HTTP {e.code}")
        return False
    except Exception as e:
        print(f"  ERROR downloading {rel_path}: {e}")
        return False


def clear_staged(file_paths: list[str] | None = None):
    """Clear staged files on production after successful download."""
    import urllib.request
    import urllib.error

    url = f"{SITE_URL}/api/sync/staged/clear"
    if file_paths:
        body = json.dumps({"files": file_paths}).encode()
    else:
        body = json.dumps({"all": True}).encode()

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {SYNC_TOKEN}")
    req.add_header("Content-Type", "application/json")
    ssl_ctx = _get_ssl_context()

    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        print(f"\n  Cleared {result.get('count', 0)} items from staging.")
        if result.get("errors"):
            for err in result["errors"]:
                print(f"    Warning: {err['path']}: {err['error']}")
        return True
    except Exception as e:
        print(f"\n  ERROR clearing staging: {e}")
        return False


def mark_jobs_processed():
    """Mark all staged jobs as processed in pending_uploads.json on production."""
    import urllib.request
    import urllib.error

    url = f"{SITE_URL}/api/sync/staged/mark-processed"
    body = json.dumps({"all": True}).encode()

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {SYNC_TOKEN}")
    req.add_header("Content-Type", "application/json")
    ssl_ctx = _get_ssl_context()

    try:
        with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        count = result.get("count", 0)
        if count > 0:
            print(f"  Marked {count} job(s) as processed in Pending Uploads.")
        return True
    except Exception as e:
        print(f"  WARNING: Could not mark jobs as processed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Download staged uploads from production for local ML processing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="List staged files without downloading")
    parser.add_argument("--clear-after", action="store_true",
                        help="Clear staging on production after successful download")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST,
                        help=f"Download destination (default: {DEFAULT_DEST.relative_to(PROJECT_ROOT)})")
    args = parser.parse_args()

    if not SYNC_TOKEN:
        print("ERROR: RHODESLI_SYNC_TOKEN not set.")
        print("  Set it in .env or export it:")
        print("  export RHODESLI_SYNC_TOKEN=your-token")
        sys.exit(1)

    # List staged files
    print(f"Checking staged files on {SITE_URL} ...")
    listing = fetch_json("/api/sync/staged")

    files = listing.get("files", [])
    total_files = listing.get("total_files", 0)
    total_size = listing.get("total_size_bytes", 0)

    if total_files == 0:
        print("No staged files to download.")
        return

    # Filter to actual photos (skip _metadata.json)
    photo_files = [f for f in files if not f["filename"].startswith("_")]
    metadata_files = [f for f in files if f["filename"].startswith("_")]
    photo_size = sum(f["size_bytes"] for f in photo_files)

    print(f"\nFound {len(photo_files)} photo(s) ({photo_size / 1024 / 1024:.1f} MB) "
          f"in {len(set(str(Path(f['path']).parent) for f in photo_files))} upload batch(es)")
    if metadata_files:
        print(f"  ({len(metadata_files)} metadata files will also be downloaded)")

    for f in photo_files:
        print(f"  {f['filename']} ({f['size_bytes'] / 1024:.0f} KB) — {f['uploaded_at'][:10]}")

    if args.dry_run:
        print("\nDRY RUN — no files downloaded.")
        return

    # Download all files (photos + metadata)
    print(f"\nDownloading to {args.dest}/ ...")
    downloaded = []
    for f in files:
        success = download_file(f["path"], args.dest)
        if success:
            downloaded.append(f["path"])

    if not downloaded:
        print("\nNo new files downloaded (all already exist locally).")
        return

    print(f"\nDownloaded {len(downloaded)} file(s) to {args.dest}/")

    # Clear staging if requested
    if args.clear_after and downloaded:
        # Clear the job directories (parent dirs of downloaded files)
        job_dirs = list(set(str(Path(p).parent) for p in downloaded if str(Path(p).parent) != "."))
        if job_dirs:
            print(f"\nClearing {len(job_dirs)} job dir(s) from staging...")
            clear_staged(job_dirs)
        else:
            clear_staged()
        # Mark staging jobs as processed so they disappear from Pending Uploads
        mark_jobs_processed()

    print(f"\nNext steps:")
    print(f"  1. python -m core.ingest_inbox --directory {args.dest} --job-id staged-$(date +%Y%m%d)")
    print(f"  2. python scripts/cluster_new_faces.py --dry-run")
    print(f"  3. python scripts/upload_to_r2.py --dry-run")


if __name__ == "__main__":
    main()
