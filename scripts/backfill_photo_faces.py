#!/usr/bin/env python3
"""Backfill missing photo_faces and photos rows in Supabase.

Compares embeddings.npy face_ids against photo_faces table and inserts
any missing entries. Also inserts missing photos table entries for files
that exist in embeddings but not in Supabase.

Usage:
    python scripts/backfill_photo_faces.py --dry-run   # Show what would be inserted
    python scripts/backfill_photo_faces.py --execute    # Actually insert

Created: Session 130 — Data Integrity Deep Audit
"""

import argparse
import hashlib
import logging
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.supabase_data import get_supabase_client
from app.utils import generate_face_id, generate_photo_id

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _load_existing_photo_faces(client) -> set[str]:
    """Load all face_ids currently in photo_faces table."""
    all_face_ids = set()
    offset = 0
    page_size = 1000
    while True:
        resp = client.table("photo_faces").select("face_id").range(offset, offset + page_size - 1).execute()
        if not resp.data:
            break
        all_face_ids.update(r["face_id"] for r in resp.data)
        if len(resp.data) < page_size:
            break
        offset += page_size
    return all_face_ids


def _load_existing_photos(client) -> dict[str, str]:
    """Load all photo_id -> path from photos table."""
    photos = {}
    offset = 0
    page_size = 1000
    while True:
        resp = client.table("photos").select("photo_id, path").range(offset, offset + page_size - 1).execute()
        if not resp.data:
            break
        for r in resp.data:
            photos[r["photo_id"]] = r.get("path", "")
        if len(resp.data) < page_size:
            break
        offset += page_size
    return photos


def _load_embeddings_faces(data_dir: Path) -> list[dict]:
    """Load all faces from embeddings.npy with their photo associations."""
    embeddings = np.load(str(data_dir / "embeddings.npy"), allow_pickle=True)
    filename_counts: dict[str, int] = {}
    faces = []

    for entry in embeddings:
        filename = entry["filename"]
        if filename not in filename_counts:
            filename_counts[filename] = 0
        idx = filename_counts[filename]
        filename_counts[filename] += 1

        face_id = entry.get("face_id") or generate_face_id(filename, idx)
        photo_id = generate_photo_id(filename)

        faces.append(
            {
                "face_id": face_id,
                "photo_id": photo_id,
                "filename": filename,
            }
        )

    return faces


def run_backfill(data_dir: Path, dry_run: bool = True) -> dict:
    """Run the backfill and return a summary."""
    client = get_supabase_client()
    if not client:
        logger.error("Supabase client not available")
        return {"error": "no_client"}

    # Load current state
    existing_face_ids = _load_existing_photo_faces(client)
    existing_photos = _load_existing_photos(client)
    embedding_faces = _load_embeddings_faces(data_dir)

    logger.info(f"Existing photo_faces rows: {len(existing_face_ids)}")
    logger.info(f"Existing photos rows: {len(existing_photos)}")
    logger.info(f"Embeddings faces: {len(embedding_faces)}")

    # Build filename -> existing photo_id map (handles inbox vs SHA256 mismatch)
    # The photos table may use inbox IDs while embeddings use SHA256 IDs.
    # We need to map through filenames to find the correct photo_id.
    filename_to_existing_pid = {}
    for pid, path in existing_photos.items():
        if path:
            fname = Path(path).name
            # Prefer inbox IDs (they have richer metadata from upload pipeline)
            if fname not in filename_to_existing_pid or pid.startswith("inbox_"):
                filename_to_existing_pid[fname] = pid

    # Find missing faces
    missing_faces = [f for f in embedding_faces if f["face_id"] not in existing_face_ids]
    logger.info(f"Missing photo_faces entries: {len(missing_faces)}")

    # Find photos that truly don't exist (no matching filename in photos table)
    photos_needed = {}
    for face in missing_faces:
        fname = face["filename"]
        if fname not in filename_to_existing_pid:
            sha_pid = face["photo_id"]
            if sha_pid not in photos_needed:
                photos_needed[sha_pid] = fname

    logger.info(f"Truly missing photos entries: {len(photos_needed)}")

    if dry_run:
        logger.info("\n=== DRY RUN — No changes made ===")
        if photos_needed:
            logger.info(f"\nWould insert {len(photos_needed)} photos:")
            for pid, fn in sorted(photos_needed.items()):
                logger.info(f"  {pid} -> raw_photos/{fn}")
        if missing_faces:
            # Group by filename
            by_file = defaultdict(list)
            for f in missing_faces:
                by_file[f["filename"]].append(f["face_id"])
            logger.info(f"\nWould insert {len(missing_faces)} photo_faces from {len(by_file)} files:")
            for fn in sorted(by_file):
                logger.info(f"  {fn}: {len(by_file[fn])} faces")
        return {
            "missing_photos": len(photos_needed),
            "missing_faces": len(missing_faces),
            "dry_run": True,
        }

    # Execute: Insert missing photos first, then photo_faces
    photos_inserted = 0
    if photos_needed:
        photo_rows = []
        for pid, fn in photos_needed.items():
            photo_rows.append(
                {
                    "photo_id": pid,
                    "path": f"raw_photos/{fn}",
                    "source": "",
                    "collection": "",
                }
            )

        batch_size = 100
        for i in range(0, len(photo_rows), batch_size):
            batch = photo_rows[i : i + batch_size]
            try:
                client.table("photos").upsert(batch).execute()
                photos_inserted += len(batch)
                logger.info(f"Inserted photos batch {i // batch_size + 1}: {len(batch)} rows")
            except Exception as e:
                logger.error(f"Failed to insert photos batch: {e}")

    # Insert missing photo_faces
    faces_inserted = 0
    if missing_faces:
        # Rebuild filename map after photo inserts
        if photos_inserted > 0:
            existing_photos = _load_existing_photos(client)
            for pid, path in existing_photos.items():
                if path:
                    fname = Path(path).name
                    if fname not in filename_to_existing_pid or pid.startswith("inbox_"):
                        filename_to_existing_pid[fname] = pid

        face_rows = []
        for face in missing_faces:
            # Use existing photo_id from photos table (handles inbox vs SHA256)
            pid = filename_to_existing_pid.get(face["filename"], face["photo_id"])
            face_rows.append(
                {
                    "face_id": face["face_id"],
                    "photo_id": pid,
                }
            )

        batch_size = 100
        for i in range(0, len(face_rows), batch_size):
            batch = face_rows[i : i + batch_size]
            try:
                client.table("photo_faces").upsert(batch).execute()
                faces_inserted += len(batch)
                logger.info(f"Inserted photo_faces batch {i // batch_size + 1}: {len(batch)} rows")
            except Exception as e:
                logger.error(f"Failed to insert photo_faces batch: {e}")

    summary = {
        "photos_inserted": photos_inserted,
        "faces_inserted": faces_inserted,
        "dry_run": False,
    }
    logger.info("\n=== BACKFILL COMPLETE ===")
    logger.info(f"Photos inserted: {photos_inserted}")
    logger.info(f"Photo_faces inserted: {faces_inserted}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Backfill missing photo_faces rows")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be inserted")
    parser.add_argument("--execute", action="store_true", help="Actually insert rows")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data", help="Data directory")
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("Must specify --dry-run or --execute")
        sys.exit(1)

    run_backfill(args.data_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
