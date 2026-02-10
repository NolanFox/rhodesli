#!/usr/bin/env python3
"""
Sync production data to local.

Downloads identities.json and photo_index.json from the live site
using token-based auth (RHODESLI_SYNC_TOKEN).

Usage:
    # Set token first (one time):
    export RHODESLI_SYNC_TOKEN=your-token-here
    # Or add to .env file in project root

    # Dry run (fetch and compare, don't write):
    python scripts/sync_from_production.py --dry-run

    # Sync:
    python scripts/sync_from_production.py

    # From a downloaded ZIP (fallback):
    python scripts/sync_from_production.py --from-zip ~/Downloads/rhodesli-data-export.zip
"""

import argparse
import json
import os
import shutil
import sys
import time
import zipfile
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
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def backup_file(filepath: Path) -> Path | None:
    """Back up a file with timestamp suffix. Returns backup path or None."""
    if not filepath.exists():
        return None
    ts = int(time.time())
    backup = filepath.with_suffix(f".bak.{ts}")
    shutil.copy2(filepath, backup)
    return backup


def _get_ssl_context():
    """Get SSL context, using certifi certs if available (fixes macOS Python)."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        # Fall back to default context; if that fails, try unverified
        ctx = ssl.create_default_context()
        return ctx


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
            print(f"ERROR: Unauthorized. Check RHODESLI_SYNC_TOKEN is set correctly.")
            print(f"  Token present: {'yes' if SYNC_TOKEN else 'no'}")
            print(f"  Token length: {len(SYNC_TOKEN)}")
        elif e.code == 503:
            print(f"ERROR: Sync API not configured on server. Set RHODESLI_SYNC_TOKEN on Railway.")
        elif e.code == 404:
            print(f"ERROR: Endpoint not found at {url}. Is the latest code deployed?")
        else:
            print(f"ERROR: HTTP {e.code} from {url}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: Cannot reach {url}: {e.reason}")
        sys.exit(1)


def summarize_identities(data: dict) -> dict:
    """Extract summary stats from identities data."""
    identities = data.get("identities", data)
    if isinstance(identities, dict) and "identities" in identities:
        identities = identities["identities"]

    total = len(identities)
    confirmed = sum(1 for v in identities.values() if v.get("state") == "CONFIRMED")
    proposed = sum(1 for v in identities.values() if v.get("state") == "PROPOSED")
    inbox = sum(1 for v in identities.values() if v.get("state") == "INBOX")
    named = sum(1 for v in identities.values()
                if v.get("name") and not v["name"].startswith("Unidentified"))
    return {
        "total": total,
        "confirmed": confirmed,
        "proposed": proposed,
        "inbox": inbox,
        "named": named,
    }


def summarize_photos(data: dict) -> dict:
    """Extract summary stats from photo index data."""
    photos = data.get("photos", {})
    face_to_photo = data.get("face_to_photo", {})
    return {
        "photos": len(photos),
        "face_mappings": len(face_to_photo),
    }


def compare_and_print(label: str, local_file: Path, remote_data: dict, summarize_fn):
    """Compare local vs remote data and print diff summary."""
    if local_file.exists():
        with open(local_file) as f:
            local_data = json.load(f)
        local_stats = summarize_fn(local_data)
    else:
        local_stats = {k: 0 for k in summarize_fn(remote_data)}

    remote_stats = summarize_fn(remote_data)

    print(f"\n  {label}:")
    for key in remote_stats:
        local_val = local_stats.get(key, 0)
        remote_val = remote_stats[key]
        delta = remote_val - local_val
        arrow = f" (+{delta})" if delta > 0 else f" ({delta})" if delta < 0 else ""
        print(f"    {key}: {local_val} -> {remote_val}{arrow}")


def sync_from_api(dry_run: bool = False):
    """Sync data from production via sync API."""
    if not SYNC_TOKEN:
        print("ERROR: RHODESLI_SYNC_TOKEN not set.")
        print("  Set it in .env or export it:")
        print("  export RHODESLI_SYNC_TOKEN=your-token")
        print("  Or generate one: python scripts/generate_sync_token.py")
        sys.exit(1)

    print(f"Syncing from {SITE_URL} ...")

    # Check status first (public endpoint, no token needed)
    print("  Checking server status...")
    try:
        import urllib.request
        ssl_ctx = _get_ssl_context()
        with urllib.request.urlopen(f"{SITE_URL}/api/sync/status", timeout=10, context=ssl_ctx) as resp:
            status = json.loads(resp.read().decode("utf-8"))
        print(f"  Server: {status.get('identities', '?')} identities, "
              f"{status.get('photos', '?')} photos, "
              f"{status.get('confirmed', '?')} confirmed")
    except Exception as e:
        print(f"  Warning: Could not reach status endpoint: {e}")
        print(f"  Continuing anyway...")

    # Fetch data
    print("\n  Fetching identities.json...")
    identities_data = fetch_json("/api/sync/identities")

    print("  Fetching photo_index.json...")
    photo_index_data = fetch_json("/api/sync/photo-index")

    # Compare
    identities_file = DATA_DIR / "identities.json"
    photo_index_file = DATA_DIR / "photo_index.json"

    compare_and_print("Identities", identities_file, identities_data, summarize_identities)
    compare_and_print("Photo Index", photo_index_file, photo_index_data, summarize_photos)

    if dry_run:
        print("\n  DRY RUN — no files written.")
        return

    # Back up
    print("\n  Backing up local files...")
    for filepath in [identities_file, photo_index_file]:
        backup = backup_file(filepath)
        if backup:
            print(f"    {filepath.name} -> {backup.name}")

    # Write
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(identities_file, "w") as f:
        json.dump(identities_data, f, indent=2)
    print(f"  Wrote {identities_file}")

    with open(photo_index_file, "w") as f:
        json.dump(photo_index_data, f, indent=2)
    print(f"  Wrote {photo_index_file}")

    print("\nSync complete. Run 'git diff data/' to see changes.")


def sync_from_zip(zip_path: str):
    """Sync data from a downloaded ZIP file."""
    zip_path = Path(zip_path).expanduser()
    if not zip_path.exists():
        print(f"ERROR: ZIP file not found: {zip_path}")
        sys.exit(1)

    print(f"Syncing from ZIP: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        print(f"  ZIP contains: {names}")

        for name in ["identities.json", "photo_index.json"]:
            if name not in names:
                print(f"  WARNING: {name} not found in ZIP, skipping")
                continue

            target = DATA_DIR / name
            backup = backup_file(target)
            if backup:
                print(f"  Backed up {name} -> {backup.name}")

            with zf.open(name) as src:
                data = json.load(src)

            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(target, "w") as f:
                json.dump(data, f, indent=2)
            print(f"  Wrote {target}")

    print("\nSync complete. Run 'git diff data/' to see changes.")


def main():
    parser = argparse.ArgumentParser(
        description="Sync production data to local.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and compare but don't write files")
    parser.add_argument("--from-zip", type=str, metavar="PATH",
                        help="Sync from a downloaded ZIP file instead of API")
    args = parser.parse_args()

    if args.from_zip:
        sync_from_zip(args.from_zip)
    else:
        sync_from_api(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
