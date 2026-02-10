#!/usr/bin/env python3
"""
Single-command upload processing pipeline for Rhodesli.

Downloads staged photos from production, runs face detection and clustering,
uploads to R2, pushes data back to production, and clears staging.

Usage:
    # Interactive mode (prompts between steps):
    python scripts/process_uploads.py

    # Auto mode (no prompts except clustering review):
    python scripts/process_uploads.py --auto

    # Dry-run mode (download + ML + clustering preview only):
    python scripts/process_uploads.py --dry-run

Requires:
    - RHODESLI_SYNC_TOKEN (for API access)
    - R2 credentials (for upload, not needed in --dry-run)

See docs/ops/PIPELINE.md for full documentation.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PENDING_DIR = PROJECT_ROOT / "raw_photos" / "pending"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
BACKUP_DIR = DATA_DIR / "backups"

# Load .env if it exists
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key not in os.environ:
                os.environ[key] = value


def print_step(step_num: int, total: int, description: str):
    """Print a step header."""
    print()
    print(f"{'=' * 60}")
    print(f"  Step {step_num}/{total}: {description}")
    print(f"{'=' * 60}")
    print()


def prompt_continue(message: str = "Continue?") -> bool:
    """Ask user to continue. Returns True if yes."""
    try:
        response = input(f"{message} [y/n] ").strip().lower()
        return response in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        return False


def run_script(args: list[str], description: str) -> subprocess.CompletedProcess:
    """Run a Python script and return the result."""
    cmd = [sys.executable] + args
    print(f"  Running: {' '.join(args)}")
    print()
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"\n  ERROR: {description} failed (exit code {result.returncode})")
    return result


def count_photos_in_dir(directory: Path) -> int:
    """Count photo files in a directory (excluding metadata and JSON)."""
    if not directory.exists():
        return 0
    return sum(
        1 for f in directory.iterdir()
        if f.is_file()
        and not f.name.startswith("_")
        and f.suffix.lower() not in (".json", ".txt", ".md")
    )


def count_identities(path: Path) -> dict:
    """Count identities by state from an identities.json file."""
    if not path.exists():
        return {}
    with open(path) as f:
        data = json.load(f)
    identities = data.get("identities", {})
    counts = {"total": len(identities)}
    for identity in identities.values():
        state = identity.get("state", "UNKNOWN")
        counts[state] = counts.get(state, 0) + 1
    return counts


def count_photos(path: Path) -> int:
    """Count photos from a photo_index.json file."""
    if not path.exists():
        return 0
    with open(path) as f:
        data = json.load(f)
    return len(data.get("photos", {}))


def check_env_vars(dry_run: bool) -> list[str]:
    """Check required environment variables. Returns list of missing vars."""
    missing = []
    if not os.environ.get("RHODESLI_SYNC_TOKEN"):
        missing.append("RHODESLI_SYNC_TOKEN")
    if not dry_run:
        for var in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID",
                     "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME"):
            if not os.environ.get(var):
                missing.append(var)
    return missing


def create_backups() -> dict:
    """Create timestamped backups of data files. Returns backup paths."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    backups = {}
    for filename in ("identities.json", "photo_index.json"):
        src = DATA_DIR / filename
        if src.exists():
            dest = BACKUP_DIR / f"{filename}.{timestamp}.bak"
            shutil.copy2(src, dest)
            backups[filename] = dest
            print(f"  Backed up: {filename} -> {dest.name}")

    return backups


def step_backup(interactive: bool) -> dict | None:
    """Step 1: Create pre-flight backups."""
    print_step(1, 7, "Creating pre-flight backups")
    backups = create_backups()
    if not backups:
        print("  WARNING: No data files found to back up.")
    return backups


def step_download(interactive: bool) -> int:
    """Step 2: Download staged photos. Returns count downloaded."""
    print_step(2, 7, "Downloading staged photos from production")

    result = run_script(
        ["scripts/download_staged.py", "--dest", str(PENDING_DIR)],
        "Download staged photos",
    )
    if result.returncode != 0:
        return -1

    photo_count = count_photos_in_dir(PENDING_DIR)
    if photo_count == 0:
        print("  No photos to process. Pipeline complete (nothing to do).")
    else:
        print(f"\n  {photo_count} photo(s) ready for processing in {PENDING_DIR}/")
    return photo_count


def step_ml_processing(interactive: bool) -> subprocess.CompletedProcess:
    """Step 3: Run face detection and embedding generation."""
    print_step(3, 7, "Running face detection (ML processing)")

    job_id = f"staged-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # Check for metadata to get source label
    source_args = []
    metadata_file = PENDING_DIR / "_metadata.json"
    if metadata_file.exists():
        try:
            with open(metadata_file) as f:
                meta = json.load(f)
            source = meta.get("source", "")
            if source:
                source_args = ["--source", source]
                print(f"  Source from metadata: {source}")
        except (json.JSONDecodeError, KeyError):
            pass

    args = [
        "-m", "core.ingest_inbox",
        "--directory", str(PENDING_DIR),
        "--job-id", job_id,
    ] + source_args

    result = run_script(args, "Face detection")
    return result


def step_clustering(interactive: bool) -> subprocess.CompletedProcess:
    """Step 4: Run clustering dry-run. ALWAYS pauses for review."""
    print_step(4, 7, "Running face clustering (proposals)")

    result = run_script(
        ["scripts/cluster_new_faces.py", "--dry-run"],
        "Face clustering",
    )
    if result.returncode != 0:
        return result

    print()
    print("  Review the clustering proposals above.")
    print("  These are PROPOSED matches — they will NOT be auto-applied.")
    print("  You can review and confirm them in the web UI after deployment.")
    print()

    if not prompt_continue("Continue with upload and deployment?"):
        print("\n  Pipeline paused. Your data and backups are safe.")
        print("  Re-run without --dry-run to resume from here.")
        sys.exit(0)

    return result


def step_upload_r2(interactive: bool) -> subprocess.CompletedProcess:
    """Step 5: Upload photos and crops to R2."""
    print_step(5, 7, "Uploading photos and crops to R2")

    if interactive and not prompt_continue("Upload to R2?"):
        print("  Skipped R2 upload.")
        return subprocess.CompletedProcess(args=[], returncode=1)

    result = run_script(
        ["scripts/upload_to_r2.py", "--execute"],
        "R2 upload",
    )
    return result


def step_push_production(interactive: bool) -> subprocess.CompletedProcess:
    """Step 6: Push updated data to production."""
    print_step(6, 7, "Pushing data to production")

    if interactive and not prompt_continue("Push data to production?"):
        print("  Skipped production push.")
        return subprocess.CompletedProcess(args=[], returncode=1)

    result = run_script(
        ["scripts/push_to_production.py"],
        "Push to production",
    )
    return result


def step_clear_staging(interactive: bool) -> subprocess.CompletedProcess:
    """Step 7: Clear staging on production."""
    print_step(7, 7, "Clearing staging on production")

    result = run_script(
        ["scripts/download_staged.py", "--clear-after", "--dest", str(PENDING_DIR)],
        "Clear staging",
    )
    return result


def print_summary(
    before_ids: dict,
    before_photos: int,
    photo_count: int,
    backups: dict,
):
    """Print pipeline completion summary."""
    after_ids = count_identities(DATA_DIR / "identities.json")
    after_photos = count_photos(DATA_DIR / "photo_index.json")

    print()
    print("=" * 60)
    print("  Pipeline Complete!")
    print("=" * 60)
    print()
    print(f"  Downloaded:    {photo_count} photo(s)")
    print(f"  Identities:    {before_ids.get('total', '?')} -> {after_ids.get('total', '?')}")
    print(f"  Photos:        {before_photos} -> {after_photos}")
    print(f"  Confirmed:     {before_ids.get('CONFIRMED', 0)}")
    print(f"  Backups:       {len(backups)} file(s) in {BACKUP_DIR}/")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Rhodesli upload processing pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Download + ML + clustering preview only (steps 1-4, no upload/push)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Skip confirmation prompts (except clustering review)",
    )
    args = parser.parse_args()

    interactive = not args.auto and not args.dry_run

    print("=" * 60)
    print("  Rhodesli Upload Processing Pipeline")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'AUTO' if args.auto else 'INTERACTIVE'}")
    print("=" * 60)

    # Pre-flight checks
    missing = check_env_vars(args.dry_run)
    if missing:
        print(f"\nERROR: Missing environment variables: {', '.join(missing)}")
        print("Set them in .env or export them before running.")
        sys.exit(1)

    # Capture before-state for summary
    before_ids = count_identities(DATA_DIR / "identities.json")
    before_photos = count_photos(DATA_DIR / "photo_index.json")

    # Step 1: Backups
    backups = step_backup(interactive)

    # Step 2: Download
    photo_count = step_download(interactive)
    if photo_count <= 0:
        if photo_count == 0:
            sys.exit(0)  # Nothing to process
        else:
            print("\n  FAILED: Download step failed. Backups are in:")
            for name, path in (backups or {}).items():
                print(f"    {path}")
            sys.exit(1)

    # Step 3: ML processing
    result = step_ml_processing(interactive)
    if result.returncode != 0:
        print("\n  FAILED: Face detection failed. Backups are in:")
        for name, path in (backups or {}).items():
            print(f"    {path}")
        sys.exit(1)

    # Step 4: Clustering (ALWAYS pauses for review, even in --auto)
    result = step_clustering(interactive)
    if result.returncode != 0:
        print("\n  FAILED: Clustering failed.")
        sys.exit(1)

    if args.dry_run:
        print()
        print("=" * 60)
        print("  DRY RUN COMPLETE")
        print("=" * 60)
        print()
        print(f"  Downloaded: {photo_count} photo(s)")
        print(f"  Backups: {len(backups or {})} file(s) in {BACKUP_DIR}/")
        print()
        print("  To continue with full pipeline:")
        print("    python scripts/process_uploads.py")
        print()
        print("  Or run remaining steps manually:")
        print("    python scripts/upload_to_r2.py --execute")
        print("    python scripts/push_to_production.py")
        print("    python scripts/download_staged.py --clear-after")
        sys.exit(0)

    # Step 5: Upload to R2
    result = step_upload_r2(interactive)
    if result.returncode != 0:
        print("\n  WARNING: R2 upload failed or was skipped.")
        print("  You can retry: python scripts/upload_to_r2.py --execute")

    # Step 6: Push to production
    result = step_push_production(interactive)
    if result.returncode != 0:
        print("\n  WARNING: Production push failed or was skipped.")
        print("  You can retry: python scripts/push_to_production.py")

    # Step 7: Clear staging
    step_clear_staging(interactive)

    # Summary
    print_summary(before_ids, before_photos, photo_count, backups or {})


if __name__ == "__main__":
    main()
