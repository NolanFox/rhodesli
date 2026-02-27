"""Extract confirmed/rejected pairs for similarity calibration.

Loads confirmed identities + face embeddings, generates positive pairs
(faces merged into same identity) and negative pairs (cross-identity),
computes pair features, and saves to JSON.

Usage:
    python -m rhodesli_ml.scripts.extract_pairs
    python -m rhodesli_ml.scripts.extract_pairs --data-dir data/
"""

import argparse
import json
from pathlib import Path

import numpy as np

from rhodesli_ml.calibration.data import (
    generate_pairs,
    load_confirmed_identities,
    load_face_embeddings,
    split_identities,
)


def extract_and_save(data_dir: Path, output_path: Path, seed: int = 42):
    """Extract training pairs and save to JSON with stats."""
    identities = load_confirmed_identities(data_dir)
    face_embeddings = load_face_embeddings(data_dir)

    print(f"Confirmed identities: {len(identities)}")
    multi = [i for i in identities if len([f for f in i['face_ids'] if f in face_embeddings]) >= 2]
    print(f"Multi-face identities: {len(multi)}")

    train_ids, eval_ids = split_identities(identities, face_embeddings, seed=seed)
    print(f"Train identities: {len(train_ids)}, Eval identities: {len(eval_ids)}")

    train_pairs = generate_pairs(train_ids, face_embeddings, neg_ratio=3, seed=seed)
    eval_pairs = generate_pairs(eval_ids, face_embeddings, neg_ratio=3, seed=seed + 1)

    # Compute distance stats
    def pair_stats(pairs, label_name):
        positives = [(a, b) for a, b, l in pairs if l == 1.0]
        negatives = [(a, b) for a, b, l in pairs if l == 0.0]
        pos_dists = [np.linalg.norm(a - b) for a, b in positives]
        neg_dists = [np.linalg.norm(a - b) for a, b in negatives]
        return {
            "total": len(pairs),
            "positives": len(positives),
            "negatives": len(negatives),
            "pos_dist_mean": round(float(np.mean(pos_dists)), 4) if pos_dists else 0,
            "pos_dist_std": round(float(np.std(pos_dists)), 4) if pos_dists else 0,
            "neg_dist_mean": round(float(np.mean(neg_dists)), 4) if neg_dists else 0,
            "neg_dist_std": round(float(np.std(neg_dists)), 4) if neg_dists else 0,
        }

    train_stats = pair_stats(train_pairs, "train")
    eval_stats = pair_stats(eval_pairs, "eval")

    # Save pairs as feature vectors (not raw embeddings — too large)
    def pairs_to_features(pairs):
        features = []
        for emb_a, emb_b, label in pairs:
            dist = float(np.linalg.norm(emb_a - emb_b))
            cosine_sim = float(np.dot(emb_a, emb_b) / (np.linalg.norm(emb_a) * np.linalg.norm(emb_b) + 1e-8))
            features.append({
                "distance": round(dist, 6),
                "cosine_similarity": round(cosine_sim, 6),
                "label": label,
            })
        return features

    output = {
        "metadata": {
            "confirmed_identities": len(identities),
            "multi_face_identities": len(multi),
            "total_embeddings": len(face_embeddings),
            "seed": seed,
        },
        "train": {
            "stats": train_stats,
            "pairs": pairs_to_features(train_pairs),
        },
        "eval": {
            "stats": eval_stats,
            "pairs": pairs_to_features(eval_pairs),
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved to {output_path}")
    print(f"\nTrain: {train_stats}")
    print(f"Eval:  {eval_stats}")

    return output


def main():
    parser = argparse.ArgumentParser(description="Extract training pairs for calibration")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("rhodesli_ml/data/training_pairs.json"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    extract_and_save(args.data_dir, args.output, args.seed)


if __name__ == "__main__":
    main()
