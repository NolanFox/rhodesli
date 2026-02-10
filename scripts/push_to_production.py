#!/usr/bin/env python3
"""
Push locally-processed data to production.

Uploads identities.json and photo_index.json to the live site
using token-based auth (RHODESLI_SYNC_TOKEN).

Usage:
    # Dry run (compare local vs remote, don't push):
    python scripts/push_to_production.py --dry-run

    # Push both files:
    python scripts/push_to_production.py

    # Push only identities:
    python scripts/push_to_production.py --identities-only

    # Push only photo index:
    python scripts/push_to_production.py --photo-index-only

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
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _get_ssl_context():
    """Get SSL context, using certifi certs if available."""
    import ssl

    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch_json(endpoint: str) -> dict:
    """Fetch JSON from sync API endpoint."""
    import urllib.error
    import urllib.request

    url = f"{SITE_URL}{endpoint}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {SYNC_TOKEN}")
    ssl_ctx = _get_ssl_context()

    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("ERROR: Unauthorized. Check RHODESLI_SYNC_TOKEN.")
        elif e.code == 404:
            print(f"ERROR: Endpoint not found: {url}")
            print("  The push API may not be deployed yet.")
            print("  Deploy the latest code first, then retry.")
        else:
            print(f"ERROR: HTTP {e.code} from {url}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: Cannot reach {url}: {e.reason}")
        sys.exit(1)


def push_json(endpoint: str, payload: dict) -> dict:
    """POST JSON to sync API endpoint."""
    import urllib.error
    import urllib.request

    url = f"{SITE_URL}{endpoint}"
    body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {SYNC_TOKEN}")
    req.add_header("Content-Type", "application/json")
    ssl_ctx = _get_ssl_context()

    try:
        with urllib.request.urlopen(req, timeout=120, context=ssl_ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("ERROR: Unauthorized. Check RHODESLI_SYNC_TOKEN.")
        elif e.code == 404:
            print(f"ERROR: Push endpoint not found: {url}")
            print("  Deploy the latest code first (it includes the push API).")
        elif e.code == 400:
            body = e.read().decode("utf-8")
            print(f"ERROR: Bad request: {body}")
        else:
            print(f"ERROR: HTTP {e.code} from {url}")
            try:
                print(f"  Body: {e.read().decode('utf-8')[:200]}")
            except Exception:
                pass
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: Cannot reach {url}: {e.reason}")
        sys.exit(1)


def summarize(label, data, key):
    """Print summary of a data file."""
    items = data.get(key, data) if isinstance(data, dict) else data
    count = len(items) if isinstance(items, (dict, list)) else "?"
    if label == "identities":
        confirmed = sum(
            1 for v in items.values() if v.get("state") == "CONFIRMED"
        )
        print(f"  {label}: {count} total, {confirmed} confirmed")
    elif label == "photos":
        print(f"  {label}: {count}")


def main():
    parser = argparse.ArgumentParser(
        description="Push locally-processed data to production.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compare local vs remote without pushing",
    )
    parser.add_argument(
        "--identities-only",
        action="store_true",
        help="Only push identities.json",
    )
    parser.add_argument(
        "--photo-index-only",
        action="store_true",
        help="Only push photo_index.json",
    )
    args = parser.parse_args()

    if not SYNC_TOKEN:
        print("ERROR: RHODESLI_SYNC_TOKEN not set.")
        sys.exit(1)

    push_identities = not args.photo_index_only
    push_photo_index = not args.identities_only

    # Load local data
    print("Loading local data...")
    payload = {}

    if push_identities:
        ids_path = DATA_DIR / "identities.json"
        if not ids_path.exists():
            print(f"ERROR: {ids_path} not found")
            sys.exit(1)
        with open(ids_path) as f:
            local_ids = json.load(f)
        payload["identities"] = local_ids
        id_data = local_ids.get("identities", local_ids)
        local_confirmed = sum(
            1 for v in id_data.values() if v.get("state") == "CONFIRMED"
        )
        print(f"  Local identities: {len(id_data)} ({local_confirmed} confirmed)")

    if push_photo_index:
        pi_path = DATA_DIR / "photo_index.json"
        if not pi_path.exists():
            print(f"ERROR: {pi_path} not found")
            sys.exit(1)
        with open(pi_path) as f:
            local_pi = json.load(f)
        payload["photo_index"] = local_pi
        local_photos = local_pi.get("photos", {})
        print(f"  Local photos: {len(local_photos)}")

    # Fetch current production state for comparison
    print("\nChecking production state...")
    try:
        status = fetch_json("/api/sync/status")
        print(
            f"  Production: {status.get('identities', '?')} identities, "
            f"{status.get('photos', '?')} photos, "
            f"{status.get('confirmed', '?')} confirmed"
        )
    except SystemExit:
        print("  Could not reach production.")
        return

    if args.dry_run:
        print("\nDRY RUN — comparing local vs production:")
        if push_identities:
            print(
                f"  Identities: local={len(id_data)} vs "
                f"production={status.get('identities', '?')}"
            )
        if push_photo_index:
            print(
                f"  Photos: local={len(local_photos)} vs "
                f"production={status.get('photos', '?')}"
            )
        print("\nNo changes pushed.")
        return

    # Push
    print(f"\nPushing to {SITE_URL} ...")
    payload_size_mb = len(json.dumps(payload).encode()) / (1024 * 1024)
    print(f"  Payload size: {payload_size_mb:.1f} MB")

    result = push_json("/api/sync/push", payload)

    print("\nPush result:")
    for key, info in result.get("results", {}).items():
        print(f"  {key}: {info.get('status')} ({info.get('count')} items)")
        if info.get("backup"):
            print(f"    Production backup: {info['backup']}")

    # Verify
    print("\nVerifying production state after push...")
    status_after = fetch_json("/api/sync/status")
    print(
        f"  Production: {status_after.get('identities', '?')} identities, "
        f"{status_after.get('photos', '?')} photos, "
        f"{status_after.get('confirmed', '?')} confirmed"
    )

    print("\nPush complete.")


if __name__ == "__main__":
    main()
