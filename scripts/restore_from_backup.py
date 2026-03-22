#!/usr/bin/env python3
"""Restore identities from a Session 133 backup snapshot.

Usage:
    python scripts/restore_from_backup.py --backup data_backup_session133/identities_pre_phase2.json --dry-run
    python scripts/restore_from_backup.py --backup data_backup_session133/identities_pre_phase2.json --execute

This restores ONLY the identity fields that the Phase 2 scripts modify:
  - merged_into
  - anchor_ids
  - candidate_ids
  - updated_at

It does NOT touch: name, state, identity_id, created_at, or any other fields.
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


def main():
    parser = argparse.ArgumentParser(description="Restore identities from backup")
    parser.add_argument("--backup", required=True, help="Path to backup JSON file")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    with open(args.backup) as f:
        backup = json.load(f)

    print(f"Loaded {len(backup)} identities from {args.backup}")

    sb = get_client()

    if args.dry_run:
        # Count what would change
        merged_count = sum(1 for i in backup if i.get("merged_into"))
        with_anchors = sum(1 for i in backup if i.get("anchor_ids"))
        with_candidates = sum(1 for i in backup if i.get("candidate_ids"))
        print("Would restore:")
        print(f"  {merged_count} identities with merged_into")
        print(f"  {with_anchors} identities with anchor_ids")
        print(f"  {with_candidates} identities with candidate_ids")
        print("\nNo changes made.")
        return

    print(f"[EXECUTE] Restoring {len(backup)} identities...")
    now = datetime.now(timezone.utc).isoformat()
    success = 0
    errors = 0

    for i, ident in enumerate(backup):
        iid = ident["identity_id"]
        try:
            sb.table("identities").update(
                {
                    "merged_into": ident.get("merged_into"),
                    "anchor_ids": ident.get("anchor_ids"),
                    "candidate_ids": ident.get("candidate_ids"),
                    "updated_at": now,
                }
            ).eq("identity_id", iid).execute()
            success += 1
        except Exception as e:
            print(f"  ERROR on {iid}: {e}")
            errors += 1

        if (i + 1) % 500 == 0:
            print(f"  Progress: {i + 1}/{len(backup)} ({success} ok, {errors} err)")

    print(f"\nDone: {success} restored, {errors} errors")


if __name__ == "__main__":
    main()
