#!/usr/bin/env python3
"""Resolve 691 dangling merge references in Supabase.

Dangling = merged_into points to an identity_id that doesn't exist.
Since backup (data_backup_session25/) doesn't contain these targets either,
the fix is to CLEAR merged_into — effectively un-merging these identities
back to active status.

Usage:
    python scripts/resolve_dangling_merges.py --dry-run   # Report only
    python scripts/resolve_dangling_merges.py --execute    # Fix in Supabase
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


def find_dangling(identities):
    """Find all identities with merged_into pointing to non-existent targets."""
    all_ids = {i["identity_id"] for i in identities}
    dangling = []
    for ident in identities:
        target = ident.get("merged_into")
        if target and target not in all_ids:
            dangling.append(ident)
    return dangling


def main():
    parser = argparse.ArgumentParser(description="Resolve dangling merge references")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Report only, no changes")
    group.add_argument("--execute", action="store_true", help="Fix in Supabase")
    args = parser.parse_args()

    sb = get_client()
    print("Fetching all identities...")
    identities = paginated_select(sb.table("identities"), "identity_id,name,state,merged_into,anchor_ids,candidate_ids")
    print(f"  {len(identities)} identities fetched")

    dangling = find_dangling(identities)
    print(f"\nDangling merge references: {len(dangling)}")

    # Group by missing target
    by_target = defaultdict(list)
    for ident in dangling:
        by_target[ident["merged_into"]].append(ident)

    print(f"Unique missing targets: {len(by_target)}")
    print("\nTop missing targets:")
    for target, sources in sorted(by_target.items(), key=lambda x: -len(x[1]))[:10]:
        print(f"  {target[:12]}... -> {len(sources)} identities")

    if args.dry_run:
        print("\n[DRY RUN] Would clear merged_into on these identities:")
        # Count how many have faces vs empty
        with_faces = sum(1 for i in dangling if (i.get("anchor_ids") or []) or (i.get("candidate_ids") or []))
        empty = len(dangling) - with_faces
        print(f"  With faces (will become active): {with_faces}")
        print(f"  Without faces (will become active but empty): {empty}")
        print("\nNo changes made.")
        return

    # EXECUTE: Clear merged_into in batches
    print(f"\n[EXECUTE] Clearing merged_into on {len(dangling)} identities...")
    now = datetime.now(timezone.utc).isoformat()
    success = 0
    errors = 0

    for i, ident in enumerate(dangling):
        iid = ident["identity_id"]
        try:
            sb.table("identities").update(
                {
                    "merged_into": None,
                    "updated_at": now,
                }
            ).eq("identity_id", iid).execute()
            success += 1
        except Exception as e:
            print(f"  ERROR on {iid}: {e}")
            errors += 1

        if (i + 1) % 100 == 0:
            print(f"  Progress: {i + 1}/{len(dangling)} ({success} ok, {errors} err)")

    print(f"\nDone: {success} cleared, {errors} errors")

    # Verify
    print("\nVerifying...")
    identities2 = paginated_select(sb.table("identities"), "identity_id,merged_into")
    remaining = find_dangling(identities2)
    print(f"Remaining dangling references: {len(remaining)}")
    if remaining:
        print("WARNING: Some dangling references remain!")
        for i in remaining[:5]:
            print(f"  {i['identity_id'][:12]} -> {i['merged_into'][:12]}")


if __name__ == "__main__":
    main()
