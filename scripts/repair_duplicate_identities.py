#!/usr/bin/env python3
"""
Session 129 Data Repair: Merge duplicate CONFIRMED identities.

Found:
  - Esther Burd Fox: 65207728 (83 anchors) + d4f29ffb (29 anchors)
  - Robert Mattatia: b9f41a3b (1 anchor) + 142a164e (1 anchor)

Root cause: User confirmed identities on production that already existed
under the same name. The confirm flow doesn't check for duplicate names.

This script:
  1. Combines anchor_ids from the smaller into the larger identity
  2. Sets merged_into on the smaller identity
  3. Logs the repair to audit_log
  4. Dry-run by default (--execute to apply)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from supabase import create_client

MERGES = [
    {
        "name": "Esther Burd Fox",
        "keep": "65207728-9ee6-48c1-be68-a2da23354caf",
        "merge": "d4f29ffb-43f4-44ea-b575-16f4e84cebc7",
    },
    {
        "name": "Robert Mattatia",
        "keep": "b9f41a3b-445b-4df5-9bea-c4bacc5e75f8",
        "merge": "142a164e-a94e-441b-a7de-ed08b37ff282",
    },
]


def ensure_list(val):
    if val is None:
        return []
    if isinstance(val, str):
        return json.loads(val)
    return list(val)


def main():
    parser = argparse.ArgumentParser(description="Merge duplicate identities")
    parser.add_argument("--execute", action="store_true", help="Actually apply changes")
    args = parser.parse_args()

    sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY"))

    for merge_spec in MERGES:
        name = merge_spec["name"]
        keep_id = merge_spec["keep"]
        merge_id = merge_spec["merge"]

        print(f"\n{'=' * 60}")
        print(f"Merging duplicate: {name}")
        print(f"  Keep:  {keep_id}")
        print(f"  Merge: {merge_id}")

        # Fetch both identities
        keep_data = sb.table("identities").select("*").eq("identity_id", keep_id).execute()
        merge_data = sb.table("identities").select("*").eq("identity_id", merge_id).execute()

        if not keep_data.data:
            print(f"  ERROR: Keep identity {keep_id} not found!")
            continue
        if not merge_data.data:
            print(f"  ERROR: Merge identity {merge_id} not found!")
            continue

        keep = keep_data.data[0]
        merge = merge_data.data[0]

        keep_anchors = ensure_list(keep.get("anchor_ids"))
        merge_anchors = ensure_list(merge.get("anchor_ids"))
        keep_candidates = ensure_list(keep.get("candidate_ids"))
        merge_candidates = ensure_list(merge.get("candidate_ids"))
        keep_negatives = ensure_list(keep.get("negative_ids"))
        merge_negatives = ensure_list(merge.get("negative_ids"))

        print(
            f"  Keep:  {keep['name']} ({keep['state']}) — {len(keep_anchors)} anchors, {len(keep_candidates)} candidates"
        )
        print(
            f"  Merge: {merge['name']} ({merge['state']}) — {len(merge_anchors)} anchors, {len(merge_candidates)} candidates"
        )

        # Combine anchor_ids (deduplicated)
        combined_anchors = list(dict.fromkeys(keep_anchors + merge_anchors))
        combined_candidates = list(dict.fromkeys(keep_candidates + merge_candidates))
        # Remove any candidates that are now anchors
        combined_candidates = [c for c in combined_candidates if c not in set(combined_anchors)]
        combined_negatives = list(dict.fromkeys(keep_negatives + merge_negatives))

        new_faces = len(combined_anchors) - len(keep_anchors)
        print(f"  Combined anchors: {len(combined_anchors)} (+{new_faces} new)")
        print(f"  Combined candidates: {len(combined_candidates)}")

        if not args.execute:
            print("  [DRY RUN] Would update keep identity and set merged_into on merge identity")
            continue

        now = datetime.now(timezone.utc).isoformat()

        # Update keep identity with combined faces
        sb.table("identities").update(
            {
                "anchor_ids": combined_anchors,
                "candidate_ids": combined_candidates,
                "negative_ids": combined_negatives,
                "updated_at": now,
            }
        ).eq("identity_id", keep_id).execute()
        print(f"  Updated keep identity with {len(combined_anchors)} anchors")

        # Set merged_into on merge identity
        sb.table("identities").update(
            {
                "merged_into": keep_id,
                "updated_at": now,
            }
        ).eq("identity_id", merge_id).execute()
        print(f"  Set merged_into={keep_id[:12]}... on merge identity")

        # Log to audit_log
        sb.table("audit_log").insert(
            {
                "action": "merge_repair",
                "entity_type": "identity",
                "entity_id": keep_id,
                "user_email": "session-129-repair-script",
                "metadata": json.dumps(
                    {
                        "merged_identity_id": merge_id,
                        "merged_name": merge["name"],
                        "faces_added": new_faces,
                        "total_anchors": len(combined_anchors),
                        "reason": "Duplicate CONFIRMED identity — same name, different IDs",
                        "session": 129,
                    }
                ),
            }
        ).execute()
        print("  Audit log entry created")

    print(f"\n{'=' * 60}")
    if not args.execute:
        print("DRY RUN complete. Use --execute to apply changes.")
    else:
        print("REPAIR COMPLETE. Verify in production.")


if __name__ == "__main__":
    main()
