#!/usr/bin/env python3
"""Sync volume-only data to Supabase (source of truth).

Recovers data from gemini_api_calls.full_response and writes to date_labels
and photo_locations tables. Handles the gap where Gemini results were logged
to gemini_api_calls but never written to date_labels/photo_locations.

Also syncs data from local JSON files (date_labels.json, photo_locations.json)
that may not have been written to Supabase.

Usage:
    # Dry run (default) — shows what would be migrated
    python scripts/sync_volume_data_to_supabase.py --dry-run

    # Execute migration
    python scripts/sync_volume_data_to_supabase.py --execute

Session 143: Created to fix data gap where Rhodes photos analyzed through
web UI had results on Railway volume JSON but not in Supabase.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def get_supabase_client():
    """Get a Supabase client. Requires .env to be loaded."""
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        logger.error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        sys.exit(1)
    return create_client(url, key)


def load_all_rows(sb, table, select="*", page_size=1000):
    """Paginate through all rows of a Supabase table."""
    all_rows = []
    offset = 0
    while True:
        result = sb.table(table).select(select).range(offset, offset + page_size - 1).execute()
        rows = result.data or []
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return all_rows


def inventory_gemini_to_date_labels_gap(sb):
    """Find successful gemini_api_calls that have no corresponding date_labels entry.

    Returns list of dicts with photo_id, call_type, full_response, created_at.
    """
    # Get all successful calls with full_response
    logger.info("Loading gemini_api_calls (successful, with full_response)...")
    all_calls = []
    offset = 0
    page_size = 1000
    while True:
        result = (
            sb.table("gemini_api_calls")
            .select("photo_id, call_type, full_response, response_summary, model_used, created_at, gemini_config")
            .eq("status", "success")
            .not_.is_("full_response", "null")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = result.data or []
        all_calls.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size

    logger.info(f"  Found {len(all_calls)} successful calls with full_response")

    # Deduplicate by photo_id — keep the LATEST call per photo
    latest_by_photo = {}
    for call in all_calls:
        pid = call.get("photo_id")
        if not pid:
            continue
        existing = latest_by_photo.get(pid)
        if not existing or (call.get("created_at", "") > existing.get("created_at", "")):
            latest_by_photo[pid] = call

    logger.info(f"  Unique photos with Gemini results: {len(latest_by_photo)}")

    # Get all existing date_labels
    logger.info("Loading existing date_labels...")
    existing_labels = load_all_rows(sb, "date_labels", select="photo_id")
    existing_photo_ids = {row["photo_id"] for row in existing_labels}
    logger.info(f"  Existing date_labels: {len(existing_photo_ids)}")

    # Find the gap
    missing = []
    for pid, call in latest_by_photo.items():
        if pid not in existing_photo_ids:
            missing.append(call)

    logger.info(f"  Missing from date_labels: {len(missing)} photos")
    return missing


def extract_date_label_from_gemini_response(call):
    """Convert a gemini_api_calls row into a date_labels entry.

    Handles both old-format (date_estimation/re_analysis) and new-format
    (batch_full_extraction) responses.
    """
    full_response = call.get("full_response")
    if not full_response:
        return None

    # full_response is already a dict (JSONB)
    if isinstance(full_response, str):
        try:
            full_response = json.loads(full_response)
        except (json.JSONDecodeError, TypeError):
            return None

    photo_id = call.get("photo_id")
    if not photo_id:
        return None

    # Extract date estimation — handle both nested and flat formats
    date_est = full_response.get("date_estimation", full_response)

    estimated_decade = date_est.get("estimated_decade")
    if not isinstance(estimated_decade, int):
        # No valid date estimation in this response
        return None

    prob_range = date_est.get("probable_range", [])
    location = full_response.get("location", {})

    # Build the label entry (same structure as batch script)
    label_data = {
        "photo_id": photo_id,
        "source": "gemini",
        "source_method": call.get("call_type", "recovered_from_api_log"),
        # Date estimation
        "estimated_decade": estimated_decade,
        "best_year_estimate": date_est.get("best_year_estimate"),
        "confidence": date_est.get("confidence"),
        "probable_range": prob_range,
        "decade_probabilities": date_est.get("decade_probabilities"),
        # Location
        "location_estimate": location if isinstance(location, dict) else date_est.get("location_estimate", ""),
        # Rich metadata (if available from full preset)
        "scene_description": full_response.get("scene_description", ""),
        "subject_ages": full_response.get("subject_ages", []),
        "people_count": full_response.get("people_count"),
        "photo_type": full_response.get("photo_type", ""),
        "setting": full_response.get("setting", ""),
        "keywords": full_response.get("keywords", []),
        "controlled_tags": full_response.get("controlled_tags", []),
        "face_analysis": full_response.get("face_analysis", {}),
        "group_composition": full_response.get("group_composition", {}),
        "cultural_markers": full_response.get("cultural_markers", {}),
        "photo_technique": full_response.get("photo_technique", {}),
        "text_signage": full_response.get("text_signage", {}),
        # Provenance
        "model": call.get("model_used", ""),
        "prompt_version": "recovered_from_api_log",
        "recovered_at": call.get("created_at", ""),
        "recovery_source": "gemini_api_calls",
    }

    # Build the Supabase row (matches sync_date_labels_batch format)
    row = {
        "photo_id": photo_id,
        "data": label_data,
        "estimated_decade": estimated_decade,
        "best_year_estimate": date_est.get("best_year_estimate"),
        "confidence": date_est.get("confidence"),
        "year_range_start": prob_range[0] if len(prob_range) >= 2 else None,
        "year_range_end": prob_range[1] if len(prob_range) >= 2 else None,
        "scene_description": full_response.get("scene_description", ""),
        "model": call.get("model_used", ""),
        "prompt_version": "recovered_from_api_log",
    }

    return row


def inventory_local_json_gaps(sb):
    """Find entries in local JSON files not present in Supabase tables.

    Returns dict with 'date_labels' and 'photo_locations' lists.
    """
    gaps = {"date_labels": [], "photo_locations": []}

    # Check date_labels.json
    labels_path = Path("rhodesli_ml/data/date_labels.json")
    if labels_path.exists():
        with open(labels_path) as f:
            local_labels = json.load(f)
        local_entries = local_labels.get("labels", [])
        logger.info(f"Local date_labels.json: {len(local_entries)} entries")

        existing = load_all_rows(sb, "date_labels", select="photo_id")
        existing_ids = {r["photo_id"] for r in existing}

        for entry in local_entries:
            pid = entry.get("photo_id")
            if pid and pid not in existing_ids:
                gaps["date_labels"].append(entry)

        logger.info(f"  Missing from Supabase date_labels: {len(gaps['date_labels'])}")
    else:
        logger.info("No local date_labels.json found")

    # Check photo_locations.json
    locations_path = Path("data/photo_locations.json")
    if locations_path.exists():
        with open(locations_path) as f:
            local_locations = json.load(f)
        # photo_locations.json has a "photos" envelope
        photos_dict = local_locations.get("photos", local_locations)
        logger.info(f"Local photo_locations.json: {len(photos_dict)} entries")

        existing = load_all_rows(sb, "photo_locations", select="photo_id")
        existing_ids = {r["photo_id"] for r in existing}

        for pid, loc_data in photos_dict.items():
            if pid not in existing_ids:
                gaps["photo_locations"].append({"photo_id": pid, "data": loc_data})

        logger.info(f"  Missing from Supabase photo_locations: {len(gaps['photo_locations'])}")
    else:
        logger.info("No local photo_locations.json found")

    return gaps


def check_face_alignments(sb):
    """Check face_alignments table for completeness."""
    logger.info("\n=== Face Alignments Check ===")

    # Count face alignments
    alignments = load_all_rows(sb, "face_alignments", select="photo_id")
    logger.info(f"  Face alignments in Supabase: {len(alignments)}")

    # Count photos that have Gemini alignment calls
    alignment_calls = []
    offset = 0
    page_size = 1000
    while True:
        result = (
            sb.table("gemini_api_calls")
            .select("photo_id")
            .eq("status", "success")
            .eq("call_type", "alignment")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = result.data or []
        alignment_calls.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size

    alignment_call_ids = {r["photo_id"] for r in alignment_calls}
    alignment_ids = {r["photo_id"] for r in alignments}
    missing = alignment_call_ids - alignment_ids

    logger.info(f"  Photos with alignment API calls: {len(alignment_call_ids)}")
    logger.info(f"  Missing from face_alignments table: {len(missing)}")

    return missing


def check_photo_locations_table(sb):
    """Check if photo_locations table exists and its state."""
    logger.info("\n=== Photo Locations Check ===")
    try:
        rows = load_all_rows(sb, "photo_locations", select="photo_id")
        logger.info(f"  Photo locations in Supabase: {len(rows)}")
        return True, len(rows)
    except Exception as e:
        if "relation" in str(e).lower() and "does not exist" in str(e).lower():
            logger.warning("  photo_locations table does NOT exist in Supabase")
            return False, 0
        logger.warning(f"  Error checking photo_locations: {e}")
        return False, 0


def execute_migration(sb, gemini_gaps, json_gaps, dry_run=True):
    """Execute the migration of missing data to Supabase.

    Returns dict with counts of migrated rows per table.
    """
    results = {"date_labels_from_gemini": 0, "date_labels_from_json": 0, "photo_locations": 0}

    # 1. Migrate from gemini_api_calls → date_labels
    if gemini_gaps:
        logger.info(
            f"\n{'[DRY RUN] Would migrate' if dry_run else 'Migrating'} {len(gemini_gaps)} date labels from gemini_api_calls..."
        )
        rows_to_upsert = []
        for call in gemini_gaps:
            row = extract_date_label_from_gemini_response(call)
            if row:
                rows_to_upsert.append(row)
            else:
                pid = call.get("photo_id", "?")
                logger.warning(f"  Could not extract date label from call for {pid}")

        logger.info(f"  Extractable: {len(rows_to_upsert)} / {len(gemini_gaps)}")

        if not dry_run and rows_to_upsert:
            batch_size = 50
            for i in range(0, len(rows_to_upsert), batch_size):
                batch = rows_to_upsert[i : i + batch_size]
                try:
                    sb.table("date_labels").upsert(batch, on_conflict="photo_id").execute()
                    results["date_labels_from_gemini"] += len(batch)
                except Exception as e:
                    logger.error(f"  Batch upsert failed: {e}")
            logger.info(f"  Migrated: {results['date_labels_from_gemini']} date labels from gemini_api_calls")
        elif dry_run:
            results["date_labels_from_gemini"] = len(rows_to_upsert)
            # Show sample
            for row in rows_to_upsert[:5]:
                pid = row["photo_id"]
                decade = row.get("estimated_decade", "?")
                conf = row.get("confidence", "?")
                logger.info(f"    {pid}: {decade}s (confidence: {conf})")
            if len(rows_to_upsert) > 5:
                logger.info(f"    ... and {len(rows_to_upsert) - 5} more")

    # 2. Migrate from local JSON → date_labels
    json_date_gaps = json_gaps.get("date_labels", [])
    if json_date_gaps:
        logger.info(
            f"\n{'[DRY RUN] Would migrate' if dry_run else 'Migrating'} {len(json_date_gaps)} date labels from local JSON..."
        )
        rows_to_upsert = []
        for entry in json_date_gaps:
            pid = entry.get("photo_id")
            if not pid:
                continue
            prob_range = entry.get("probable_range", [])
            row = {
                "photo_id": pid,
                "data": entry,
                "estimated_decade": entry.get("estimated_decade"),
                "best_year_estimate": entry.get("best_year_estimate"),
                "confidence": entry.get("confidence"),
                "year_range_start": prob_range[0] if len(prob_range) >= 2 else None,
                "year_range_end": prob_range[1] if len(prob_range) >= 2 else None,
                "scene_description": entry.get("scene_description"),
                "model": entry.get("model"),
                "prompt_version": entry.get("prompt_version"),
                "reanalyzed_at": entry.get("reanalyzed_at"),
                "location_evidence": entry.get("location_estimate"),
                "gemini_raw_location": entry.get("gemini_raw_location"),
            }
            rows_to_upsert.append(row)

        if not dry_run and rows_to_upsert:
            batch_size = 50
            for i in range(0, len(rows_to_upsert), batch_size):
                batch = rows_to_upsert[i : i + batch_size]
                try:
                    sb.table("date_labels").upsert(batch, on_conflict="photo_id").execute()
                    results["date_labels_from_json"] += len(batch)
                except Exception as e:
                    logger.error(f"  Batch upsert failed: {e}")
            logger.info(f"  Migrated: {results['date_labels_from_json']} date labels from JSON")
        elif dry_run:
            results["date_labels_from_json"] = len(rows_to_upsert)

    # 3. Migrate photo_locations from local JSON
    json_loc_gaps = json_gaps.get("photo_locations", [])
    if json_loc_gaps:
        logger.info(
            f"\n{'[DRY RUN] Would migrate' if dry_run else 'Migrating'} {len(json_loc_gaps)} photo locations from local JSON..."
        )
        rows_to_upsert = []
        for entry in json_loc_gaps:
            pid = entry.get("photo_id")
            loc = entry.get("data", {})
            if not pid:
                continue
            row = {
                "photo_id": pid,
                "data": loc,
                "location_name": loc.get("location_name", ""),
                "location_estimate": loc.get("location_estimate", ""),
                "confidence": loc.get("confidence"),
                "lat": loc.get("lat"),
                "lng": loc.get("lng"),
                "region": loc.get("region", ""),
                "biographical_evidence": loc.get("biographical_evidence"),
                "gemini_raw_location": loc.get("gemini_raw_location"),
            }
            rows_to_upsert.append(row)

        if not dry_run and rows_to_upsert:
            batch_size = 50
            for i in range(0, len(rows_to_upsert), batch_size):
                batch = rows_to_upsert[i : i + batch_size]
                try:
                    sb.table("photo_locations").upsert(batch, on_conflict="photo_id").execute()
                    results["photo_locations"] += len(batch)
                except Exception as e:
                    logger.error(f"  Batch upsert failed: {e}")
            logger.info(f"  Migrated: {results['photo_locations']} photo locations")
        elif dry_run:
            results["photo_locations"] = len(rows_to_upsert)

    return results


def main():
    parser = argparse.ArgumentParser(description="Sync volume-only data to Supabase")
    parser.add_argument("--execute", action="store_true", help="Execute migration (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Show what would be migrated (default)")
    args = parser.parse_args()

    dry_run = not args.execute

    from dotenv import load_dotenv

    load_dotenv()

    sb = get_supabase_client()

    logger.info("=" * 60)
    logger.info(f"Rhodesli Volume → Supabase Data Sync {'[DRY RUN]' if dry_run else '[EXECUTE]'}")
    logger.info("=" * 60)

    # 1. Inventory gaps: gemini_api_calls → date_labels
    logger.info("\n=== Gap Analysis: gemini_api_calls → date_labels ===")
    gemini_gaps = inventory_gemini_to_date_labels_gap(sb)

    # 2. Inventory gaps: local JSON → Supabase tables
    logger.info("\n=== Gap Analysis: Local JSON → Supabase ===")
    json_gaps = inventory_local_json_gaps(sb)

    # 3. Check photo_locations table
    loc_exists, loc_count = check_photo_locations_table(sb)

    # 4. Check face_alignments
    alignment_gaps = check_face_alignments(sb)

    # 5. Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    total_gaps = len(gemini_gaps) + len(json_gaps.get("date_labels", [])) + len(json_gaps.get("photo_locations", []))
    logger.info(f"  Date labels missing (from gemini_api_calls): {len(gemini_gaps)}")
    logger.info(f"  Date labels missing (from local JSON):       {len(json_gaps.get('date_labels', []))}")
    logger.info(f"  Photo locations missing (from local JSON):   {len(json_gaps.get('photo_locations', []))}")
    logger.info(f"  Face alignment gaps:                         {len(alignment_gaps)}")
    logger.info(f"  Total data gaps to fill:                     {total_gaps}")

    if total_gaps == 0 and len(alignment_gaps) == 0:
        logger.info("\nNo gaps found. Supabase is in sync.")
        return

    # 6. Execute or report
    if total_gaps > 0:
        results = execute_migration(sb, gemini_gaps, json_gaps, dry_run=dry_run)

        logger.info("\n" + "=" * 60)
        if dry_run:
            logger.info("DRY RUN RESULTS — Would migrate:")
        else:
            logger.info("EXECUTION RESULTS — Migrated:")
        logger.info(f"  Date labels from gemini_api_calls: {results['date_labels_from_gemini']}")
        logger.info(f"  Date labels from local JSON:       {results['date_labels_from_json']}")
        logger.info(f"  Photo locations from local JSON:   {results['photo_locations']}")

        if dry_run:
            logger.info("\nRe-run with --execute to apply changes.")

    if alignment_gaps:
        logger.info(f"\nFace alignment gaps ({len(alignment_gaps)} photos) — recovery not implemented.")
        logger.info("Face alignments are stored directly by the alignment pipeline; no recovery path from API logs.")


if __name__ == "__main__":
    main()
