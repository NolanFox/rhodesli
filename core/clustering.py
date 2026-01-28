"""
Identity Clustering with MLS and Temporal Priors.

Clusters face embeddings into identity groups using Mutual Likelihood Score
and era-based temporal penalties. See docs/adr_003_identity_clustering.md.

Key features:
- Agglomerative clustering with complete linkage
- Deterministic results (stable across re-runs)
- Match probability ranges for each cluster
"""

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

from core.temporal import mls_with_temporal


# MLS drop required to consider faces as different identities
# This is subtracted from the reference MLS (identical faces with same σ²)
# Cross-era penalty is ~180, so drop of 150 separates cross-era matches
MLS_DROP_THRESHOLD = 150


def mls_to_distance(mls: float) -> float:
    """
    Convert MLS score to distance metric for clustering.

    Higher MLS (more similar) → lower distance.
    We use negative MLS directly (distance = -mls).

    Args:
        mls: Mutual Likelihood Score

    Returns:
        Distance (can be negative for very similar faces)
    """
    return -mls


def mls_to_probability(mls: float) -> float:
    """
    Convert MLS to approximate match probability in [0, 1].

    Uses calibrated sigmoid:
    - MLS=0 → 50%
    - MLS=-500 → ~1%
    - MLS=500 → ~99%

    Args:
        mls: Mutual Likelihood Score

    Returns:
        Probability in [0, 1]
    """
    return 1 / (1 + np.exp(-mls / 100))


def compute_match_range(faces: list[dict]) -> tuple[float, float] | None:
    """
    Compute match probability range for all pairs in a cluster.

    Args:
        faces: List of face dicts with mu, sigma_sq, era

    Returns:
        (min_probability, max_probability) or None if < 2 faces
    """
    if len(faces) < 2:
        return None

    scores = []
    for i, f1 in enumerate(faces):
        for f2 in faces[i + 1:]:
            mls = mls_with_temporal(
                f1["mu"], f1["sigma_sq"], f1["era"],
                f2["mu"], f2["sigma_sq"], f2["era"]
            )
            prob = mls_to_probability(mls)
            scores.append(prob)

    return (min(scores), max(scores))


def format_match_range(match_range: tuple[float, float] | None) -> str:
    """
    Format match probability range as human-readable string.

    Args:
        match_range: (min_prob, max_prob) or None

    Returns:
        String like "82%-91%" or "N/A"
    """
    if match_range is None:
        return "N/A"

    min_prob, max_prob = match_range
    return f"{int(round(min_prob * 100))}%-{int(round(max_prob * 100))}%"


def _compute_reference_mls(faces: list[dict]) -> float:
    """
    Compute reference MLS for identical faces with average σ² in dataset.

    This is the MLS you'd get for identical embeddings with the given uncertainty.
    """
    if not faces:
        return 0.0

    # Average σ² across all faces
    avg_sigma_sq = np.mean([f["sigma_sq"].mean() for f in faces])

    # Reference MLS = -512 * log(2 * avg_σ²)
    # This is the uncertainty penalty term only (Mahalanobis = 0 for identical)
    return -512 * np.log(2 * avg_sigma_sq)


def cluster_identities(faces: list[dict]) -> list[dict]:
    """
    Cluster faces into identity groups using MLS + temporal priors.

    Args:
        faces: List of face dicts with mu, sigma_sq, era, filename

    Returns:
        List of cluster dicts, each with:
        - faces: List of faces in this cluster
        - match_range: (min_prob, max_prob) or None
        - cluster_id: Integer cluster identifier
    """
    if len(faces) == 0:
        return []

    # Sort faces by filename for deterministic ordering
    faces = sorted(faces, key=lambda f: f.get("filename", ""))

    if len(faces) == 1:
        return [{
            "faces": faces,
            "match_range": None,
            "cluster_id": 0,
        }]

    # Compute adaptive threshold based on average σ² in dataset
    ref_mls = _compute_reference_mls(faces)
    mls_threshold = ref_mls - MLS_DROP_THRESHOLD

    # Compute pairwise distance matrix
    n = len(faces)
    distances = np.zeros((n, n))

    for i in range(n):
        for j in range(i + 1, n):
            mls = mls_with_temporal(
                faces[i]["mu"], faces[i]["sigma_sq"], faces[i]["era"],
                faces[j]["mu"], faces[j]["sigma_sq"], faces[j]["era"]
            )
            dist = mls_to_distance(mls)
            distances[i, j] = dist
            distances[j, i] = dist

    # Convert to condensed form for scipy
    condensed = squareform(distances)

    # Hierarchical clustering with complete linkage
    Z = linkage(condensed, method="complete")

    # Cut tree at adaptive threshold (distance = -MLS)
    labels = fcluster(Z, t=-mls_threshold, criterion="distance")

    # Group faces by cluster label
    clusters_dict = {}
    for idx, label in enumerate(labels):
        if label not in clusters_dict:
            clusters_dict[label] = []
        clusters_dict[label].append(faces[idx])

    # Build result list
    clusters = []
    for cluster_id, cluster_faces in sorted(clusters_dict.items()):
        match_range = compute_match_range(cluster_faces)
        clusters.append({
            "faces": cluster_faces,
            "match_range": match_range,
            "cluster_id": int(cluster_id),
        })

    return clusters
