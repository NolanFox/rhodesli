"""
Probabilistic Face Embeddings (PFE) and Mutual Likelihood Score (MLS).

This module implements forensic face matching using probability distributions
instead of point embeddings. See docs/adr_001_mls_math.md for mathematical
derivation and rationale.

Key concepts:
- μ (mu): Mean embedding vector, shape (512,)
- σ² (sigma_sq): Variance vector representing uncertainty, shape (512,)
- MLS: Mutual Likelihood Score for comparing two PFEs
"""

import numpy as np


def mutual_likelihood_score(
    mu1: np.ndarray,
    sigma_sq1: np.ndarray,
    mu2: np.ndarray,
    sigma_sq2: np.ndarray,
) -> float:
    """
    Compute Mutual Likelihood Score between two probabilistic face embeddings.

    MLS(f₁, f₂) = -Σ[(μ₁ - μ₂)² / (σ₁² + σ₂²)] - Σ[log(σ₁² + σ₂²)]

    Term 1 (Mahalanobis-like): Penalizes mean differences weighted by uncertainty
    Term 2 (Uncertainty penalty): Penalizes high uncertainty

    Args:
        mu1: Mean embedding of face 1, shape (512,)
        sigma_sq1: Variance of face 1, shape (512,)
        mu2: Mean embedding of face 2, shape (512,)
        sigma_sq2: Variance of face 2, shape (512,)

    Returns:
        MLS score (float). Higher = more likely same person.
        Score is in (-∞, 0] as it's a log-likelihood.
    """
    combined_var = sigma_sq1 + sigma_sq2

    # Term 1: Mahalanobis-like weighted difference
    diff_sq = (mu1 - mu2) ** 2
    mahalanobis_term = -np.sum(diff_sq / combined_var)

    # Term 2: Uncertainty penalty (prevents σ² → ∞ trivial solution)
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
