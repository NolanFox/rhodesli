"""Session 156 Track F4 — Manual location correction for 2 Detroit Belle Isle Conservatory photos.

Per user authorization 2026-05-08: fix incorrect Gemini location predictions
on 2 photos. User noted: "fix the gemini data pull so that it actually works
not just manually overwrite — we need to keep trying until we are able to
replicate it with gemini." Manual fix is for now; Gemini prompt iteration
is a separate BACKLOG item (PRD-LOCATION-001).

Photos in scope:
- inbox_fox-charlie-001_204_02068_p_13akf5twbc3600 (currently "New York City")
- inbox_fox-charlie-001_3_01659_p_13akf5twbc1045  (currently "United States")

Both should be Detroit, MI (Belle Isle Conservatory) per:
- LoC LC-DIG-det-4a17798 (Detroit Publishing Co. interior, 1905) + 6 corroborating sources
- Albert Fox GEDCOM RESI Detroit 1917 + Albert draft induction 7 Jun 1918
- Session 154 Track C1 evidence

Updates the photo_locations table. Writes audit_log row per photo.
Defaults to dry-run; pass --execute to mutate.
"""

import argparse
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.supabase_data import get_supabase_client  # noqa: E402

DETROIT = {
    "location_name": "Detroit, Michigan",
    "location_estimate": "Belle Isle Conservatory, Detroit, Michigan (c.1917-1918)",
    "lat": 42.3314,
    "lng": -83.0458,
    "confidence": "high",
    "region": "United States",
    "source_type": "human_corrected",
    "biographical_evidence": (
        "Library of Congress LC-DIG-det-4a17798 (Detroit Publishing Co. interior, 1905) "
        "matches the Conservatory architecture in both photos. Albert Fox GEDCOM RESI "
        "Detroit 1917 + Albert draft induction 7 Jun 1918 places the family in Detroit "
        "during the photo date range. Session 154 Track C1 + Session 153b independent "
        "audit corroborate."
    ),
}

PHOTOS_TO_FIX = [
    "inbox_fox-charlie-001_204_02068_p_13akf5twbc3600",
    "inbox_fox-charlie-001_3_01659_p_13akf5twbc1045",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    sb = get_supabase_client()
    if sb is None:
        print("ABORT: Supabase unavailable", file=sys.stderr)
        sys.exit(1)

    now_iso = datetime.now(timezone.utc).isoformat()

    for pid in PHOTOS_TO_FIX:
        # Read current row
        r = sb.table("photo_locations").select("*").eq("photo_id", pid).execute()
        if not r.data:
            print(f"  ! {pid}: no photo_locations row — will INSERT")
            old = None
        else:
            old = r.data[0]
            print(f"  {pid}: current location = '{old.get('location_name')}' (lat {old.get('lat')}, lng {old.get('lng')}, conf {old.get('confidence')})")

        new_row = {
            "photo_id": pid,
            "location_name": DETROIT["location_name"],
            "location_estimate": DETROIT["location_estimate"],
            "lat": DETROIT["lat"],
            "lng": DETROIT["lng"],
            "confidence": DETROIT["confidence"],
            "region": DETROIT["region"],
            "biographical_evidence": DETROIT["biographical_evidence"],
        }
        # Preserve other columns if they exist
        if old:
            for k in ("missing_child_analysis", "visual_evidence", "gemini_response", "created_at"):
                if k in old and old[k] is not None and k not in new_row:
                    new_row[k] = old[k]

        if not args.execute:
            print(f"    [DRY-RUN] would upsert: {new_row['location_name']} lat={new_row['lat']}")
            continue

        # Upsert
        sb.table("photo_locations").upsert(new_row, on_conflict="photo_id").execute()
        print(f"    ✓ updated to Detroit, MI (lat {new_row['lat']})")

        # Audit log
        audit_row = {
            "action": "location_correction",
            "entity_type": "photo",
            "entity_id": pid,
            "user_id": None,
            "user_email": "session-156",
            "old_value": json.dumps({
                "location_name": old.get("location_name") if old else None,
                "lat": old.get("lat") if old else None,
                "lng": old.get("lng") if old else None,
                "confidence": old.get("confidence") if old else None,
            }),
            "new_value": json.dumps({
                "location_name": new_row["location_name"],
                "lat": new_row["lat"],
                "lng": new_row["lng"],
                "confidence": new_row["confidence"],
            }),
            "metadata": {
                "session_id": "156",
                "track": "F4",
                "evidence_source": "Session 154 Track C1 + LoC LC-DIG-det-4a17798 + Albert Fox GEDCOM RESI Detroit 1917",
                "manual_correction_reason": "Gemini prediction was incorrect (NYC for 02068, generic US for 01659). User-authorized manual override pending Gemini prompt iteration (PRD-LOCATION-001).",
            },
        }
        sb.table("audit_log").insert(audit_row).execute()
        print(f"    ✓ audit_log written")

    print("\nDone." if args.execute else "\n[DRY-RUN] use --execute to apply")


if __name__ == "__main__":
    main()
