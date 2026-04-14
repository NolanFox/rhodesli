#!/usr/bin/env python3
"""Backfill Session 148c investigation data into identification_investigations table.

Reads docs/session_context/session-148c-investigation.json and inserts via
log_identification_investigation().

Usage:
    python scripts/backfill_investigation_148c.py
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from app.supabase_data import log_identification_investigation


def main():
    json_path = project_root / "docs" / "session_context" / "session-148c-investigation.json"
    if not json_path.exists():
        print(f"ERROR: {json_path} not found")
        sys.exit(1)

    with open(json_path) as f:
        raw = json.load(f)

    # Map JSON fields to table columns
    target = raw.get("target", {})

    # Build known_references as array
    known_refs = []
    for key, ref in raw.get("known_references", {}).items():
        known_refs.append(
            {
                "identity_id": ref.get("identity_id"),
                "name": key,
                "anchor_count": ref.get("anchor_count"),
                "role": ref.get("centroid_source", "reference"),
            }
        )

    # Build methodology_steps as array
    methodology = raw.get("methodology", {})
    method_steps = []
    for step_key in sorted(methodology.keys()):
        step_num = int(step_key.replace("step_", ""))
        method_steps.append(
            {
                "step_number": step_num,
                "description": methodology[step_key],
            }
        )

    # Build candidates from consolidated_nellie_candidate
    consolidated = raw.get("consolidated_nellie_candidate", {})
    candidates = []
    for entry in consolidated.get("face_ids_likely_same_person", []):
        candidates.append(
            {
                "face_id": entry.get("face_id"),
                "photo_id": entry.get("photo", "").split(" ")[0] if entry.get("photo") else None,
                "photo_filename": entry.get("photo"),
                "embedding_distance": entry.get("sherry_dist"),
                "decision": "ACCEPT",
                "evidence": entry.get("photo", ""),
            }
        )

    # Build clusters array
    clusters_raw = raw.get("clusters_of_interest", {})
    clusters = []
    for cluster_key, cluster_data in clusters_raw.items():
        clusters.append(
            {
                "cluster_name": cluster_key,
                "face_count": cluster_data.get("faces"),
                "photo_count": cluster_data.get("photos"),
                "avg_reference_distance": cluster_data.get("avg_sherry_dist"),
                "status": cluster_data.get("status", "UNKNOWN"),
                "assessment": cluster_data.get("assessment"),
            }
        )

    # Build also_identified
    also_raw = raw.get("also_identified", {})
    also_identified = []
    for key, entry in also_raw.items():
        also_identified.append(
            {
                "name": key,
                "face_id": entry.get("face_id"),
                "photo_id": entry.get("photo"),
                "status": entry.get("status"),
                "description": entry.get("description"),
            }
        )

    # Build signals_used from the consolidated candidate note
    signals_used = {
        "event_context": {"strength": "VERY_STRONG", "note": "corsage, aisle walk, cake topper, dancing with groom"},
        "cross_photo_tracking": {"strength": "STRONG", "note": "same person across 5+ photos in same outfit"},
        "age_genealogy_filter": {"strength": "STRONG", "note": "eliminated young women clusters"},
        "kinship_embedding": {"strength": "WEAK", "note": "high intra-person distances (0.87-1.29)"},
    }

    data = {
        "investigation_name": raw.get("investigation", "Unknown Investigation"),
        "session_id": raw.get("session", "148c"),
        "community_id": "fader",
        "target_name": target.get("name", "Unknown"),
        "target_birth_year": target.get("birth_year"),
        "target_death_year": target.get("death_year"),
        "target_relationship": target.get("relationship_to_known"),
        "target_spouse": target.get("spouse"),
        "target_geography": target.get("geography"),
        "known_references": known_refs,
        "methodology_steps": method_steps,
        "candidates": candidates,
        "clusters": clusters,
        "outcome": "CONFIRMED",
        "confidence_overall": consolidated.get("overall_confidence", "HIGH").replace(" ", "_"),
        "signals_used": signals_used,
        "also_identified": also_identified,
        "feature_ideas": raw.get("feature_ideas_from_methodology", []),
        "investigator": "claude",
    }

    success = log_identification_investigation(data)
    if success:
        print(f"SUCCESS: Inserted investigation '{data['investigation_name']}' for target '{data['target_name']}'")
    else:
        print("FAILED: Could not insert investigation. Check Supabase connection and table existence.")
        sys.exit(1)


if __name__ == "__main__":
    main()
