#!/usr/bin/env python3
"""
Push locally-processed data to production via git.

Commits essential data files and pushes to origin/main, which triggers
a Railway redeploy with the updated data bundled in the Docker image.

Usage:
    # Dry run (compare local vs remote, don't push):
    python scripts/push_to_production.py --dry-run

    # Push all data files:
    python scripts/push_to_production.py

    # Push with a custom commit message:
    python scripts/push_to_production.py -m "data: updated after clustering run"

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


def get_production_stats() -> dict | None:
    """Fetch stats from production sync/status endpoint."""
    if not SYNC_TOKEN:
        return None

    import ssl
    import urllib.error
    import urllib.request

    try:
        import certifi
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ssl_ctx = ssl.create_default_context()

    url = f"{SITE_URL}/api/sync/status"
    req = urllib.request.Request(url)

    try:
        with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  (could not reach production: {e})")
        return None


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
        description="Push data to production via git commit + push.",
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
    args = parser.parse_args()

    print("=== Push to Production (via git) ===\n")

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

    # Step 3: Show local stats
    local_stats = get_local_stats()
    print("Local data:")
    print(f"  Identities: {local_stats.get('identities', '?')} ({local_stats.get('confirmed', '?')} confirmed)")
    print(f"  Photos: {local_stats.get('photos', '?')}")

    # Step 4: Show production stats for comparison
    print("\nProduction data:")
    prod_stats = get_production_stats()
    if prod_stats:
        print(f"  Identities: {prod_stats.get('identities', '?')} ({prod_stats.get('confirmed', '?')} confirmed)")
        print(f"  Photos: {prod_stats.get('photos', '?')}")
    else:
        print("  (unavailable)")

    # Step 5: Check for changes
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

    # Step 6: Stage and commit
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

    # Step 7: Push to origin
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
