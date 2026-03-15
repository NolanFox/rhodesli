#!/usr/bin/env python3
"""DATA-019: Re-assign community-batch-20260214 photos from Fox Family to Rhodes.

These 114 photos have collection="Jews of Rhodes: Family Memories & Heritage"
but were batch-ingested under the Fox Family community. They need to be
reassigned to the Rhodes community.

Usage:
    python scripts/fix_data_019_community_reassignment.py              # dry-run
    python scripts/fix_data_019_community_reassignment.py --execute    # apply changes
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser(description="DATA-019: Reassign community-batch Rhodes photos")
    parser.add_argument("--execute", action="store_true", help="Apply changes (default: dry-run)")
    args = parser.parse_args()

    # Load photo_index to find affected photos
    photo_index_path = Path("data/photo_index.json")
    if not photo_index_path.exists():
        print("ERROR: data/photo_index.json not found")
        sys.exit(1)

    with open(photo_index_path) as f:
        photo_data = json.load(f)

    # Find community-batch-20260214 photos with Rhodes collection
    affected_photo_ids = []
    for pid, p in photo_data["photos"].items():
        if p.get("job_id") == "community-batch-20260214" and "Jews of Rhodes" in p.get("collection", ""):
            affected_photo_ids.append(pid)

    print(f"Found {len(affected_photo_ids)} affected photos (community-batch-20260214 with Rhodes collection)")
    if not affected_photo_ids:
        print("Nothing to fix.")
        return

    # Connect to Supabase
    from dotenv import load_dotenv

    load_dotenv()

    from app.supabase_data import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        print("ERROR: Cannot connect to Supabase")
        sys.exit(1)

    # Get community IDs
    rhodes = sb.table("communities").select("id").eq("slug", "rhodes").execute()
    fox = sb.table("communities").select("id").eq("slug", "fox-family").execute()

    if not rhodes.data:
        print("ERROR: Rhodes community not found")
        sys.exit(1)
    if not fox.data:
        print("ERROR: Fox Family community not found")
        sys.exit(1)

    rhodes_id = rhodes.data[0]["id"]
    fox_id = fox.data[0]["id"]
    print(f"Rhodes community ID: {rhodes_id}")
    print(f"Fox Family community ID: {fox_id}")

    # Check current state in photo_communities
    misassigned = []
    for pid in affected_photo_ids:
        result = sb.table("photo_communities").select("*").eq("photo_id", pid).execute()
        if result.data:
            for row in result.data:
                if row["community_id"] == fox_id:
                    misassigned.append(pid)

    print(f"\n{len(misassigned)} photos currently assigned to Fox Family that should be Rhodes")

    if not misassigned:
        print("All photos already correctly assigned. Nothing to do.")
        return

    # Show sample
    for pid in misassigned[:5]:
        p = photo_data["photos"].get(pid, {})
        print(f"  {pid[:30]}... → {p.get('path', '???')[:60]}")
    if len(misassigned) > 5:
        print(f"  ... and {len(misassigned) - 5} more")

    if not args.execute:
        print(f"\nDRY RUN — would reassign {len(misassigned)} photos from Fox Family to Rhodes")
        print("Run with --execute to apply changes")
        return

    # Backup current state
    backup_dir = Path("data/backups")
    backup_dir.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"pre_data019_fix_{ts}.json"

    backup_data = {"affected_photo_ids": misassigned, "fox_community_id": fox_id, "rhodes_community_id": rhodes_id}
    with open(backup_path, "w") as f:
        json.dump(backup_data, f, indent=2)
    print(f"\nBackup saved to {backup_path}")

    # Execute reassignment
    reassigned = 0
    for pid in misassigned:
        try:
            # Update community_id from Fox to Rhodes
            sb.table("photo_communities").update({"community_id": rhodes_id}).eq("photo_id", pid).eq(
                "community_id", fox_id
            ).execute()
            reassigned += 1
        except Exception as e:
            print(f"  ERROR reassigning {pid}: {e}")

    print(f"\nReassigned {reassigned}/{len(misassigned)} photos from Fox Family to Rhodes")

    # Also check identity_communities for identities that ONLY appear in these photos
    # Find face IDs from these photos
    affected_face_ids = set()
    for pid in misassigned:
        p = photo_data["photos"].get(pid, {})
        affected_face_ids.update(p.get("face_ids", []))

    print(f"\n{len(affected_face_ids)} face IDs in affected photos")

    # Find identities that contain these face IDs
    from core.registry import IdentityRegistry

    registry = IdentityRegistry.load(Path("data/identities.json"))
    affected_identity_ids = set()
    for iid, ident in registry._identities.items():
        all_faces = set(ident.get("anchor_ids", []) + ident.get("candidate_ids", []))
        if all_faces & affected_face_ids:
            affected_identity_ids.add(iid)

    print(f"{len(affected_identity_ids)} identities reference faces in affected photos")

    # For each affected identity, check if ALL their faces are in affected photos
    identity_reassign = []
    for iid in affected_identity_ids:
        ident = registry._identities[iid]
        all_faces = set(ident.get("anchor_ids", []) + ident.get("candidate_ids", []))
        if all_faces <= affected_face_ids:
            identity_reassign.append(iid)

    print(f"{len(identity_reassign)} identities have ALL faces in affected photos (candidates for reassignment)")

    id_reassigned = 0
    for iid in identity_reassign:
        try:
            sb.table("identity_communities").update({"community_id": rhodes_id}).eq("identity_id", iid).eq(
                "community_id", fox_id
            ).execute()
            id_reassigned += 1
        except Exception as e:
            print(f"  ERROR reassigning identity {iid}: {e}")

    print(f"Reassigned {id_reassigned}/{len(identity_reassign)} identities from Fox Family to Rhodes")
    print("\nDATA-019 fix complete. Verify: Fox Family speed-run should no longer show Rhodes photos.")


if __name__ == "__main__":
    main()
