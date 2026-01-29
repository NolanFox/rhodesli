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
#
# IMPORTANT: Lower values = stricter clustering = more separate identities
# Higher values = looser clustering = more merging (risks "super-clusters")
#
# POST-SCALAR-FIX (docs/adr_006_scalar_sigma_fix.md):
# After fixing the MLS formula, the reference score for identical faces is:
#   ref_mls = -log(2 * sigma_sq)  (single term, not 512×)
#
# For sigma_sq=0.05: ref_mls ≈ -log(0.1) ≈ 2.3
# For sigma_sq=0.2:  ref_mls ≈ -log(0.4) ≈ 0.9
#
# The discriminative term (squared distance / combined_variance) dominates.
# With sigma_sq=0.2, typical MLS ranges:
#   - Same person (sq_dist < 0.5): MLS ≈ -0.5 to -2
#   - Different person (sq_dist > 1.5): MLS ≈ -4 to -10+
#
# Threshold of 3 means: MLS must be within 3 of the best possible score.
# This is calibrated for sigma_sq ~ 0.2 typical in bootstrapped data.
MLS_DROP_THRESHOLD = 3


def mls_to_distance(mls: float, max_mls: float) -> float:
    """
    Convert MLS score to distance metric for clustering.

    Higher MLS (more similar) → lower distance.
    Uses shifted distance: distance = max_mls - mls

    This guarantees:
    - distance >= 0 (required by scipy.cluster.hierarchy.linkage)
    - Best possible match has distance == 0
    - Ordering preserved: if MLS_A > MLS_B then distance_A < distance_B

    Args:
        mls: Mutual Likelihood Score
        max_mls: Maximum MLS in the current batch (shift value)

    Returns:
        Non-negative distance
    """
    return max_mls - mls


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

    POST-SCALAR-FIX (docs/adr_006_scalar_sigma_fix.md):
    With scalar sigma, reference MLS = -log(2 * avg_σ²) (single term, not 512×).
    For avg_sigma_sq=0.05: ref_mls ≈ -log(0.1) ≈ 2.3
    For avg_sigma_sq=0.1:  ref_mls ≈ -log(0.2) ≈ 1.6
    """
    if not faces:
        return 0.0

    # Average σ² across all faces (sigma_sq is uniform, so mean is the scalar value)
    avg_sigma_sq = np.mean([f["sigma_sq"].mean() for f in faces])

    # Reference MLS = -log(2 * avg_σ²) for scalar sigma
    # This is the uncertainty penalty term only (Mahalanobis = 0 for identical)
    # NOTE: Single log term, NOT multiplied by 512 (scalar sigma fix)
    return -np.log(2 * avg_sigma_sq)


def _print_mls_stats(mls_values: list[float]) -> None:
    """
    Print MLS distribution statistics for observability.

    POST-SCALAR-FIX score ranges (docs/adr_006_scalar_sigma_fix.md):
    - MLS > -50: Strong match (same person, high confidence)
    - MLS -200 to -50: Moderate match (possibly same person)
    - MLS -500 to -200: Weak/uncertain match
    - MLS < -500: Different identities (should NOT cluster together)

    Good separation shows a bimodal distribution with same-identity pairs
    having high MLS (> -100) and different-identity pairs having low MLS (< -500).
    """
    arr = np.array(mls_values)
    print("\n" + "=" * 60)
    print("MLS DISTRIBUTION STATS (higher = more similar)")
    print("=" * 60)
    print(f"  Count: {len(arr)}")
    print(f"  Min:   {arr.min():.1f}")
    print(f"  Max:   {arr.max():.1f}")
    print(f"  Mean:  {arr.mean():.1f}")
    print(f"  Std:   {arr.std():.1f}")

    # Simple histogram with fixed buckets (calibrated for scalar-sigma MLS)
    buckets = [
        (-np.inf, -1000, "< -1000 (very different)"),
        (-1000, -500, "-1000 to -500 (different)"),
        (-500, -200, "-500 to -200 (weak match)"),
        (-200, -50, "-200 to -50 (moderate match)"),
        (-50, np.inf, "> -50 (strong match)"),
    ]
    print("\n  Histogram:")
    for low, high, label in buckets:
        count = np.sum((arr > low) & (arr <= high))
        bar = "#" * min(count, 40)
        print(f"    {label:30s}: {count:4d} {bar}")
    print("=" * 60 + "\n")


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

    # Compute pairwise MLS matrix first, then convert to distances
    n = len(faces)
    mls_matrix = np.zeros((n, n))
    mls_values = []  # For observability

    for i in range(n):
        for j in range(i + 1, n):
            mls = mls_with_temporal(
                faces[i]["mu"], faces[i]["sigma_sq"], faces[i]["era"],
                faces[j]["mu"], faces[j]["sigma_sq"], faces[j]["era"]
            )
            mls_values.append(mls)  # Collect for stats
            mls_matrix[i, j] = mls
            mls_matrix[j, i] = mls

    # Print MLS distribution for observability
    _print_mls_stats(mls_values)

    # Compute max MLS for shifted distance metric
    # This ensures distance >= 0 (required by scipy linkage)
    max_mls = max(mls_values)

    # Convert MLS to distances using shifted metric: distance = max_mls - mls
    distances = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            dist = mls_to_distance(mls_matrix[i, j], max_mls)
            distances[i, j] = dist
            distances[j, i] = dist

    # Defensive logging: verify distances are non-negative
    min_distance = distances[distances > 0].min() if np.any(distances > 0) else 0.0
    max_distance = distances.max()
    print(f"\nDistance stats: min={min_distance:.3f}, max={max_distance:.3f}")
    assert min_distance >= 0, f"Negative distance detected: {min_distance}"

    # Convert threshold to distance space using same transform
    # MLS threshold becomes: distance_threshold = max_mls - mls_threshold
    distance_threshold = max_mls - mls_threshold

    print(f"Clustering with: ref_mls={ref_mls:.1f}, mls_threshold={mls_threshold:.1f}")
    print(f"Shifted distance: max_mls={max_mls:.1f}, distance_threshold={distance_threshold:.1f}")

    # Convert to condensed form for scipy
    condensed = squareform(distances)

    # Hierarchical clustering with complete linkage
    Z = linkage(condensed, method="complete")

    # Cut tree at shifted threshold
    labels = fcluster(Z, t=distance_threshold, criterion="distance")

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
