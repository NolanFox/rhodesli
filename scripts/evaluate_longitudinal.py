#!/usr/bin/env python3
"""Build and evaluate the Phase 0 longitudinal matching baseline."""

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from scripts.build_golden_set import build_golden_set
from scripts.evaluate_golden_set import compute_distance, evaluate_at_threshold, load_face_data
from scripts.evaluate_mls_vs_euclidean import (
    build_pairs,
    compute_auc,
    compute_precision_at_recall,
    find_optimal_threshold,
    load_confirmed_identities,
    score_pairs,
)


def atomic_write_json(path: Path, payload: dict) -> None:
    """Write JSON atomically to avoid partial artifacts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def compute_gini(values: list[int]) -> float:
    """Compute Gini coefficient for positive-pair concentration reporting."""
    if not values:
        return 0.0
    arr = np.sort(np.asarray(values, dtype=np.float64))
    if np.all(arr == 0):
        return 0.0
    n = arr.size
    index = np.arange(1, n + 1)
    return float((2 * np.sum(index * arr) / (n * np.sum(arr))) - (n + 1) / n)


def compute_identity_volume_stats(mappings: list[dict]) -> dict:
    """Summarize dominant and tail identity concentration in the golden set."""
    face_counts = Counter(mapping["identity_id"] for mapping in mappings)
    dominant = face_counts.most_common(3)
    tail_ids = sorted(identity_id for identity_id, count in face_counts.items() if count < 5)
    pair_counts = {
        identity_id: (count * (count - 1)) // 2
        for identity_id, count in face_counts.items()
        if count >= 2
    }
    return {
        "identity_face_counts": dict(face_counts),
        "dominant_identity_ids": [identity_id for identity_id, _count in dominant],
        "dominant_identities": [
            {"identity_id": identity_id, "face_count": count}
            for identity_id, count in dominant
        ],
        "tail_identity_ids": tail_ids,
        "tail_identity_count": len(tail_ids),
        "positive_pair_gini": round(compute_gini(list(pair_counts.values())), 4),
    }


def build_pair_records(golden_set: dict, face_data: dict) -> tuple[list[dict], dict]:
    """Build pair records plus slice metadata from a golden-set mapping list."""
    mappings = golden_set["mappings"]
    volume_stats = compute_identity_volume_stats(mappings)
    face_to_identity = {mapping["face_id"]: mapping["identity_id"] for mapping in mappings}
    valid_faces = [face_id for face_id in face_to_identity if face_id in face_data]
    missing_faces = sorted(face_id for face_id in face_to_identity if face_id not in face_data)
    dominant_ids = set(volume_stats["dominant_identity_ids"])
    tail_ids = set(volume_stats["tail_identity_ids"])

    pairs = []
    for face_a, face_b in combinations(valid_faces, 2):
        identity_a = face_to_identity[face_a]
        identity_b = face_to_identity[face_b]
        same_identity = identity_a == identity_b
        positive_slice = None
        if same_identity:
            if identity_a in dominant_ids:
                positive_slice = "dominant"
            elif identity_a in tail_ids:
                positive_slice = "tail"
            else:
                positive_slice = "other"

        pairs.append(
            {
                "face_a": face_a,
                "face_b": face_b,
                "distance": compute_distance(face_data, face_a, face_b),
                "same_identity": same_identity,
                "positive_slice": positive_slice,
            }
        )

    metadata = {
        **volume_stats,
        "valid_face_count": len(valid_faces),
        "missing_faces": missing_faces,
        "missing_face_count": len(missing_faces),
    }
    return pairs, metadata


def recall_at_threshold(pairs: list[dict], threshold: float, *, positive_slice: str | None = None) -> dict:
    """Compute recall on the requested same-identity slice."""
    positives = [pair for pair in pairs if pair["same_identity"]]
    if positive_slice is not None:
        positives = [pair for pair in positives if pair["positive_slice"] == positive_slice]

    total = len(positives)
    if total == 0:
        return {"pair_count": 0, "recall": None}

    matched = sum(1 for pair in positives if pair["distance"] < threshold)
    return {
        "pair_count": total,
        "recall": round(matched / total, 4),
    }


def build_mls_comparison(data_path: Path, face_data: dict, cross_pairs: int, seed: int) -> dict:
    """Compute the lightweight MLS-vs-Euclidean comparison used in Phase 0."""
    confirmed = load_confirmed_identities(data_path)
    same_pairs, cross_pairs_built = build_pairs(
        confirmed,
        face_data,
        cross_pair_count=cross_pairs,
        seed=seed,
    )
    same_scored = score_pairs(same_pairs, face_data)
    cross_scored = score_pairs(cross_pairs_built, face_data)

    if not same_scored or not cross_scored:
        return {
            "same_pairs": len(same_scored),
            "cross_pairs": len(cross_scored),
            "euclidean_auc": None,
            "mls_auc": None,
            "euclidean_precision_at_recall_0_95": None,
            "mls_precision_at_recall_0_95": None,
            "euclidean_optimal_f1": None,
            "mls_optimal_f1": None,
        }

    labels = np.array([1] * len(same_scored) + [0] * len(cross_scored))
    euclidean_scores = np.array([-pair["euclidean"] for pair in same_scored + cross_scored])
    mls_scores = np.array([pair["mls"] for pair in same_scored + cross_scored])

    return {
        "same_pairs": len(same_scored),
        "cross_pairs": len(cross_scored),
        "euclidean_auc": round(float(compute_auc(labels, euclidean_scores)), 4),
        "mls_auc": round(float(compute_auc(labels, mls_scores)), 4),
        "euclidean_precision_at_recall_0_95": round(
            float(compute_precision_at_recall(labels, euclidean_scores, 0.95)), 4
        ),
        "mls_precision_at_recall_0_95": round(
            float(compute_precision_at_recall(labels, mls_scores, 0.95)), 4
        ),
        "euclidean_optimal_f1": round(float(find_optimal_threshold(labels, euclidean_scores)[1]), 4),
        "mls_optimal_f1": round(float(find_optimal_threshold(labels, mls_scores)[1]), 4),
    }


def generate_phase0_baseline(
    data_path: Path,
    *,
    threshold: float = 1.196,
    cross_pairs: int = 200,
    seed: int = 42,
    golden_set: dict | None = None,
) -> tuple[dict, dict]:
    """Generate the Phase 0 baseline report and the rebuilt Golden Set V2."""
    rebuilt_golden_set = golden_set or build_golden_set(data_path)
    face_data = load_face_data(data_path)
    pair_records, pair_metadata = build_pair_records(rebuilt_golden_set, face_data)

    report = {
        "threshold": threshold,
        "golden_set_stats": rebuilt_golden_set["stats"],
        "pair_metadata": {
            "valid_face_count": pair_metadata["valid_face_count"],
            "missing_face_count": pair_metadata["missing_face_count"],
            "dominant_identities": pair_metadata["dominant_identities"],
            "tail_identity_count": pair_metadata["tail_identity_count"],
            "positive_pair_gini": pair_metadata["positive_pair_gini"],
        },
        "threshold_metrics": evaluate_at_threshold(pair_records, threshold),
        "slice_metrics": {
            "overall_positive_pairs": recall_at_threshold(pair_records, threshold),
            "dominant_positive_pairs": recall_at_threshold(pair_records, threshold, positive_slice="dominant"),
            "tail_positive_pairs": recall_at_threshold(pair_records, threshold, positive_slice="tail"),
        },
        "mls_vs_euclidean": build_mls_comparison(data_path, face_data, cross_pairs, seed),
    }
    return report, rebuilt_golden_set


def main():
    parser = argparse.ArgumentParser(description="Build the Phase 0 longitudinal baseline.")
    parser.add_argument("--threshold", type=float, default=1.196, help="Euclidean threshold for baseline metrics.")
    parser.add_argument("--cross-pairs", type=int, default=200, help="Cross-identity pairs for MLS comparison.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for MLS comparison.")
    parser.add_argument(
        "--golden-set-output",
        type=Path,
        default=project_root / "evaluation" / "golden_set_v2.json",
        help="Where to write the rebuilt Golden Set V2.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "evaluation" / "baselines" / "longitudinal_phase0_baseline.json",
        help="Where to write the baseline report JSON.",
    )
    parser.add_argument(
        "--write-golden-set",
        action="store_true",
        help="Write the rebuilt Golden Set V2 to --golden-set-output.",
    )
    args = parser.parse_args()

    data_path = project_root / "data"
    report, rebuilt_golden_set = generate_phase0_baseline(
        data_path,
        threshold=args.threshold,
        cross_pairs=args.cross_pairs,
        seed=args.seed,
    )

    if args.write_golden_set:
        atomic_write_json(args.golden_set_output, rebuilt_golden_set)

    atomic_write_json(args.output, report)

    print("=" * 60)
    print("LONGITUDINAL PHASE 0 BASELINE")
    print("=" * 60)
    print(f"Golden set stats: {report['golden_set_stats']}")
    print(f"Threshold metrics @ {args.threshold:.3f}: {report['threshold_metrics']}")
    print(f"Slice metrics: {report['slice_metrics']}")
    print(f"MLS vs Euclidean: {report['mls_vs_euclidean']}")
    if args.write_golden_set:
        print(f"Wrote rebuilt golden set: {args.golden_set_output}")
    print(f"Wrote baseline report: {args.output}")

    return report


if __name__ == "__main__":
    main()
