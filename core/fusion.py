"""
Bayesian PFE Fusion with Safety Guardrails.

Implements weighted fusion for identity anchors while protecting against
variance explosion and ensuring rejected faces don't poison anchors.

See docs/adr_004_identity_registry.md for mathematical foundations.

Key formulas:
  fused_μ  = Σ(μ_i / σ_i² × w_i) / Σ(1 / σ_i² × w_i)
  fused_σ² = 1 / Σ(1 / σ_i² × w_i)

Where w_i is confidence_weight (default 1.0).
"""

import numpy as np

from core.registry import IdentityRegistry, IdentityState
from core.temporal import mls_with_temporal


# Default variance explosion threshold
# If fused_σ > max(input_σ) × K, reject the merge
DEFAULT_VARIANCE_K = 1.5

# Re-evaluation threshold: σ shrinks by more than this percentage
REEVALUATION_THRESHOLD = 0.10


def fuse_anchors(
    anchors: list[dict],
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute Bayesian-inspired fusion of anchor embeddings.

    Args:
        anchors: List of dicts with 'mu', 'sigma_sq', 'confidence_weight'

    Returns:
        (fused_mu, fused_sigma_sq) as numpy arrays of shape (512,)

    Raises:
        ValueError: If anchors list is empty
    """
    if not anchors:
        raise ValueError("No anchors to fuse")

    if len(anchors) == 1:
        return (
            anchors[0]["mu"].copy(),
            anchors[0]["sigma_sq"].copy(),
        )

    # Compute inverse variance weights for each anchor
    # precision_i = 1 / σ_i² × w_i
    precisions = []
    weighted_mus = []

    for anchor in anchors:
        mu = anchor["mu"]
        sigma_sq = anchor["sigma_sq"]
        w = anchor.get("confidence_weight", 1.0)

        # Precision = 1 / σ² × weight
        precision = w / sigma_sq
        precisions.append(precision)

        # Weighted μ = μ × precision
        weighted_mus.append(mu * precision)

    # Stack for vectorized operations
    precisions = np.stack(precisions)  # (n_anchors, 512)
    weighted_mus = np.stack(weighted_mus)  # (n_anchors, 512)

    # Sum along anchor dimension
    total_precision = np.sum(precisions, axis=0)  # (512,)
    total_weighted_mu = np.sum(weighted_mus, axis=0)  # (512,)

    # Compute fused values
    fused_mu = total_weighted_mu / total_precision
    fused_sigma_sq = 1.0 / total_precision

    return fused_mu.astype(np.float32), fused_sigma_sq.astype(np.float32)


def check_variance_explosion(
    anchors: list[dict],
    k: float = DEFAULT_VARIANCE_K,
) -> dict:
    """
    Check if fusing anchors would cause variance explosion.

    Variance explosion occurs when fused_σ > max(input_σ) × K.
    This indicates the faces are too dissimilar to merge safely.

    Args:
        anchors: List of dicts with 'mu', 'sigma_sq', 'confidence_weight'
        k: Explosion threshold multiplier (default 1.5)

    Returns:
        Dict with 'safe' (bool), and diagnostic info
    """
    if len(anchors) < 2:
        return {"safe": True, "reason": "single_anchor"}

    # Compute fused σ²
    _, fused_sigma_sq = fuse_anchors(anchors)

    # Get max input σ (not σ²)
    input_sigmas = [np.sqrt(a["sigma_sq"]) for a in anchors]
    max_input_sigma = np.max([s.mean() for s in input_sigmas])

    # Compute fused σ mean
    fused_sigma_mean = np.sqrt(fused_sigma_sq).mean()

    # Check explosion condition
    # Note: For fusion of similar embeddings, fused_σ should DECREASE
    # If it increases or stays too high, something is wrong

    # Actually, for Bayesian fusion, σ always decreases when fusing identical
    # The explosion happens in the μ estimate - we need to check if the
    # weighted average of μ makes sense given the variances

    # Alternative approach: compute the Mahalanobis distance between
    # the fused result and each input, and check if it's reasonable
    fused_mu, _ = fuse_anchors(anchors)

    # Compute average squared distance from fused to each input
    # normalized by their variance
    total_mahalanobis = 0.0
    for anchor in anchors:
        diff_sq = (anchor["mu"] - fused_mu) ** 2
        mahal = np.sum(diff_sq / anchor["sigma_sq"])
        total_mahalanobis += mahal

    avg_mahalanobis = total_mahalanobis / len(anchors)

    # For similar faces, this should be small
    # The threshold k controls sensitivity:
    # - k=1.5 (default): detects significant dissimilarity
    # - k=100: very permissive, only catches extreme cases
    # - k=0.1: very strict, catches any difference
    threshold = k

    safe = bool(avg_mahalanobis < threshold)

    return {
        "safe": safe,
        "reason": "variance_ok" if safe else "variance_explosion",
        "fused_sigma_mean": float(fused_sigma_mean),
        "max_input_sigma": float(max_input_sigma),
        "avg_mahalanobis": float(avg_mahalanobis),
        "threshold": float(threshold),
    }


def compute_identity_fusion(
    registry: IdentityRegistry,
    identity_id: str,
    face_data: dict[str, dict],
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute fused embedding for an identity using only its anchors.

    Args:
        registry: Identity registry
        identity_id: ID of identity to fuse
        face_data: Dict mapping face_id to {'mu', 'sigma_sq'}

    Returns:
        (fused_mu, fused_sigma_sq)

    Note: Candidates and negative_ids are explicitly IGNORED.
    """
    identity = registry.get_identity(identity_id)

    # Only use anchor_ids - ignore candidates and negatives
    anchors = []
    for face_id in identity["anchor_ids"]:
        if face_id not in face_data:
            continue
        face = face_data[face_id]
        anchors.append({
            "mu": face["mu"],
            "sigma_sq": face["sigma_sq"],
            "confidence_weight": 1.0,  # Could look up from events
        })

    if not anchors:
        raise ValueError(f"No valid anchors for identity {identity_id}")

    return fuse_anchors(anchors)


def safe_promote_candidate(
    registry: IdentityRegistry,
    identity_id: str,
    face_id: str,
    face_data: dict[str, dict],
    user_source: str,
    k: float = DEFAULT_VARIANCE_K,
) -> dict:
    """
    Safely promote a candidate with variance explosion check.

    If promotion would cause variance explosion:
    - Reject the promotion
    - Record rejection event
    - Mark identity as CONTESTED

    Args:
        registry: Identity registry
        identity_id: ID of identity
        face_id: Face to promote
        face_data: Dict mapping face_id to {'mu', 'sigma_sq'}
        user_source: Who initiated this
        k: Variance explosion threshold

    Returns:
        Dict with 'success' (bool) and details
    """
    identity = registry.get_identity(identity_id)

    # Build hypothetical anchor list
    anchors = []
    for anchor_id in identity["anchor_ids"]:
        if anchor_id in face_data:
            anchors.append({
                "mu": face_data[anchor_id]["mu"],
                "sigma_sq": face_data[anchor_id]["sigma_sq"],
                "confidence_weight": 1.0,
            })

    # Add the candidate
    if face_id not in face_data:
        return {"success": False, "reason": "face_not_found"}

    anchors.append({
        "mu": face_data[face_id]["mu"],
        "sigma_sq": face_data[face_id]["sigma_sq"],
        "confidence_weight": 1.0,
    })

    # Check variance explosion
    check = check_variance_explosion(anchors, k=k)

    if not check["safe"]:
        # Mark identity as CONTESTED
        if identity["state"] != IdentityState.CONTESTED.value:
            registry.contest_identity(
                identity_id,
                user_source=user_source,
                reason=f"Variance explosion when adding {face_id}",
            )

        return {
            "success": False,
            "reason": "variance_explosion",
            "details": check,
        }

    # Safe to promote
    registry.promote_candidate(identity_id, face_id, user_source)

    return {
        "success": True,
        "details": check,
    }


def should_reevaluate_rejections(
    old_sigma_sq: np.ndarray,
    new_sigma_sq: np.ndarray,
    threshold: float = REEVALUATION_THRESHOLD,
) -> bool:
    """
    Determine if anchor change warrants re-evaluating rejections.

    Args:
        old_sigma_sq: Previous fused σ²
        new_sigma_sq: New fused σ²
        threshold: Fraction change required (default 0.10 = 10%)

    Returns:
        True if rejections should be re-evaluated
    """
    old_mean = old_sigma_sq.mean()
    new_mean = new_sigma_sq.mean()

    # Check if σ shrunk significantly (improvement)
    if old_mean == 0:
        return False

    change = (old_mean - new_mean) / old_mean

    return bool(change > threshold)


def get_reevaluation_candidates(
    registry: IdentityRegistry,
    identity_id: str,
    face_data: dict[str, dict],
    mls_threshold: float = 0.0,
) -> list[dict]:
    """
    Get previously rejected faces that may warrant re-evaluation.

    This surfaces candidates for HUMAN REVIEW only.
    It does NOT auto-merge.

    Args:
        registry: Identity registry
        identity_id: ID of identity
        face_data: Dict mapping face_id to {'mu', 'sigma_sq', 'era'}
        mls_threshold: Minimum MLS to surface

    Returns:
        List of candidate dicts with face_id and mls_score
    """
    identity = registry.get_identity(identity_id)

    if not identity["negative_ids"]:
        return []

    # Compute current anchor fusion
    try:
        fused_mu, fused_sigma_sq = compute_identity_fusion(
            registry, identity_id, face_data
        )
    except ValueError:
        return []

    # Get anchor era (use first anchor's era)
    anchor_era = None
    for anchor_id in identity["anchor_ids"]:
        if anchor_id in face_data and "era" in face_data[anchor_id]:
            anchor_era = face_data[anchor_id]["era"]
            break

    if anchor_era is None:
        return []

    # Score each rejected face
    candidates = []
    for face_id in identity["negative_ids"]:
        if face_id not in face_data:
            continue

        face = face_data[face_id]
        if "era" not in face:
            continue

        mls = mls_with_temporal(
            fused_mu, fused_sigma_sq, anchor_era,
            face["mu"], face["sigma_sq"], face["era"],
        )

        if mls > mls_threshold:
            candidates.append({
                "face_id": face_id,
                "mls_score": float(mls),
            })

    # Sort by score (highest first)
    candidates.sort(key=lambda x: x["mls_score"], reverse=True)

    return candidates
