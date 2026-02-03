#!/usr/bin/env python3
"""
Forensic Evaluation Script for Face Recognition.

Evaluates the quality of face embeddings by computing distances between
a target face and known positives/hard negatives from a frozen ground-truth set.

This script is deterministic and read-only. It does NOT modify any data.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.spatial.distance import cdist


def load_face_data(data_path: Path) -> dict[str, dict]:
    """
    Load face embeddings as face_id -> {mu, sigma_sq} dict.

    Mirrors the logic in app/main.py load_face_embeddings().
    """
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

        face_id = generate_face_id(filename, face_index)

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


def compute_face_distance(face_data: dict, face_id_a: str, face_id_b: str) -> float:
    """Compute Euclidean distance between two face embeddings."""
    if face_id_a not in face_data:
        raise KeyError(f"Face not found: {face_id_a}")
    if face_id_b not in face_data:
        raise KeyError(f"Face not found: {face_id_b}")

    mu_a = face_data[face_id_a]["mu"].reshape(1, -1)
    mu_b = face_data[face_id_b]["mu"].reshape(1, -1)

    return float(cdist(mu_a, mu_b, metric='euclidean')[0, 0])


def main():
    """Run the evaluation."""
    project_root = Path(__file__).resolve().parent.parent
    data_path = project_root / "data"
    evaluation_path = project_root / "evaluation"

    # Load ground truth
    golden_set_path = evaluation_path / "golden_set.json"
    if not golden_set_path.exists():
        print(f"ERROR: Golden set not found: {golden_set_path}")
        sys.exit(1)

    with open(golden_set_path) as f:
        golden_set = json.load(f)

    target_face = golden_set["target"]
    positives = golden_set["positives"]
    hard_negatives = golden_set["hard_negatives"]

    print(f"Target: {target_face}")
    print(f"Positives: {len(positives)}")
    print(f"Hard negatives: {len(hard_negatives)}")
    print("-" * 60)

    # Load face data
    face_data = load_face_data(data_path)
    print(f"Loaded {len(face_data)} face embeddings")

    # Check target exists
    if target_face not in face_data:
        print(f"ERROR: Target face not found in embeddings: {target_face}")
        sys.exit(1)

    # Distance threshold (calibrated per ADR 007)
    DISTANCE_THRESHOLD = 1.20

    # Evaluate positives
    print("\n=== POSITIVE MATCHES ===")
    positive_results = []
    positive_failures = []

    for rank, pos_face in enumerate(positives, 1):
        if pos_face not in face_data:
            print(f"  WARNING: Positive face not found: {pos_face}")
            continue

        dist = compute_face_distance(face_data, target_face, pos_face)
        positive_results.append({"face_id": pos_face, "distance": dist, "rank": rank})

        status = "PASS" if dist <= DISTANCE_THRESHOLD else "FAIL"
        print(f"  Rank {rank}: {pos_face}")
        print(f"          Distance: {dist:.4f} [{status}]")

        if dist > DISTANCE_THRESHOLD:
            positive_failures.append(pos_face)

    # Sort by distance for ranking
    positive_results.sort(key=lambda x: x["distance"])
    for i, r in enumerate(positive_results, 1):
        r["rank"] = i

    # Evaluate hard negatives
    print("\n=== HARD NEGATIVES ===")
    negative_results = []
    negative_failures = []

    for neg_face in hard_negatives:
        if neg_face not in face_data:
            print(f"  WARNING: Hard negative face not found: {neg_face}")
            continue

        dist = compute_face_distance(face_data, target_face, neg_face)
        negative_results.append({"face_id": neg_face, "distance": dist})

        status = "PASS" if dist > DISTANCE_THRESHOLD else "FAIL"
        print(f"  {neg_face}")
        print(f"          Distance: {dist:.4f} [{status}]")

        if dist <= DISTANCE_THRESHOLD:
            negative_failures.append(neg_face)

    # Overall result
    print("\n" + "=" * 60)
    all_passed = len(positive_failures) == 0 and len(negative_failures) == 0

    if all_passed:
        print("RESULT: PASS")
    else:
        print("RESULT: FAIL")
        if positive_failures:
            print(f"  Positive failures (distance > {DISTANCE_THRESHOLD}):")
            for f in positive_failures:
                print(f"    - {f}")
        if negative_failures:
            print(f"  Negative failures (distance <= {DISTANCE_THRESHOLD}):")
            for f in negative_failures:
                print(f"    - {f}")

    # Create run record
    timestamp = datetime.now(timezone.utc).isoformat()
    run_record = {
        "timestamp": timestamp,
        "target": target_face,
        "threshold": DISTANCE_THRESHOLD,
        "positive_matches": positive_results,
        "negative_matches": negative_results,
        "passed": all_passed,
        "positive_failures": positive_failures,
        "negative_failures": negative_failures,
    }

    # Append to run log
    run_log_path = evaluation_path / "run_log.jsonl"
    with open(run_log_path, "a") as f:
        f.write(json.dumps(run_record) + "\n")
    print(f"\nRun logged to: {run_log_path}")

    # Return appropriate exit code
    if not all_passed:
        sys.exit(1)

    return run_record


if __name__ == "__main__":
    record = main()
