#!/usr/bin/env python3
"""
Safely remove an isolated photo registry entry after proving it is detached.

Intended for contamination cleanup where:
- the photo record is duplicated or otherwise expendable
- its face IDs are not referenced by identities or annotations
- the underlying raw asset is still retained by another photo entry

Dry-run is the default behavior. Execute mode creates a backup first.
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def _face_ids_in_identities(identity_data: dict) -> set[str]:
    faces = set()
    for identity in identity_data.get("identities", {}).values():
        if not isinstance(identity, dict):
            continue
        for key in ("anchor_ids", "candidate_ids", "negative_ids"):
            for face_id in identity.get(key, []) or []:
                if isinstance(face_id, str) and not face_id.startswith("identity:"):
                    faces.add(face_id)
    return faces


def validate_isolated_photo(photo_id: str, data_dir: Path) -> dict:
    """Return the photo record and safety-check metadata, or raise ValueError."""
    from core.photo_registry import PhotoRegistry

    photo_registry = PhotoRegistry.load(data_dir / "photo_index.json")
    photo = photo_registry._photos.get(photo_id)
    if not photo:
        raise ValueError(f"Photo not found: {photo_id}")

    face_ids = sorted(photo.get("face_ids", set()))
    path = photo.get("path", "")

    identities_path = data_dir / "identities.json"
    identity_data = json.loads(identities_path.read_text()) if identities_path.exists() else {}
    referenced_faces = _face_ids_in_identities(identity_data)
    referenced_by_identity = sorted(set(face_ids) & referenced_faces)
    if referenced_by_identity:
        raise ValueError(
            f"Photo is not isolated; faces referenced by identities: {referenced_by_identity}"
        )

    history_blob = json.dumps(identity_data.get("history", []), sort_keys=True)
    history_refs = [face_id for face_id in face_ids if face_id in history_blob]
    if history_refs:
        raise ValueError(
            f"Photo is not isolated; faces referenced by identity history: {history_refs}"
        )

    annotations_path = data_dir / "annotations.json"
    annotations_blob = annotations_path.read_text() if annotations_path.exists() else ""
    annotation_refs = [face_id for face_id in face_ids if face_id in annotations_blob]
    if annotation_refs:
        raise ValueError(
            f"Photo is not isolated; faces referenced by annotations: {annotation_refs}"
        )

    shared_photo_ids = sorted(
        other_photo_id
        for other_photo_id, other_photo in photo_registry._photos.items()
        if other_photo_id != photo_id and other_photo.get("path") == path
    )
    if not shared_photo_ids:
        raise ValueError(
            "Refusing cleanup because no other photo entry retains the same raw asset path"
        )

    return {
        "photo_registry": photo_registry,
        "photo": photo,
        "face_ids": face_ids,
        "shared_photo_ids": shared_photo_ids,
    }


def cleanup_isolated_photo(photo_id: str, data_dir: Path, dry_run: bool = True) -> dict:
    """Remove one isolated photo entry from photo_index.json with backup + orphan tracking."""
    details = validate_isolated_photo(photo_id, data_dir)
    photo_registry = details["photo_registry"]
    face_ids = details["face_ids"]

    summary = {
        "photo_id": photo_id,
        "dry_run": dry_run,
        "path": details["photo"].get("path", ""),
        "face_ids_orphaned": face_ids,
        "shared_photo_ids": details["shared_photo_ids"],
        "backup_path": None,
    }

    if dry_run:
        return summary

    backup_dir = (
        data_dir
        / "cleanup_backups"
        / f"isolated_photo_{photo_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    )
    backup_dir.mkdir(parents=True, exist_ok=True)
    summary["backup_path"] = str(backup_dir)

    for filename in ("photo_index.json", "orphaned_face_ids.json", "identities.json", "annotations.json"):
        src = data_dir / filename
        if src.exists():
            shutil.copy2(src, backup_dir / filename)

    for face_id in face_ids:
        photo_registry._face_to_photo.pop(face_id, None)
    photo_registry._photos.pop(photo_id, None)
    photo_registry.save(data_dir / "photo_index.json")

    orphan_path = data_dir / "orphaned_face_ids.json"
    orphan_data = {"schema_version": 1, "orphaned_face_ids": [], "last_updated": None}
    if orphan_path.exists():
        orphan_data = json.loads(orphan_path.read_text())
    existing = set(orphan_data.get("orphaned_face_ids", []))
    existing.update(face_ids)
    orphan_data["schema_version"] = 1
    orphan_data["orphaned_face_ids"] = sorted(existing)
    orphan_data["last_updated"] = datetime.now(timezone.utc).isoformat()
    orphan_path.write_text(json.dumps(orphan_data, indent=2) + "\n")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Safely remove an isolated photo registry entry after safety checks"
    )
    parser.add_argument("photo_id", help="Photo ID to clean up")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    group.add_argument("--execute", action="store_true", help="Apply cleanup after safety checks")
    args = parser.parse_args()

    data_dir = project_root / "data"
    dry_run = not args.execute

    summary = cleanup_isolated_photo(args.photo_id, data_dir=data_dir, dry_run=dry_run)

    mode = "DRY RUN" if dry_run else "EXECUTED"
    print(f"\n{'=' * 60}")
    print(f"ISOLATED PHOTO CLEANUP {mode}: {summary['photo_id']}")
    print(f"{'=' * 60}")
    print(f"Path:                {summary['path']}")
    print(f"Face IDs orphaned:   {len(summary['face_ids_orphaned'])}")
    print(f"Shared photo IDs:    {len(summary['shared_photo_ids'])}")
    if summary["shared_photo_ids"]:
        for other_photo_id in summary["shared_photo_ids"]:
            print(f"  - {other_photo_id}")
    if summary["backup_path"]:
        print(f"Backup created:      {summary['backup_path']}")
    if dry_run:
        print("\n[DRY RUN] No changes made. Use --execute to apply.")
    else:
        print("\nCleanup complete.")


if __name__ == "__main__":
    main()
