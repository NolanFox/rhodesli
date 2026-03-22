#!/usr/bin/env python3
"""Fix orphaned faces — faces in photo_faces not claimed by any active identity.

Creates new INBOX identities for each orphaned face.

Usage:
    python scripts/fix_orphaned_faces.py --dry-run
    python scripts/fix_orphaned_faces.py --execute
"""

import argparse
import json
import os
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from supabase import create_client


def get_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        sys.exit(1)
    return create_client(url, key)


def paginated_select(table, columns="*", page_size=1000):
    all_rows = []
    offset = 0
    while True:
        resp = table.select(columns).range(offset, offset + page_size - 1).execute()
        if not resp.data:
            break
        all_rows.extend(resp.data)
        if len(resp.data) < page_size:
            break
        offset += page_size
    return all_rows


def ensure_list(val):
    if val is None:
        return []
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return []
    if isinstance(val, list):
        return val
    return []


def main():
    parser = argparse.ArgumentParser(description="Fix orphaned faces")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    sb = get_client()

    print("Fetching data...")
    identities = paginated_select(
        sb.table("identities"),
        "identity_id,state,anchor_ids,candidate_ids,merged_into",
    )
    photo_faces = paginated_select(sb.table("photo_faces"), "face_id,photo_id")

    existing_face_ids = {row["face_id"] for row in photo_faces}
    face_to_photo = {row["face_id"]: row["photo_id"] for row in photo_faces}

    # Collect all faces claimed by active identities
    claimed = set()
    for ident in identities:
        if ident.get("merged_into"):
            continue
        for key in ["anchor_ids", "candidate_ids"]:
            for fid in ensure_list(ident.get(key)):
                claimed.add(fid)

    orphaned = existing_face_ids - claimed
    print(f"\nOrphaned faces: {len(orphaned)}")

    if not orphaned:
        print("No orphaned faces — nothing to do.")
        return

    # Group by photo
    by_photo = defaultdict(list)
    for fid in orphaned:
        by_photo[face_to_photo.get(fid, "UNKNOWN")].append(fid)

    print(f"Across {len(by_photo)} photos")
    for pid, fids in sorted(by_photo.items(), key=lambda x: -len(x[1]))[:10]:
        print(f"  {pid[:25]}: {len(fids)} orphaned")

    if args.dry_run:
        print(f"\n[DRY RUN] Would create {len(orphaned)} new INBOX identities")
        print("No changes made.")
        return

    # EXECUTE: Create one INBOX identity per orphaned face
    print(f"\n[EXECUTE] Creating {len(orphaned)} new INBOX identities...")
    now = datetime.now(timezone.utc).isoformat()
    success = 0
    errors = 0

    # Get current max unidentified number
    max_num = 0
    for ident in identities:
        name = ident.get("name", "") or ""
        if name.startswith("Unidentified Person "):
            try:
                num = int(name.split()[-1])
                max_num = max(max_num, num)
            except (ValueError, IndexError):
                pass

    next_num = max_num + 1

    for fid in sorted(orphaned):
        new_id = str(uuid.uuid4())
        try:
            sb.table("identities").insert(
                {
                    "identity_id": new_id,
                    "name": f"Unidentified Person {next_num}",
                    "state": "INBOX",
                    "anchor_ids": [fid],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "created_at": now,
                    "updated_at": now,
                }
            ).execute()
            success += 1
            next_num += 1
        except Exception as e:
            print(f"  ERROR creating identity for {fid}: {e}")
            errors += 1

        if success % 50 == 0 and success > 0:
            print(f"  Progress: {success} created")

    print(f"\nDone: {success} created, {errors} errors")

    # Verify
    print("\nVerifying...")
    identities2 = paginated_select(
        sb.table("identities"),
        "identity_id,state,anchor_ids,candidate_ids,merged_into",
    )
    claimed2 = set()
    for ident in identities2:
        if ident.get("merged_into"):
            continue
        for key in ["anchor_ids", "candidate_ids"]:
            for fid in ensure_list(ident.get(key)):
                claimed2.add(fid)
    remaining = existing_face_ids - claimed2
    print(f"Remaining orphaned faces: {len(remaining)}")


if __name__ == "__main__":
    main()
