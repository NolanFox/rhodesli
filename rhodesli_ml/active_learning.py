"""Active learning pipeline foundation.

Identifies uncertain face pairs near the decision boundary for admin
labeling, which feeds back into calibration and clustering improvements.

Session: 92
"""

import logging

logger = logging.getLogger(__name__)

# Decision boundary range — pairs in this distance range are most
# informative for improving the similarity model
UNCERTAIN_LOW = 0.4
UNCERTAIN_HIGH = 0.6


def find_uncertain_pairs(
    embeddings_cache: dict,
    identities: dict,
    low: float = UNCERTAIN_LOW,
    high: float = UNCERTAIN_HIGH,
    max_pairs: int = 50,
) -> list[dict]:
    """Find face pairs near the decision boundary for admin labeling.

    These are pairs where the model is least confident — labeling them
    provides the most information for improving similarity calibration.

    Args:
        embeddings_cache: Dict mapping face_id -> embedding vector (numpy array).
        identities: Dict of identity records from the registry.
        low: Lower distance threshold (default 0.4).
        high: Upper distance threshold (default 0.6).
        max_pairs: Maximum number of pairs to return.

    Returns:
        List of dicts with face_id_a, face_id_b, distance, identity_a, identity_b,
        sorted by distance (closest to boundary midpoint first).
    """
    try:
        import numpy as np
    except ImportError:
        logger.warning("numpy not available — cannot compute uncertain pairs")
        return []

    # Get all face IDs with embeddings
    face_ids = list(embeddings_cache.keys())
    if len(face_ids) < 2:
        return []

    # Build identity lookup: face_id -> identity_id
    face_to_identity = {}
    for identity_id, data in identities.items():
        if data.get("merged_into"):
            continue
        for fid in data.get("anchor_ids", []) + data.get("candidate_ids", []):
            face_to_identity[fid] = identity_id

    # Compute pairwise distances for a sample (full pairwise is O(n^2))
    # Use random sampling if too many faces
    sample_ids = face_ids
    if len(face_ids) > 200:
        rng = np.random.default_rng(42)
        sample_ids = list(rng.choice(face_ids, size=200, replace=False))

    midpoint = (low + high) / 2
    candidates = []

    for i, fid_a in enumerate(sample_ids):
        emb_a = embeddings_cache.get(fid_a)
        if emb_a is None:
            continue
        emb_a_flat = np.array(emb_a).flatten()

        for fid_b in sample_ids[i + 1 :]:
            emb_b = embeddings_cache.get(fid_b)
            if emb_b is None:
                continue
            emb_b_flat = np.array(emb_b).flatten()

            dist = float(np.linalg.norm(emb_a_flat - emb_b_flat))
            if low <= dist <= high:
                # Skip pairs already in the same identity
                id_a = face_to_identity.get(fid_a)
                id_b = face_to_identity.get(fid_b)
                if id_a and id_b and id_a == id_b:
                    continue

                candidates.append(
                    {
                        "face_id_a": fid_a,
                        "face_id_b": fid_b,
                        "distance": round(dist, 4),
                        "identity_a": id_a,
                        "identity_b": id_b,
                        "distance_from_midpoint": round(abs(dist - midpoint), 4),
                    }
                )

    # Sort by distance from midpoint (most uncertain first)
    candidates.sort(key=lambda x: x["distance_from_midpoint"])
    return candidates[:max_pairs]


def add_labeled_pair(
    labeled_pairs: list[dict],
    face_id_a: str,
    face_id_b: str,
    is_same_person: bool,
    labeled_by: str = "admin",
) -> list[dict]:
    """Record an admin-labeled pair for active learning.

    Args:
        labeled_pairs: Existing list of labeled pair dicts.
        face_id_a: First face ID.
        face_id_b: Second face ID.
        is_same_person: True if admin confirms same person, False if not.
        labeled_by: Who labeled this pair (default "admin").

    Returns:
        Updated labeled_pairs list with the new pair appended.
    """
    from datetime import datetime, timezone

    # Normalize order (alphabetical) to avoid duplicates
    if face_id_a > face_id_b:
        face_id_a, face_id_b = face_id_b, face_id_a

    # Check for existing label on this pair
    for existing in labeled_pairs:
        if existing.get("face_id_a") == face_id_a and existing.get("face_id_b") == face_id_b:
            # Update existing label
            existing["is_same_person"] = is_same_person
            existing["labeled_by"] = labeled_by
            existing["labeled_at"] = datetime.now(timezone.utc).isoformat()
            logger.info(f"Updated label for pair ({face_id_a}, {face_id_b}): {is_same_person}")
            return labeled_pairs

    # Add new label
    labeled_pairs.append(
        {
            "face_id_a": face_id_a,
            "face_id_b": face_id_b,
            "is_same_person": is_same_person,
            "labeled_by": labeled_by,
            "labeled_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    logger.info(f"Added label for pair ({face_id_a}, {face_id_b}): {is_same_person}")
    return labeled_pairs
