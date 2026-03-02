#!/usr/bin/env python3
"""Stage GEDCOM-enriched Gemini re-analysis results as Gatekeeper proposals.

Reads enrichment batch results and compares with existing date_labels.json
and photo_locations.json to create proposals for admin review.

Usage:
    python scripts/stage_enrichment_proposals.py results/enrichment_82c_batch1.json
    python scripts/stage_enrichment_proposals.py results/enrichment_82c_batch1.json --dry-run
"""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path) -> dict:
    """Load JSON file or return empty dict."""
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def save_json_atomic(data: dict, path: Path):
    """Save JSON file atomically (temp file + rename)."""
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".json")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, str(path))
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def build_proposals(enrichment_path: str, data_dir: Path) -> dict:
    """Build enrichment proposals by comparing new results with existing data.

    Args:
        enrichment_path: Path to enrichment batch results JSON
        data_dir: Path to data/ directory containing date_labels.json and photo_locations.json

    Returns:
        Proposals dict ready to save
    """
    # Load enrichment results
    with open(enrichment_path) as f:
        enrichment = json.load(f)

    # Load existing data
    date_labels_data = load_json(data_dir / "date_labels.json")
    labels_by_id = {}
    for label in date_labels_data.get("labels", []):
        pid = label.get("photo_id", "")
        if pid:
            labels_by_id[pid] = label

    photo_locations_data = load_json(data_dir / "photo_locations.json")
    locations_by_id = photo_locations_data.get("photos", {})

    now = datetime.now(timezone.utc).isoformat()
    proposals = {}

    for result in enrichment.get("results", []):
        photo_id = result.get("photo_id", "")
        if not photo_id:
            continue
        if result.get("status") != "success":
            continue

        r = result.get("result", {})
        if not r:
            continue

        date_est = r.get("date_estimation", {})
        location = r.get("location", {})

        # Get old data
        old_label = labels_by_id.get(photo_id, {})
        old_location = locations_by_id.get(photo_id, {})

        # Build old values
        old_location_info = {
            "place": old_location.get("location_name", old_label.get("location_estimate", "")),
            "confidence": old_location.get("confidence", ""),
        }
        old_date_info = {
            "year": old_label.get("best_year_estimate"),
            "decade": old_label.get("estimated_decade"),
            "confidence": old_label.get("confidence", ""),
        }

        # Build new values
        new_location_info = {
            "place": location.get("place", ""),
            "confidence": location.get("confidence", ""),
            "evidence": location.get("evidence", ""),
        }
        new_date_info = {
            "year": date_est.get("best_year_estimate"),
            "decade": date_est.get("estimated_decade"),
            "confidence": date_est.get("confidence", ""),
            "probable_range": date_est.get("probable_range", []),
            "decade_probabilities": date_est.get("decade_probabilities", {}),
            "reasoning_summary": date_est.get("reasoning_summary", ""),
        }

        # Check if anything actually changed
        location_changed = (
            old_location_info["place"].lower().strip() != new_location_info["place"].lower().strip()
            if old_location_info["place"] and new_location_info["place"]
            else bool(new_location_info["place"])
        )
        date_changed = (
            old_date_info["year"] != new_date_info["year"]
            if old_date_info["year"] is not None and new_date_info["year"] is not None
            else bool(new_date_info["year"])
        )
        confidence_improved = (
            _confidence_rank(new_date_info.get("confidence", "")) >
            _confidence_rank(old_date_info.get("confidence", ""))
        )

        # Only create proposal if something changed
        if not (location_changed or date_changed or confidence_improved):
            continue

        proposals[photo_id] = {
            "status": "pending",
            "created_at": now,
            "old_location": old_location_info,
            "new_location": new_location_info,
            "old_date": old_date_info,
            "new_date": new_date_info,
            "scene_description": r.get("scene_description", ""),
            "has_gedcom": result.get("has_gedcom", False),
            "gedcom_value_assessment": r.get("gedcom_value_assessment"),
            "cost": result.get("cost", 0),
            "location_changed": location_changed,
            "date_changed": date_changed,
            "confidence_improved": confidence_improved,
            "reviewed_at": None,
            "reviewed_by": None,
        }

    output = {
        "schema_version": 1,
        "source": enrichment.get("batch_id", "unknown"),
        "variant": enrichment.get("variant", "unknown"),
        "model": enrichment.get("model", "unknown"),
        "created_at": now,
        "total_cost": enrichment.get("total_cost", 0),
        "proposals": proposals,
    }

    return output


def _confidence_rank(confidence: str) -> int:
    """Rank confidence levels for comparison."""
    return {"high": 3, "medium": 2, "low": 1}.get(confidence, 0)


def main():
    parser = argparse.ArgumentParser(description="Stage enrichment proposals for admin review")
    parser.add_argument("enrichment_file", help="Path to enrichment batch results JSON")
    parser.add_argument("--data-dir", default="data", help="Path to data directory")
    parser.add_argument("--output", default=None, help="Output path (default: data/enrichment_proposals.json)")
    parser.add_argument("--dry-run", action="store_true", help="Print summary without saving")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_path = Path(args.output) if args.output else data_dir / "enrichment_proposals.json"

    if not Path(args.enrichment_file).exists():
        print(f"ERROR: Enrichment file not found: {args.enrichment_file}", file=sys.stderr)
        sys.exit(1)

    proposals = build_proposals(args.enrichment_file, data_dir)
    count = len(proposals["proposals"])

    # Summary
    location_changes = sum(1 for p in proposals["proposals"].values() if p.get("location_changed"))
    date_changes = sum(1 for p in proposals["proposals"].values() if p.get("date_changed"))
    gedcom_count = sum(1 for p in proposals["proposals"].values() if p.get("has_gedcom"))

    print(f"Enrichment Proposals Summary")
    print(f"  Source: {proposals['source']}")
    print(f"  Model: {proposals['model']}")
    print(f"  Total proposals: {count}")
    print(f"  Location changes: {location_changes}")
    print(f"  Date changes: {date_changes}")
    print(f"  GEDCOM-enriched: {gedcom_count}")
    print(f"  Total cost: ${proposals['total_cost']:.4f}")
    print()

    for photo_id, p in proposals["proposals"].items():
        changes = []
        if p.get("location_changed"):
            old_loc = p["old_location"]["place"] or "(none)"
            new_loc = p["new_location"]["place"]
            changes.append(f"Location: {old_loc} -> {new_loc}")
        if p.get("date_changed"):
            old_yr = p["old_date"].get("year") or "(none)"
            new_yr = p["new_date"].get("year")
            changes.append(f"Date: {old_yr} -> {new_yr}")
        if p.get("confidence_improved"):
            old_conf = p["old_date"].get("confidence") or "(none)"
            new_conf = p["new_date"].get("confidence")
            changes.append(f"Confidence: {old_conf} -> {new_conf}")
        gedcom_tag = " [GEDCOM]" if p.get("has_gedcom") else ""
        print(f"  {photo_id}{gedcom_tag}")
        for c in changes:
            print(f"    {c}")
        print()

    if args.dry_run:
        print("DRY RUN — no file written")
    else:
        save_json_atomic(proposals, output_path)
        print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
