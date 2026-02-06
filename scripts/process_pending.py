"""Process approved pending uploads.

Moves files from staging to uploads directory and updates status
in pending_uploads.json.

Usage:
    python scripts/process_pending.py --dry-run    # Preview what would be processed
    python scripts/process_pending.py --execute    # Actually process

This script is intended to be run locally by admins after approving
uploads via the web UI. It handles the file movement step; actual
ML processing (face detection, embeddings) is done separately via
core/ingest_inbox.py.
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Resolve project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def load_pending_uploads() -> dict:
    """Load pending uploads registry."""
    path = DATA_DIR / "pending_uploads.json"
    if not path.exists():
        return {"uploads": {}}
    with open(path) as f:
        return json.load(f)


def save_pending_uploads(data: dict) -> None:
    """Save pending uploads registry (atomic write)."""
    path = DATA_DIR / "pending_uploads.json"
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    tmp.rename(path)


def main():
    parser = argparse.ArgumentParser(description="Process approved pending uploads")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview what would be processed")
    group.add_argument("--execute", action="store_true", help="Actually process approved uploads")
    args = parser.parse_args()

    pending = load_pending_uploads()
    approved = [
        (job_id, upload)
        for job_id, upload in pending["uploads"].items()
        if upload["status"] == "approved"
    ]

    if not approved:
        print("No approved uploads to process.")
        return

    print(f"Found {len(approved)} approved upload(s):")
    for job_id, upload in approved:
        file_count = upload.get("file_count", len(upload.get("files", [])))
        print(f"  - {job_id}: {file_count} file(s) from {upload.get('uploader_email', 'unknown')}")
        print(f"    Source: {upload.get('source', 'Unknown')}")
        print(f"    Approved: {upload.get('reviewed_at', 'Unknown')}")

    if args.dry_run:
        print("\n[DRY RUN] No changes made. Run with --execute to process.")
        return

    # Execute: move files from staging to uploads
    print("\nProcessing...")
    staging_base = DATA_DIR / "staging"
    uploads_base = DATA_DIR / "uploads"
    uploads_base.mkdir(parents=True, exist_ok=True)

    processed = 0
    for job_id, upload in approved:
        staging_dir = staging_base / job_id
        uploads_dir = uploads_base / job_id

        if not staging_dir.exists():
            print(f"  WARNING: Staging directory not found for {job_id}, skipping")
            upload["status"] = "processed"
            upload["processed_at"] = datetime.now(timezone.utc).isoformat()
            upload["process_note"] = "staging directory missing"
            continue

        # Copy files to uploads directory
        print(f"  Moving {job_id} from staging to uploads...")
        shutil.copytree(staging_dir, uploads_dir, dirs_exist_ok=True)

        # Update status
        upload["status"] = "processed"
        upload["processed_at"] = datetime.now(timezone.utc).isoformat()
        processed += 1

        print(f"  Done. Files in {uploads_dir}")

    save_pending_uploads(pending)
    print(f"\nProcessed {processed} upload(s).")
    print("Next step: Run face detection on the new uploads:")
    for job_id, upload in approved:
        uploads_dir = uploads_base / job_id
        if uploads_dir.exists():
            source = upload.get("source", "")
            source_arg = f' --source "{source}"' if source else ""
            print(f"  python -m core.ingest_inbox --directory {uploads_dir} --job-id {job_id}{source_arg}")


if __name__ == "__main__":
    main()
