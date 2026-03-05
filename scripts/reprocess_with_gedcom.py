#!/usr/bin/env python3
"""Reprocess photos with GEDCOM-enriched Gemini analysis.

Usage:
    # Dry run: list eligible photos
    python scripts/reprocess_with_gedcom.py --dry-run

    # Process single photo (the Asheville litmus test)
    python scripts/reprocess_with_gedcom.py --photo-id 746dd11e5b4d86a1

    # Batch: process all eligible photos
    python scripts/reprocess_with_gedcom.py --batch --limit 5

    # Batch with cost cap
    python scripts/reprocess_with_gedcom.py --batch --max-cost 1.00

Session 89 — AD-201, AD-202
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def find_eligible_photos() -> list[dict]:
    """Find photos that have identified faces with GEDCOM links.

    Returns list of dicts with photo_id, filename, face_count, linked_count, names.
    """
    from core.registry import IdentityRegistry

    # Load photo index
    photo_index_path = Path("data/photo_index.json")
    if not photo_index_path.exists():
        logger.error("data/photo_index.json not found")
        return []
    photo_index = json.loads(photo_index_path.read_text())
    photos = photo_index.get("photos", {})
    face_to_photo = photo_index.get("face_to_photo", {})

    # Load identities
    registry = IdentityRegistry.load(Path("data/identities.json"))
    identities = registry._identities

    # Load GEDCOM face links from Supabase
    try:
        from app.supabase_data import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            logger.warning("Supabase not available — cannot load GEDCOM links")
            return []
        resp = sb.table("gedcom_face_links").select("identity_id,gedcom_id").execute()
        gedcom_links = {}
        if resp and resp.data:
            for row in resp.data:
                gedcom_links[row["identity_id"]] = row["gedcom_id"]
    except Exception as e:
        logger.warning(f"Failed to load GEDCOM links: {e}")
        return []

    if not gedcom_links:
        logger.info("No GEDCOM links found")
        return []

    logger.info(f"Found {len(gedcom_links)} GEDCOM identity links")

    # Find photos with faces that have linked identities
    eligible = []
    for photo_id, photo_data in photos.items():
        face_ids = photo_data.get("face_ids", [])
        linked_faces = []
        for face_id in face_ids:
            # Find identity for this face
            for iid, idata in identities.items():
                if face_id in idata.get("anchor_ids", []) or face_id in idata.get("candidate_ids", []):
                    if iid in gedcom_links:
                        name = idata.get("name", "Unknown")
                        linked_faces.append({"face_id": face_id, "identity_id": iid, "name": name})
                    break

        if linked_faces:
            eligible.append(
                {
                    "photo_id": photo_id,
                    "filename": photo_data.get("path", photo_data.get("filename", "")),
                    "face_count": len(face_ids),
                    "linked_count": len(linked_faces),
                    "names": [f["name"] for f in linked_faces],
                }
            )

    eligible.sort(key=lambda x: x["linked_count"], reverse=True)
    return eligible


def process_photo(photo_id: str, dry_run: bool = False) -> dict:
    """Process a single photo with GEDCOM-enriched Gemini analysis.

    Returns result dict with status, changes, cost.
    """
    from app.estimate_routes import (
        _call_gemini_date_estimate,
        _load_photo_image_bytes,
        _build_gedcom_context_for_photo,
        _geocode_location,
        _guess_region,
    )
    from rhodesli_ml.gemini_config import GEMINI_MODEL, get_model_pricing
    from datetime import datetime, timezone

    # Build GEDCOM context
    gedcom_context = _build_gedcom_context_for_photo(photo_id)
    has_gedcom = bool(gedcom_context)

    if dry_run:
        pricing = get_model_pricing(GEMINI_MODEL)
        return {
            "photo_id": photo_id,
            "status": "dry_run",
            "has_gedcom": has_gedcom,
            "estimated_cost": pricing.get("per_photo", 0.037),
            "gedcom_tokens": len(gedcom_context) // 4 if gedcom_context else 0,
        }

    # Load image
    image_bytes, suffix = _load_photo_image_bytes(photo_id)
    if not image_bytes:
        return {"photo_id": photo_id, "status": "error", "error": "Could not load image"}

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return {"photo_id": photo_id, "status": "error", "error": "GEMINI_API_KEY not set"}

    # Load old data for comparison
    date_labels_path = Path("data/date_labels.json")
    old_labels = json.loads(date_labels_path.read_text()) if date_labels_path.exists() else {}
    old_label = old_labels.get(photo_id, {})

    locations_path = Path("data/photo_locations.json")
    old_locations = json.loads(locations_path.read_text()) if locations_path.exists() else {}
    old_location = old_locations.get(photo_id, {})
    old_location_name = old_location.get("location_name", "Unknown")

    # Call Gemini
    result = _call_gemini_date_estimate(
        image_bytes,
        suffix,
        api_key,
        photo_id=photo_id,
        gedcom_context=gedcom_context,
        call_type="re_analysis",
        trigger="batch_rerun",
    )

    if not result:
        return {"photo_id": photo_id, "status": "error", "error": "Gemini returned no result"}

    new_decade = result.get("estimated_decade")
    new_year = result.get("best_year_estimate")
    new_confidence = result.get("confidence", "unknown")
    location_data = result.get("location", {})
    new_location = location_data.get("place", "") if isinstance(location_data, dict) else ""

    # Update date_labels.json
    if date_labels_path.exists():
        all_labels = json.loads(date_labels_path.read_text())
        all_labels[photo_id] = {
            **old_label,
            "estimated_decade": new_decade,
            "best_year_estimate": new_year,
            "confidence": new_confidence,
            "probable_range": result.get("probable_range", []),
            "reasoning_summary": result.get("reasoning_summary", ""),
            "evidence": result.get("evidence", {}),
            "location_estimate": new_location,
            "reanalyzed_at": datetime.now(timezone.utc).isoformat(),
            "reanalyzed_with_gedcom": has_gedcom,
        }
        date_labels_path.write_text(json.dumps(all_labels, indent=2, ensure_ascii=False))

    # Update photo_locations.json
    if new_location and locations_path.exists():
        all_locations = json.loads(locations_path.read_text())
        new_lat, new_lng = _geocode_location(new_location)
        all_locations[photo_id] = {
            "photo_id": photo_id,
            "lat": new_lat,
            "lng": new_lng,
            "location_name": new_location,
            "location_estimate": location_data.get("visual_evidence", ""),
            "confidence": location_data.get("confidence", "medium"),
            "region": _guess_region(new_location),
            "reanalyzed_at": datetime.now(timezone.utc).isoformat(),
        }
        locations_path.write_text(json.dumps(all_locations, indent=2, ensure_ascii=False))

    # Build diff
    changes = []
    old_decade = old_label.get("estimated_decade")
    if old_decade and new_decade and old_decade != new_decade:
        changes.append(f"Date: {old_decade}s → {new_decade}s")
    if old_location_name and new_location and old_location_name != new_location:
        changes.append(f"Location: {old_location_name} → {new_location}")

    pricing = get_model_pricing(GEMINI_MODEL)
    return {
        "photo_id": photo_id,
        "status": "success",
        "has_gedcom": has_gedcom,
        "new_decade": new_decade,
        "new_year": new_year,
        "new_location": new_location,
        "confidence": new_confidence,
        "changes": changes,
        "estimated_cost": pricing.get("per_photo", 0.037),
    }


def main():
    parser = argparse.ArgumentParser(description="Reprocess photos with GEDCOM-enriched Gemini analysis")
    parser.add_argument("--photo-id", help="Process a single photo by ID")
    parser.add_argument("--dry-run", action="store_true", help="List eligible photos without calling Gemini")
    parser.add_argument("--batch", action="store_true", help="Process all eligible photos")
    parser.add_argument("--limit", type=int, default=0, help="Max photos to process (0 = all)")
    parser.add_argument("--max-cost", type=float, default=5.0, help="Max USD to spend (default $5)")
    args = parser.parse_args()

    if not args.photo_id and not args.dry_run and not args.batch:
        parser.print_help()
        return

    if args.dry_run or args.batch:
        eligible = find_eligible_photos()
        print(f"\n{'=' * 60}")
        print(f"GEDCOM-eligible photos: {len(eligible)}")
        print(f"{'=' * 60}")

        from rhodesli_ml.gemini_config import get_model_pricing, GEMINI_MODEL

        pricing = get_model_pricing(GEMINI_MODEL)
        cost_per = pricing.get("per_photo", 0.037)
        total_cost = len(eligible) * cost_per

        for i, p in enumerate(eligible):
            names = ", ".join(p["names"][:3])
            if len(p["names"]) > 3:
                names += f" (+{len(p['names']) - 3} more)"
            print(f"  {i + 1:3d}. {p['photo_id']} — {p['linked_count']} linked faces — {names}")

        print(f"\nEstimated cost: ${total_cost:.2f} ({len(eligible)} photos × ${cost_per:.3f}/photo)")
        print(f"Model: {GEMINI_MODEL}")

        if args.dry_run:
            return

    if args.batch:
        photos_to_process = eligible
        if args.limit:
            photos_to_process = photos_to_process[: args.limit]

        cost_so_far = 0.0
        results = []
        for i, p in enumerate(photos_to_process):
            if cost_so_far >= args.max_cost:
                print(f"\nCost cap reached (${args.max_cost:.2f}). Stopping.")
                break

            print(f"\n[{i + 1}/{len(photos_to_process)}] Processing {p['photo_id']}...")
            result = process_photo(p["photo_id"])
            results.append(result)
            cost_so_far += result.get("estimated_cost", 0)

            if result["status"] == "success":
                changes = result.get("changes", [])
                if changes:
                    for change in changes:
                        print(f"  Changed: {change}")
                else:
                    print("  No changes")
            else:
                print(f"  Error: {result.get('error', 'unknown')}")

            # Rate limit: 1 second between calls
            if i < len(photos_to_process) - 1:
                time.sleep(1)

        print(f"\n{'=' * 60}")
        print(f"Processed: {len(results)}")
        print(f"Success: {sum(1 for r in results if r['status'] == 'success')}")
        print(f"Errors: {sum(1 for r in results if r['status'] == 'error')}")
        print(f"Total cost: ~${cost_so_far:.2f}")

    elif args.photo_id:
        result = process_photo(args.photo_id, dry_run=args.dry_run)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
