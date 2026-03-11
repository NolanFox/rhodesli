#!/usr/bin/env python3
"""Evaluate MLS vs Euclidean distance for face similarity matching.

Resolves AD-027: MLS vs Euclidean — Open Experiment.

Uses confirmed identities (anchor_ids with 2+ faces) as ground truth:
- Same-identity pairs: all face pairs within the same confirmed identity
- Cross-identity pairs: random face pairs from different confirmed identities

Computes both Euclidean distance (current production metric) and MLS
(Mutual Likelihood Score from core/pfe.py), then compares:
- ROC AUC
- Precision at recall=0.95
- Optimal threshold for each metric (max F1)
- Distribution statistics

This script is read-only. It does NOT modify any data or production code.

Usage:
    python scripts/evaluate_mls_vs_euclidean.py
    python scripts/evaluate_mls_vs_euclidean.py --cross-pairs 500
    python scripts/evaluate_mls_vs_euclidean.py --seed 42
"""

import argparse
import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np

# Add project root to path for core imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
from core.embeddings_io import generate_face_id, load_face_data as shared_load_face_data
from core.identity_scoring import extract_face_ids as shared_extract_face_ids


def load_face_data(data_path: Path) -> dict:
    """Load face embeddings as face_id -> {mu, sigma_sq} dict.

    Mirrors the logic in app/main.py load_face_embeddings().
    """
    return shared_load_face_data(data_path / "embeddings.npy")


def load_confirmed_identities(data_path: Path) -> list[dict]:
    """Load confirmed identities with 2+ confirmed faces.

    Returns list of dicts with keys: identity_id, name, anchor_ids.
    Only includes identities with state=CONFIRMED, non-merged, and 2+ faces
    across both anchors and confirmed candidates.
    """
    identities_path = data_path / "identities.json"
    if not identities_path.exists():
        raise FileNotFoundError(f"Identities not found: {identities_path}")

    with open(identities_path) as f:
        data = json.load(f)

    confirmed = []
    for iid, ident in data["identities"].items():
        if ident.get("state") != "CONFIRMED":
            continue
        if ident.get("merged_into"):
            continue

        anchors = shared_extract_face_ids(ident)

        if len(anchors) >= 2:
            confirmed.append({
                "identity_id": iid,
                "name": ident.get("name", "Unknown"),
                "anchor_ids": anchors,
            })

    return confirmed


def build_pairs(
    confirmed_identities: list[dict],
    face_data: dict,
    cross_pair_count: int = 500,
    seed: int = 42,
) -> tuple[list[dict], list[dict]]:
    """Build same-identity and cross-identity face pairs.

    Args:
        confirmed_identities: List of confirmed identity dicts with anchor_ids.
        face_data: Dict mapping face_id -> {mu, sigma_sq}.
        cross_pair_count: Number of random cross-identity pairs to generate.
        seed: Random seed for reproducibility.

    Returns:
        (same_pairs, cross_pairs) where each pair is a dict with
        face_a, face_b, identity_a, identity_b keys.
    """
    rng = np.random.default_rng(seed)

    # Filter to faces that have embeddings
    valid_identities = []
    for ident in confirmed_identities:
        valid_faces = [fid for fid in ident["anchor_ids"] if fid in face_data]
        if len(valid_faces) >= 2:
            valid_identities.append({
                **ident,
                "valid_faces": valid_faces,
            })

    # Same-identity pairs: all combinations within each identity
    same_pairs = []
    for ident in valid_identities:
        for fa, fb in combinations(ident["valid_faces"], 2):
            same_pairs.append({
                "face_a": fa,
                "face_b": fb,
                "identity_a": ident["identity_id"],
                "identity_b": ident["identity_id"],
                "name_a": ident["name"],
                "name_b": ident["name"],
            })

    # Cross-identity pairs: random pairs from different identities
    cross_pairs = []
    if len(valid_identities) < 2:
        return same_pairs, cross_pairs

    # Build a flat list of (face_id, identity_id, name) for sampling
    all_faces = []
    for ident in valid_identities:
        for fid in ident["valid_faces"]:
            all_faces.append((fid, ident["identity_id"], ident["name"]))

    attempts = 0
    max_attempts = cross_pair_count * 10
    seen = set()

    while len(cross_pairs) < cross_pair_count and attempts < max_attempts:
        attempts += 1
        i, j = rng.integers(0, len(all_faces), size=2)
        if i == j:
            continue
        fa, ida, na = all_faces[i]
        fb, idb, nb = all_faces[j]
        if ida == idb:
            continue
        pair_key = tuple(sorted([fa, fb]))
        if pair_key in seen:
            continue
        seen.add(pair_key)
        cross_pairs.append({
            "face_a": fa,
            "face_b": fb,
            "identity_a": ida,
            "identity_b": idb,
            "name_a": na,
            "name_b": nb,
        })

    return same_pairs, cross_pairs


def compute_euclidean(mu_a: np.ndarray, mu_b: np.ndarray) -> float:
    """Compute Euclidean distance between two mu vectors."""
    return float(np.sqrt(np.sum((mu_a - mu_b) ** 2)))


def compute_mls(
    mu_a: np.ndarray,
    sigma_sq_a: np.ndarray,
    mu_b: np.ndarray,
    sigma_sq_b: np.ndarray,
) -> float:
    """Compute MLS using core/pfe.py logic (imported at call time)."""
    from core.pfe import mutual_likelihood_score

    return mutual_likelihood_score(mu_a, sigma_sq_a, mu_b, sigma_sq_b)


def score_pairs(
    pairs: list[dict], face_data: dict
) -> list[dict]:
    """Compute both Euclidean and MLS for each pair.

    Returns list of dicts with added 'euclidean' and 'mls' keys.
    """
    scored = []
    for pair in pairs:
        fa = face_data[pair["face_a"]]
        fb = face_data[pair["face_b"]]

        euclidean = compute_euclidean(fa["mu"], fb["mu"])
        mls = compute_mls(fa["mu"], fa["sigma_sq"], fb["mu"], fb["sigma_sq"])

        scored.append({
            **pair,
            "euclidean": euclidean,
            "mls": mls,
        })

    return scored


def compute_auc(labels: np.ndarray, scores: np.ndarray) -> float:
    """Compute ROC AUC using the trapezoidal rule.

    Args:
        labels: Binary labels (1=same identity, 0=different).
        scores: Similarity scores (higher = more likely same person).

    Returns:
        AUC value in [0, 1].
    """
    # Sort by descending score
    sorted_indices = np.argsort(-scores)
    sorted_labels = labels[sorted_indices]

    # Count positives and negatives
    n_pos = int(np.sum(labels))
    n_neg = len(labels) - n_pos

    if n_pos == 0 or n_neg == 0:
        return 0.5  # undefined, return chance level

    # Compute TPR and FPR at each threshold
    tpr_points = [0.0]
    fpr_points = [0.0]
    tp = 0
    fp = 0

    for label in sorted_labels:
        if label == 1:
            tp += 1
        else:
            fp += 1
        tpr_points.append(tp / n_pos)
        fpr_points.append(fp / n_neg)

    # Trapezoidal integration
    auc = 0.0
    for i in range(1, len(fpr_points)):
        auc += (fpr_points[i] - fpr_points[i - 1]) * (
            tpr_points[i] + tpr_points[i - 1]
        ) / 2.0

    return auc


def compute_precision_at_recall(
    labels: np.ndarray, scores: np.ndarray, target_recall: float = 0.95
) -> float:
    """Compute precision at a target recall level.

    Args:
        labels: Binary labels (1=same, 0=different).
        scores: Similarity scores (higher = more likely same).
        target_recall: Target recall level.

    Returns:
        Precision at the given recall, or 0.0 if unreachable.
    """
    sorted_indices = np.argsort(-scores)
    sorted_labels = labels[sorted_indices]

    n_pos = int(np.sum(labels))
    if n_pos == 0:
        return 0.0

    tp = 0
    fp = 0

    for label in sorted_labels:
        if label == 1:
            tp += 1
        else:
            fp += 1
        recall = tp / n_pos
        if recall >= target_recall:
            precision = tp / (tp + fp)
            return precision

    return 0.0


def find_optimal_threshold(
    labels: np.ndarray, scores: np.ndarray, n_steps: int = 200
) -> tuple[float, float]:
    """Find the threshold that maximizes F1.

    Args:
        labels: Binary labels.
        scores: Similarity scores (higher = more likely same).
        n_steps: Number of threshold values to evaluate.

    Returns:
        (best_threshold, best_f1).
    """
    min_score = float(np.min(scores))
    max_score = float(np.max(scores))
    thresholds = np.linspace(min_score, max_score, n_steps)

    best_f1 = 0.0
    best_threshold = min_score

    for threshold in thresholds:
        predicted = (scores >= threshold).astype(int)
        tp = int(np.sum((predicted == 1) & (labels == 1)))
        fp = int(np.sum((predicted == 1) & (labels == 0)))
        fn = int(np.sum((predicted == 0) & (labels == 1)))

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        if f1 > best_f1:
            best_f1 = f1
            best_threshold = float(threshold)

    return best_threshold, best_f1


def evaluate_metric(
    same_scores: np.ndarray,
    cross_scores: np.ndarray,
    metric_name: str,
    higher_is_same: bool,
) -> dict:
    """Evaluate a single metric (Euclidean or MLS).

    For Euclidean: lower distance = more similar (invert for AUC).
    For MLS: higher score = more similar (use directly for AUC).

    Args:
        same_scores: Metric values for same-identity pairs.
        cross_scores: Metric values for cross-identity pairs.
        metric_name: Name for display.
        higher_is_same: If True, higher score means more similar (MLS).
                        If False, lower score means more similar (Euclidean).

    Returns:
        Dict with auc, precision_at_recall_95, optimal_threshold, optimal_f1,
        and distribution stats.
    """
    labels = np.concatenate([
        np.ones(len(same_scores)),
        np.zeros(len(cross_scores)),
    ])
    raw_scores = np.concatenate([same_scores, cross_scores])

    # For AUC, scores must be "higher = more likely same person"
    if higher_is_same:
        similarity_scores = raw_scores
    else:
        # Negate distance so higher = more similar
        similarity_scores = -raw_scores

    auc = compute_auc(labels, similarity_scores)
    precision_at_95 = compute_precision_at_recall(labels, similarity_scores, 0.95)
    optimal_threshold, optimal_f1 = find_optimal_threshold(labels, similarity_scores)

    return {
        "metric": metric_name,
        "auc": round(auc, 4),
        "precision_at_recall_95": round(precision_at_95, 4),
        "optimal_threshold": round(optimal_threshold, 4),
        "optimal_f1": round(optimal_f1, 4),
        "same_mean": round(float(np.mean(same_scores)), 4),
        "same_std": round(float(np.std(same_scores)), 4),
        "same_min": round(float(np.min(same_scores)), 4),
        "same_max": round(float(np.max(same_scores)), 4),
        "cross_mean": round(float(np.mean(cross_scores)), 4),
        "cross_std": round(float(np.std(cross_scores)), 4),
        "cross_min": round(float(np.min(cross_scores)), 4),
        "cross_max": round(float(np.max(cross_scores)), 4),
    }


def print_results(euclidean_results: dict, mls_results: dict, n_same: int, n_cross: int) -> None:
    """Print formatted comparison results to stdout."""
    print("=" * 70)
    print("MLS vs EUCLIDEAN EVALUATION — AD-027 Resolution")
    print("=" * 70)
    print()

    print(f"Dataset: {n_same} same-identity pairs, {n_cross} cross-identity pairs")
    print(f"Sigma type: ALL scalar/uniform (not per-dimension)")
    print()

    # Comparison table
    print("-" * 70)
    print(f"{'Metric':<30} {'Euclidean':>18} {'MLS':>18}")
    print("-" * 70)
    print(f"{'ROC AUC':<30} {euclidean_results['auc']:>18.4f} {mls_results['auc']:>18.4f}")
    print(f"{'Precision @ Recall=0.95':<30} {euclidean_results['precision_at_recall_95']:>18.4f} {mls_results['precision_at_recall_95']:>18.4f}")
    print(f"{'Optimal F1':<30} {euclidean_results['optimal_f1']:>18.4f} {mls_results['optimal_f1']:>18.4f}")
    print(f"{'Optimal Threshold':<30} {euclidean_results['optimal_threshold']:>18.4f} {mls_results['optimal_threshold']:>18.4f}")
    print("-" * 70)
    print()

    # Distribution stats
    for label, results in [("Euclidean Distance", euclidean_results), ("MLS Score", mls_results)]:
        print(f"{label}:")
        print(f"  Same-identity:  mean={results['same_mean']:.4f}  "
              f"std={results['same_std']:.4f}  "
              f"range=[{results['same_min']:.4f}, {results['same_max']:.4f}]")
        print(f"  Cross-identity: mean={results['cross_mean']:.4f}  "
              f"std={results['cross_std']:.4f}  "
              f"range=[{results['cross_min']:.4f}, {results['cross_max']:.4f}]")
        print()

    # Separation analysis
    # For Euclidean: separation = cross_mean - same_mean (want positive, larger is better)
    euc_sep = euclidean_results["cross_mean"] - euclidean_results["same_mean"]
    euc_pooled_std = np.sqrt(
        (euclidean_results["same_std"] ** 2 + euclidean_results["cross_std"] ** 2) / 2
    )
    euc_d_prime = euc_sep / euc_pooled_std if euc_pooled_std > 0 else 0.0

    # For MLS: separation = same_mean - cross_mean (want positive, larger is better)
    mls_sep = mls_results["same_mean"] - mls_results["cross_mean"]
    mls_pooled_std = np.sqrt(
        (mls_results["same_std"] ** 2 + mls_results["cross_std"] ** 2) / 2
    )
    mls_d_prime = mls_sep / mls_pooled_std if mls_pooled_std > 0 else 0.0

    print("Separation (d'):")
    print(f"  Euclidean: {euc_d_prime:.4f}")
    print(f"  MLS:       {mls_d_prime:.4f}")
    print()

    # Winner
    auc_diff = mls_results["auc"] - euclidean_results["auc"]
    print("=" * 70)
    if abs(auc_diff) < 0.005:
        print(f"VERDICT: NEGLIGIBLE DIFFERENCE (AUC delta = {auc_diff:+.4f})")
        print("MLS provides no meaningful improvement over Euclidean for this dataset.")
        print("Recommendation: Keep Euclidean (simpler, no sigma_sq dependency).")
    elif auc_diff > 0:
        print(f"VERDICT: MLS WINS (AUC delta = {auc_diff:+.4f})")
        print("MLS provides meaningful improvement. Consider switching production metric.")
    else:
        print(f"VERDICT: EUCLIDEAN WINS (AUC delta = {auc_diff:+.4f})")
        print("Euclidean outperforms MLS. Keep current production metric.")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate MLS vs Euclidean for face similarity (AD-027)."
    )
    parser.add_argument(
        "--cross-pairs",
        type=int,
        default=500,
        help="Number of random cross-identity pairs (default: 500)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--data-path",
        type=Path,
        default=None,
        help="Path to data directory (default: data/)",
    )
    args = parser.parse_args()

    data_path = args.data_path or (project_root / "data")

    # Load data
    print("Loading face embeddings...")
    face_data = load_face_data(data_path)
    print(f"Loaded {len(face_data)} face embeddings")

    print("Loading confirmed identities...")
    confirmed = load_confirmed_identities(data_path)
    print(f"Found {len(confirmed)} confirmed identities with 2+ anchors:")
    for ident in confirmed:
        n_valid = sum(1 for fid in ident["anchor_ids"] if fid in face_data)
        print(f"  {ident['name']}: {n_valid}/{len(ident['anchor_ids'])} faces with embeddings")
    print()

    # Build pairs
    print(f"Building pairs (cross-pairs={args.cross_pairs}, seed={args.seed})...")
    same_pairs, cross_pairs = build_pairs(
        confirmed, face_data, cross_pair_count=args.cross_pairs, seed=args.seed
    )
    print(f"Same-identity pairs: {len(same_pairs)}")
    print(f"Cross-identity pairs: {len(cross_pairs)}")
    print()

    if len(same_pairs) == 0:
        print("ERROR: No same-identity pairs found. Need confirmed identities with 2+ faces.")
        sys.exit(1)
    if len(cross_pairs) == 0:
        print("ERROR: No cross-identity pairs found. Need 2+ confirmed identities.")
        sys.exit(1)

    # Score all pairs
    print("Computing Euclidean distances and MLS scores...")
    scored_same = score_pairs(same_pairs, face_data)
    scored_cross = score_pairs(cross_pairs, face_data)
    print()

    # Extract arrays
    same_euclidean = np.array([p["euclidean"] for p in scored_same])
    same_mls = np.array([p["mls"] for p in scored_same])
    cross_euclidean = np.array([p["euclidean"] for p in scored_cross])
    cross_mls = np.array([p["mls"] for p in scored_cross])

    # Evaluate both metrics
    euclidean_results = evaluate_metric(
        same_euclidean, cross_euclidean, "Euclidean", higher_is_same=False
    )
    mls_results = evaluate_metric(
        same_mls, cross_mls, "MLS", higher_is_same=True
    )

    # Print comparison
    print_results(euclidean_results, mls_results, len(same_pairs), len(cross_pairs))

    # Return results for programmatic use
    return {
        "euclidean": euclidean_results,
        "mls": mls_results,
        "n_same_pairs": len(same_pairs),
        "n_cross_pairs": len(cross_pairs),
        "n_confirmed_identities": len(confirmed),
        "seed": args.seed,
    }


if __name__ == "__main__":
    results = main()
