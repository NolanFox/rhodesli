#!/usr/bin/env python3
"""
Push locally-processed data to production via git, with merge-aware logic.

CRITICAL: This script NEVER blind-overwrites production data. It:
1. Fetches current production state via sync API
2. Merges local + production data (production wins on conflicts)
3. Writes the merged result locally
4. Git commits and pushes

This prevents overwriting user actions on production (merges, confirmations,
rejections, renames) that happened since the last local sync.

Usage:
    # Dry run (compare local vs remote, don't push):
    python scripts/push_to_production.py --dry-run

    # Push all data files:
    python scripts/push_to_production.py

    # Push with a custom commit message:
    python scripts/push_to_production.py -m "data: updated after clustering run"

    # Skip merge (DANGEROUS — only for known-clean states):
    python scripts/push_to_production.py --no-merge

Requires git configured with push access to origin.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Load .env if it exists (for RHODESLI_SYNC_TOKEN used by verification)
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
DATA_DIR = PROJECT_ROOT / "data"

# Essential data files that get committed
DATA_FILES = [
    "data/identities.json",
    "data/photo_index.json",
    "data/annotations.json",
    "data/file_hashes.json",
    "data/golden_set.json",
    "data/proposals.json",
]


def run(cmd: list[str], check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command from the project root."""
    return subprocess.run(
        cmd, cwd=PROJECT_ROOT, check=check, capture_output=capture, text=True
    )


def check_data_integrity() -> bool:
    """Run data integrity check before pushing."""
    integrity_script = PROJECT_ROOT / "scripts" / "check_data_integrity.py"
    if not integrity_script.exists():
        print("  (skipping integrity check — script not found)")
        return True

    result = run([sys.executable, str(integrity_script)], check=False)
    if result.returncode != 0:
        print("ERROR: Data integrity check failed:")
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return False
    return True


def get_local_stats() -> dict:
    """Get stats from local data files."""
    stats = {}

    ids_path = DATA_DIR / "identities.json"
    if ids_path.exists():
        with open(ids_path) as f:
            data = json.load(f)
        identities = data.get("identities", data)
        stats["identities"] = len(identities)
        stats["confirmed"] = sum(
            1 for v in identities.values() if v.get("state") == "CONFIRMED"
        )

    pi_path = DATA_DIR / "photo_index.json"
    if pi_path.exists():
        with open(pi_path) as f:
            data = json.load(f)
        stats["photos"] = len(data.get("photos", {}))

    return stats


def _get_ssl_context():
    """Get SSL context, using certifi certs if available."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch_production_json(endpoint: str) -> dict | None:
    """Fetch JSON data from production sync API."""
    if not SYNC_TOKEN:
        return None

    import urllib.error
    import urllib.request

    url = f"{SITE_URL}{endpoint}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {SYNC_TOKEN}")
    ssl_ctx = _get_ssl_context()

    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  WARNING: Could not fetch {endpoint}: {e}")
        return None


def get_production_stats() -> dict | None:
    """Fetch stats from production sync/status endpoint."""
    if not SYNC_TOKEN:
        return None

    import urllib.error
    import urllib.request

    url = f"{SITE_URL}/api/sync/status"
    req = urllib.request.Request(url)
    ssl_ctx = _get_ssl_context()

    try:
        with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  (could not reach production: {e})")
        return None


def _extract_face_ids(identity: dict) -> set[str]:
    """Extract all face IDs from an identity (anchors + candidates)."""
    face_ids = set()
    for anchor in identity.get("anchor_ids", []):
        if isinstance(anchor, str):
            face_ids.add(anchor)
        elif isinstance(anchor, dict):
            face_ids.add(anchor["face_id"])
    face_ids.update(identity.get("candidate_ids", []))
    return face_ids


def _is_production_modified(local: dict, prod: dict) -> bool:
    """Check if production identity differs from local in ways that indicate user action.

    Production wins if the admin changed state, name, faces, or merge status.
    """
    # State change (confirm, reject, skip, etc.)
    if prod.get("state") != local.get("state"):
        return True
    # Name change (rename)
    if prod.get("name") != local.get("name"):
        return True
    # merged_into changed
    if prod.get("merged_into") != local.get("merged_into"):
        return True
    # Face set changed (merge, detach, add)
    if _extract_face_ids(prod) != _extract_face_ids(local):
        return True
    # Negative IDs changed (rejection)
    if set(prod.get("negative_ids", [])) != set(local.get("negative_ids", [])):
        return True
    return False


def merge_identities(local_data: dict, prod_data: dict) -> tuple[dict, dict]:
    """Merge local and production identity data. Production wins on conflicts.

    Returns (merged_data, merge_report).
    """
    local_ids = local_data.get("identities", {})
    prod_ids = prod_data.get("identities", {})
    merged = {}
    report = {"kept_local": 0, "kept_production": 0, "new_local": 0, "production_only": 0}

    all_keys = set(list(local_ids.keys()) + list(prod_ids.keys()))

    for iid in all_keys:
        local = local_ids.get(iid)
        prod = prod_ids.get(iid)

        if local and not prod:
            merged[iid] = local  # New from local pipeline
            report["new_local"] += 1
        elif prod and not local:
            merged[iid] = prod  # Exists only on production
            report["production_only"] += 1
        elif local and prod:
            if _is_production_modified(local, prod):
                merged[iid] = prod  # Production wins — user action detected
                report["kept_production"] += 1
            else:
                merged[iid] = local  # No conflict, use local (may have pipeline updates)
                report["kept_local"] += 1

    merged_data = {
        "schema_version": local_data.get("schema_version", 1),
        "identities": merged,
    }
    return merged_data, report


def merge_photo_index(local_data: dict, prod_data: dict) -> tuple[dict, dict]:
    """Merge local and production photo index. Production wins on conflicts.

    Returns (merged_data, merge_report).
    """
    local_photos = local_data.get("photos", {})
    prod_photos = prod_data.get("photos", {})
    merged_photos = {}
    report = {"kept_local": 0, "kept_production": 0, "new_local": 0, "production_only": 0}

    all_keys = set(list(local_photos.keys()) + list(prod_photos.keys()))

    for pid in all_keys:
        local = local_photos.get(pid)
        prod = prod_photos.get(pid)

        if local and not prod:
            merged_photos[pid] = local
            report["new_local"] += 1
        elif prod and not local:
            merged_photos[pid] = prod
            report["production_only"] += 1
        elif local and prod:
            # Check if production has changes (source, collection, metadata)
            if prod != local:
                merged_photos[pid] = prod  # Production wins
                report["kept_production"] += 1
            else:
                merged_photos[pid] = local
                report["kept_local"] += 1

    # Merge face_to_photo (union — production wins on conflicts)
    local_f2p = local_data.get("face_to_photo", {})
    prod_f2p = prod_data.get("face_to_photo", {})
    merged_f2p = {**local_f2p, **prod_f2p}

    merged_data = {
        "schema_version": local_data.get("schema_version", 1),
        "photos": merged_photos,
        "face_to_photo": merged_f2p,
    }
    return merged_data, report


def perform_merge() -> bool:
    """Fetch production data and merge with local. Returns True if merge happened."""
    print("Fetching production data for merge...")

    prod_identities = fetch_production_json("/api/sync/identities")
    prod_photo_index = fetch_production_json("/api/sync/photo-index")

    if not prod_identities and not prod_photo_index:
        print("  WARNING: Could not fetch production data. Proceeding without merge.")
        print("  This may overwrite production changes!")
        return False

    merged_any = False

    # Merge identities
    if prod_identities:
        local_path = DATA_DIR / "identities.json"
        with open(local_path) as f:
            local_data = json.load(f)

        merged_data, report = merge_identities(local_data, prod_identities)

        if report["kept_production"] > 0 or report["production_only"] > 0:
            with open(local_path, "w") as f:
                json.dump(merged_data, f, indent=2)
            print(f"  Identities merged: {report['kept_production']} production wins, "
                  f"{report['new_local']} new local, "
                  f"{report['production_only']} production-only, "
                  f"{report['kept_local']} unchanged")
            merged_any = True
        else:
            print(f"  Identities: no production changes to merge ({report['kept_local']} unchanged, {report['new_local']} new)")

    # Merge photo index
    if prod_photo_index:
        local_path = DATA_DIR / "photo_index.json"
        with open(local_path) as f:
            local_data = json.load(f)

        merged_data, report = merge_photo_index(local_data, prod_photo_index)

        if report["kept_production"] > 0 or report["production_only"] > 0:
            with open(local_path, "w") as f:
                json.dump(merged_data, f, indent=2)
            print(f"  Photo index merged: {report['kept_production']} production wins, "
                  f"{report['new_local']} new local, "
                  f"{report['production_only']} production-only, "
                  f"{report['kept_local']} unchanged")
            merged_any = True
        else:
            print(f"  Photo index: no production changes to merge ({report['kept_local']} unchanged, {report['new_local']} new)")

    return merged_any


def git_has_changes() -> bool:
    """Check if any essential data files have changes (staged or unstaged)."""
    existing = [f for f in DATA_FILES if (PROJECT_ROOT / f).exists()]
    if not existing:
        return False

    # Check for unstaged changes
    result = run(["git", "diff", "--name-only", "--"] + existing, check=False)
    if result.stdout.strip():
        return True

    # Check for untracked files
    result = run(["git", "ls-files", "--others", "--exclude-standard", "--"] + existing, check=False)
    if result.stdout.strip():
        return True

    # Check for staged changes
    result = run(["git", "diff", "--cached", "--name-only", "--"] + existing, check=False)
    if result.stdout.strip():
        return True

    return False


def main():
    parser = argparse.ArgumentParser(
        description="Push data to production via git commit + push (merge-aware).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compare local vs remote without pushing",
    )
    parser.add_argument(
        "-m", "--message",
        default=None,
        help="Custom commit message (default: auto-generated)",
    )
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Skip merge step (DANGEROUS — may overwrite production changes)",
    )
    args = parser.parse_args()

    print("=== Push to Production (merge-aware) ===\n")

    # Step 1: Verify essential data files exist
    missing = [f for f in DATA_FILES[:2] if not (PROJECT_ROOT / f).exists()]
    if missing:
        print(f"ERROR: Missing essential files: {missing}")
        sys.exit(1)

    # Step 2: Run integrity check
    print("Running data integrity check...")
    if not check_data_integrity():
        print("\nAborted. Fix integrity issues before pushing.")
        sys.exit(1)
    print("  Integrity check passed.\n")

    # Step 3: Merge with production (CRITICAL — prevents overwriting user actions)
    if not args.no_merge:
        perform_merge()
        print()

    # Step 4: Show local stats (after merge)
    local_stats = get_local_stats()
    print("Local data (after merge):")
    print(f"  Identities: {local_stats.get('identities', '?')} ({local_stats.get('confirmed', '?')} confirmed)")
    print(f"  Photos: {local_stats.get('photos', '?')}")

    # Step 5: Show production stats for comparison
    print("\nProduction data:")
    prod_stats = get_production_stats()
    if prod_stats:
        print(f"  Identities: {prod_stats.get('identities', '?')} ({prod_stats.get('confirmed', '?')} confirmed)")
        print(f"  Photos: {prod_stats.get('photos', '?')}")
    else:
        print("  (unavailable)")

    # Step 6: Check for changes
    if not git_has_changes():
        print("\nNo changes to push — data files are up to date in git.")
        return

    # Show what will change
    existing = [f for f in DATA_FILES if (PROJECT_ROOT / f).exists()]
    result = run(["git", "diff", "--stat", "--"] + existing, check=False)
    untracked = run(["git", "ls-files", "--others", "--exclude-standard", "--"] + existing, check=False)

    print("\nChanges to push:")
    if result.stdout.strip():
        print(result.stdout.strip())
    if untracked.stdout.strip():
        for f in untracked.stdout.strip().split("\n"):
            print(f"  new file: {f}")

    if args.dry_run:
        print("\nDRY RUN — no changes pushed.")
        return

    # Step 7: Stage and commit
    print("\nStaging data files...")
    run(["git", "add"] + existing)

    commit_msg = args.message or (
        f"data: push to production ({local_stats.get('identities', '?')} identities, "
        f"{local_stats.get('photos', '?')} photos)"
    )

    print(f"Committing: {commit_msg}")
    result = run(
        ["git", "commit", "-m", commit_msg],
        check=False,
    )
    if result.returncode != 0:
        if "nothing to commit" in (result.stdout + result.stderr):
            print("  Nothing to commit — data already up to date.")
            return
        print(f"ERROR: git commit failed:\n{result.stdout}\n{result.stderr}")
        sys.exit(1)

    # Step 8: Push to origin
    print("Pushing to origin/main...")
    result = run(["git", "push", "origin", "main"], check=False)
    if result.returncode != 0:
        print(f"ERROR: git push failed:\n{result.stdout}\n{result.stderr}")
        print("\nThe commit was created locally. You can retry with: git push origin main")
        sys.exit(1)

    print("\nPush complete. Railway will redeploy automatically (1-2 minutes).")
    print(f"Monitor at: {SITE_URL}")


if __name__ == "__main__":
    main()
