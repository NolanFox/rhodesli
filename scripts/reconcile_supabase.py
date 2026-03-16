#!/usr/bin/env python3
"""Reconcile JSON data files with Supabase tables. Session 105b.

Non-destructive by default — exports stale rows before any deletion.

Usage:
    python scripts/reconcile_supabase.py --audit
    python scripts/reconcile_supabase.py --export-stale
    python scripts/reconcile_supabase.py --prune --confirm
    python scripts/reconcile_supabase.py --backfill-missing
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _get_data_dir() -> Path:
    """Resolve data directory."""
    env = os.environ.get("DATA_DIR")
    if env:
        return Path(env)
    return Path("data")


def _load_json_ids(data_dir: Path) -> tuple[set, set]:
    """Load identity and photo IDs from JSON files."""
    identity_ids = set()
    photo_ids = set()

    id_path = data_dir / "identities.json"
    if id_path.exists():
        with open(id_path) as f:
            data = json.load(f)
        identity_ids = set(data.get("identities", {}).keys())

    pi_path = data_dir / "photo_index.json"
    if pi_path.exists():
        with open(pi_path) as f:
            data = json.load(f)
        photo_ids = set(data.get("photos", {}).keys())

    return identity_ids, photo_ids


def _load_json_face_to_photo(data_dir: Path) -> dict:
    """Load face_to_photo mapping from JSON."""
    pi_path = data_dir / "photo_index.json"
    if pi_path.exists():
        with open(pi_path) as f:
            data = json.load(f)
        return data.get("face_to_photo", {})
    return {}


def _get_supabase_ids(client) -> tuple[set, set, set]:
    """Fetch all IDs from Supabase tables (paginated)."""
    pg_identity_ids = set()
    pg_photo_ids = set()
    pg_face_ids = set()

    page_size = 1000

    # Identities
    offset = 0
    while True:
        result = client.table("identities").select("identity_id").range(offset, offset + page_size - 1).execute()
        if not result.data:
            break
        for row in result.data:
            pg_identity_ids.add(row["identity_id"])
        if len(result.data) < page_size:
            break
        offset += page_size

    # Photos
    offset = 0
    while True:
        result = client.table("photos").select("photo_id").range(offset, offset + page_size - 1).execute()
        if not result.data:
            break
        for row in result.data:
            pg_photo_ids.add(row["photo_id"])
        if len(result.data) < page_size:
            break
        offset += page_size

    # Photo faces
    offset = 0
    while True:
        result = client.table("photo_faces").select("face_id").range(offset, offset + page_size - 1).execute()
        if not result.data:
            break
        for row in result.data:
            pg_face_ids.add(row["face_id"])
        if len(result.data) < page_size:
            break
        offset += page_size

    return pg_identity_ids, pg_photo_ids, pg_face_ids


def audit(data_dir: Path) -> dict:
    """Compare JSON and Supabase data, return discrepancy report."""
    from app.supabase_data import get_supabase_client

    client = get_supabase_client()
    if not client:
        logger.error("Supabase client not available")
        return {"error": "no_client"}

    json_identity_ids, json_photo_ids = _load_json_ids(data_dir)
    json_face_to_photo = _load_json_face_to_photo(data_dir)
    json_face_ids = set(json_face_to_photo.keys())

    pg_identity_ids, pg_photo_ids, pg_face_ids = _get_supabase_ids(client)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "json": {
            "identities": len(json_identity_ids),
            "photos": len(json_photo_ids),
            "faces": len(json_face_ids),
        },
        "postgres": {
            "identities": len(pg_identity_ids),
            "photos": len(pg_photo_ids),
            "faces": len(pg_face_ids),
        },
        "stale_in_pg": {
            "identities": sorted(pg_identity_ids - json_identity_ids),
            "photos": sorted(pg_photo_ids - json_photo_ids),
            "faces": sorted(list(pg_face_ids - json_face_ids)[:50]),  # Cap at 50 for display
            "identity_count": len(pg_identity_ids - json_identity_ids),
            "photo_count": len(pg_photo_ids - json_photo_ids),
            "face_count": len(pg_face_ids - json_face_ids),
        },
        "missing_from_pg": {
            "identities": sorted(json_identity_ids - pg_identity_ids),
            "photos": sorted(json_photo_ids - pg_photo_ids),
            "faces_count": len(json_face_ids - pg_face_ids),
            "identity_count": len(json_identity_ids - pg_identity_ids),
            "photo_count": len(json_photo_ids - pg_photo_ids),
        },
    }

    # Summary
    total_stale = report["stale_in_pg"]["identity_count"] + report["stale_in_pg"]["photo_count"]
    total_missing = report["missing_from_pg"]["identity_count"] + report["missing_from_pg"]["photo_count"]
    synced = total_stale == 0 and total_missing == 0

    report["summary"] = {
        "synced": synced,
        "total_stale": total_stale,
        "total_missing": total_missing,
    }

    return report


def export_stale(data_dir: Path, output_path: Path) -> dict:
    """Export full row data for stale Supabase rows to a JSON artifact."""
    from app.supabase_data import get_supabase_client

    client = get_supabase_client()
    if not client:
        logger.error("Supabase client not available")
        return {"error": "no_client"}

    json_identity_ids, json_photo_ids = _load_json_ids(data_dir)
    pg_identity_ids, pg_photo_ids, _ = _get_supabase_ids(client)

    stale_identity_ids = sorted(pg_identity_ids - json_identity_ids)
    stale_photo_ids = sorted(pg_photo_ids - json_photo_ids)

    # Fetch full row data for stale identities
    stale_identities = []
    batch_size = 200
    for i in range(0, len(stale_identity_ids), batch_size):
        batch = stale_identity_ids[i : i + batch_size]
        result = client.table("identities").select("*").in_("identity_id", batch).execute()
        if result.data:
            stale_identities.extend(result.data)

    # Fetch full row data for stale photos
    stale_photos = []
    for i in range(0, len(stale_photo_ids), batch_size):
        batch = stale_photo_ids[i : i + batch_size]
        result = client.table("photos").select("*").in_("photo_id", batch).execute()
        if result.data:
            stale_photos.extend(result.data)

    artifact = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Backup of stale Supabase rows before pruning (Session 105b)",
        "stale_identities": stale_identities,
        "stale_photos": stale_photos,
        "counts": {
            "identities": len(stale_identities),
            "photos": len(stale_photos),
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(artifact, f, indent=2, default=str)

    logger.info(f"Exported {len(stale_identities)} identities + {len(stale_photos)} photos to {output_path}")
    return artifact


def prune_stale(data_dir: Path, confirm: bool = False) -> dict:
    """Delete stale rows from Supabase (rows not present in JSON).

    REQUIRES --confirm flag. Always exports first as safety net.
    """
    from app.supabase_data import get_supabase_client

    if not confirm:
        logger.error("Prune requires --confirm flag. Run --audit first to review.")
        return {"error": "confirmation_required"}

    # Export first as safety net
    export_path = Path("docs/assessments/session-105b-stale-export.json")
    artifact = export_stale(data_dir, export_path)
    if "error" in artifact:
        return artifact

    client = get_supabase_client()
    json_identity_ids, json_photo_ids = _load_json_ids(data_dir)
    pg_identity_ids, pg_photo_ids, _ = _get_supabase_ids(client)

    stale_identity_ids = sorted(pg_identity_ids - json_identity_ids)
    stale_photo_ids = sorted(pg_photo_ids - json_photo_ids)

    # Delete stale identities in batches
    id_deleted = 0
    batch_size = 200
    for i in range(0, len(stale_identity_ids), batch_size):
        batch = stale_identity_ids[i : i + batch_size]
        try:
            client.table("identities").delete().in_("identity_id", batch).execute()
            id_deleted += len(batch)
        except Exception as e:
            logger.error(f"Failed to delete identity batch: {e}")

    # Delete stale photos (and their photo_faces via FK cascade or manual)
    photo_deleted = 0
    for i in range(0, len(stale_photo_ids), batch_size):
        batch = stale_photo_ids[i : i + batch_size]
        try:
            # Delete photo_faces first (FK constraint)
            client.table("photo_faces").delete().in_("photo_id", batch).execute()
            client.table("photos").delete().in_("photo_id", batch).execute()
            photo_deleted += len(batch)
        except Exception as e:
            logger.error(f"Failed to delete photo batch: {e}")

    result = {
        "identities_deleted": id_deleted,
        "photos_deleted": photo_deleted,
        "export_path": str(export_path),
    }
    logger.info(f"Pruned {id_deleted} identities + {photo_deleted} photos from Supabase")
    return result


def backfill_missing(data_dir: Path) -> dict:
    """Add rows from JSON that are missing in Supabase."""
    from app.supabase_data import (
        get_supabase_client,
        shadow_write_identities_batch,
        shadow_write_photos_batch,
        shadow_write_photo_faces_batch,
    )

    client = get_supabase_client()
    if not client:
        return {"error": "no_client"}

    json_identity_ids, json_photo_ids = _load_json_ids(data_dir)
    pg_identity_ids, pg_photo_ids, _ = _get_supabase_ids(client)

    # Backfill missing identities
    missing_ids = json_identity_ids - pg_identity_ids
    id_written = 0
    if missing_ids:
        id_path = data_dir / "identities.json"
        with open(id_path) as f:
            all_identities = json.load(f).get("identities", {})
        items = [dict(v, identity_id=k) for k, v in all_identities.items() if k in missing_ids]
        id_written = shadow_write_identities_batch(items)

    # Backfill missing photos
    missing_photos = json_photo_ids - pg_photo_ids
    photo_written = 0
    face_written = 0
    if missing_photos:
        pi_path = data_dir / "photo_index.json"
        with open(pi_path) as f:
            pi_data = json.load(f)
        all_photos = pi_data.get("photos", {})
        items = [dict(v, photo_id=k) for k, v in all_photos.items() if k in missing_photos]
        photo_written = shadow_write_photos_batch(items)

        # Also backfill photo_faces for missing photos
        face_items = [
            {"photo_id": k, "face_ids": list(v.get("face_ids", []))}
            for k, v in all_photos.items()
            if k in missing_photos
        ]
        face_written = shadow_write_photo_faces_batch(face_items)

    result = {
        "identities_backfilled": id_written,
        "photos_backfilled": photo_written,
        "faces_backfilled": face_written,
    }
    logger.info(f"Backfilled {id_written} identities + {photo_written} photos + {face_written} faces")
    return result


def main():
    parser = argparse.ArgumentParser(description="Reconcile JSON data with Supabase")
    parser.add_argument("--audit", action="store_true", help="Compare JSON vs Supabase and report")
    parser.add_argument("--export-stale", action="store_true", help="Export stale PG rows to artifact")
    parser.add_argument("--prune", action="store_true", help="Delete stale PG rows (requires --confirm)")
    parser.add_argument("--backfill-missing", action="store_true", help="Add JSON rows missing from PG")
    parser.add_argument("--confirm", action="store_true", help="Confirm destructive operations")
    parser.add_argument("--data-dir", type=Path, default=None, help="Data directory override")
    args = parser.parse_args()

    data_dir = args.data_dir or _get_data_dir()

    if not any([args.audit, args.export_stale, args.prune, args.backfill_missing]):
        parser.print_help()
        return

    if args.audit:
        report = audit(data_dir)
        print(json.dumps(report, indent=2, default=str))

    if args.export_stale:
        output = Path("docs/assessments/session-105b-stale-export.json")
        export_stale(data_dir, output)

    if args.prune:
        result = prune_stale(data_dir, confirm=args.confirm)
        print(json.dumps(result, indent=2))

    if args.backfill_missing:
        result = backfill_missing(data_dir)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
