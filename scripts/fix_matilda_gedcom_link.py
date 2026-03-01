#!/usr/bin/env python3
"""Fix Matilda's GEDCOM face link in Supabase.

Identity a2889099 (Mathilda Capouano Capelouto) was linked to the wrong
GEDCOM xref @I132423679471@ in the gedcom_face_links table.
Correct xref is @I132127360994@ (Matilda Cap Capelouto, daughter of Abraham).

The data/gedcom_matches.json file already has the correct value.
This script fixes the Supabase gedcom_face_links table to match.

Usage:
    python scripts/fix_matilda_gedcom_link.py --dry-run
    python scripts/fix_matilda_gedcom_link.py --execute
"""

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

IDENTITY_ID = "a2889099-2d75-42ee-93b4-81232b9f4e16"
WRONG_XREF = "@I132423679471@"
CORRECT_XREF = "@I132127360994@"


def main():
    parser = argparse.ArgumentParser(description="Fix Matilda GEDCOM face link")
    parser.add_argument("--execute", action="store_true", help="Apply fix (default: dry-run)")
    args = parser.parse_args()

    # Verify gedcom_matches.json has the correct value
    matches_path = PROJECT_ROOT / "data" / "gedcom_matches.json"
    with open(matches_path) as f:
        matches_data = json.load(f)

    matilda_match = None
    for m in matches_data.get("matches", []):
        if m.get("identity_id", "").startswith("a2889099"):
            matilda_match = m
            break

    if not matilda_match:
        print("ERROR: Matilda (a2889099) not found in gedcom_matches.json")
        return 1

    json_xref = matilda_match.get("gedcom_xref")
    print(f"gedcom_matches.json xref: {json_xref}")
    print(f"Expected correct xref:    {CORRECT_XREF}")

    if json_xref != CORRECT_XREF:
        print(f"ERROR: gedcom_matches.json has unexpected xref {json_xref}")
        return 1

    print(f"\nWill fix gedcom_face_links for identity {IDENTITY_ID}")
    print(f"  Wrong xref:   {WRONG_XREF}")
    print(f"  Correct xref: {CORRECT_XREF}")

    if not args.execute:
        print("\nDRY RUN — use --execute to apply fix")
        return 0

    # Connect to Supabase and fix the link
    from app.supabase_data import get_supabase_client
    sb = get_supabase_client()
    if not sb:
        print("ERROR: Cannot connect to Supabase")
        return 1

    # Check current state
    resp = sb.table("gedcom_face_links").select("*").eq(
        "identity_id", IDENTITY_ID
    ).execute()

    if resp.data:
        current = resp.data[0]
        print(f"\nCurrent link: gedcom_id={current.get('gedcom_id')}")

        if current.get("gedcom_id") == CORRECT_XREF:
            print("Already correct — no fix needed")
            return 0

        # Delete old link(s) for this identity
        sb.table("gedcom_face_links").delete().eq(
            "identity_id", IDENTITY_ID
        ).execute()
        print("Deleted old link")

    # Insert correct link
    sb.table("gedcom_face_links").upsert({
        "identity_id": IDENTITY_ID,
        "gedcom_id": CORRECT_XREF,
        "confidence": 1.0,
        "linked_by": "fix-session81-matilda",
    }, on_conflict="identity_id,gedcom_id").execute()
    print(f"Inserted correct link: {IDENTITY_ID} -> {CORRECT_XREF}")

    # Verify
    resp = sb.table("gedcom_face_links").select("*").eq(
        "identity_id", IDENTITY_ID
    ).execute()
    if resp.data and resp.data[0].get("gedcom_id") == CORRECT_XREF:
        print("\nVerified: fix applied successfully")
    else:
        print("\nWARNING: Verification failed — check Supabase manually")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
