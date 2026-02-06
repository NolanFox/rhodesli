#!/usr/bin/env python3
"""Evaluate ML clustering accuracy against golden set.

Loads face embeddings, computes pairwise distances for golden set faces,
and reports precision/recall/F1 at various distance thresholds.

For each pair of faces in the golden set:
  - Same identity + distance < threshold = True Positive
  - Same identity + distance >= threshold = False Negative
  - Different identity + distance >= threshold = True Negative
  - Different identity + distance < threshold = False Positive

Also sweeps thresholds to find the optimal operating point.

This script is read-only. It does NOT modify any data.

Usage:
    python scripts/evaluate_golden_set.py
    python scripts/evaluate_golden_set.py --threshold 0.6
    python scripts/evaluate_golden_set.py --sweep
"""

import argparse
import json
import sys
from itertools import combinations
from pathlib import Path

# Defer numpy import inside functions for testability
# (per CLAUDE.md: deferred imports pattern)

# Add project root to path for core imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.config import MATCH_THRESHOLD_HIGH, MATCH_THRESHOLD_MEDIUM


def load_face_data(data_path: Path) -> dict:
    """Load face embeddings as face_id -> {mu, sigma_sq} dict.

    Mirrors the logic in app/main.py load_face_embeddings().
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

        # Use stored face_id if present (inbox format), otherwise generate
        face_id = entry.get("face_id") or generate_face_id(filename, face_index)

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


def generate_face_id(filename: str, face_index: int) -> str:
    """Generate a stable face ID from filename and index."""
    stem = Path(filename).stem
    return f"{stem}:face{face_index}"


def compute_distance(face_data: dict, face_id_a: str, face_id_b: str) -> float:
    """Compute Euclidean distance between two face embeddings (mu vectors).

    Uses the same metric as core/neighbors.py (Euclidean on mu vectors).
    """
    from scipy.spatial.distance import cdist

    mu_a = face_data[face_id_a]["mu"].reshape(1, -1)
    mu_b = face_data[face_id_b]["mu"].reshape(1, -1)

    return float(cdist(mu_a, mu_b, metric="euclidean")[0, 0])


def evaluate_at_threshold(
    pairs: list[dict], threshold: float
) -> dict:
    """Evaluate precision/recall/F1 at a given threshold.

    Args:
        pairs: List of dicts with 'distance' and 'same_identity' keys
        threshold: Distance threshold (below = match, above = no match)

    Returns:
        Dict with tp, fp, tn, fn, precision, recall, f1, accuracy
    """
    tp = fp = tn = fn = 0

    for pair in pairs:
        predicted_same = pair["distance"] < threshold
        actual_same = pair["same_identity"]

        if actual_same and predicted_same:
            tp += 1
        elif actual_same and not predicted_same:
            fn += 1
        elif not actual_same and predicted_same:
            fp += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    accuracy = (tp + tn) / len(pairs) if pairs else 0.0

    return {
        "threshold": threshold,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate ML clustering accuracy against golden set."
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Distance threshold to evaluate (default: uses calibrated thresholds)",
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="Sweep thresholds from 0.5 to 2.0 to find optimal",
    )
    parser.add_argument(
        "--golden-set",
        type=Path,
        default=None,
        help="Path to golden set file (default: data/golden_set.json)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Sample N random different-identity pairs (for large datasets)",
    )
    args = parser.parse_args()

    data_path = project_root / "data"
    golden_set_path = args.golden_set or (data_path / "golden_set.json")

    print("=" * 60)
    print("EVALUATE GOLDEN SET")
    print("=" * 60)

    # Load golden set
    if not golden_set_path.exists():
        print(f"ERROR: Golden set not found: {golden_set_path}")
        print("Run 'python scripts/build_golden_set.py --execute' first.")
        sys.exit(1)

    with open(golden_set_path) as f:
        golden_set = json.load(f)

    mappings = golden_set["mappings"]
    stats = golden_set["stats"]

    print(f"Golden set: {stats['total_mappings']} mappings, "
          f"{stats['unique_identities']} identities")
    print()

    # Load face data
    print("Loading face embeddings...")
    face_data = load_face_data(data_path)
    print(f"Loaded {len(face_data)} face embeddings")
    print()

    # Build face_id -> identity_id mapping
    face_to_identity = {}
    for mapping in mappings:
        face_to_identity[mapping["face_id"]] = mapping["identity_id"]

    # Filter to faces that have embeddings
    valid_faces = [fid for fid in face_to_identity if fid in face_data]
    missing_faces = [fid for fid in face_to_identity if fid not in face_data]

    if missing_faces:
        print(f"WARNING: {len(missing_faces)} faces in golden set have no embeddings:")
        for fid in missing_faces[:10]:
            print(f"  - {fid}")
        if len(missing_faces) > 10:
            print(f"  ... and {len(missing_faces) - 10} more")
        print()

    if len(valid_faces) < 2:
        print("ERROR: Need at least 2 faces with embeddings to evaluate.")
        sys.exit(1)

    print(f"Valid faces with embeddings: {len(valid_faces)}")

    # Compute all pairwise distances
    print("Computing pairwise distances...")
    pairs = []
    same_identity_count = 0
    diff_identity_count = 0

    for face_a, face_b in combinations(valid_faces, 2):
        distance = compute_distance(face_data, face_a, face_b)
        same_identity = face_to_identity[face_a] == face_to_identity[face_b]

        pairs.append({
            "face_a": face_a,
            "face_b": face_b,
            "distance": distance,
            "same_identity": same_identity,
        })

        if same_identity:
            same_identity_count += 1
        else:
            diff_identity_count += 1

    print(f"Total pairs: {len(pairs)}")
    print(f"  Same identity: {same_identity_count}")
    print(f"  Different identity: {diff_identity_count}")
    print()

    # If sampling requested for different-identity pairs (to reduce computation)
    if args.sample and diff_identity_count > args.sample:
        import random

        same_pairs = [p for p in pairs if p["same_identity"]]
        diff_pairs = [p for p in pairs if not p["same_identity"]]
        sampled_diff = random.sample(diff_pairs, args.sample)
        pairs = same_pairs + sampled_diff
        print(f"Sampled {args.sample} different-identity pairs "
              f"(kept all {len(same_pairs)} same-identity pairs)")
        print()

    # Distance statistics for same vs different identity pairs
    same_distances = [p["distance"] for p in pairs if p["same_identity"]]
    diff_distances = [p["distance"] for p in pairs if not p["same_identity"]]

    if same_distances:
        print("Same-identity distance stats:")
        print(f"  Min:    {min(same_distances):.4f}")
        print(f"  Max:    {max(same_distances):.4f}")
        print(f"  Mean:   {sum(same_distances)/len(same_distances):.4f}")
        sorted_same = sorted(same_distances)
        median_idx = len(sorted_same) // 2
        print(f"  Median: {sorted_same[median_idx]:.4f}")
        print()

    if diff_distances:
        print("Different-identity distance stats:")
        print(f"  Min:    {min(diff_distances):.4f}")
        print(f"  Max:    {max(diff_distances):.4f}")
        print(f"  Mean:   {sum(diff_distances)/len(diff_distances):.4f}")
        sorted_diff = sorted(diff_distances)
        median_idx = len(sorted_diff) // 2
        print(f"  Median: {sorted_diff[median_idx]:.4f}")
        print()

    # Evaluate at specified or default thresholds
    print("=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)

    if args.threshold:
        thresholds = [args.threshold]
    else:
        thresholds = [MATCH_THRESHOLD_HIGH, MATCH_THRESHOLD_MEDIUM]

    for threshold in thresholds:
        result = evaluate_at_threshold(pairs, threshold)
        print(f"\nThreshold: {threshold:.2f}")
        print(f"  Precision: {result['precision']:.4f}")
        print(f"  Recall:    {result['recall']:.4f}")
        print(f"  F1:        {result['f1']:.4f}")
        print(f"  Accuracy:  {result['accuracy']:.4f}")
        print(f"  TP={result['tp']}  FP={result['fp']}  "
              f"TN={result['tn']}  FN={result['fn']}")

    # Threshold sweep
    if args.sweep:
        import numpy as np

        print()
        print("=" * 60)
        print("THRESHOLD SWEEP")
        print("=" * 60)
        print(f"{'Threshold':>10}  {'Precision':>10}  {'Recall':>10}  "
              f"{'F1':>10}  {'Accuracy':>10}")
        print("-" * 60)

        best_f1 = 0.0
        best_threshold = 0.0

        for threshold in np.arange(0.50, 2.05, 0.05):
            result = evaluate_at_threshold(pairs, float(threshold))
            print(f"{threshold:>10.2f}  {result['precision']:>10.4f}  "
                  f"{result['recall']:>10.4f}  {result['f1']:>10.4f}  "
                  f"{result['accuracy']:>10.4f}")

            if result["f1"] > best_f1:
                best_f1 = result["f1"]
                best_threshold = threshold

        print()
        print(f"Optimal threshold (max F1): {best_threshold:.2f} "
              f"(F1={best_f1:.4f})")

    # Show misclassified pairs at the primary threshold
    primary_threshold = args.threshold or MATCH_THRESHOLD_MEDIUM
    print()
    print("=" * 60)
    print(f"MISCLASSIFIED PAIRS (threshold={primary_threshold:.2f})")
    print("=" * 60)

    # Build identity_id -> name lookup
    id_to_name = {}
    for mapping in mappings:
        id_to_name[mapping["identity_id"]] = mapping["identity_name"]

    false_positives = []
    false_negatives = []

    for pair in pairs:
        predicted_same = pair["distance"] < primary_threshold
        actual_same = pair["same_identity"]

        if actual_same and not predicted_same:
            false_negatives.append(pair)
        elif not actual_same and predicted_same:
            false_positives.append(pair)

    if false_negatives:
        false_negatives.sort(key=lambda p: p["distance"])
        print(f"\nFalse Negatives (same person, distance >= {primary_threshold:.2f}):")
        for pair in false_negatives[:20]:
            id_a = face_to_identity[pair["face_a"]]
            name = id_to_name.get(id_a, "Unknown")
            print(f"  {pair['face_a']} <-> {pair['face_b']}  "
                  f"dist={pair['distance']:.4f}  ({name})")
        if len(false_negatives) > 20:
            print(f"  ... and {len(false_negatives) - 20} more")
    else:
        print("\nNo false negatives (all same-identity pairs matched).")

    if false_positives:
        false_positives.sort(key=lambda p: p["distance"])
        print(f"\nFalse Positives (different person, distance < {primary_threshold:.2f}):")
        for pair in false_positives[:20]:
            id_a = face_to_identity[pair["face_a"]]
            id_b = face_to_identity[pair["face_b"]]
            name_a = id_to_name.get(id_a, "Unknown")
            name_b = id_to_name.get(id_b, "Unknown")
            print(f"  {pair['face_a']} <-> {pair['face_b']}  "
                  f"dist={pair['distance']:.4f}  ({name_a} vs {name_b})")
        if len(false_positives) > 20:
            print(f"  ... and {len(false_positives) - 20} more")
    else:
        print("\nNo false positives (all different-identity pairs separated).")


if __name__ == "__main__":
    main()
