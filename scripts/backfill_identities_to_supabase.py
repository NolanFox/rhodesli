#!/usr/bin/env python3
"""One-time backfill: push all local JSON identities to Supabase.

Usage:
    python scripts/backfill_identities_to_supabase.py --dry-run
    python scripts/backfill_identities_to_supabase.py --execute
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Just count, don't write")
    parser.add_argument("--execute", action="store_true", help="Actually write to Supabase")
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("Must specify --dry-run or --execute")
        sys.exit(1)

    # Load local identities
    json_path = Path("data/identities.json")
    with open(json_path) as f:
        data = json.load(f)

    identities = data.get("identities", {})
    print(f"Local JSON: {len(identities)} identities")

    # Count by state
    states = {}
    for v in identities.values():
        s = v.get("state", "UNKNOWN")
        states[s] = states.get(s, 0) + 1
    print(f"By state: {states}")

    if args.dry_run:
        print("\n[DRY RUN] Would upsert all identities to Supabase")
        return

    # Execute
    from app.supabase_data import shadow_write_identities_batch, get_supabase_client

    client = get_supabase_client()
    if not client:
        print("ERROR: No Supabase client available. Check env vars.")
        sys.exit(1)

    # Check current Supabase count
    result = client.table("identities").select("identity_id", count="exact").execute()
    print(f"Supabase before: {result.count} identities")

    # Build items list
    items = [dict(v, identity_id=k) for k, v in identities.items()]
    written = shadow_write_identities_batch(items)
    print(f"Upserted {written} identities to Supabase")

    # Verify
    result = client.table("identities").select("identity_id", count="exact").execute()
    print(f"Supabase after: {result.count} identities")


if __name__ == "__main__":
    main()
