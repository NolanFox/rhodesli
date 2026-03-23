#!/usr/bin/env python3
"""Audit and optionally repair multi-claimed faces.

A multi-claimed face is one that appears in anchor_ids of 2+ non-merged identities.
This is a data integrity issue — each face should belong to exactly one identity.

Usage:
    python scripts/audit_multi_claimed_faces.py                # dry-run (default)
    python scripts/audit_multi_claimed_faces.py --execute      # apply repairs

Ownership rules (in priority order):
  1. CONFIRMED identity wins over PROPOSED/INBOX
  2. If same state, identity with more anchor faces wins
  3. If still tied, older identity (earlier created_at) wins

When a face is removed from a non-owner identity:
  - If the identity has no remaining anchor_ids or candidate_ids, mark it merged_into the owner
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()


STATE_PRIORITY = {"CONFIRMED": 0, "PROPOSED": 1, "INBOX": 2}


def get_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        sys.exit(1)
    from supabase import create_client

    return create_client(url, key)


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


def find_multi_claimed(identities: list[dict]) -> dict[str, list[dict]]:
    """Find faces claimed by 2+ non-merged identities.

    Returns dict mapping face_id -> list of identity dicts that claim it.
    """
    face_to_identities: dict[str, list[dict]] = defaultdict(list)

    for ident in identities:
        if ident.get("merged_into"):
            continue
        anchor_ids = ensure_list(ident.get("anchor_ids"))
        for face_id in anchor_ids:
            face_to_identities[face_id].append(ident)

    # Keep only multi-claimed
    return {face_id: owners for face_id, owners in face_to_identities.items() if len(owners) > 1}


def pick_owner(claimants: list[dict]) -> dict:
    """Pick the rightful owner among competing identities for a face.

    Priority: CONFIRMED > PROPOSED > INBOX, then more faces, then older.
    """

    def sort_key(ident):
        state = ident.get("state", "INBOX")
        anchor_count = len(ensure_list(ident.get("anchor_ids")))
        created = ident.get("created_at", "9999")
        return (STATE_PRIORITY.get(state, 99), -anchor_count, created)

    sorted_claimants = sorted(claimants, key=sort_key)
    return sorted_claimants[0]


def compute_repairs(
    multi_claimed: dict[str, list[dict]],
) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Compute what repairs are needed.

    Returns:
        faces_to_remove: dict[identity_id -> list of face_ids to remove]
        empty_to_merge: dict[identity_id -> merge_into identity_id]
    """
    faces_to_remove: dict[str, list[str]] = defaultdict(list)
    # Track which identity each non-owner should merge into
    merge_targets: dict[str, str] = {}

    for face_id, claimants in multi_claimed.items():
        owner = pick_owner(claimants)
        for claimant in claimants:
            if claimant["identity_id"] != owner["identity_id"]:
                faces_to_remove[claimant["identity_id"]].append(face_id)
                merge_targets[claimant["identity_id"]] = owner["identity_id"]

    # Determine which identities would become empty after removal
    empty_to_merge: dict[str, str] = {}
    # We need to check if removing these faces leaves the identity empty
    # Build a map of identity -> remaining faces after removal
    identity_map = {}
    for face_id, claimants in multi_claimed.items():
        for c in claimants:
            identity_map[c["identity_id"]] = c

    for ident_id, faces in faces_to_remove.items():
        ident = identity_map.get(ident_id)
        if not ident:
            continue
        current_anchors = set(ensure_list(ident.get("anchor_ids")))
        current_candidates = set(ensure_list(ident.get("candidate_ids")))
        remaining_anchors = current_anchors - set(faces)
        if not remaining_anchors and not current_candidates:
            empty_to_merge[ident_id] = merge_targets[ident_id]

    return dict(faces_to_remove), empty_to_merge


def main():
    parser = argparse.ArgumentParser(description="Audit/repair multi-claimed faces")
    parser.add_argument("--execute", action="store_true", help="Apply repairs (default: dry-run)")
    args = parser.parse_args()

    client = get_client()

    # Fetch all identities
    print("Fetching identities from Supabase...")
    result = client.table("identities").select("*").execute()
    identities = result.data
    print(f"  Found {len(identities)} total identities")

    active = [i for i in identities if not i.get("merged_into")]
    print(f"  Active (non-merged): {len(active)}")

    # Find multi-claimed faces
    multi_claimed = find_multi_claimed(identities)
    print(f"\nMulti-claimed faces: {len(multi_claimed)}")

    if not multi_claimed:
        print("No multi-claimed faces found. Data is clean.")
        return

    # Show details
    for face_id, claimants in sorted(multi_claimed.items()):
        owner = pick_owner(claimants)
        print(f"\n  Face: {face_id}")
        for c in claimants:
            marker = " <-- OWNER" if c["identity_id"] == owner["identity_id"] else " (remove)"
            state = c.get("state", "?")
            name = c.get("name", "?")
            anchor_count = len(ensure_list(c.get("anchor_ids")))
            print(f"    {c['identity_id']} [{state}] {name} ({anchor_count} faces){marker}")

    # Compute repairs
    faces_to_remove, empty_to_merge = compute_repairs(multi_claimed)

    print("\n--- Repair Plan ---")
    print(f"Identities needing face removal: {len(faces_to_remove)}")
    for ident_id, faces in faces_to_remove.items():
        print(f"  {ident_id}: remove {len(faces)} face(s): {faces}")

    print(f"\nIdentities to mark as merged (empty after removal): {len(empty_to_merge)}")
    for ident_id, target in empty_to_merge.items():
        print(f"  {ident_id} -> merged_into {target}")

    if not args.execute:
        print("\n[DRY RUN] No changes made. Use --execute to apply.")
        return

    # Apply repairs
    print("\nApplying repairs...")
    for ident_id, faces_to_drop in faces_to_remove.items():
        # Re-fetch current state to avoid stale data
        row = client.table("identities").select("anchor_ids, version_id").eq("identity_id", ident_id).single().execute()
        current_anchors = ensure_list(row.data.get("anchor_ids"))
        new_anchors = [f for f in current_anchors if f not in set(faces_to_drop)]
        version = row.data.get("version_id", 0) or 0

        update = {
            "anchor_ids": new_anchors,
            "version_id": version + 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        if ident_id in empty_to_merge:
            update["merged_into"] = empty_to_merge[ident_id]

        client.table("identities").update(update).eq("identity_id", ident_id).execute()
        action = "removed faces + marked merged" if ident_id in empty_to_merge else "removed faces"
        print(f"  {ident_id}: {action} ({len(faces_to_drop)} faces)")

    print("\nRepairs complete.")


if __name__ == "__main__":
    main()
