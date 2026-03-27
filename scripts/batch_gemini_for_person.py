#!/usr/bin/env python3
"""Batch Gemini date estimation for all photos containing specific identities.

Uses the production _call_gemini_date_estimate() function with:
- GEDCOM genealogical context for identified faces
- Full Supabase logging to gemini_api_calls table
- Prompt manifest tracking
- Retry logic with exponential backoff
- Incremental results saved to date_labels.json

Usage:
    # Dry run: count photos, show cost estimate
    python scripts/batch_gemini_for_person.py --dry-run \\
        --identity 65207728-9ee6-48c1-be68-a2da23354caf \\
        --identity 85546ebf-75b9-4971-a9d4-b2ce2271bc19

    # Run estimation for Esther + Albert
    python scripts/batch_gemini_for_person.py \\
        --identity 65207728-9ee6-48c1-be68-a2da23354caf \\
        --identity 85546ebf-75b9-4971-a9d4-b2ce2271bc19 \\
        --max-cost 15.00

    # Skip photos that already have estimates
    python scripts/batch_gemini_for_person.py --skip-existing ...

Session 142: Created for batch Gemini analysis of Esther Burd Fox and Albert Fox photos.
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class QuotaExhaustedError(Exception):
    """Raised when Gemini API returns 429 RESOURCE_EXHAUSTED."""

    pass


def get_photos_for_identities(identity_ids: list[str]) -> dict[str, dict]:
    """Get all unique photos containing any of the given identities.

    Reads from Supabase (source of truth) for identity face lists,
    and from local photo_index.json for photo metadata + face-to-photo mapping.

    Returns dict of {photo_id: photo_entry} with identity attribution.
    """
    from dotenv import load_dotenv

    load_dotenv()

    # Read identities from Supabase (has the latest face assignments)
    try:
        from supabase import create_client

        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if url and key:
            sb = create_client(url, key)
            logger.info("Reading identities from Supabase (source of truth)")
            identities = {}
            for iid in identity_ids:
                r = (
                    sb.table("identities")
                    .select("identity_id, name, anchor_ids, candidate_ids")
                    .eq("identity_id", iid)
                    .execute()
                )
                if r.data:
                    row = r.data[0]
                    # Handle JSONB string encoding (Lesson 142)
                    for key_name in ("anchor_ids", "candidate_ids"):
                        val = row.get(key_name, [])
                        if isinstance(val, str):
                            val = json.loads(val)
                        row[key_name] = val or []
                    identities[iid] = row
        else:
            raise ValueError("Supabase not configured")
    except Exception as e:
        logger.warning(f"Supabase unavailable ({e}), falling back to local JSON")
        with open("data/identities.json") as f:
            identities_data = json.load(f)
        identities = identities_data.get("identities", identities_data)
        identities = {iid: identities.get(iid) for iid in identity_ids if iid in identities}

    # Photo index is local (has face-to-photo mapping)
    with open("data/photo_index.json") as f:
        photo_index = json.load(f)
    photos = photo_index.get("photos", photo_index)
    face_to_photo = photo_index.get("face_to_photo", {})

    # Also load photo_faces from Supabase for faces not in local index
    # Paginate to get ALL rows (Supabase default limit is 1000)
    supabase_face_to_photo = {}
    try:
        from supabase import create_client

        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if url and key:
            sb = create_client(url, key)
            offset = 0
            page_size = 1000
            while True:
                r = sb.table("photo_faces").select("face_id, photo_id").range(offset, offset + page_size - 1).execute()
                rows = r.data or []
                for row in rows:
                    supabase_face_to_photo[row["face_id"]] = row["photo_id"]
                if len(rows) < page_size:
                    break
                offset += page_size
            logger.info(f"Loaded {len(supabase_face_to_photo)} face-to-photo mappings from Supabase")
    except Exception as e:
        logger.warning(f"Could not load photo_faces from Supabase: {e}")

    # Merge face-to-photo mappings (Supabase takes precedence for completeness)
    merged_ftp = {**face_to_photo, **supabase_face_to_photo}

    result = {}
    for iid in identity_ids:
        identity = identities.get(iid)
        if not identity:
            logger.warning(f"Identity {iid} not found")
            continue

        name = identity.get("name", f"Unknown ({iid[:8]})")
        face_ids = []
        for fid in identity.get("anchor_ids", []) + identity.get("candidate_ids", []):
            if isinstance(fid, str):
                face_ids.append(fid)
            elif isinstance(fid, dict):
                face_ids.append(fid.get("face_id", ""))

        photo_ids = set()
        for fid in face_ids:
            pid = merged_ftp.get(fid)
            if pid:
                photo_ids.add(pid)

        logger.info(f"{name}: {len(face_ids)} faces -> {len(photo_ids)} photos")
        for pid in photo_ids:
            if pid not in result:
                photo_entry = photos.get(pid, {})
                result[pid] = {
                    **photo_entry,
                    "photo_id": pid,
                    "identities": [name],
                }
            else:
                result[pid]["identities"].append(name)

    return result


def load_existing_estimates() -> set[str]:
    """Load photo IDs that already have Gemini date estimates."""
    existing = set()

    # Check date_labels.json
    labels_path = Path("rhodesli_ml/data/date_labels.json")
    if labels_path.exists():
        with open(labels_path) as f:
            data = json.load(f)
        for entry in data.get("labels", []):
            existing.add(entry.get("photo_id", ""))

    return existing


def resolve_photo_path(photo_entry: dict) -> Path | None:
    """Resolve the local file path for a photo."""
    filename = photo_entry.get("filename") or photo_entry.get("path", "")
    if not filename:
        return None

    # Try raw_photos directory
    path = Path("raw_photos") / Path(filename).name
    if path.exists():
        return path

    # Try with full path
    path = Path(filename)
    if path.exists():
        return path

    return None


def run_batch(
    identity_ids: list[str],
    dry_run: bool = False,
    skip_existing: bool = True,
    max_cost: float = 15.0,
    delay_between: float = 2.0,
):
    """Run Gemini date estimation on all photos for given identities."""
    from dotenv import load_dotenv

    load_dotenv()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key and not dry_run:
        logger.error("GEMINI_API_KEY not set. Add it to .env or set as environment variable.")
        sys.exit(1)

    # Get all photos
    photos = get_photos_for_identities(identity_ids)
    logger.info(f"Total unique photos: {len(photos)}")

    # Filter already-estimated
    if skip_existing:
        existing = load_existing_estimates()
        before = len(photos)
        photos = {pid: p for pid, p in photos.items() if pid not in existing}
        skipped = before - len(photos)
        if skipped:
            logger.info(f"Skipping {skipped} photos with existing estimates")

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
        logger.warning(f"{missing_files} photos have no local file (R2-only)")

    photos = photos_with_files
    logger.info(f"Photos to process: {len(photos)}")

    # Cost estimate — "full" preset has ~2x more output than "quick"
    cost_per_photo = 0.055  # Gemini 3.1 Pro with full preset (larger response)
    estimated_cost = len(photos) * cost_per_photo
    logger.info(f"Estimated cost: ${estimated_cost:.2f} (at ${cost_per_photo}/photo)")

    if estimated_cost > max_cost:
        logger.warning(f"Estimated cost ${estimated_cost:.2f} exceeds max ${max_cost:.2f}")
        # Process up to max_cost worth
        max_photos = int(max_cost / cost_per_photo)
        photo_list = list(photos.items())[:max_photos]
        logger.info(f"Processing first {max_photos} photos to stay under budget")
    else:
        photo_list = list(photos.items())

    if dry_run:
        logger.info("=== DRY RUN ===")
        logger.info(f"Would process {len(photo_list)} photos")
        logger.info(f"Estimated cost: ${len(photo_list) * cost_per_photo:.2f}")
        logger.info(f"Estimated time: {len(photo_list) * (delay_between + 3):.0f}s")
        for pid, photo in photo_list[:10]:
            filename = photo.get("filename", photo.get("path", "unknown"))
            identities_str = ", ".join(photo.get("identities", []))
            logger.info(f"  {pid[:12]}... {filename} [{identities_str}]")
        if len(photo_list) > 10:
            logger.info(f"  ... and {len(photo_list) - 10} more")
        return

    # Import production functions
    from rhodesli_ml.gemini_extraction import build_extraction_prompt
    from rhodesli_ml.gemini_config import GEMINI_MODEL, get_model_pricing
    from rhodesli_ml.prompt_manifest import build_prompt_lineage_fields, build_prompt_manifest
    from app.supabase_data import log_gemini_call
    from scripts.run_combined_pipeline import load_gedcom_data, build_gedcom_context
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

    # Pre-load photo_index for face-to-photo + face bbox lookup
    with open("data/photo_index.json") as f:
        _pi = json.load(f)
    local_face_to_photo = _pi.get("face_to_photo", {})

    # P0 GEDCOM preload optimization (Session 142 Codex speed audit):
    # Load GEDCOM tree ONCE instead of per-photo (~60-90s per call eliminated).
    logger.info("Pre-loading GEDCOM data from Supabase (one-time)...")
    _preloaded_gedcom_data = None
    try:
        _preloaded_gedcom_data = load_gedcom_data()
        if _preloaded_gedcom_data:
            n_links = len(_preloaded_gedcom_data.get("face_links", {}))
            logger.info(f"GEDCOM data pre-loaded: {n_links} face links")
        else:
            logger.warning("GEDCOM data unavailable — context will be None for all photos")
    except Exception as e:
        logger.warning(f"Failed to pre-load GEDCOM data: {e}")

    # Pre-load identity registry for face->identity lookups in GEDCOM context
    _identities_for_gedcom = {}
    try:
        from supabase import create_client as _sc

        _sb_url = os.environ.get("SUPABASE_URL")
        _sb_key = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if _sb_url and _sb_key:
            _sb = _sc(_sb_url, _sb_key)
            _offset = 0
            _page_size = 1000
            while True:
                _resp = (
                    _sb.table("identities")
                    .select("identity_id, name, anchor_ids, candidate_ids")
                    .range(_offset, _offset + _page_size - 1)
                    .execute()
                )
                _rows = _resp.data or []
                for _row in _rows:
                    for _k in ("anchor_ids", "candidate_ids"):
                        _v = _row.get(_k, [])
                        if isinstance(_v, str):
                            _v = json.loads(_v)
                        _row[_k] = _v or []
                    _identities_for_gedcom[_row["identity_id"]] = _row
                if len(_rows) < _page_size:
                    break
                _offset += _page_size
            logger.info(f"Pre-loaded {len(_identities_for_gedcom)} identities for GEDCOM context")
    except Exception as e:
        logger.warning(f"Failed to pre-load identities for GEDCOM: {e}")

    # Build face_id -> identity_id reverse map for GEDCOM lookups
    _face_to_identity = {}
    for _iid, _ident in _identities_for_gedcom.items():
        for _fid in _ident.get("anchor_ids", []) + _ident.get("candidate_ids", []):
            if isinstance(_fid, str):
                _face_to_identity[_fid] = _iid
            elif isinstance(_fid, dict):
                _face_to_identity[_fid.get("face_id", "")] = _iid

    # Cache GEDCOM context per photo — uses pre-loaded data (no Supabase per call)
    _gedcom_cache = {}

    def _get_cached_gedcom_context(photo_id):
        if photo_id not in _gedcom_cache:
            try:
                if not _preloaded_gedcom_data:
                    _gedcom_cache[photo_id] = None
                    return None

                # Get face_ids for this photo
                _photos = _pi.get("photos", _pi)
                photo_entry = _photos.get(photo_id, {})
                photo_face_ids = photo_entry.get("face_ids", [])

                if not photo_face_ids:
                    _gedcom_cache[photo_id] = None
                    return None

                # Build face stubs with identity names (same interface as run_combined_pipeline)
                class _FaceStub:
                    def __init__(self, face_id, identity_name):
                        self.face_id = face_id
                        self.identity_name = identity_name

                faces = []
                for fid in photo_face_ids:
                    iid = _face_to_identity.get(fid)
                    name = _identities_for_gedcom[iid].get("name") if iid and iid in _identities_for_gedcom else None
                    faces.append(_FaceStub(fid, name))

                ctx = build_gedcom_context(photo_id, faces, _identities_for_gedcom, _preloaded_gedcom_data)
                _gedcom_cache[photo_id] = ctx or None
            except Exception as e:
                logger.warning(f"  GEDCOM context failed for {photo_id}: {e}")
                _gedcom_cache[photo_id] = None
        return _gedcom_cache[photo_id]

    def _get_face_coordinates(photo_id):
        """Get face bounding boxes for a photo from embeddings data.

        Codex P0: Sort left-to-right by bbox[0] (x-coordinate) to match
        the prompt's face_index ordering convention.
        """
        coords = []
        _photos = _pi.get("photos", _pi)
        photo_entry = _photos.get(photo_id, {})
        face_ids = photo_entry.get("face_ids", [])
        for fid in face_ids:
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
        # Sort left-to-right by x-coordinate for consistent face_index ordering
        coords.sort(key=lambda c: c["bbox"][0])
        return coords if coords else None

    def _call_gemini_full(image_bytes, suffix, photo_id, gedcom_context, photo_metadata, face_coordinates):
        """Call Gemini with FULL preset — face analysis, subject ages, group composition, etc."""
        import time as _time

        prompt_text = build_extraction_prompt(
            preset="full",
            face_coordinates=face_coordinates,
            gedcom_context=gedcom_context,
            photo_metadata=photo_metadata,
        )
        enrichment_level = (
            "gedcom+faces"
            if gedcom_context and face_coordinates
            else ("gedcom" if gedcom_context else ("faces" if face_coordinates else "none"))
        )
        prompt_variant = f"full_{enrichment_level}"
        prompt_manifest = build_prompt_manifest(
            prompt_family="date_estimation",
            prompt_version="v3",
            prompt_variant=prompt_variant,
            prompt_contract_version="2",
            channel="batch",
            context_flags={
                "uses_gedcom": bool(gedcom_context),
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

                    # Validate
                    date_est = parsed.get("date_estimation", parsed)
                    decade = date_est.get("estimated_decade")
                    if not isinstance(decade, int) or decade < 1800 or decade > 2030:
                        status = "error"
                        error_msg = f"Invalid decade: {decade}"
                        return None

                    if "location" in parsed and "location" not in date_est:
                        date_est["location"] = parsed["location"]

                    return parsed  # Return FULL response (not just date_est)

                except Exception as e:
                    latency_ms = int((_time.time() - start_time) * 1000)
                    error_msg = str(e)
                    # Detect quota exhaustion — stop entire batch immediately
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
            # Log to Supabase (AD-152)
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
                        date_est = parsed.get("date_estimation", parsed)
                        loc = parsed.get("location", {})
                        response_summary = {
                            "estimated_decade": date_est.get("estimated_decade"),
                            "best_year_estimate": date_est.get("best_year_estimate"),
                            "confidence": date_est.get("confidence"),
                            "location_place": loc.get("place") if isinstance(loc, dict) else None,
                            "face_count": len(face_coordinates) if face_coordinates else 0,
                            "subject_ages": parsed.get("subject_ages"),
                            "group_composition": parsed.get("group_composition"),
                        }
                    log_gemini_call(
                        photo_id=photo_id,
                        model_used=GEMINI_MODEL,
                        call_type="batch_full_extraction",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        cost_usd=round(cost_usd, 6),
                        latency_ms=latency_ms,
                        status=status,
                        error_message=error_msg,
                        gemini_config={
                            "enrichment_level": enrichment_level,
                            "prompt_version": "v3_enriched",
                            "prompt_variant": prompt_variant,
                            "prompt_manifest_id": prompt_manifest["prompt_manifest_id"],
                            "prompt_family": prompt_manifest["prompt_family"],
                            "prompt_contract_version": prompt_manifest["prompt_contract_version"],
                            "temperature": 0.1,
                            "trigger": "batch_person_analysis",
                            "preset": "full",
                            "face_count": len(face_coordinates) if face_coordinates else 0,
                            "request_surface": "scripts.batch_gemini_for_person",
                            "request_mode": "batch",
                        },
                        response_summary=response_summary,
                        prompt_text=prompt_text,
                        full_response=parsed if parsed else None,
                        gedcom_context=gedcom_context,
                    )
                except Exception as log_err:
                    logger.warning(f"  Failed to log Gemini call: {log_err}")

    # Load existing labels for incremental save
    labels_path = Path("rhodesli_ml/data/date_labels.json")
    if labels_path.exists():
        with open(labels_path) as f:
            labels_data = json.load(f)
    else:
        labels_data = {"schema_version": 2, "labels": []}

    existing_labels = {e["photo_id"]: i for i, e in enumerate(labels_data["labels"])}

    success_count = 0
    error_count = 0
    total_cost = 0.0

    for i, (pid, photo) in enumerate(photo_list):
        filename = photo.get("filename", photo.get("path", "unknown"))
        identities_str = ", ".join(photo.get("identities", []))
        logger.info(f"[{i + 1}/{len(photo_list)}] {filename} [{identities_str}]")

        # Load image
        local_path = Path(photo["_local_path"])
        try:
            image_bytes = local_path.read_bytes()
        except Exception as e:
            logger.error(f"  Failed to read {local_path}: {e}")
            error_count += 1
            continue

        suffix = local_path.suffix

        # Build GEDCOM context (cached per photo)
        gedcom_context = _get_cached_gedcom_context(pid)

        # Get face coordinates for this photo
        face_coordinates = _get_face_coordinates(pid)
        if face_coordinates:
            logger.info(f"  {len(face_coordinates)} faces with bounding boxes")

        # Call Gemini with FULL preset
        try:
            result = _call_gemini_full(
                image_bytes=image_bytes,
                suffix=suffix,
                photo_id=pid,
                gedcom_context=gedcom_context,
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
                f"Gemini daily quota exhausted. {i + 1} photos processed, "
                f"{remaining} remaining. Retry after quota resets."
            )
            break
        except Exception as e:
            logger.error(f"  Gemini call failed: {e}")
            error_count += 1
            time.sleep(delay_between)
            continue

        if result:
            date_est = result.get("date_estimation", result)
            decade = date_est.get("estimated_decade", "?")
            year = date_est.get("best_year_estimate", "?")
            confidence = date_est.get("confidence", "?")
            logger.info(f"  -> {decade}s (best: {year}, conf: {confidence})")

            # Save to labels — capture FULL response from "full" preset
            label_entry = {
                "photo_id": pid,
                "filename": filename,
                # Date estimation
                "estimated_decade": date_est.get("estimated_decade"),
                "best_year_estimate": date_est.get("best_year_estimate"),
                "confidence": date_est.get("confidence"),
                "probable_range": date_est.get("probable_range"),
                "decade_probabilities": date_est.get("decade_probabilities"),
                # Location
                "location_estimate": result.get("location", {}),
                # Rich metadata (full preset)
                "scene_description": result.get("scene_description", ""),
                "clothing_notes": result.get("clothing_notes", result.get("clothing_era", "")),
                "subject_ages": result.get("subject_ages", []),
                "people_count": result.get("people_count"),
                "photo_type": result.get("photo_type", ""),
                "setting": result.get("setting", ""),
                "condition": result.get("condition", result.get("photo_condition", "")),
                "keywords": result.get("keywords", []),
                "controlled_tags": result.get("controlled_tags", []),
                # Face analysis (full preset with coords)
                "face_analysis": result.get("face_analysis", {}),
                "group_composition": result.get("group_composition", {}),
                "cultural_markers": result.get("cultural_markers", {}),
                "photo_technique": result.get("photo_technique", {}),
                "text_signage": result.get("text_signage", {}),
                # Provenance
                "source_method": "gemini_batch_full",
                "prompt_version": "v3_enriched_full",
                "preset": "full",
                "face_coordinates_sent": bool(face_coordinates),
                "gedcom_context_sent": bool(gedcom_context),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "batch_context": {
                    "identities": photo.get("identities", []),
                    "trigger": "session_142_esther_albert",
                },
            }

            if pid in existing_labels:
                labels_data["labels"][existing_labels[pid]] = label_entry
            else:
                labels_data["labels"].append(label_entry)
                existing_labels[pid] = len(labels_data["labels"]) - 1

            success_count += 1
            total_cost += cost_per_photo

            # Incremental save every 10 photos
            if success_count % 10 == 0:
                with open(labels_path, "w") as f:
                    json.dump(labels_data, f, indent=2)
                logger.info(f"  [saved {success_count} labels so far]")
        else:
            logger.warning("  No result returned")
            error_count += 1

        # Rate limit delay
        time.sleep(delay_between)

    # Final save
    with open(labels_path, "w") as f:
        json.dump(labels_data, f, indent=2)

    logger.info("=== BATCH COMPLETE ===")
    logger.info(f"Success: {success_count}, Errors: {error_count}")
    logger.info(f"Estimated cost: ${total_cost:.2f}")
    logger.info(f"Results saved to {labels_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch Gemini estimation for person photos")
    parser.add_argument("--identity", action="append", required=True, help="Identity UUID (can specify multiple)")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without calling API")
    parser.add_argument("--skip-existing", action="store_true", default=True, help="Skip already-estimated photos")
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    parser.add_argument("--max-cost", type=float, default=15.0, help="Maximum cost in USD")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between API calls")
    args = parser.parse_args()

    run_batch(
        identity_ids=args.identity,
        dry_run=args.dry_run,
        skip_existing=args.skip_existing,
        max_cost=args.max_cost,
        delay_between=args.delay,
    )
