#!/usr/bin/env python3
"""
Backfill merge_history for pre-existing merged identities.

Some identities were merged before the merge_history feature was added.
Their target identities lack merge_history entries, so the "Undo Merge"
button shows "Nothing to undo." This script adds stub entries so the UI
can at least display when the merge happened (even though full undo data
is unavailable).

Usage:
    python scripts/backfill_merge_history.py              # dry-run (default)
    python scripts/backfill_merge_history.py --execute     # apply changes
"""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Backfill merge_history for pre-existing merges")
    parser.add_argument("--execute", action="store_true", help="Apply changes (default: dry-run)")
    parser.add_argument("--data-dir", default="data", help="Path to data directory")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    identities_path = data_dir / "identities.json"

    if not identities_path.exists():
        print(f"ERROR: {identities_path} not found")
        sys.exit(1)

    with open(identities_path) as f:
        data = json.load(f)

    identities = data.get("identities", {})

    # Find source identities that have been merged into a target
    merged_sources = {
        iid: ident for iid, ident in identities.items()
        if ident.get("merged_into")
    }

    print(f"Found {len(merged_sources)} merged source identities")

    backfill_count = 0
    for source_id, source in merged_sources.items():
        target_id = source["merged_into"]
        target = identities.get(target_id)
        if not target:
            print(f"  WARN: target {target_id} not found for source {source_id}")
            continue

        # Check if target already has a merge_history entry for this source
        existing_history = target.get("merge_history", [])
        already_tracked = any(
            entry.get("source_id") == source_id
            for entry in existing_history
        )
        if already_tracked:
            continue

        # Need to backfill
        source_name = source.get("name", "Unknown")
        merge_time = source.get("updated_at", source.get("created_at", "unknown"))
        print(f"  BACKFILL: {source_name} ({source_id[:8]}) -> {target.get('name', '?')} ({target_id[:8]})")

        if args.execute:
            stub_entry = {
                "merge_event_id": f"backfill-{source_id[:12]}",
                "timestamp": merge_time,
                "source_id": source_id,
                "source_name": source_name,
                "source_state": source.get("state", "unknown"),
                "faces_added": {"anchors": [], "candidates": [], "negatives": []},
                "direction_auto_corrected": False,
                "merged_by": "backfill_script",
                "note": "Pre-merge-history merge. Full undo data unavailable.",
            }
            target.setdefault("merge_history", []).append(stub_entry)

        backfill_count += 1

    print(f"\n{'Would backfill' if not args.execute else 'Backfilled'} {backfill_count} merge history entries")

    if args.execute and backfill_count > 0:
        with open(identities_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Wrote {identities_path}")
    elif not args.execute and backfill_count > 0:
        print("(dry-run mode — use --execute to apply)")


if __name__ == "__main__":
    main()
