#!/usr/bin/env python3
"""Batch Gemini event context extraction for all photos in a community.

Runs the "identification" preset (event_context + relationship_inference)
with response_schema enforcement on all photos in a given community.

Upserts results to Supabase date_labels table (source of truth — Lesson 162).
Logs every call to gemini_api_calls table (AD-152).

Usage:
    # Dry run: count photos, show cost estimate
    python scripts/batch_event_context.py --dry-run

    # Run on 5 photos to verify
    python scripts/batch_event_context.py --limit 5

    # Full run on all Fader photos
    python scripts/batch_event_context.py --max-cost 10.0

    # Custom community
    python scripts/batch_event_context.py --community-id <uuid>

Session 151: Created for batch Fader event context extraction (deferred from Session 150).
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Fader collection community ID
FADER_COMMUNITY_ID = "1a2c23d6-fc5e-4d0e-b020-1721579485bf"


class QuotaExhaustedError(Exception):
    """Raised when Gemini API returns 429 RESOURCE_EXHAUSTED."""

    pass


def get_supabase_client():
    """Create a Supabase client with dotenv loaded."""
    from dotenv import load_dotenv

    load_dotenv()

    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) must be set")
    return create_client(url, key)


def get_community_photo_ids(community_id: str) -> list[str]:
    """Get all photo_ids belonging to a community from Supabase."""
    sb = get_supabase_client()
    photo_ids = []
    offset = 0
    page_size = 1000
    while True:
        resp = (
            sb.table("photo_communities")
            .select("photo_id")
            .eq("community_id", community_id)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = resp.data or []
        for row in rows:
            photo_ids.append(row["photo_id"])
        if len(rows) < page_size:
            break
        offset += page_size
    logger.info(f"Found {len(photo_ids)} photos in community {community_id}")
    return photo_ids


def get_photos_with_metadata(photo_ids: list[str]) -> dict[str, dict]:
    """Load photo metadata from Supabase for given photo_ids."""
    sb = get_supabase_client()
    photos = {}
    # Batch query in chunks of 100
    for i in range(0, len(photo_ids), 100):
        chunk = photo_ids[i : i + 100]
        resp = sb.table("photos").select("photo_id, path, source, collection").in_("photo_id", chunk).execute()
        for row in resp.data or []:
            photos[row["photo_id"]] = row
    logger.info(f"Loaded metadata for {len(photos)} photos")
    return photos


def load_existing_event_context() -> set[str]:
    """Load photo_ids that already have event_context in date_labels."""
    sb = get_supabase_client()
    existing = set()
    offset = 0
    while True:
        resp = sb.table("date_labels").select("photo_id, data").range(offset, offset + 999).execute()
        if not resp.data:
            break
        for row in resp.data:
            data = row.get("data") or {}
            if isinstance(data, str):
                data = json.loads(data)
            if data.get("event_context"):
                existing.add(row["photo_id"])
        if len(resp.data) < 1000:
            break
        offset += 1000
    logger.info(f"Found {len(existing)} photos with existing event_context")
    return existing


def resolve_photo_path(photo_entry: dict) -> Path | None:
    """Resolve the local file path for a photo.

    Security: rejects absolute paths and path traversal (Codex P1).
    Only resolves within raw_photos/ directory.
    """
    filename = photo_entry.get("path", "")
    if not filename:
        return None
    basename = Path(filename).name
    # Reject path traversal attempts
    if ".." in basename or basename.startswith("/"):
        logger.warning(f"  Rejected suspicious path: {filename}")
        return None
    path = Path("raw_photos") / basename
    if path.exists():
        return path
    return None


def run_batch(
    community_id: str,
    dry_run: bool = False,
    skip_existing: bool = True,
    max_cost: float = 10.0,
    delay_between: float = 2.0,
    limit: int | None = None,
):
    """Run Gemini identification preset on all photos in a community."""
    from dotenv import load_dotenv

    load_dotenv()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key and not dry_run:
        logger.error("GEMINI_API_KEY not set.")
        sys.exit(1)

    # Get community photos
    photo_ids = get_community_photo_ids(community_id)
    if not photo_ids:
        logger.error("No photos found in community")
        return

    photos = get_photos_with_metadata(photo_ids)

    # Filter already-processed
    if skip_existing:
        existing = load_existing_event_context()
        before = len(photos)
        photos = {pid: p for pid, p in photos.items() if pid not in existing}
        skipped = before - len(photos)
        if skipped:
            logger.info(f"Skipping {skipped} photos with existing event_context")

    # Filter photos without local files
    photos_with_files = {}
    missing_files = 0
    for pid, photo in photos.items():
        path = resolve_photo_path(photo)
        if path:
            photos_with_files[pid] = {**photo, "_local_path": str(path)}
        else:
            missing_files += 1

    if missing_files:
        logger.warning(f"{missing_files} photos have no local file (R2-only, skipped)")

    photos = photos_with_files
    logger.info(f"Photos to process: {len(photos)}")

    # Apply limit
    photo_list = list(photos.items())
    if limit:
        photo_list = photo_list[:limit]
        logger.info(f"Limited to {limit} photos")

    # Cost estimate
    cost_per_photo = 0.04  # identification preset (smaller than full)
    estimated_cost = len(photo_list) * cost_per_photo
    logger.info(f"Estimated cost: ${estimated_cost:.2f} (at ${cost_per_photo}/photo)")

    if estimated_cost > max_cost:
        max_photos = int(max_cost / cost_per_photo)
        photo_list = photo_list[:max_photos]
        logger.info(f"Capped at {max_photos} photos to stay under ${max_cost:.2f} budget")

    if dry_run:
        logger.info("=== DRY RUN ===")
        logger.info(f"Would process {len(photo_list)} photos")
        logger.info(f"Estimated cost: ${len(photo_list) * cost_per_photo:.2f}")
        logger.info(f"Estimated time: {len(photo_list) * (delay_between + 3):.0f}s")
        for pid, photo in photo_list[:10]:
            filename = Path(photo.get("path", "unknown")).name
            logger.info(f"  {pid[:12]}... {filename}")
        if len(photo_list) > 10:
            logger.info(f"  ... and {len(photo_list) - 10} more")
        return

    # Import production functions
    from rhodesli_ml.gemini_extraction import build_extraction_prompt, build_response_schema
    from rhodesli_ml.gemini_config import GEMINI_MODEL, get_model_pricing
    from rhodesli_ml.prompt_manifest import build_prompt_lineage_fields, build_prompt_manifest
    from app.supabase_data import log_gemini_call
    from google import genai
    from google.genai import types
    import numpy as np

    # Pre-load face data for bounding box coordinates
    embeddings_path = Path("data/embeddings.npy")
    face_data = {}
    if embeddings_path.exists():
        emb = np.load(str(embeddings_path), allow_pickle=True)
        for idx, entry in enumerate(emb):
            fid = entry.get("face_id")
            if not fid:
                fname = entry.get("filename", "")
                fid = f"{Path(fname).stem}:face{idx}" if fname else f"face{idx}"
            face_data[fid] = entry
        logger.info(f"Loaded {len(face_data)} face entries from embeddings.npy")

    # Pre-load photo_faces from Supabase for face-to-photo mapping
    sb = get_supabase_client()
    photo_face_ids: dict[str, list[str]] = {}
    offset = 0
    while True:
        resp = sb.table("photo_faces").select("face_id, photo_id").range(offset, offset + 999).execute()
        rows = resp.data or []
        for row in rows:
            pid = row["photo_id"]
            if pid not in photo_face_ids:
                photo_face_ids[pid] = []
            photo_face_ids[pid].append(row["face_id"])
        if len(rows) < 1000:
            break
        offset += 1000
    logger.info(f"Loaded face mappings for {len(photo_face_ids)} photos")

    # Build response schema for identification preset
    response_schema = build_response_schema(preset="identification")

    def _get_face_coordinates(photo_id):
        """Get face bounding boxes for a photo, sorted left-to-right."""
        coords = []
        fids = photo_face_ids.get(photo_id, [])
        for fid in fids:
            fd = face_data.get(fid)
            if fd is not None:
                bbox = fd.get("bbox", [])
                if isinstance(bbox, str):
                    try:
                        bbox = json.loads(bbox)
                    except Exception:
                        bbox = []
                if hasattr(bbox, "tolist"):
                    bbox = bbox.tolist()
                if bbox and len(bbox) >= 4:
                    coords.append({"face_id": fid, "bbox": bbox})
        coords.sort(key=lambda c: c["bbox"][0])
        return coords if coords else None

    def _call_gemini_identification(image_bytes, suffix, photo_id, photo_metadata, face_coordinates):
        """Call Gemini with identification preset + response_schema."""
        import time as _time

        prompt_text = build_extraction_prompt(
            preset="identification",
            face_coordinates=face_coordinates,
            photo_metadata=photo_metadata,
        )
        enrichment_level = "faces" if face_coordinates else "none"
        prompt_variant = f"identification_{enrichment_level}"
        prompt_manifest = build_prompt_manifest(
            prompt_family="event_context_extraction",
            prompt_version="v1",
            prompt_variant=prompt_variant,
            prompt_contract_version="1",
            channel="batch",
            context_flags={
                "uses_gedcom": False,
                "uses_geo": True,
                "uses_time": True,
                "uses_face_coords": bool(face_coordinates),
            },
            template_source="rhodesli_ml.gemini_extraction.build_extraction_prompt",
        )

        client = genai.Client(
            api_key=api_key,
            http_options={"timeout": 180_000},
        )
        mime_type = "image/png" if suffix.lower() == ".png" else "image/jpeg"

        start_time = _time.time()
        status = "success"
        error_msg = None
        parsed = None
        latency_ms = 0

        max_retries = 2
        retry_delays = [5, 15]
        try:
            for attempt in range(1 + max_retries):
                try:
                    if attempt > 0:
                        delay = retry_delays[attempt - 1]
                        logger.info(f"  Retry {attempt}/{max_retries} after {delay}s")
                        _time.sleep(delay)
                        start_time = _time.time()

                    response = client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=[
                            types.Content(
                                parts=[
                                    types.Part.from_text(text=prompt_text),
                                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                                ]
                            )
                        ],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=response_schema,
                            temperature=0.1,
                        ),
                    )
                    latency_ms = int((_time.time() - start_time) * 1000)

                    text = response.text
                    if not text:
                        status = "error"
                        error_msg = "Empty response"
                        return None

                    parsed = json.loads(text)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        parsed = parsed[0]

                    return parsed

                except Exception as e:
                    latency_ms = int((_time.time() - start_time) * 1000)
                    error_msg = str(e)
                    if "429" in error_msg and "RESOURCE_EXHAUSTED" in error_msg:
                        status = "error"
                        logger.error(f"  Quota exhausted: {e}")
                        raise QuotaExhaustedError(str(e))
                    is_retryable = any(
                        s in error_msg for s in ["504", "503", "DEADLINE_EXCEEDED", "timeout", "Timeout"]
                    )
                    if is_retryable and attempt < max_retries:
                        logger.warning(f"  Retryable error (attempt {attempt + 1}): {e}")
                        continue
                    status = "error"
                    logger.warning(f"  Gemini API error (final): {e}")
                    return None
        finally:
            if photo_id:
                try:
                    pricing = get_model_pricing(GEMINI_MODEL)
                    prompt_tokens = len(prompt_text) // 4
                    resp_text = json.dumps(parsed) if parsed else ""
                    completion_tokens = len(resp_text) // 4
                    total_tokens = prompt_tokens + completion_tokens
                    cost_usd = (
                        prompt_tokens * pricing.get("input", 2.0) / 1_000_000
                        + completion_tokens * pricing.get("output", 12.0) / 1_000_000
                    )
                    response_summary = None
                    if parsed:
                        ec = parsed.get("event_context", {})
                        ri = parsed.get("relationship_inference", {})
                        response_summary = {
                            "event_type": ec.get("event_type"),
                            "formality_level": ec.get("formality_level"),
                            "role_count": len(ec.get("role_indicators", [])),
                            "couple_pairs": len(ri.get("couple_pairs", [])),
                            "parent_child_pairs": len(ri.get("parent_child_pairs", [])),
                            "face_count": len(face_coordinates) if face_coordinates else 0,
                        }
                    log_gemini_call(
                        photo_id=photo_id,
                        model_used=GEMINI_MODEL,
                        call_type="batch_event_context",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        cost_usd=round(cost_usd, 6),
                        latency_ms=latency_ms,
                        status=status,
                        error_message=error_msg,
                        gemini_config={
                            "enrichment_level": enrichment_level,
                            "prompt_version": "v1",
                            "prompt_variant": prompt_variant,
                            "prompt_manifest_id": prompt_manifest["prompt_manifest_id"],
                            "prompt_family": prompt_manifest["prompt_family"],
                            "prompt_contract_version": prompt_manifest["prompt_contract_version"],
                            "temperature": 0.1,
                            "trigger": "batch_event_context",
                            "preset": "identification",
                            "face_count": len(face_coordinates) if face_coordinates else 0,
                            "request_surface": "scripts.batch_event_context",
                            "request_mode": "batch",
                        },
                        response_summary=response_summary,
                        prompt_text=prompt_text,
                        full_response=parsed if parsed else None,
                    )
                except Exception as log_err:
                    logger.warning(f"  Failed to log Gemini call: {log_err}")

    success_count = 0
    error_count = 0
    total_cost = 0.0

    for i, (pid, photo) in enumerate(photo_list):
        filename = Path(photo.get("path", "unknown")).name
        logger.info(f"[{i + 1}/{len(photo_list)}] {filename}")

        local_path = Path(photo["_local_path"])
        try:
            image_bytes = local_path.read_bytes()
        except Exception as e:
            logger.error(f"  Failed to read {local_path}: {e}")
            error_count += 1
            continue

        suffix = local_path.suffix
        face_coordinates = _get_face_coordinates(pid)
        if face_coordinates:
            logger.info(f"  {len(face_coordinates)} faces with bounding boxes")

        try:
            result = _call_gemini_identification(
                image_bytes=image_bytes,
                suffix=suffix,
                photo_id=pid,
                photo_metadata={
                    "filename": filename,
                    "source": photo.get("source", ""),
                    "collection": photo.get("collection", ""),
                },
                face_coordinates=face_coordinates,
            )
        except QuotaExhaustedError:
            remaining = len(photo_list) - (i + 1)
            logger.error(
                f"Quota exhausted. {i + 1} processed, {remaining} remaining. "
                f"Re-run with --skip-existing after quota resets."
            )
            break
        except Exception as e:
            logger.error(f"  Gemini call failed: {e}")
            error_count += 1
            time.sleep(delay_between)
            continue

        if result:
            ec = result.get("event_context", {})
            ri = result.get("relationship_inference", {})
            event_type = ec.get("event_type", "?")
            formality = ec.get("formality_level", "?")
            couples = len(ri.get("couple_pairs", []))
            logger.info(f"  -> event={event_type}, formality={formality}, couples={couples}")

            # Upsert to Supabase date_labels (source of truth — Lesson 162)
            # Read-merge-write: preserve existing date_estimation and human corrections
            try:
                _sb = get_supabase_client()
                existing_resp = _sb.table("date_labels").select("data").eq("photo_id", pid).execute()
                existing_data = (existing_resp.data[0]["data"] if existing_resp.data else {}) or {}
                if isinstance(existing_data, str):
                    existing_data = json.loads(existing_data)

                # Merge: keep existing fields, add/update event_context and relationship_inference
                merged_data = {**existing_data}
                merged_data["event_context"] = ec
                merged_data["relationship_inference"] = ri
                # Also store the full identification result for other fields
                for key in (
                    "date_estimation",
                    "face_analysis",
                    "location",
                    "historical_context",
                    "scene_category",
                    "objects",
                    "subject_ages",
                ):
                    if key in result and key not in merged_data:
                        merged_data[key] = result[key]
                merged_data["event_context_source"] = "gemini_batch_identification"
                merged_data["event_context_created_at"] = datetime.now(timezone.utc).isoformat()

                _sb.table("date_labels").upsert(
                    {"photo_id": pid, "data": merged_data},
                    on_conflict="photo_id",
                ).execute()
            except Exception as sync_err:
                logger.error(f"  Supabase date_labels upsert FAILED: {sync_err}")
                error_count += 1
                time.sleep(delay_between)
                continue  # Don't count as success if write failed (Codex P1)

            success_count += 1
            total_cost += cost_per_photo

            # Lesson 161: Verify FULL output quality on first successful call
            if success_count == 1:
                _missing = []
                if not ec.get("event_type"):
                    _missing.append("event_type")
                if not ec.get("formality_level"):
                    _missing.append("formality_level")
                if not ri:
                    _missing.append("relationship_inference")
                if not face_coordinates:
                    _missing.append("face_coordinates (not sent)")
                if _missing:
                    logger.warning(f"  *** FIRST RESULT QUALITY CHECK: Missing: {', '.join(_missing)} ***")
                else:
                    logger.info("  FIRST RESULT QUALITY CHECK: All event context fields present")
        else:
            logger.warning("  No result returned")
            error_count += 1

        time.sleep(delay_between)

    logger.info("=== BATCH COMPLETE ===")
    logger.info(f"Success: {success_count}, Errors: {error_count}")
    logger.info(f"Estimated cost: ${total_cost:.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch Gemini event context extraction for community photos")
    parser.add_argument(
        "--community-id",
        default=FADER_COMMUNITY_ID,
        help=f"Community UUID (default: Fader {FADER_COMMUNITY_ID})",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show plan without calling API")
    parser.add_argument(
        "--skip-existing", action="store_true", default=True, help="Skip photos with existing event_context"
    )
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    parser.add_argument("--limit", type=int, default=None, help="Max photos to process")
    parser.add_argument("--max-cost", type=float, default=10.0, help="Maximum cost in USD")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between API calls")
    args = parser.parse_args()

    run_batch(
        community_id=args.community_id,
        dry_run=args.dry_run,
        skip_existing=args.skip_existing,
        max_cost=args.max_cost,
        delay_between=args.delay,
        limit=args.limit,
    )
