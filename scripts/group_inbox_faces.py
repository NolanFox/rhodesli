#!/usr/bin/env python3
"""Group similar INBOX identities by face embedding similarity.

After ingestion, each photo creates one identity per detected face.
This script compares ALL inbox faces pairwise and merges similar ones
into clusters, so the admin reviews ~15 groups instead of ~75 individuals.

Uses the same best-linkage / union-find approach as cluster_new_faces.py,
but compares inbox-vs-inbox instead of inbox-vs-confirmed.

Usage:
    python scripts/group_inbox_faces.py --dry-run     # Preview grouping
    python scripts/group_inbox_faces.py --execute      # Actually merge
    python scripts/group_inbox_faces.py --threshold 0.90  # Stricter grouping
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path for core imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.config import GROUPING_THRESHOLD


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

        face_id = entry.get("face_id") or _generate_face_id(filename, face_index)

        if "mu" in entry:
            mu = entry["mu"]
            sigma_sq = entry["sigma_sq"]
        else:
            mu = np.asarray(entry["embedding"], dtype=np.float32)
            det_score = entry.get("det_score", 0.5)
            sigma_sq_val = 1.0 - (det_score * 0.9)
            sigma_sq = np.full(512, sigma_sq_val, dtype=np.float32)

        face_data[face_id] = {
            "mu": np.asarray(mu, dtype=np.float32),
            "sigma_sq": np.asarray(sigma_sq, dtype=np.float32),
        }

    return face_data


def _generate_face_id(filename: str, face_index: int) -> str:
    """Generate a stable face ID from filename and index."""
    stem = Path(filename).stem
    return f"{stem}:face{face_index}"


def main():
    parser = argparse.ArgumentParser(
        description="Group similar INBOX identities by face embedding similarity."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview grouping without modifying data (default)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually merge grouped identities in identities.json",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=GROUPING_THRESHOLD,
        help=f"Distance threshold for grouping (default: {GROUPING_THRESHOLD})",
    )
    args = parser.parse_args()

    if args.execute:
        args.dry_run = False

    data_path = project_root / "data"

    print("=" * 60)
    print("GROUP INBOX FACES")
    print("=" * 60)
    print(f"Data path: {data_path}")
    print(f"Threshold: {args.threshold}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'EXECUTE'}")
    print()

    # Load data
    from core.photo_registry import PhotoRegistry
    from core.registry import IdentityRegistry, IdentityState

    print("Loading identities...")
    identities_path = data_path / "identities.json"
    registry = IdentityRegistry.load(identities_path)
    inbox_count = len(registry.list_identities(state=IdentityState.INBOX, include_merged=False))
    print(f"  INBOX identities: {inbox_count}")

    print("Loading face embeddings...")
    face_data = load_face_data(data_path)
    print(f"  Face embeddings: {len(face_data)}")

    print("Loading photo registry...")
    photo_index_path = data_path / "photo_index.json"
    photo_registry = PhotoRegistry.load(photo_index_path)
    print()

    # Run grouping
    from core.grouping import group_inbox_identities

    results = group_inbox_identities(
        registry=registry,
        face_data=face_data,
        photo_registry=photo_registry,
        threshold=args.threshold,
        dry_run=args.dry_run,
    )

    # Display results
    if not results["groups"]:
        print("No groups found at this threshold.")
        print(f"All {results['identities_before']} inbox identities are distinct.")
        print(f"Try increasing --threshold (current: {args.threshold})")
        return

    print(f"Found {results['total_groups']} group(s) "
          f"({results['identities_before']} identities -> "
          f"{results['identities_after']} after grouping)")
    print()
    print("-" * 80)

    for i, group in enumerate(results["groups"], 1):
        print(f"\nGroup {i}: {group['size']} faces "
              f"(avg distance: {group['avg_distance']:.4f})")
        print(f"  Primary: {group['primary_name']} ({group['primary_id'][:8]}...)")
        for mid, mname in zip(group["member_ids"], group["member_names"]):
            print(f"  + Merge:  {mname} ({mid[:8]}...)")

    print()
    print("-" * 80)
    total_faces_in_groups = sum(g["size"] for g in results["groups"])
    print(f"\nSummary:")
    print(f"  Groups formed:       {results['total_groups']}")
    print(f"  Faces in groups:     {total_faces_in_groups}")
    print(f"  Identities removed:  {results['total_merged']}")
    print(f"  Identities before:   {results['identities_before']}")
    print(f"  Identities after:    {results['identities_after']}")

    if results["skipped_co_occurrence"] > 0:
        print(f"  Skipped (same photo): {results['skipped_co_occurrence']}")

    if args.dry_run:
        print()
        print("[DRY RUN] No changes made to identities.json.")
        print("Run with --execute to apply these merges.")
    else:
        # Save the merged registry
        registry.save(identities_path)
        print()
        print(f"Saved updated identities to {identities_path}")

        # Report merge outcomes
        successes = sum(1 for r in results["merge_results"] if r.get("success"))
        failures = len(results["merge_results"]) - successes
        if failures > 0:
            print(f"  Merges succeeded: {successes}")
            print(f"  Merges failed:    {failures}")
            for r in results["merge_results"]:
                if not r.get("success"):
                    print(f"    {r.get('source_id', '?')[:8]} -> "
                          f"{r.get('target_id', '?')[:8]}: {r.get('reason', 'unknown')}")


if __name__ == "__main__":
    main()
