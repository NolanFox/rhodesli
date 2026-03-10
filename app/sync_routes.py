"""
Sync routes extracted from app/main.py.

All /api/sync/* routes plus sync-exclusive helpers (_check_sync_token, _prune_bak_files).
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fasthtml.common import *
from starlette.responses import FileResponse

# Import route decorator only (bound once, never reassigned)
from app.main import rt

# All other main.py functions accessed via module reference
# so that test patches on app.main.X work correctly
import app.main as _main_mod


def _check_sync_token(request):
    """Validate Bearer token for sync API. Returns None if valid, Response if not."""
    if not _main_mod.SYNC_API_TOKEN:
        return Response("Sync API not configured (RHODESLI_SYNC_TOKEN not set)", status_code=503)
    auth_header = request.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
    if token != _main_mod.SYNC_API_TOKEN:
        return Response("Unauthorized", status_code=401)
    return None


@rt("/api/sync/status")
def get(request):
    """Public endpoint — shows data stats without requiring auth."""
    registry = _main_mod.load_registry()
    identities = registry.list_identities()
    confirmed = sum(1 for i in identities if i.get("state") == "CONFIRMED")
    proposed = sum(1 for i in identities if i.get("state") == "PROPOSED")
    inbox = sum(1 for i in identities if i.get("state") == "INBOX")

    photo_count = 0
    photo_index_path = _main_mod.data_path / "photo_index.json"
    if photo_index_path.exists():
        with open(photo_index_path) as f:
            index = json.load(f)
            photo_count = len(index.get("photos", {}))

    return {
        "identities": len(identities),
        "confirmed": confirmed,
        "proposed": proposed,
        "inbox": inbox,
        "photos": photo_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@rt("/api/sync/identities")
def get(request):
    """Download identities.json via sync token. For scripts/sync_from_production.py."""
    denied = _check_sync_token(request)
    if denied:
        return denied
    fpath = _main_mod.data_path / "identities.json"
    if not fpath.exists():
        return Response("File not found", status_code=404)
    with open(fpath) as f:
        data = json.load(f)
    return data


@rt("/api/sync/photo-index")
def get(request):
    """Download photo_index.json via sync token. For scripts/sync_from_production.py."""
    denied = _check_sync_token(request)
    if denied:
        return denied
    fpath = _main_mod.data_path / "photo_index.json"
    if not fpath.exists():
        return Response("File not found", status_code=404)
    with open(fpath) as f:
        data = json.load(f)
    return data


@rt("/api/sync/annotations")
def get(request):
    """Download annotations.json via sync token. For scripts/sync_from_production.py."""
    denied = _check_sync_token(request)
    if denied:
        return denied
    annotations = _main_mod._load_annotations()
    return annotations


# --- Staged Files API (for downloading uploads from production to local ML) ---


@rt("/api/sync/staged")
def get(request):
    """List all staged upload files awaiting local ML processing."""
    denied = _check_sync_token(request)
    if denied:
        return denied

    staging_dir = _main_mod.data_path / "staging"
    if not staging_dir.exists():
        return {"files": [], "total_files": 0, "total_size_bytes": 0}

    files = []
    total_size = 0
    for fpath in staging_dir.rglob("*"):
        if not fpath.is_file():
            continue
        rel = fpath.relative_to(staging_dir)
        size = fpath.stat().st_size
        mtime = datetime.fromtimestamp(fpath.stat().st_mtime, tz=timezone.utc).isoformat()
        files.append(
            {
                "filename": fpath.name,
                "path": str(rel),
                "size_bytes": size,
                "uploaded_at": mtime,
            }
        )
        total_size += size

    return {"files": files, "total_files": len(files), "total_size_bytes": total_size}


@_main_mod.app.get("/api/sync/staged/download/{filepath:path}")
async def download_staged_file(request, filepath: str):
    """Download a single staged file. Path is relative to staging root."""
    denied = _check_sync_token(request)
    if denied:
        return denied

    # Security: block path traversal
    if ".." in filepath or filepath.startswith("/"):
        return Response("Invalid path", status_code=400)

    staging_dir = _main_mod.data_path / "staging"
    target = (staging_dir / filepath).resolve()

    # Ensure resolved path is still inside staging dir
    if not str(target).startswith(str(staging_dir.resolve())):
        return Response("Invalid path", status_code=400)

    if not target.exists() or not target.is_file():
        return Response("File not found", status_code=404)

    return FileResponse(
        str(target),
        filename=target.name,
        media_type="application/octet-stream",
    )


# Move staged download route before FastHTML's catch-all static route
_main_mod._reorder_routes_atomic()


@rt("/api/sync/staged/clear")
async def post(request):
    """Remove staged files after successful download and processing."""
    denied = _check_sync_token(request)
    if denied:
        return denied

    import shutil

    body = await request.json()
    staging_dir = _main_mod.data_path / "staging"

    if body.get("all"):
        # Clear entire staging directory
        removed = []
        if staging_dir.exists():
            for item in list(staging_dir.iterdir()):
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
                removed.append(str(item.relative_to(staging_dir)))
        return {"cleared": "all", "removed": removed, "count": len(removed)}

    file_list = body.get("files", [])
    if not file_list:
        return Response("No files specified", status_code=400)

    removed = []
    errors = []
    for rel_path in file_list:
        if ".." in rel_path or rel_path.startswith("/"):
            errors.append({"path": rel_path, "error": "invalid path"})
            continue
        target = (staging_dir / rel_path).resolve()
        if not str(target).startswith(str(staging_dir.resolve())):
            errors.append({"path": rel_path, "error": "invalid path"})
            continue
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            else:
                target.unlink(missing_ok=True)
            removed.append(rel_path)
            # Clean up empty parent directories
            parent = target.parent
            while parent != staging_dir and parent.exists():
                if not any(parent.iterdir()):
                    parent.rmdir()
                    parent = parent.parent
                else:
                    break
        else:
            errors.append({"path": rel_path, "error": "not found"})

    return {"removed": removed, "errors": errors, "count": len(removed)}


@rt("/api/sync/staged/mark-processed")
async def post(request):
    """Mark staging jobs as processed in pending_uploads.json.

    Called by the pipeline after successful processing to remove jobs from
    the Pending Uploads admin page.

    Accepts JSON body with:
        job_ids: list of job IDs to mark as processed
        all: bool — mark ALL staged jobs as processed
    """
    denied = _check_sync_token(request)
    if denied:
        return denied

    body = await request.json()
    pending = _main_mod._load_pending_uploads()

    marked = []
    if body.get("all"):
        for job_id, upload in pending["uploads"].items():
            if upload.get("status") == "staged":
                upload["status"] = "processed"
                upload["processed_at"] = datetime.now(timezone.utc).isoformat()
                marked.append(job_id)
    else:
        job_ids = body.get("job_ids", [])
        if not job_ids:
            return Response("Must provide 'job_ids' or 'all'", status_code=400)
        for job_id in job_ids:
            if job_id in pending["uploads"]:
                upload = pending["uploads"][job_id]
                if upload.get("status") in ("staged", "approved"):
                    upload["status"] = "processed"
                    upload["processed_at"] = datetime.now(timezone.utc).isoformat()
                    marked.append(job_id)

    if marked:
        _main_mod._save_pending_uploads(pending)

    return {"marked_processed": marked, "count": len(marked)}


@rt("/api/sync/repair-upload")
async def post(request):
    """Repair a broken upload by copying file from uploads/ to raw_photos/ and uploading to R2.

    Accepts JSON body with:
        job_id: The upload job ID to repair

    Protected by sync token.
    """
    denied = _check_sync_token(request)
    if denied:
        return denied

    import shutil

    body = await request.json()
    repair_job_id = body.get("job_id", "")
    if not repair_job_id:
        return Response("Must provide 'job_id'", status_code=400)

    data_path = _main_mod.data_path
    results = {"job_id": repair_job_id, "actions": []}

    # Find the uploads directory for this job
    # Approval handler stores in data_path/uploads/ (not data_path.parent/uploads/)
    uploads_dir = data_path / "uploads" / repair_job_id
    staging_dir = data_path / "staging" / repair_job_id
    raw_photos_dir = data_path.parent / "raw_photos"
    raw_photos_dir.mkdir(parents=True, exist_ok=True)

    # Check which directory has the files
    source_dir = None
    if uploads_dir.exists():
        source_dir = uploads_dir
        results["actions"].append(f"Found uploads dir: {uploads_dir}")
    elif staging_dir.exists():
        source_dir = staging_dir
        results["actions"].append(f"Found staging dir: {staging_dir}")
    else:
        results["actions"].append(f"No uploads or staging dir found for {repair_job_id}")
        # List what directories DO exist
        for d in [data_path.parent / "uploads", data_path.parent / "staging"]:
            if d.exists():
                subdirs = [x.name for x in d.iterdir() if x.is_dir()]
                results["actions"].append(f"Available in {d.name}/: {subdirs[:20]}")
        return results

    # Copy image files to raw_photos/
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".tiff", ".bmp"}
    copied_files = []
    for f in source_dir.iterdir():
        if f.is_file() and f.suffix.lower() in image_exts:
            dest = raw_photos_dir / f.name
            if not dest.exists():
                shutil.copy2(f, dest)
                results["actions"].append(f"Copied {f.name} to raw_photos/")
            else:
                results["actions"].append(f"{f.name} already in raw_photos/")
            copied_files.append(f)

    # Upload to R2
    try:
        _main_mod._upload_new_files_to_r2(data_path, repair_job_id)
        results["actions"].append("R2 upload completed")
    except Exception as e:
        results["actions"].append(f"R2 upload failed: {e}")

    # Invalidate caches
    _main_mod._invalidate_all_caches()
    results["actions"].append("Caches invalidated")

    return results


# --- Push API (for pushing locally-processed data back to production) ---


@rt("/api/sync/push")
async def post(request):
    """Push updated identities.json and/or photo_index.json to production.

    Accepts JSON body with keys:
        identities: full identities.json content (optional)
        photo_index: full photo_index.json content (optional)

    Creates timestamped backups before overwriting.
    Protected by sync token (same as pull endpoints).
    """
    denied = _check_sync_token(request)
    if denied:
        return denied

    import shutil
    import time

    data_path = _main_mod.data_path
    body = await request.json()

    accepted_keys = {"identities", "photo_index", "annotations", "photo_locations", "date_labels"}
    if not any(body.get(k) for k in accepted_keys):
        return Response(
            f"Must provide one of {sorted(accepted_keys)} in request body",
            status_code=400,
        )

    results = {}
    ts = int(time.time())

    # Push identities.json
    if body.get("identities"):
        identities_data = body["identities"]
        # Basic validation: must have identities key or be a dict of identities
        if not isinstance(identities_data, dict):
            return Response("identities must be a JSON object", status_code=400)

        fpath = data_path / "identities.json"
        backup_path = data_path / f"identities.json.bak.{ts}"

        if fpath.exists():
            shutil.copy2(fpath, backup_path)

        with open(fpath, "w") as f:
            json.dump(identities_data, f, indent=2)

        # Count what we received
        id_data = identities_data.get("identities", identities_data)
        results["identities"] = {
            "status": "written",
            "count": len(id_data),
            "backup": backup_path.name,
        }

    # Push photo_index.json
    if body.get("photo_index"):
        photo_data = body["photo_index"]
        if not isinstance(photo_data, dict):
            return Response("photo_index must be a JSON object", status_code=400)

        fpath = data_path / "photo_index.json"
        backup_path = data_path / f"photo_index.json.bak.{ts}"

        if fpath.exists():
            shutil.copy2(fpath, backup_path)

        with open(fpath, "w") as f:
            json.dump(photo_data, f, indent=2)

        photos = photo_data.get("photos", {})
        results["photo_index"] = {
            "status": "written",
            "count": len(photos),
            "backup": backup_path.name,
        }

    # Push annotations.json
    if body.get("annotations"):
        ann_data = body["annotations"]
        if not isinstance(ann_data, dict):
            return Response("annotations must be a JSON object", status_code=400)

        fpath = data_path / "annotations.json"
        backup_path = data_path / f"annotations.json.bak.{ts}"

        if fpath.exists():
            shutil.copy2(fpath, backup_path)

        with open(fpath, "w") as f:
            json.dump(ann_data, f, indent=2, ensure_ascii=False)

        ann_count = len(ann_data.get("annotations", {}))
        results["annotations"] = {
            "status": "written",
            "count": ann_count,
            "backup": backup_path.name,
        }

    # Push photo_locations.json
    if body.get("photo_locations"):
        loc_data = body["photo_locations"]
        if not isinstance(loc_data, dict):
            return Response("photo_locations must be a JSON object", status_code=400)

        fpath = data_path / "photo_locations.json"
        backup_path = data_path / f"photo_locations.json.bak.{ts}"

        if fpath.exists():
            shutil.copy2(fpath, backup_path)

        with open(fpath, "w") as f:
            json.dump(loc_data, f, indent=2)

        loc_count = len(loc_data.get("photos", {}))
        results["photo_locations"] = {
            "status": "written",
            "count": loc_count,
            "backup": backup_path.name,
        }

    # Push date_labels.json
    if body.get("date_labels"):
        dl_data = body["date_labels"]
        if not isinstance(dl_data, dict):
            return Response("date_labels must be a JSON object", status_code=400)

        fpath = data_path / "date_labels.json"
        backup_path = data_path / f"date_labels.json.bak.{ts}"

        if fpath.exists():
            shutil.copy2(fpath, backup_path)

        with open(fpath, "w") as f:
            json.dump(dl_data, f, indent=2)

        dl_count = len(dl_data.get("photos", dl_data))
        results["date_labels"] = {
            "status": "written",
            "count": dl_count,
            "backup": backup_path.name,
        }

    # Invalidate ALL in-memory caches so subsequent requests see the new data
    _main_mod._invalidate_all_caches()

    # Prune old .bak files to prevent unbounded disk growth (AD-162).
    # Keep at most 3 of each type (identities, photo_index, annotations).
    _prune_bak_files(data_path)

    return {"status": "ok", "results": results, "timestamp": ts}


def _prune_bak_files(directory: Path, max_keep: int = 3):
    """Remove old .bak.{timestamp} files, keeping only the most recent max_keep of each type."""
    from collections import defaultdict

    bak_files = defaultdict(list)
    for f in directory.iterdir():
        if ".bak." in f.name and f.is_file():
            # Group by base name (e.g., "identities.json" from "identities.json.bak.123")
            base = f.name.split(".bak.")[0]
            bak_files[base].append(f)
    for base, files in bak_files.items():
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for old_file in files[max_keep:]:
            try:
                old_file.unlink()
                logging.info(f"Pruned old backup: {old_file.name}")
            except OSError:
                pass


@rt("/api/sync/resync-supabase")
async def post(request, sess):
    """Re-sync JSON data to Supabase. Admin-only.

    Reads identities.json and photo_index.json from the volume,
    then upserts ALL records to Supabase. Also backfills upload_date
    on photos missing it (uses current timestamp as fallback).

    Session 96e-cont6 (initial), cont7 (upload_date backfill).
    """
    admin_check = _main_mod._check_admin(sess)
    if admin_check:
        return admin_check

    try:
        from datetime import datetime, timezone
        from core.registry import IdentityRegistry
        from core.photo_registry import PhotoRegistry
        from app.supabase_data import shadow_write_photos_batch, shadow_write_identities_batch

        data_path = _main_mod.data_path
        json_registry = IdentityRegistry.load(data_path / "identities.json")
        json_photo_reg = PhotoRegistry.load(data_path / "photo_index.json")

        # Backfill upload_date on photos missing it (BUG-1 wiped upload_date
        # for photos uploaded before the cont6 fix). Use current timestamp
        # as a reasonable fallback — these photos ARE uploaded, just missing
        # the timestamp. Also persist back to volume JSON so it sticks.
        backfill_count = 0
        now_iso = datetime.now(timezone.utc).isoformat()
        for photo_id, photo_data in json_photo_reg._photos.items():
            if not photo_data.get("upload_date"):
                photo_data["upload_date"] = now_iso
                backfill_count += 1

        # Save backfilled JSON to volume so it persists across restarts
        if backfill_count > 0:
            json_photo_reg.save(data_path / "photo_index.json")
            logging.info(f"Backfilled upload_date on {backfill_count} photos")

        photo_items = [dict(v, photo_id=k) for k, v in json_photo_reg._photos.items()]
        shadow_write_photos_batch(photo_items)

        id_items = [dict(v, identity_id=k) for k, v in json_registry._identities.items()]
        shadow_write_identities_batch(id_items)

        # Invalidate photo registry cache so the app sees updated data
        _main_mod._photo_registry_cache = None

        return {
            "status": "ok",
            "photos_synced": len(photo_items),
            "identities_synced": len(id_items),
            "upload_date_backfilled": backfill_count,
        }
    except Exception as e:
        return Response(f"Sync error: {e}", status_code=500)
