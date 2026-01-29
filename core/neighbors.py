"""
Nearest Neighbor Discovery for Identity Matching.

Finds similar identities based on centroid distance for merge candidates.
Uses MLS (Mutual Likelihood Score) as the similarity metric - higher values
indicate more similar identities.

Safety Foundation: All neighbor results include merge eligibility via
validate_merge() - no merge may proceed without explicit validation.
"""

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from core.photo_registry import PhotoRegistry
    from core.registry import IdentityRegistry

from core.fusion import compute_identity_fusion
from core.pfe import mutual_likelihood_score

logger = logging.getLogger(__name__)


def compute_identity_centroid(
    registry: "IdentityRegistry",
    identity_id: str,
    face_data: dict[str, dict],
) -> tuple[np.ndarray, np.ndarray] | None:
    """
    Compute centroid (fused mu, sigma_sq) for an identity.

    Args:
        registry: Identity registry
        identity_id: ID of identity to compute centroid for
        face_data: Dict mapping face_id to {'mu', 'sigma_sq'}

    Returns:
        (fused_mu, fused_sigma_sq) tuple, or None if identity has no valid anchors.
    """
    try:
        return compute_identity_fusion(registry, identity_id, face_data)
    except ValueError:
        logger.debug(f"No valid anchors for identity {identity_id}")
        return None


def find_nearest_neighbors(
    identity_id: str,
    registry: "IdentityRegistry",
    photo_registry: "PhotoRegistry",
    face_data: dict[str, dict],
    limit: int = 10,
) -> list[dict]:
    """
    Find identities most similar to the given identity.

    Uses MLS between identity centroids as similarity measure.

    Excludes:
    - The identity itself
    - Merged/deleted identities
    - Identities with no valid anchors (can't compute centroid)

    Each result includes merge eligibility (can_merge) computed via
    validate_merge() - this is the Safety Foundation constraint.

    Args:
        identity_id: Target identity ID
        registry: Identity registry
        photo_registry: For co-occurrence validation
        face_data: Dict mapping face_id to {'mu', 'sigma_sq'}
        limit: Maximum neighbors to return (default 10)

    Returns:
        List of dicts sorted by similarity (highest MLS first):
        [{
            "identity_id": str,
            "name": str,
            "state": str,
            "face_count": int,
            "mls_score": float,
            "can_merge": bool,
            "merge_blocked_reason": str | None,
        }]
    """
    from core.registry import validate_merge

    # Compute target centroid
    target_centroid = compute_identity_centroid(registry, identity_id, face_data)
    if target_centroid is None:
        logger.warning(f"Cannot find neighbors: no centroid for {identity_id}")
        return []

    target_mu, target_sigma_sq = target_centroid

    # Get all other active identities (exclude merged by default)
    all_identities = registry.list_identities(include_merged=False)

    neighbors = []
    for identity in all_identities:
        other_id = identity["identity_id"]

        # Skip self
        if other_id == identity_id:
            continue

        # Compute other centroid
        other_centroid = compute_identity_centroid(registry, other_id, face_data)
        if other_centroid is None:
            continue

        other_mu, other_sigma_sq = other_centroid

        # Compute MLS similarity (higher = more similar)
        mls = mutual_likelihood_score(
            target_mu, target_sigma_sq,
            other_mu, other_sigma_sq,
        )

        # Check if merge is possible (Safety Foundation)
        can_merge, reason = validate_merge(
            identity_id, other_id, registry, photo_registry
        )

        # Count faces
        face_count = len(identity.get("anchor_ids", [])) + len(identity.get("candidate_ids", []))

        neighbors.append({
            "identity_id": other_id,
            "name": identity.get("name") or f"Identity {other_id[:8]}...",
            "state": identity["state"],
            "face_count": face_count,
            "mls_score": float(mls),
            "can_merge": can_merge,
            "merge_blocked_reason": None if can_merge else reason,
        })

    # Sort by MLS descending (higher = more similar)
    neighbors.sort(key=lambda x: x["mls_score"], reverse=True)

    return neighbors[:limit]


def sort_faces_by_outlier_score(
    identity_id: str,
    registry: "IdentityRegistry",
    face_data: dict[str, dict],
) -> list[tuple[str, float]]:
    """
    Sort faces by distance from identity centroid (descending = outliers first).

    Uses MLS from face to centroid: lower MLS = further away = more of an outlier.
    Returns faces sorted by outlier score (distance), highest first.

    Args:
        identity_id: ID of identity to analyze
        registry: Identity registry
        face_data: Dict mapping face_id to {'mu', 'sigma_sq'}

    Returns:
        List of (face_id, outlier_score) tuples, sorted by score descending.
        Higher score = further from centroid = more likely to be an outlier.
    """
    identity = registry.get_identity(identity_id)

    # Compute centroid
    centroid = compute_identity_centroid(registry, identity_id, face_data)
    if centroid is None:
        return []

    centroid_mu, centroid_sigma_sq = centroid

    # Score each face
    scored_faces = []
    all_entries = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])

    for entry in all_entries:
        # Handle both string and dict anchor formats
        if isinstance(entry, str):
            face_id = entry
        else:
            face_id = entry.get("face_id")

        if face_id not in face_data:
            continue

        face = face_data[face_id]

        # Compute MLS from face to centroid
        mls = mutual_likelihood_score(
            centroid_mu, centroid_sigma_sq,
            face["mu"], face["sigma_sq"],
        )

        # Convert to outlier score: negate MLS so lower similarity = higher score
        outlier_score = -mls
        scored_faces.append((face_id, outlier_score))

    # Sort by outlier score descending (outliers first)
    scored_faces.sort(key=lambda x: x[1], reverse=True)

    return scored_faces
