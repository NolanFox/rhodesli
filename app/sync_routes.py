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

    # Session 105: Write to Supabase so DATA_SOURCE=postgres sees the data.
    # This is synchronous — if it fails, we return the error (not fire-and-forget).
    supabase_results = {}
    try:
        from app.supabase_data import (
            shadow_write_identities_batch,
            shadow_write_photos_batch,
            shadow_write_photo_faces_batch,
            add_photo_to_community,
        )

        if body.get("identities"):
            id_data = body["identities"]
            identities_dict = id_data.get("identities", id_data)
            if isinstance(identities_dict, dict):
                items = [dict(v, identity_id=k) for k, v in identities_dict.items()]
                written = shadow_write_identities_batch(items)
                supabase_results["identities_synced"] = written

        if body.get("photo_index"):
            pi_data = body["photo_index"]
            photos = pi_data.get("photos", {})
            if isinstance(photos, dict):
                items = [dict(v, photo_id=k) for k, v in photos.items()]
                written = shadow_write_photos_batch(items)
                supabase_results["photos_synced"] = written

                # Session 105b: Write photo_faces alongside photos
                face_items = [{"photo_id": k, "face_ids": list(v.get("face_ids", []))} for k, v in photos.items()]
                faces_written = shadow_write_photo_faces_batch(face_items)
                supabase_results["photo_faces_synced"] = faces_written

                # Auto-assign photos to communities based on existing community assignments
                # (best effort — if community info is available from photo data)
                community_tagged = 0
                for photo_id, photo_data in photos.items():
                    community_id = photo_data.get("community_id")
                    if community_id:
                        if add_photo_to_community(photo_id, community_id):
                            community_tagged += 1
                if community_tagged:
                    supabase_results["community_tagged"] = community_tagged

    except Exception as e:
        logging.error(f"Sync push Supabase write failed: {e}")
        supabase_results["error"] = str(e)

    # Invalidate ALL in-memory caches so subsequent requests see the new data
    _main_mod._invalidate_all_caches()

    # Prune old .bak files to prevent unbounded disk growth (AD-162).
    # Keep at most 3 of each type (identities, photo_index, annotations).
    _prune_bak_files(data_path)

    results["supabase"] = supabase_results
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
        from core.registry import IdentityRegistry, IdentityState
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

        # Repair orphan faces: faces in photo_index that have no identity.
        # This happens when the upload pipeline writes faces to photo_index
        # but fails to create the INBOX identity (e.g., partial pipeline failure).
        # Without an identity, Create Identity silently returns 404 (cont8 bug).
        all_registered_faces = set()
        for iid, idata in json_registry._identities.items():
            all_registered_faces.update(idata.get("anchor_ids", []))
            all_registered_faces.update(idata.get("candidate_ids", []))

        orphan_count = 0
        for photo_id, photo_data in json_photo_reg._photos.items():
            for face_id in photo_data.get("face_ids", []):
                if face_id not in all_registered_faces:
                    json_registry.create_identity(
                        anchor_ids=[face_id],
                        user_source="resync_orphan_repair",
                        state=IdentityState.INBOX,
                    )
                    orphan_count += 1

        if orphan_count > 0:
            json_registry.save(data_path / "identities.json")
            logging.info(f"Created {orphan_count} INBOX identities for orphan faces")

        photo_items = [dict(v, photo_id=k) for k, v in json_photo_reg._photos.items()]
        shadow_write_photos_batch(photo_items)

        # Session 105b: Write photo_faces alongside photos
        from app.supabase_data import shadow_write_photo_faces_batch

        face_items = [
            {"photo_id": k, "face_ids": list(v.get("face_ids", []))} for k, v in json_photo_reg._photos.items()
        ]
        faces_written = shadow_write_photo_faces_batch(face_items)

        id_items = [dict(v, identity_id=k) for k, v in json_registry._identities.items()]
        shadow_write_identities_batch(id_items)

        # Invalidate ALL caches — _photo_cache reads upload_date from JSON,
        # so we must clear it to force rebuild with backfilled dates.
        # Just clearing _photo_registry_cache is NOT enough (bug found cont8).
        _main_mod._invalidate_all_caches()

        return {
            "status": "ok",
            "photos_synced": len(photo_items),
            "identities_synced": len(id_items),
            "photo_faces_synced": faces_written,
            "upload_date_backfilled": backfill_count,
            "orphan_faces_repaired": orphan_count,
        }
    except Exception as e:
        return Response(f"Sync error: {e}", status_code=500)


@rt("/api/admin/reconcile")
async def post(request, sess):
    """Reconcile Supabase with JSON — audit, backfill, or prune stale rows.

    Admin-only. Session 105b.

    Query params:
        action=audit — compare JSON vs Supabase, return diff report
        action=backfill — add JSON rows missing from Supabase
        action=prune&confirm=true — delete Supabase rows not in JSON (exports first)
    """
    admin_check = _main_mod._check_admin(sess)
    if admin_check:
        return admin_check

    import json as _json_rec

    params = dict(request.query_params)
    action = params.get("action", "audit")
    data_path = _main_mod.data_path

    try:
        from app.supabase_data import get_supabase_client

        client = get_supabase_client()
        if not client:
            return Response("Supabase not configured", status_code=503)

        # Load JSON IDs
        json_identity_ids = set()
        json_photo_ids = set()
        json_face_to_photo = {}

        id_path = data_path / "identities.json"
        if id_path.exists():
            with open(id_path) as f:
                id_data = _json_rec.load(f)
            json_identity_ids = set(id_data.get("identities", {}).keys())

        pi_path = data_path / "photo_index.json"
        if pi_path.exists():
            with open(pi_path) as f:
                pi_data = _json_rec.load(f)
            json_photo_ids = set(pi_data.get("photos", {}).keys())
            json_face_to_photo = pi_data.get("face_to_photo", {})

        # Load Supabase IDs (paginated)
        pg_identity_ids = set()
        pg_photo_ids = set()
        page_size = 1000

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

        stale_identities = sorted(pg_identity_ids - json_identity_ids)
        stale_photos = sorted(pg_photo_ids - json_photo_ids)
        missing_identities = sorted(json_identity_ids - pg_identity_ids)
        missing_photos = sorted(json_photo_ids - pg_photo_ids)

        if action == "audit":
            return {
                "json_identities": len(json_identity_ids),
                "json_photos": len(json_photo_ids),
                "json_faces": len(json_face_to_photo),
                "pg_identities": len(pg_identity_ids),
                "pg_photos": len(pg_photo_ids),
                "stale_identities": len(stale_identities),
                "stale_photos": len(stale_photos),
                "missing_identities": len(missing_identities),
                "missing_photos": len(missing_photos),
                "stale_identity_sample": stale_identities[:20],
                "missing_identity_sample": missing_identities[:20],
            }

        elif action == "backfill":
            from app.supabase_data import (
                shadow_write_identities_batch,
                shadow_write_photos_batch,
                shadow_write_photo_faces_batch,
            )

            id_written = 0
            if missing_identities:
                all_ids = id_data.get("identities", {})
                items = [dict(v, identity_id=k) for k, v in all_ids.items() if k in set(missing_identities)]
                id_written = shadow_write_identities_batch(items)

            photo_written = 0
            face_written = 0
            if missing_photos:
                all_photos = pi_data.get("photos", {})
                items = [dict(v, photo_id=k) for k, v in all_photos.items() if k in set(missing_photos)]
                photo_written = shadow_write_photos_batch(items)
                face_items = [
                    {"photo_id": k, "face_ids": list(v.get("face_ids", []))}
                    for k, v in all_photos.items()
                    if k in set(missing_photos)
                ]
                face_written = shadow_write_photo_faces_batch(face_items)

            _main_mod._invalidate_all_caches()
            return {
                "action": "backfill",
                "identities_written": id_written,
                "photos_written": photo_written,
                "faces_written": face_written,
            }

        elif action == "prune":
            if params.get("confirm") != "true":
                return Response("Prune requires confirm=true", status_code=400)

            # Export stale rows first (non-destructive safety net)
            exported = {"identities": [], "photos": []}
            batch_size = 200

            for i in range(0, len(stale_identities), batch_size):
                batch = stale_identities[i : i + batch_size]
                result = client.table("identities").select("*").in_("identity_id", batch).execute()
                if result.data:
                    exported["identities"].extend(result.data)

            for i in range(0, len(stale_photos), batch_size):
                batch = stale_photos[i : i + batch_size]
                result = client.table("photos").select("*").in_("photo_id", batch).execute()
                if result.data:
                    exported["photos"].extend(result.data)

            # Save export artifact
            export_path = data_path / "reconcile_export.json"
            with open(export_path, "w") as f:
                _json_rec.dump(
                    {
                        "exported_at": datetime.now(timezone.utc).isoformat(),
                        "stale_identities": exported["identities"],
                        "stale_photos": exported["photos"],
                    },
                    f,
                    indent=2,
                    default=str,
                )

            # Delete stale rows
            id_deleted = 0
            for i in range(0, len(stale_identities), batch_size):
                batch = stale_identities[i : i + batch_size]
                try:
                    client.table("identities").delete().in_("identity_id", batch).execute()
                    id_deleted += len(batch)
                except Exception as e:
                    logging.error(f"Failed to delete identity batch: {e}")

            photo_deleted = 0
            for i in range(0, len(stale_photos), batch_size):
                batch = stale_photos[i : i + batch_size]
                try:
                    client.table("photo_faces").delete().in_("photo_id", batch).execute()
                    client.table("photos").delete().in_("photo_id", batch).execute()
                    photo_deleted += len(batch)
                except Exception as e:
                    logging.error(f"Failed to delete photo batch: {e}")

            _main_mod._invalidate_all_caches()
            return {
                "action": "prune",
                "identities_deleted": id_deleted,
                "photos_deleted": photo_deleted,
                "export_path": str(export_path),
                "exported_identities": len(exported["identities"]),
                "exported_photos": len(exported["photos"]),
            }

        else:
            return Response(f"Unknown action: {action}. Use audit, backfill, or prune.", status_code=400)

    except Exception as e:
        return Response(f"Reconcile error: {e}", status_code=500)


# --- Embeddings Sync (Session 108, Lesson 147) ---


@rt("/api/sync/embeddings")
def get(request):
    """Download embeddings.npy via sync token. For sync_from_production.py --include-embeddings."""
    denied = _check_sync_token(request)
    if denied:
        return denied
    fpath = _main_mod.data_path / "embeddings.npy"
    if not fpath.exists():
        return Response("embeddings.npy not found", status_code=404)
    return FileResponse(
        str(fpath),
        filename="embeddings.npy",
        media_type="application/octet-stream",
    )


# --- Admin Re-Cluster Endpoint (Session 108) ---


@rt("/api/admin/recluster")
async def post(request, sess):
    """Re-run clustering and grouping for all faces. Admin-only.

    Session 108: When new photos are uploaded, the auto-cluster runs during
    ingest. But if it fails (e.g., orphan faces) or you want to re-run after
    confirming identities, this endpoint triggers the full pipeline:
    1. find_matches() — match unresolved faces against confirmed identities → proposals
    2. group_inbox_identities() — group similar INBOX faces → direct merge

    Query params:
        dry_run=true — preview only, don't write changes (default: true)
        threshold=1.05 — distance threshold for matching
    """
    admin_check = _main_mod._check_admin(sess)
    if admin_check:
        return admin_check

    import json as _json_rc

    params = dict(request.query_params)
    dry_run = params.get("dry_run", "true").lower() != "false"
    threshold = float(params.get("threshold", "1.05"))

    data_path = _main_mod.data_path
    results = {"dry_run": dry_run, "threshold": threshold}

    try:
        from scripts.cluster_new_faces import find_matches, load_face_data, load_identities
        from core.config import MATCH_THRESHOLD_HIGH

        identities_data = load_identities(data_path)
        face_data_dict = load_face_data(data_path)

        # Step 1: Find matches against confirmed identities
        suggestions = find_matches(identities_data, face_data_dict, threshold)
        results["proposals_found"] = len(suggestions)

        if not dry_run and suggestions:
            proposals_path = data_path / "proposals.json"
            proposals_data = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "threshold": threshold,
                "proposals": suggestions,
                "triggered_by": "admin_recluster",
            }
            with open(proposals_path, "w") as f:
                _json_rc.dump(proposals_data, f, indent=2)
            results["proposals_written"] = len(suggestions)
            # Invalidate proposals cache (PRD-051 Session 114)
            _main_mod.invalidate_proposals_cache()

        # Step 2: Group similar INBOX faces
        photo_reg = None
        try:
            from core.grouping import group_inbox_identities
            from core.registry import IdentityRegistry
            from core.photo_registry import PhotoRegistry

            registry = IdentityRegistry.load(data_path / "identities.json")
            photo_reg = PhotoRegistry.load(data_path / "photo_index.json")

            group_result = group_inbox_identities(registry, face_data_dict, photo_reg, dry_run=dry_run)
            results["groups_found"] = len(group_result.get("groups", []))
            results["merges"] = group_result.get("total_merged", 0)

            if not dry_run and group_result.get("total_merged", 0) > 0:
                registry.save(data_path / "identities.json")
                try:
                    from app.supabase_data import shadow_write_identities_batch

                    items = [dict(v, identity_id=k) for k, v in registry._identities.items()]
                    shadow_write_identities_batch(items)
                    results["supabase_synced"] = True
                except Exception as sync_err:
                    results["supabase_sync_error"] = str(sync_err)
        except Exception as grouping_err:
            results["grouping_error"] = str(grouping_err)

        # Step 3 (PRD-049): Cross-batch matching — new faces against ALL existing
        try:
            from core.cross_batch_matching import find_cross_batch_matches

            community_id = params.get("community_id")

            # Collect all INBOX face IDs for cross-batch matching
            all_inbox_face_ids = []
            all_ids = identities_data.get("identities", {})
            for iid, identity in all_ids.items():
                if identity.get("state") == "INBOX" and not identity.get("merged_into"):
                    for fid in identity.get("anchor_ids", []):
                        if isinstance(fid, str):
                            all_inbox_face_ids.append(fid)
                    all_inbox_face_ids.extend(identity.get("candidate_ids", []))

            # Use photo_reg if available from Step 2, otherwise load fresh
            if photo_reg is None:
                from core.photo_registry import PhotoRegistry

                photo_reg = PhotoRegistry.load(data_path / "photo_index.json")

            # Recluster matches globally — community_id is only used for Step 4 tagging.
            # Community filtering via identity_communities field doesn't work here because
            # JSON identities don't have identity_communities (only Supabase does).
            cross_matches = find_cross_batch_matches(
                new_face_ids=all_inbox_face_ids,
                identities=identities_data,
                face_data=face_data_dict,
                photo_registry=photo_reg,
                community_id=None,
            )
            results["cross_batch_matches"] = len(cross_matches)

            if not dry_run and cross_matches:
                proposals_path = data_path / "proposals.json"
                existing_proposals = []
                if proposals_path.exists():
                    with open(proposals_path) as _rpf:
                        pdata = _json_rc.load(_rpf)
                        existing_proposals = pdata.get("proposals", [])

                existing_pairs = {
                    (p.get("source_identity_id"), p.get("target_identity_id")) for p in existing_proposals
                }
                new_xb_proposals = []
                for m in cross_matches:
                    pair = (m["source_identity_id"], m["target_identity_id"])
                    reverse = (m["target_identity_id"], m["source_identity_id"])
                    if pair not in existing_pairs and reverse not in existing_pairs:
                        new_xb_proposals.append(
                            {
                                "source_identity_id": m["source_identity_id"],
                                "source_identity_name": m["source_identity_name"],
                                "target_identity_id": m["target_identity_id"],
                                "target_identity_name": m["target_identity_name"],
                                "distance": m["distance"],
                                "match_type": m["match_type"],
                                "confidence_tier": m["confidence_tier"],
                                "face_id": m["source_face_id"],
                                "source_state": "INBOX",
                            }
                        )
                        existing_pairs.add(pair)

                if new_xb_proposals:
                    all_proposals = existing_proposals + new_xb_proposals
                    proposals_data = {
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "threshold": threshold,
                        "proposals": all_proposals,
                        "triggered_by": "admin_recluster",
                    }
                    with open(proposals_path, "w") as _wpf:
                        _json_rc.dump(proposals_data, _wpf, indent=2)

                results["cross_batch_new_proposals"] = len(new_xb_proposals)

                # Write to Supabase ml_runs + ml_proposals
                try:
                    import time as _time_rc
                    import uuid as _uuid_rc

                    from app.supabase_data import get_supabase_client

                    sb = get_supabase_client()
                    if sb and new_xb_proposals:
                        run_id = str(_uuid_rc.uuid4())
                        start_time = _time_rc.time()
                        sb.table("ml_runs").insert(
                            {
                                "run_id": run_id,
                                "pipeline_type": "cross_batch_matching",
                                "config_json": {
                                    "threshold": threshold,
                                    "community_id": community_id,
                                    "triggered_by": "admin_recluster",
                                },
                                "status": "completed",
                                "result_summary": {
                                    "proposals_created": len(new_xb_proposals),
                                    "total_matches": len(cross_matches),
                                },
                                "duration_ms": int((_time_rc.time() - start_time) * 1000),
                            }
                        ).execute()

                        from core.config import MATCH_THRESHOLD_VERY_HIGH, MATCH_THRESHOLD_HIGH

                        rows = []
                        for p in new_xb_proposals:
                            tier = (
                                "tier1"
                                if p["distance"] < MATCH_THRESHOLD_VERY_HIGH
                                else ("tier2" if p["distance"] < MATCH_THRESHOLD_HIGH else "tier3")
                            )
                            row = {
                                "run_id": run_id,
                                "source_identity_id": p["source_identity_id"],
                                "target_identity_id": p["target_identity_id"],
                                "score": p["distance"],
                                "tier": tier,
                                "status": "pending",
                            }
                            rows.append(row)

                        for i in range(0, len(rows), 100):
                            sb.table("ml_proposals").insert(rows[i : i + 100]).execute()

                        results["supabase_proposals_written"] = len(rows)
                except Exception as sb_err:
                    results["supabase_write_error"] = str(sb_err)
                # Invalidate proposals cache after cross-batch writes (PRD-051 Session 114)
                _main_mod.invalidate_proposals_cache()
        except Exception as xb_err:
            results["cross_batch_error"] = str(xb_err)

        # Step 4: Auto-tag untagged identities to their photo's community
        # Fixes orphan-repair identities that were created without community tagging (Session 108)
        if not dry_run and community_id:
            try:
                from app.supabase_data import add_identity_to_community, load_photos_for_community

                community_photo_ids = set(load_photos_for_community(community_id) or [])
                face_to_photo_map = {}
                if photo_reg:
                    face_to_photo_map = getattr(photo_reg, "face_to_photo", {})
                    if not face_to_photo_map:
                        face_to_photo_map = getattr(photo_reg, "_face_to_photo", {})

                tagged = 0
                for iid, identity in all_ids.items():
                    if identity.get("merged_into"):
                        continue
                    existing_communities = identity.get("identity_communities", [])
                    if community_id in existing_communities:
                        continue
                    # Check if any face belongs to a photo in this community
                    face_ids = []
                    for a in identity.get("anchor_ids", []):
                        if isinstance(a, str):
                            face_ids.append(a)
                    face_ids.extend(identity.get("candidate_ids", []))

                    in_community = False
                    for fid in face_ids:
                        pid = face_to_photo_map.get(fid)
                        if pid and pid in community_photo_ids:
                            in_community = True
                            break

                    if in_community:
                        if add_identity_to_community(iid, community_id):
                            tagged += 1

                results["community_tagged"] = tagged
            except Exception as tag_err:
                results["community_tag_error"] = str(tag_err)

        if not dry_run:
            _main_mod._invalidate_all_caches()

        results["status"] = "ok"
    except Exception as e:
        results["status"] = "error"
        results["error"] = str(e)

    return results


# --- Data Health Endpoint (Session 108) ---


@rt("/api/health/data")
def get(request, sess):
    """Admin-only data health diagnostic. Returns orphan faces, stale proposals, etc."""
    admin_check = _main_mod._check_admin(sess)
    if admin_check:
        return admin_check

    import json as _json_health

    data_path = _main_mod.data_path
    report = {}

    try:
        # Load registries
        from core.registry import IdentityRegistry
        from core.photo_registry import PhotoRegistry

        id_path = data_path / "identities.json"
        pi_path = data_path / "photo_index.json"

        if not id_path.exists() or not pi_path.exists():
            return {"error": "Data files not found"}

        id_reg = IdentityRegistry.load(id_path)
        photo_reg = PhotoRegistry.load(pi_path)

        # Orphan faces: faces in photo_index with no identity
        all_registered = set()
        for iid, idata in id_reg._identities.items():
            all_registered.update(idata.get("anchor_ids", []))
            all_registered.update(idata.get("candidate_ids", []))

        orphan_faces = []
        for pid, pdata in photo_reg._photos.items():
            for fid in pdata.get("face_ids", []):
                if fid not in all_registered:
                    orphan_faces.append(fid)
        report["orphan_faces"] = {"count": len(orphan_faces), "face_ids": orphan_faces[:20]}

        # Orphan identities: identities with face_ids not in any photo
        all_photo_faces = set()
        for pid, pdata in photo_reg._photos.items():
            all_photo_faces.update(pdata.get("face_ids", []))

        orphan_identities = []
        for iid, idata in id_reg._identities.items():
            if idata.get("merged_into"):
                continue
            anchors = set(idata.get("anchor_ids", []))
            candidates = set(idata.get("candidate_ids", []))
            all_faces = anchors | candidates
            if all_faces and not all_faces.intersection(all_photo_faces):
                orphan_identities.append(iid)
        report["orphan_identities"] = {"count": len(orphan_identities), "identity_ids": orphan_identities[:20]}

        # Embedding count vs face count
        emb_path = data_path / "embeddings.npy"
        if emb_path.exists():
            import numpy as np

            emb_data = np.load(str(emb_path), allow_pickle=True)
            report["embeddings"] = {
                "count": len(emb_data),
                "photo_faces_count": len(all_photo_faces),
                "match": len(emb_data) >= len(all_photo_faces),
            }
        else:
            report["embeddings"] = {"count": 0, "photo_faces_count": len(all_photo_faces), "match": False}

        # Proposals count — unified reader (Supabase or JSON, PRD-051 Session 114)
        try:
            proposals = _main_mod._load_proposals()
            report["proposals"] = {
                "count": len(proposals.get("proposals", [])),
                "generated_at": proposals.get("generated_at", "unknown"),
            }
        except Exception:
            report["proposals"] = {"count": 0, "generated_at": None}

        # Identity stats
        total = len(id_reg._identities)
        merged = sum(1 for v in id_reg._identities.values() if v.get("merged_into"))
        confirmed = sum(1 for v in id_reg._identities.values() if v.get("state") == "CONFIRMED")
        inbox = sum(1 for v in id_reg._identities.values() if v.get("state") == "INBOX")
        proposed = sum(1 for v in id_reg._identities.values() if v.get("state") == "PROPOSED")
        report["identities"] = {
            "total": total,
            "active": total - merged,
            "confirmed": confirmed,
            "proposed": proposed,
            "inbox": inbox,
            "merged": merged,
        }

        report["photos"] = {"count": len(photo_reg._photos)}
        report["status"] = "healthy" if not orphan_faces and not orphan_identities else "issues_found"

    except Exception as e:
        report["error"] = str(e)
        report["status"] = "error"

    return report
