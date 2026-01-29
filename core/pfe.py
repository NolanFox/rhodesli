"""
Probabilistic Face Embeddings (PFE) and Mutual Likelihood Score (MLS).

This module implements forensic face matching using probability distributions
instead of point embeddings. See docs/adr_001_mls_math.md for mathematical
derivation and rationale.

Key concepts:
- μ (mu): Mean embedding vector, shape (512,)
- σ² (sigma_sq): Variance - either scalar (float) or per-dimension array (512,)
- MLS: Mutual Likelihood Score for comparing two PFEs

IMPORTANT: Scalar sigma fix (docs/adr_006_scalar_sigma_fix.md)
When sigma_sq is a uniform value across all dimensions (as produced by
compute_sigma_sq), the MLS formula must NOT sum 512 log terms. Instead,
we compute a single-term MLS to prevent the log penalty from drowning
the discriminative embedding distance signal.
"""

import numpy as np


def _is_scalar_sigma(sigma_sq: np.ndarray, rtol: float = 1e-5) -> bool:
    """Check if sigma_sq is effectively a scalar (all elements same)."""
    if sigma_sq.size == 0:
        return True
    return np.allclose(sigma_sq, sigma_sq[0], rtol=rtol)


def mutual_likelihood_score(
    mu1: np.ndarray,
    sigma_sq1: np.ndarray,
    mu2: np.ndarray,
    sigma_sq2: np.ndarray,
) -> float:
    """
    Compute Mutual Likelihood Score between two probabilistic face embeddings.

    For per-dimension σ² (true PFE):
        MLS(f₁, f₂) = -Σ[(μ₁ - μ₂)² / (σ₁² + σ₂²)] - Σ[log(σ₁² + σ₂²)]

    For scalar σ² (uniform across dimensions):
        MLS(f₁, f₂) = -Σ[(μ₁ - μ₂)²] / (σ₁² + σ₂²) - log(σ₁² + σ₂²)

    The scalar case uses a SINGLE log term instead of 512, preventing the
    uncertainty penalty from drowning the discriminative embedding distance.
    See docs/adr_006_scalar_sigma_fix.md for rationale.

    Args:
        mu1: Mean embedding of face 1, shape (512,)
        sigma_sq1: Variance of face 1, shape (512,) - may be uniform scalar
        mu2: Mean embedding of face 2, shape (512,)
        sigma_sq2: Variance of face 2, shape (512,) - may be uniform scalar

    Returns:
        MLS score (float). Higher = more likely same person.
        Score is in (-∞, 0] as it's a log-likelihood.
    """
    # Squared differences between embeddings
    diff_sq = (mu1 - mu2) ** 2
    squared_distance = np.sum(diff_sq)

    # Scalar sigma fix: When sigma is a single value (not per-dimension),
    # we compute MLS as a single term, not summed over 512 dimensions.
    # See docs/adr_006_scalar_sigma_fix.md
    if _is_scalar_sigma(sigma_sq1) and _is_scalar_sigma(sigma_sq2):
        # Both sigmas are scalars - use single-term formula
        combined_sigma_sq = float(sigma_sq1[0] + sigma_sq2[0])

        # Single Mahalanobis-like term (normalized by scalar variance)
        mahalanobis_term = -squared_distance / combined_sigma_sq

        # Single log penalty (NOT multiplied by 512!)
        uncertainty_penalty = -np.log(combined_sigma_sq)

        return float(mahalanobis_term + uncertainty_penalty)

    # Per-dimension case: original formula with element-wise operations
    combined_var = sigma_sq1 + sigma_sq2

    # Term 1: Mahalanobis-like weighted difference (element-wise)
    mahalanobis_term = -np.sum(diff_sq / combined_var)

    # Term 2: Uncertainty penalty per dimension
    uncertainty_penalty = -np.sum(np.log(combined_var))

    return float(mahalanobis_term + uncertainty_penalty)


def compute_sigma_sq(
    det_score: float,
    face_area: float,
    min_sigma_sq: float = 0.01,
    max_sigma_sq: float = 1.0,
) -> np.ndarray:
    """
    Derive uncertainty (σ²) from quality signals.

    Maps detection confidence and face size to per-dimension uncertainty.
    High quality (high det_score, large face) → low σ² (high confidence).
    Low quality (low det_score, small face) → high σ² (low confidence).

    Args:
        det_score: Face detection confidence in [0, 1]
        face_area: Face bounding box area in pixels
        min_sigma_sq: Minimum σ² for highest quality faces
        max_sigma_sq: Maximum σ² for lowest quality faces

    Returns:
        σ² array of shape (512,), dtype float32
    """
    # Clamp inputs to valid ranges
    det_score = max(0.0, min(1.0, det_score))
    face_area = max(0.0, face_area)

    # Normalize face area (10000 pixels = "good" reference size)
    area_factor = min(face_area / 10000.0, 1.0)

    # Combined quality score in [0, 1]
    quality = det_score * area_factor

    # Inverse relationship: high quality → low σ²
    sigma_sq_scalar = max_sigma_sq - (max_sigma_sq - min_sigma_sq) * quality

    # Apply uniformly across all 512 dimensions
    return np.full(512, sigma_sq_scalar, dtype=np.float32)


def create_pfe(face_data: dict, image_shape: tuple) -> dict:
    """
    Convert face detection result to Probabilistic Face Embedding.

    Args:
        face_data: Dict with keys: embedding, det_score, bbox, filename, filepath
        image_shape: Tuple of (height, width) of source image

    Returns:
        PFE dict with keys: mu, sigma_sq, plus original metadata
    """
    embedding = face_data["embedding"]
    det_score = face_data["det_score"]
    bbox = face_data["bbox"]

    # Compute face area from bounding box
    x1, y1, x2, y2 = bbox
    face_area = (x2 - x1) * (y2 - y1)

    # Derive uncertainty from quality signals
    sigma_sq = compute_sigma_sq(det_score, face_area)

    # Build PFE, preserving original metadata
    pfe = {
        "mu": np.asarray(embedding, dtype=np.float32),
        "sigma_sq": sigma_sq,
        "det_score": det_score,
        "bbox": bbox,
    }

    # Preserve optional metadata
    if "filename" in face_data:
        pfe["filename"] = face_data["filename"]
    if "filepath" in face_data:
        pfe["filepath"] = face_data["filepath"]
    if "quality" in face_data:
        pfe["quality"] = face_data["quality"]

    return pfe
