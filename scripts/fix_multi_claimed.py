#!/usr/bin/env python3
"""Fix multi-claimed faces — faces owned by 2+ active identities.

Per Session 133 prompt:
- inbox_fb4b65ccecfe: Remove from Person 4063 (Albert Fox CONFIRMED wins)
- inbox_eaf34885039f: Investigate 2820 vs 1e91425f, merge if same
- Image 026_compress:face2: Remove from Contested (Selma CONFIRMED wins)

Usage:
    python scripts/fix_multi_claimed.py --dry-run
    python scripts/fix_multi_claimed.py --execute
"""

import argparse
import json
import os
import sys
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


def remove_face_from_identity(sb, identity_id, face_id, now):
    """Remove a face_id from an identity's anchor_ids and candidate_ids."""
    resp = (
        sb.table("identities").select("identity_id,anchor_ids,candidate_ids").eq("identity_id", identity_id).execute()
    )
    if not resp.data:
        print(f"  ERROR: identity {identity_id} not found")
        return False

    ident = resp.data[0]
    anchors = ensure_list(ident.get("anchor_ids"))
    candidates = ensure_list(ident.get("candidate_ids"))
    changed = False

    if face_id in anchors:
        anchors.remove(face_id)
        changed = True
    if face_id in candidates:
        candidates.remove(face_id)
        changed = True

    if not changed:
        print(f"  WARNING: {face_id} not found in {identity_id}")
        return False

    sb.table("identities").update(
        {
            "anchor_ids": anchors,
            "candidate_ids": candidates,
            "updated_at": now,
        }
    ).eq("identity_id", identity_id).execute()
    return True


def main():
    parser = argparse.ArgumentParser(description="Fix multi-claimed faces")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    sb = get_client()
    now = datetime.now(timezone.utc).isoformat()

    # First, fetch all identities to resolve full UUIDs from 8-char prefixes
    print("Fetching all identities for UUID resolution...")
    all_idents = paginated_select(
        sb.table("identities"),
        "identity_id,name,state,anchor_ids,candidate_ids,merged_into",
    )
    id_by_prefix = {}
    for ident in all_idents:
        prefix = ident["identity_id"][:8]
        id_by_prefix[prefix] = ident["identity_id"]

    def full_id(prefix):
        return id_by_prefix.get(prefix, prefix)

    # Define fixes
    fixes = [
        {
            "face_id": "inbox_fb4b65ccecfe",
            "remove_from": full_id("f1fa51b2"),  # Person 4063
            "keep_on": full_id("85546ebf"),  # Albert Fox CONFIRMED
            "reason": "Albert Fox CONFIRMED wins over Person 4063",
        },
        {
            "face_id": "Image 026_compress:face2",
            "remove_from": full_id("224495e8"),  # Contested Identity
            "keep_on": full_id("cca5f7ff"),  # Selma Capeluto CONFIRMED
            "reason": "Selma Capeluto CONFIRMED wins over Contested Identity",
        },
    ]

    # For inbox_eaf34885039f: need to check if 2820 and 1e91425f are the same
    # Can't use LIKE on UUID columns — search by face_id containment
    print("Investigating inbox_eaf34885039f ownership...")
    face_owners = []
    for ident in all_idents:
        if ident.get("merged_into"):
            continue
        for key in ["anchor_ids", "candidate_ids"]:
            if "inbox_eaf34885039f" in ensure_list(ident.get(key)):
                face_owners.append(ident)
                break

    resp_2820_data = [i for i in face_owners if i["identity_id"].startswith("434f4f8a")]
    resp_1e91_data = [i for i in face_owners if i["identity_id"].startswith("1e91425f")]
    resp_2820 = type("R", (), {"data": resp_2820_data})()
    resp_1e91 = type("R", (), {"data": resp_1e91_data})()

    if resp_2820.data:
        p2820 = resp_2820.data[0]
        print(f"  Person 2820 ({p2820['identity_id'][:8]}): {p2820.get('name', '?')}, state={p2820.get('state', '?')}")
        print(f"    anchors: {ensure_list(p2820.get('anchor_ids'))[:5]}")
    if resp_1e91.data:
        p1e91 = resp_1e91.data[0]
        print(f"  Person 1e91 ({p1e91['identity_id'][:8]}): {p1e91.get('name', '?')}, state={p1e91.get('state', '?')}")
        print(f"    anchors: {ensure_list(p1e91.get('anchor_ids'))[:5]}")

    # Determine fix for inbox_eaf34885039f
    if resp_2820.data and resp_1e91.data:
        p2820_state = resp_2820.data[0].get("state", "?")
        p1e91_state = resp_1e91.data[0].get("state", "?")
        # Keep on whichever is CONFIRMED, or the one with more anchors
        if p2820_state == "CONFIRMED":
            fixes.append(
                {
                    "face_id": "inbox_eaf34885039f",
                    "remove_from": resp_1e91.data[0]["identity_id"],
                    "keep_on": resp_2820.data[0]["identity_id"],
                    "reason": f"Person 2820 is {p2820_state}, wins",
                }
            )
        elif p1e91_state == "CONFIRMED":
            fixes.append(
                {
                    "face_id": "inbox_eaf34885039f",
                    "remove_from": resp_2820.data[0]["identity_id"],
                    "keep_on": resp_1e91.data[0]["identity_id"],
                    "reason": f"Person 1e91 is {p1e91_state}, wins",
                }
            )
        else:
            # Both INBOX — keep on whichever has more anchors
            a1 = len(ensure_list(resp_2820.data[0].get("anchor_ids")))
            a2 = len(ensure_list(resp_1e91.data[0].get("anchor_ids")))
            if a1 >= a2:
                fixes.append(
                    {
                        "face_id": "inbox_eaf34885039f",
                        "remove_from": resp_1e91.data[0]["identity_id"],
                        "keep_on": resp_2820.data[0]["identity_id"],
                        "reason": f"Person 2820 has {a1} anchors vs {a2}",
                    }
                )
            else:
                fixes.append(
                    {
                        "face_id": "inbox_eaf34885039f",
                        "remove_from": resp_2820.data[0]["identity_id"],
                        "keep_on": resp_1e91.data[0]["identity_id"],
                        "reason": f"Person 1e91 has {a2} anchors vs {a1}",
                    }
                )

    print(f"\n{len(fixes)} fixes planned:")
    for fix in fixes:
        print(
            f"  {fix['face_id']}: remove from {fix['remove_from'][:8]}, keep on {fix['keep_on'][:8]} — {fix['reason']}"
        )

    if args.dry_run:
        print("\nNo changes made.")
        return

    print("\n[EXECUTE]")
    for fix in fixes:
        print(f"  Removing {fix['face_id']} from {fix['remove_from'][:8]}...")
        ok = remove_face_from_identity(sb, fix["remove_from"], fix["face_id"], now)
        print(f"    {'OK' if ok else 'FAILED'}")

    print("\nDone.")


if __name__ == "__main__":
    main()
