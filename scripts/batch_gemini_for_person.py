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

    # Cost estimate
    cost_per_photo = 0.037  # Gemini 3.1 Pro estimate
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

    # Import the production estimation function
    from app.estimate_routes import _call_gemini_date_estimate, _build_gedcom_context_for_photo

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

        # Build GEDCOM context for this photo
        try:
            gedcom_context = _build_gedcom_context_for_photo(pid)
        except Exception as e:
            logger.warning(f"  GEDCOM context failed: {e}")
            gedcom_context = None

        # Call Gemini
        try:
            result = _call_gemini_date_estimate(
                image_bytes=image_bytes,
                suffix=suffix,
                api_key=api_key,
                photo_id=pid,
                gedcom_context=gedcom_context,
                call_type="batch_date_estimation",
                trigger="batch_person_analysis",
                photo_metadata={
                    "filename": filename,
                    "source": photo.get("source", ""),
                    "collection": photo.get("collection", ""),
                },
            )
        except Exception as e:
            logger.error(f"  Gemini call failed: {e}")
            error_count += 1
            time.sleep(delay_between)
            continue

        if result:
            decade = result.get("estimated_decade", "?")
            year = result.get("best_year_estimate", "?")
            confidence = result.get("confidence", "?")
            logger.info(f"  -> {decade}s (best: {year}, conf: {confidence})")

            # Save to labels
            label_entry = {
                "photo_id": pid,
                "filename": filename,
                "estimated_decade": result.get("estimated_decade"),
                "best_year_estimate": result.get("best_year_estimate"),
                "confidence": result.get("confidence"),
                "probable_range": result.get("probable_range"),
                "decade_probabilities": result.get("decade_probabilities"),
                "location_estimate": result.get("location", {}),
                "scene_description": result.get("scene_description", ""),
                "clothing_notes": result.get("clothing_notes", ""),
                "subject_ages": result.get("subject_ages", []),
                "people_count": result.get("people_count"),
                "photo_type": result.get("photo_type", ""),
                "setting": result.get("setting", ""),
                "condition": result.get("condition", ""),
                "source_method": "gemini_batch_person",
                "prompt_version": "v3_enriched",
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
