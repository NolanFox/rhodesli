#!/usr/bin/env python3
"""Backfill auto-clustering on existing inbox/unresolved faces.

Runs the two-tier auto-clustering pipeline (AD-179) against all
current unresolved faces:

1. Dedup pass: removes inbox identities whose faces already exist in
   confirmed clusters (exact face_id match, distance = 0.0)
2. Tier 1 pass (distance < 0.85): auto-add face as candidate on confirmed identity
3. Tier 2 pass (0.85 <= distance < 1.10): log as suggestion for Discoveries UI

Creates data/discovery_log.json with all results.

Usage:
    python scripts/backfill_auto_cluster.py --dry-run    # Preview only (default)
    python scripts/backfill_auto_cluster.py --execute     # Apply changes
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

# Add project root to path for core imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def load_face_data(data_path: Path) -> dict:
    """Load face embeddings as face_id -> {mu, sigma_sq} dict.

    Mirrors the logic in cluster_new_faces.py load_face_data().
    """
    import numpy as np

    embeddings_path = data_path / "embeddings.npy"
    if not embeddings_path.exists():
        raise FileNotFoundError(f"Embeddings not found: {embeddings_path}")

    embeddings = np.load(embeddings_path, allow_pickle=True)

    face_data = {}
    filename_face_counts = {}

    for entry in embeddings:
        filename = entry["filename"]

        if filename not in filename_face_counts:
            filename_face_counts[filename] = 0
        face_index = filename_face_counts[filename]
        filename_face_counts[filename] += 1

        face_id = entry.get("face_id") or f"{Path(filename).stem}:face{face_index}"

        if "mu" in entry:
            mu = entry["mu"]
        else:
            mu = np.asarray(entry["embedding"], dtype=np.float32)

        face_data[face_id] = {
            "mu": np.asarray(mu, dtype=np.float32),
        }

    return face_data


def main():
    parser = argparse.ArgumentParser(
        description="Backfill auto-clustering on existing inbox/unresolved faces."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview results without modifying data (default)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply auto-clustering changes to identities.json",
    )
    args = parser.parse_args()

    if args.execute:
        args.dry_run = False

    data_path = project_root / "data"
    identities_path = data_path / "identities.json"
    log_path = str(data_path / "discovery_log.json")

    print("=" * 60)
    print("AUTO-CLUSTERING BACKFILL (AD-179)")
    print("=" * 60)
    print(f"Data path: {data_path}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'EXECUTE'}")
    print()

    # Load data
    print("Loading identities...")
    with open(identities_path) as f:
        identities_data = json.load(f)

    identities = identities_data.get("identities", {})
    total = len(identities)
    confirmed = sum(1 for i in identities.values() if i.get("state") == "CONFIRMED")
    inbox = sum(1 for i in identities.values() if i.get("state") == "INBOX")
    skipped = sum(1 for i in identities.values() if i.get("state") == "SKIPPED")
    proposed = sum(1 for i in identities.values() if i.get("state") == "PROPOSED")
    print(f"  Total: {total}")
    print(f"  CONFIRMED: {confirmed}")
    print(f"  INBOX: {inbox}")
    print(f"  SKIPPED: {skipped}")
    print(f"  PROPOSED: {proposed}")

    print("\nLoading face embeddings...")
    face_data = load_face_data(data_path)
    print(f"  Face embeddings: {len(face_data)}")
    print()

    # Import and run
    from core.auto_cluster import TIER_1_THRESHOLD, TIER_2_THRESHOLD, run_backfill

    print(f"Thresholds: Tier 1 < {TIER_1_THRESHOLD}, Tier 2 < {TIER_2_THRESHOLD}")
    print()

    results = run_backfill(
        identities_data, face_data, log_path=log_path, dry_run=args.dry_run
    )

    # Display results
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)

    # Dedup results
    dedup = results["dedup_results"]
    print(f"\n1. DEDUP PASS: {len(dedup)} duplicate inbox identities")
    if dedup:
        print("-" * 60)
        for inbox_id, conf_id, shared in dedup[:20]:
            inbox_name = identities.get(inbox_id, {}).get("name", "?")
            conf_name = identities.get(conf_id, {}).get("name", "?")
            print(f"  {inbox_name} -> {conf_name} ({len(shared)} shared faces)")
        if len(dedup) > 20:
            print(f"  ... and {len(dedup) - 20} more")

    # Tier 1 results
    t1 = results["tier_1_results"]
    print(f"\n2. TIER 1 (auto-add, distance < {TIER_1_THRESHOLD}): {len(t1)} faces")
    if t1:
        print("-" * 60)
        for r in t1[:20]:
            print(f"  {r['face_id'][:35]:<35} -> {r['target_identity_name'][:25]:<25} "
                  f"dist={r['distance']:.4f}")
        if len(t1) > 20:
            print(f"  ... and {len(t1) - 20} more")

    # Tier 2 results
    t2 = results["tier_2_results"]
    print(f"\n3. TIER 2 (suggest, {TIER_1_THRESHOLD} <= distance < {TIER_2_THRESHOLD}): {len(t2)} faces")
    if t2:
        print("-" * 60)
        for r in t2[:20]:
            print(f"  {r['face_id'][:35]:<35} -> {r['target_identity_name'][:25]:<25} "
                  f"dist={r['distance']:.4f}")
        if len(t2) > 20:
            print(f"  ... and {len(t2) - 20} more")

    # Summary
    no_match = results["no_match_count"]
    total_processed = results["total_processed"]
    print(f"\n4. NO MATCH: {no_match} faces")

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total faces processed: {total_processed}")
    print(f"  Dedup (exact match):   {len(dedup)}")
    print(f"  Tier 1 (auto-add):     {len(t1)}")
    print(f"  Tier 2 (suggest):      {len(t2)}")
    print(f"  No match:              {no_match}")

    if args.dry_run:
        print()
        print("[DRY RUN] No changes made to identities.json.")
        print("Run with --execute to apply these changes.")
    else:
        # Save updated identities
        fd, temp_path = tempfile.mkstemp(
            suffix=".json",
            dir=identities_path.parent,
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(identities_data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.rename(temp_path, str(identities_path))
            print(f"\nSaved updated identities to {identities_path}")
            print(f"Discovery log written to {log_path}")
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise


if __name__ == "__main__":
    main()
