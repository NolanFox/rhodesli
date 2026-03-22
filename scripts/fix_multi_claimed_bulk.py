#!/usr/bin/env python3
"""Fix multi-claimed faces at scale.

After un-merging 691 dangling identities, many faces are now claimed by both
the un-merged identity AND a CONFIRMED identity. Resolution rules:
1. CONFIRMED owner wins — remove face from non-CONFIRMED identity
2. If both non-CONFIRMED: keep on identity with more total faces
3. If tied: keep on the older identity (lower Person number)

After removing faces, identities with 0 remaining faces get merged into
the winner identity (preserving the merge chain for audit).

Usage:
    python scripts/fix_multi_claimed_bulk.py --dry-run
    python scripts/fix_multi_claimed_bulk.py --execute
"""

import argparse
import json
import os
import sys
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
    parser = argparse.ArgumentParser(description="Fix multi-claimed faces (bulk)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    sb = get_client()

    print("Fetching all identities...")
    identities = paginated_select(
        sb.table("identities"),
        "identity_id,name,state,anchor_ids,candidate_ids,merged_into",
    )
    print(f"  {len(identities)} identities fetched")

    # Build indexes for active (non-merged) identities
    id_map = {}
    face_to_identities = defaultdict(list)

    for ident in identities:
        if ident.get("merged_into"):
            continue
        iid = ident["identity_id"]
        id_map[iid] = ident

        for list_type in ["anchor_ids", "candidate_ids"]:
            for fid in ensure_list(ident.get(list_type)):
                face_to_identities[fid].append((iid, list_type.replace("_ids", "")))

    # Find multi-claimed faces
    multi_claimed = {fid: owners for fid, owners in face_to_identities.items() if len(owners) > 1}
    print(f"\nMulti-claimed faces: {len(multi_claimed)}")

    if not multi_claimed:
        print("No multi-claimed faces. Done.")
        return

    # Determine which identity loses each face
    # face_id -> list of (loser_id, list_type)
    removals = defaultdict(list)  # identity_id -> list of face_ids to remove

    for fid, owners in multi_claimed.items():
        # Sort owners: CONFIRMED first, then by face count descending
        def owner_sort_key(owner_tuple):
            iid, lt = owner_tuple
            ident = id_map[iid]
            state = ident.get("state", "INBOX")
            n_faces = len(ensure_list(ident.get("anchor_ids"))) + len(ensure_list(ident.get("candidate_ids")))
            # CONFIRMED=0 (wins), PROPOSED=1, INBOX=2, SKIPPED=3
            state_rank = {"CONFIRMED": 0, "PROPOSED": 1, "INBOX": 2, "SKIPPED": 3}.get(state, 4)
            return (state_rank, -n_faces)

        sorted_owners = sorted(owners, key=owner_sort_key)
        # Winner is first, rest are losers
        _winner = sorted_owners[0]
        losers = sorted_owners[1:]
        for loser_id, loser_lt in losers:
            removals[loser_id].append(fid)

    print(f"Identities to modify: {len(removals)}")
    total_removals = sum(len(fids) for fids in removals.values())
    print(f"Total face removals: {total_removals}")

    # Count how many identities will become empty after removals
    will_be_empty = 0
    for iid, faces_to_remove in removals.items():
        ident = id_map[iid]
        remaining_anchors = set(ensure_list(ident.get("anchor_ids"))) - set(faces_to_remove)
        remaining_cands = set(ensure_list(ident.get("candidate_ids"))) - set(faces_to_remove)
        if not remaining_anchors and not remaining_cands:
            will_be_empty += 1
    print(f"Identities that will become empty: {will_be_empty}")

    if args.dry_run:
        # Show sample removals
        print("\nSample removals:")
        for iid, faces in list(removals.items())[:10]:
            ident = id_map[iid]
            print(f"  {ident.get('name', '?')} ({iid[:8]}, {ident.get('state', '?')}): lose {len(faces)} faces")
        print("\nNo changes made.")
        return

    # EXECUTE
    print(f"\n[EXECUTE] Removing faces from {len(removals)} identities...")
    now = datetime.now(timezone.utc).isoformat()
    success = 0
    errors = 0
    emptied = 0

    for i, (iid, faces_to_remove) in enumerate(removals.items()):
        ident = id_map[iid]
        new_anchors = [f for f in ensure_list(ident.get("anchor_ids")) if f not in faces_to_remove]
        new_cands = [f for f in ensure_list(ident.get("candidate_ids")) if f not in faces_to_remove]

        update = {
            "anchor_ids": new_anchors,
            "candidate_ids": new_cands,
            "updated_at": now,
        }

        # If identity becomes empty and was not CONFIRMED, mark as merged into winner
        if not new_anchors and not new_cands and ident.get("state") != "CONFIRMED":
            # Find the winner for the first face
            first_face = faces_to_remove[0]
            winners = [(oid, lt) for oid, lt in face_to_identities[first_face] if oid != iid]
            if winners:
                winner_id = winners[0][0]
                update["merged_into"] = winner_id
                emptied += 1

        try:
            sb.table("identities").update(update).eq("identity_id", iid).execute()
            success += 1
        except Exception as e:
            print(f"  ERROR on {iid}: {e}")
            errors += 1

        if (i + 1) % 100 == 0:
            print(f"  Progress: {i + 1}/{len(removals)} ({success} ok, {errors} err)")

    print(f"\nDone: {success} modified, {emptied} re-merged, {errors} errors")

    # Verify
    print("\nVerifying...")
    identities2 = paginated_select(
        sb.table("identities"),
        "identity_id,state,anchor_ids,candidate_ids,merged_into",
    )
    face_to_ids2 = defaultdict(list)
    for ident in identities2:
        if ident.get("merged_into"):
            continue
        for key in ["anchor_ids", "candidate_ids"]:
            for fid in ensure_list(ident.get(key)):
                face_to_ids2[fid].append(ident["identity_id"])
    remaining_multi = sum(1 for fid, owners in face_to_ids2.items() if len(owners) > 1)
    print(f"Remaining multi-claimed faces: {remaining_multi}")


if __name__ == "__main__":
    main()
