#!/usr/bin/env python3
"""Remove test data contamination from production data files.

Usage:
    python scripts/clean_test_data.py --dry-run   # Preview changes (default)
    python scripts/clean_test_data.py --execute    # Apply changes
"""
import argparse
import json
import shutil
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def clean_annotations(dry_run: bool) -> int:
    """Remove test annotations from annotations.json."""
    path = DATA_DIR / "annotations.json"
    if not path.exists():
        print("  annotations.json not found, skipping")
        return 0

    with open(path) as f:
        data = json.load(f)

    annotations = data.get("annotations", {})
    test_patterns = ["test@test.com", "user@test.com", "admin@test.com",
                     "target-123", "target-id", "source-456"]

    to_remove = []
    for ann_id, ann in annotations.items():
        ann_str = json.dumps(ann)
        if any(p in ann_str for p in test_patterns):
            to_remove.append(ann_id)
            print(f"  REMOVE annotation {ann_id}: type={ann.get('type')}, "
                  f"submitted_by={ann.get('submitted_by')}, "
                  f"target={ann.get('target_id', '')[:20]}")

    # Also check for anonymous submissions with identical timestamps to test data
    test_timestamps = set()
    for ann_id in to_remove:
        ts = annotations[ann_id].get("submitted_at", "")
        if ts:
            # Match to the second
            test_timestamps.add(ts[:19])

    for ann_id, ann in annotations.items():
        if ann_id not in to_remove:
            ts = ann.get("submitted_at", "")
            if ts and ts[:19] in test_timestamps:
                to_remove.append(ann_id)
                print(f"  REMOVE annotation {ann_id} (same timestamp as test data): "
                      f"type={ann.get('type')}, submitted_by={ann.get('submitted_by')}")

    if not dry_run and to_remove:
        # Backup
        backup = path.with_suffix(".json.bak")
        shutil.copy2(path, backup)
        print(f"  Backup saved to {backup}")

        for ann_id in to_remove:
            del annotations[ann_id]
        data["annotations"] = annotations

        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"  Wrote cleaned annotations.json ({len(annotations)} remaining)")

    return len(to_remove)


def clean_identity_history(dry_run: bool) -> int:
    """Remove test rename entries from identities.json history."""
    path = DATA_DIR / "identities.json"
    with open(path) as f:
        data = json.load(f)

    history = data.get("history", [])
    test_patterns = ["Test Person Name", "restoration_note", "test@test.com"]

    contaminated_indices = []
    for i, h in enumerate(history):
        meta_str = json.dumps(h.get("metadata", {}))
        if any(p in meta_str for p in test_patterns):
            contaminated_indices.append(i)

    if contaminated_indices:
        # Group by identity
        from collections import Counter
        id_counts = Counter(history[i].get("identity_id", "?") for i in contaminated_indices)
        for identity_id, count in id_counts.items():
            print(f"  REMOVE {count} history entries for identity {identity_id}")

    if not dry_run and contaminated_indices:
        # Backup
        backup = path.with_suffix(".json.bak")
        shutil.copy2(path, backup)
        print(f"  Backup saved to {backup}")

        # Remove contaminated entries (reverse order to preserve indices)
        for i in sorted(contaminated_indices, reverse=True):
            history.pop(i)

        data["history"] = history

        # Fix Victoria's version_id (subtract contaminated renames)
        victoria_id = "2cf08b25-075c-41a8-a20d-d03686aafd06"
        if victoria_id in data["identities"]:
            vic = data["identities"][victoria_id]
            old_version = vic.get("version_id", 0)
            # Count remaining legitimate history entries for Victoria
            vic_remaining = sum(1 for h in history if h.get("identity_id") == victoria_id)
            # version_id should be initial (1) + history entries
            new_version = vic_remaining + 1
            if new_version != old_version:
                vic["version_id"] = new_version
                print(f"  Fixed Victoria version_id: {old_version} -> {new_version}")

        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"  Wrote cleaned identities.json ({len(history)} history entries remaining)")

    return len(contaminated_indices)


def main():
    parser = argparse.ArgumentParser(description="Clean test data from production")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Preview changes without modifying files (default)")
    parser.add_argument("--execute", action="store_true",
                        help="Apply changes to data files")
    args = parser.parse_args()

    dry_run = not args.execute
    mode = "DRY RUN" if dry_run else "EXECUTING"
    print(f"=== Clean Test Data ({mode}) ===\n")

    print("1. Checking annotations.json...")
    ann_count = clean_annotations(dry_run)

    print(f"\n2. Checking identities.json history...")
    hist_count = clean_identity_history(dry_run)

    print(f"\n=== Summary ===")
    print(f"Annotations to remove: {ann_count}")
    print(f"History entries to remove: {hist_count}")

    if dry_run and (ann_count + hist_count) > 0:
        print(f"\nRun with --execute to apply changes")


if __name__ == "__main__":
    main()
