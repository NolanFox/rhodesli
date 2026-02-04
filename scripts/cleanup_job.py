#!/usr/bin/env python3
"""
Safe cleanup of a specific ingestion job.

Removes all artifacts created by a job_id:
- Identity registry entries
- Photo registry entries
- Face crop images
- File hash entries
- Status file
- Upload directory

Embeddings are soft-deleted (marked as orphaned) per forensic invariants.

Usage:
    python scripts/cleanup_job.py JOB_ID --dry-run   # Preview changes
    python scripts/cleanup_job.py JOB_ID --execute   # Actually remove
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def cleanup_job(
    job_id: str,
    data_dir: Path,
    crops_dir: Path,
    dry_run: bool = True,
) -> dict:
    """
    Clean up all artifacts for a specific job.

    Per forensic invariants, embeddings.npy is NOT modified.
    Face IDs are tracked in orphaned_face_ids.json instead.

    Args:
        job_id: Job identifier to clean up
        data_dir: Path to data directory
        crops_dir: Path to crops directory
        dry_run: If True, only report what would be cleaned

    Returns:
        Summary dict of what was (or would be) removed
    """
    # Deferred imports to keep module light
    from core.file_hash_registry import FileHashRegistry
    from core.photo_registry import PhotoRegistry
    from core.registry import IdentityRegistry

    summary = {
        "job_id": job_id,
        "dry_run": dry_run,
        "identities_removed": [],
        "face_ids_orphaned": [],
        "photo_ids_removed": [],
        "crops_removed": [],
        "status_file_removed": False,
        "upload_dir_removed": False,
        "file_hashes_removed": [],
        "backup_path": None,
    }

    # --- 1. BACKUP (always create in execute mode) ---
    if not dry_run:
        backup_dir = (
            data_dir
            / "cleanup_backups"
            / f"{job_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        )
        backup_dir.mkdir(parents=True, exist_ok=True)
        summary["backup_path"] = str(backup_dir)

        # Backup current state files
        for filename in ["identities.json", "photo_index.json", "file_hashes.json"]:
            src = data_dir / filename
            if src.exists():
                shutil.copy2(src, backup_dir / filename)

    # --- 2. IDENTITY REGISTRY ---
    identity_path = data_dir / "identities.json"
    if identity_path.exists():
        registry = IdentityRegistry.load(identity_path)

        # Find identities to remove
        job_identities = registry.list_identities_by_job(job_id)
        for identity in job_identities:
            identity_id = identity["identity_id"]
            face_ids = registry.get_all_face_ids(identity_id)

            summary["identities_removed"].append(identity_id)
            summary["face_ids_orphaned"].extend(face_ids)

            if not dry_run:
                # Remove from registry (direct manipulation for cleanup)
                del registry._identities[identity_id]

        if not dry_run and summary["identities_removed"]:
            registry.save(identity_path)

    # --- 3. PHOTO REGISTRY ---
    photo_index_path = data_dir / "photo_index.json"
    if photo_index_path.exists():
        photo_registry = PhotoRegistry.load(photo_index_path)

        # Find photos containing job's faces
        for face_id in summary["face_ids_orphaned"]:
            photo_id = photo_registry.get_photo_for_face(face_id)
            if photo_id and photo_id not in summary["photo_ids_removed"]:
                summary["photo_ids_removed"].append(photo_id)

        if not dry_run:
            # Remove face->photo mappings and photo entries
            for face_id in summary["face_ids_orphaned"]:
                if face_id in photo_registry._face_to_photo:
                    del photo_registry._face_to_photo[face_id]

            for photo_id in summary["photo_ids_removed"]:
                if photo_id in photo_registry._photos:
                    del photo_registry._photos[photo_id]

            photo_registry.save(photo_index_path)

    # --- 4. ORPHAN EMBEDDINGS (soft delete) ---
    orphan_path = data_dir / "orphaned_face_ids.json"
    if not dry_run and summary["face_ids_orphaned"]:
        existing_orphans = []
        if orphan_path.exists():
            with open(orphan_path) as f:
                existing_orphans = json.load(f).get("orphaned_face_ids", [])

        # Add new orphans
        all_orphans = list(set(existing_orphans + summary["face_ids_orphaned"]))
        with open(orphan_path, "w") as f:
            json.dump(
                {
                    "schema_version": 1,
                    "orphaned_face_ids": all_orphans,
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                },
                f,
                indent=2,
            )

    # --- 5. FACE CROPS ---
    for face_id in summary["face_ids_orphaned"]:
        crop_path = crops_dir / f"{face_id}.jpg"
        if crop_path.exists():
            summary["crops_removed"].append(str(crop_path))
            if not dry_run:
                crop_path.unlink()

    # --- 6. FILE HASH REGISTRY ---
    hash_path = data_dir / "file_hashes.json"
    if hash_path.exists():
        hash_registry = FileHashRegistry.load(hash_path)

        # Find hashes to remove (need to iterate to collect before removal)
        hashes_to_remove = []
        for hash_val, entry in hash_registry._hashes.items():
            if entry.get("job_id") == job_id:
                hashes_to_remove.append(hash_val)

        summary["file_hashes_removed"] = hashes_to_remove

        if not dry_run and hashes_to_remove:
            hash_registry.remove_by_job(job_id)
            hash_registry.save(hash_path)

    # --- 7. STATUS FILE ---
    status_path = data_dir / "inbox" / f"{job_id}.status.json"
    if status_path.exists():
        summary["status_file_removed"] = True
        if not dry_run:
            status_path.unlink()

    # --- 8. UPLOAD DIRECTORY ---
    upload_dir = data_dir / "uploads" / job_id
    if upload_dir.exists():
        summary["upload_dir_removed"] = True
        if not dry_run:
            shutil.rmtree(upload_dir)

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Clean up artifacts from a specific ingestion job"
    )
    parser.add_argument("job_id", help="Job ID to clean up")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--dry-run", action="store_true", help="Preview changes without executing"
    )
    group.add_argument(
        "--execute", action="store_true", help="Actually remove artifacts"
    )

    args = parser.parse_args()

    # Resolve paths
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data"
    crops_dir = project_root / "app" / "static" / "crops"

    # Run cleanup
    summary = cleanup_job(
        job_id=args.job_id,
        data_dir=data_dir,
        crops_dir=crops_dir,
        dry_run=args.dry_run,
    )

    # Print summary
    mode = "DRY RUN" if args.dry_run else "EXECUTED"
    print(f"\n{'='*60}")
    print(f"CLEANUP {mode}: Job {args.job_id}")
    print(f"{'='*60}")
    print(f"Identities removed:    {len(summary['identities_removed'])}")
    print(f"Face IDs orphaned:     {len(summary['face_ids_orphaned'])}")
    print(f"Photo IDs removed:     {len(summary['photo_ids_removed'])}")
    print(f"Crops removed:         {len(summary['crops_removed'])}")
    print(f"File hashes removed:   {len(summary['file_hashes_removed'])}")
    print(f"Status file removed:   {summary['status_file_removed']}")
    print(f"Upload dir removed:    {summary['upload_dir_removed']}")

    if summary.get("backup_path"):
        print(f"\nBackup created: {summary['backup_path']}")

    if args.dry_run:
        print("\n[DRY RUN] No changes made. Use --execute to apply.")
    else:
        print("\nCleanup complete.")


if __name__ == "__main__":
    main()
