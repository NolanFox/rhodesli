#!/usr/bin/env python3
"""Transfer faces from merged identities to their merge targets.

After resolve_dangling_merges.py clears dangling references, the remaining
merged identities with faces need their anchor_ids/candidate_ids transferred
to the target identity.

Usage:
    python scripts/bulk_face_transfer.py --dry-run   # Report only
    python scripts/bulk_face_transfer.py --execute    # Fix in Supabase
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


def follow_chain(iid, merged_map, all_ids):
    """Follow merge chain to final active target. Returns None if dangling."""
    visited = {iid}
    current = iid
    while current in merged_map:
        nxt = merged_map[current]
        if nxt in visited:
            return None  # circular
        if nxt not in all_ids:
            return None  # dangling
        visited.add(nxt)
        current = nxt
    return current


def main():
    parser = argparse.ArgumentParser(description="Bulk face transfer from merged identities")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    sb = get_client()
    print("Fetching all identities...")
    identities = paginated_select(
        sb.table("identities"),
        "identity_id,name,state,merged_into,anchor_ids,candidate_ids",
    )
    print(f"  {len(identities)} identities fetched")

    # Build lookup
    id_map = {i["identity_id"]: i for i in identities}
    all_ids = set(id_map.keys())
    merged_map = {}
    for i in identities:
        if i.get("merged_into"):
            merged_map[i["identity_id"]] = i["merged_into"]

    # Find merged identities that still hold faces
    merged_with_faces = []
    for iid, target in merged_map.items():
        ident = id_map[iid]
        anchors = ensure_list(ident.get("anchor_ids"))
        candidates = ensure_list(ident.get("candidate_ids"))
        if anchors or candidates:
            final_target = follow_chain(iid, merged_map, all_ids)
            if final_target and final_target != iid:
                merged_with_faces.append(
                    {
                        "source_id": iid,
                        "source_name": ident.get("name", "?"),
                        "target_id": final_target,
                        "target_name": id_map[final_target].get("name", "?"),
                        "anchors": anchors,
                        "candidates": candidates,
                    }
                )

    print(f"\nMerged identities with faces (valid targets): {len(merged_with_faces)}")

    # Also count dangling (should be 0 after resolve_dangling_merges.py)
    dangling_with_faces = 0
    for iid, target in merged_map.items():
        ident = id_map[iid]
        anchors = ensure_list(ident.get("anchor_ids"))
        candidates = ensure_list(ident.get("candidate_ids"))
        if anchors or candidates:
            final = follow_chain(iid, merged_map, all_ids)
            if final is None or final == iid:
                dangling_with_faces += 1
    if dangling_with_faces:
        print(f"WARNING: {dangling_with_faces} merged identities with faces have no valid target!")
        print("Run resolve_dangling_merges.py first.")

    # Group transfers by target for efficiency
    transfers_by_target = defaultdict(list)
    for entry in merged_with_faces:
        transfers_by_target[entry["target_id"]].append(entry)

    total_faces = sum(len(e["anchors"]) + len(e["candidates"]) for e in merged_with_faces)
    print(f"Total faces to transfer: {total_faces}")
    print(f"Unique targets: {len(transfers_by_target)}")

    if args.dry_run:
        print("\n[DRY RUN] Top targets by incoming faces:")
        for tid, entries in sorted(
            transfers_by_target.items(), key=lambda x: -sum(len(e["anchors"]) + len(e["candidates"]) for e in x[1])
        )[:15]:
            n = sum(len(e["anchors"]) + len(e["candidates"]) for e in entries)
            tname = id_map[tid].get("name", "?")
            print(f"  {tname} ({tid[:8]}): {n} faces from {len(entries)} sources")
        print("\nNo changes made.")
        return

    # EXECUTE
    print(f"\n[EXECUTE] Transferring faces to {len(transfers_by_target)} targets...")
    now = datetime.now(timezone.utc).isoformat()
    targets_updated = 0
    sources_cleared = 0
    errors = 0

    for tid, entries in transfers_by_target.items():
        target = id_map[tid]
        target_anchors = set(ensure_list(target.get("anchor_ids")))
        target_candidates = set(ensure_list(target.get("candidate_ids")))

        # Collect all faces from sources
        new_candidates = set()
        for entry in entries:
            # All transferred faces go to candidate_ids on target
            # (they were proposed matches, not confirmed by admin)
            new_candidates.update(entry["anchors"])
            new_candidates.update(entry["candidates"])

        # Remove any that are already in target's anchors (don't demote confirmed)
        new_candidates -= target_anchors

        # Add to target's candidates
        merged_candidates = list(target_candidates | new_candidates)

        try:
            sb.table("identities").update(
                {
                    "candidate_ids": merged_candidates,
                    "updated_at": now,
                }
            ).eq("identity_id", tid).execute()
            targets_updated += 1
        except Exception as e:
            print(f"  ERROR updating target {tid}: {e}")
            errors += 1
            continue

        # Clear faces from all sources
        for entry in entries:
            try:
                sb.table("identities").update(
                    {
                        "anchor_ids": [],
                        "candidate_ids": [],
                        "updated_at": now,
                    }
                ).eq("identity_id", entry["source_id"]).execute()
                sources_cleared += 1
            except Exception as e:
                print(f"  ERROR clearing source {entry['source_id']}: {e}")
                errors += 1

        if targets_updated % 50 == 0 and targets_updated > 0:
            print(f"  Progress: {targets_updated}/{len(transfers_by_target)} targets")

    print(f"\nDone: {targets_updated} targets updated, {sources_cleared} sources cleared, {errors} errors")

    # Verify
    print("\nVerifying...")
    identities2 = paginated_select(
        sb.table("identities"),
        "identity_id,merged_into,anchor_ids,candidate_ids",
    )
    still_holding = 0
    for i in identities2:
        if i.get("merged_into"):
            a = ensure_list(i.get("anchor_ids"))
            c = ensure_list(i.get("candidate_ids"))
            if a or c:
                still_holding += 1
    print(f"Merged identities still holding faces: {still_holding}")


if __name__ == "__main__":
    main()
