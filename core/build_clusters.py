"""
Build identity clusters from PFE embeddings.

This script runs the full clustering pipeline:
1. Load PFE embeddings from data/embeddings.npy
2. Classify eras using CLIP
3. Cluster using MLS + temporal priors
4. Save cluster assignments to data/clusters.json

Run: python core/build_clusters.py
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np

from core.clustering import cluster_identities, format_match_range
from core.temporal import classify_era


def load_embeddings(embeddings_path: Path) -> list[dict]:
    """Load PFE embeddings from numpy file."""
    if not embeddings_path.exists():
        print(f"Error: Embeddings file not found: {embeddings_path}", file=sys.stderr)
        sys.exit(1)

    data = np.load(embeddings_path, allow_pickle=True)
    return list(data)


def add_era_estimates(faces: list[dict]) -> list[dict]:
    """Add era estimates to each face using CLIP classification."""
    print("Classifying eras...")

    for i, face in enumerate(faces):
        filepath = face.get("filepath")
        if not filepath or not Path(filepath).exists():
            print(f"  Warning: Image not found: {filepath}", file=sys.stderr)
            # Use default uncertain era
            from core.temporal import EraEstimate
            face["era"] = EraEstimate(
                era="1910-1930",
                probabilities={"1890-1910": 0.33, "1910-1930": 0.34, "1930-1950": 0.33},
                confidence=0.0,
            )
            continue

        # Load image and classify
        img = cv2.imread(filepath)
        if img is None:
            print(f"  Warning: Could not read: {filepath}", file=sys.stderr)
            from core.temporal import EraEstimate
            face["era"] = EraEstimate(
                era="1910-1930",
                probabilities={"1890-1910": 0.33, "1910-1930": 0.34, "1930-1950": 0.33},
                confidence=0.0,
            )
            continue

        # Convert BGR to RGB for CLIP
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        era = classify_era(img_rgb)
        face["era"] = era

        print(f"  [{i+1}/{len(faces)}] {face['filename']}: {era.era} (conf={era.confidence:.2f})")

    return faces


def build_clusters_json(clusters: list[dict]) -> list[dict]:
    """Convert clusters to JSON-serializable format."""
    result = []

    for cluster in clusters:
        cluster_data = {
            "cluster_id": cluster["cluster_id"],
            "match_range": format_match_range(cluster["match_range"]),
            "faces": [],
        }

        for face in cluster["faces"]:
            face_data = {
                "filename": face.get("filename", ""),
                "quality": float(face.get("quality", 0)),
                "det_score": float(face.get("det_score", 0)),
                "era": face["era"].era,
                "era_confidence": float(face["era"].confidence),
            }
            cluster_data["faces"].append(face_data)

        result.append(cluster_data)

    return result


def main():
    project_root = Path(__file__).resolve().parent.parent
    embeddings_path = project_root / "data" / "embeddings.npy"
    output_path = project_root / "data" / "clusters.json"

    print(f"Loading embeddings from: {embeddings_path}")
    faces = load_embeddings(embeddings_path)
    print(f"Loaded {len(faces)} faces")

    # Add era estimates
    faces = add_era_estimates(faces)

    # Cluster
    print("\nClustering identities...")
    clusters = cluster_identities(faces)
    print(f"Found {len(clusters)} identity clusters")

    # Convert to JSON
    clusters_json = build_clusters_json(clusters)

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(clusters_json, f, indent=2)
    print(f"\nSaved to: {output_path}")

    # Summary
    print("\nCluster summary:")
    for cluster in clusters_json:
        print(f"  Cluster {cluster['cluster_id']}: {len(cluster['faces'])} faces, "
              f"match range: {cluster['match_range']}")


if __name__ == "__main__":
    main()
