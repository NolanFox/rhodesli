# ADR-001: Mutual Likelihood Score (MLS) for Probabilistic Face Matching

**Status:** Accepted
**Date:** 2026-01-28
**Author:** Rhodesli Project

## Context

Historical photographs exhibit degradation, noise, blur, and varying capture conditions that make traditional point-embedding matching unreliable. Cosine similarity between face embeddings produces a single scalar that hides uncertainty—a 0.85 similarity score provides no information about whether that score is highly confident or could reasonably range from 0.70 to 0.95.

We need a matching approach that:
1. Treats each face embedding as a probability distribution, not a point
2. Explicitly models uncertainty (σ²) as a first-class citizen
3. Produces calibrated match probabilities, not arbitrary similarity scores
4. Penalizes high uncertainty to prevent trivial "everything matches" solutions

## Decision

We adopt **Probabilistic Face Embeddings (PFE)** with **Mutual Likelihood Score (MLS)** as our matching metric.

### Mathematical Foundation

Each face is represented as a Gaussian distribution in embedding space:

```
Face_i ~ N(μᵢ, Σᵢ)
```

Where:
- **μᵢ** ∈ ℝ^512: Mean embedding vector (the "best guess" location)
- **Σᵢ**: Covariance matrix (we use diagonal: σᵢ² ∈ ℝ^512)

### MLS Derivation

Given two faces with distributions N(μ₁, σ₁²) and N(μ₂, σ₂²), we want to compute the likelihood that both observations came from the same latent identity.

Under the assumption that both faces are noisy observations of the same underlying identity μ*, and each observation has independent Gaussian noise, the Mutual Likelihood Score is:

```
MLS(f₁, f₂) = Σᵢ [ -(μ₁ᵢ - μ₂ᵢ)² / (σ₁ᵢ² + σ₂ᵢ²) - log(σ₁ᵢ² + σ₂ᵢ²) ]
```

Equivalently, in vector notation:

```
MLS(f₁, f₂) = -Σ[(μ₁ - μ₂)² / (σ₁² + σ₂²)] - Σ[log(σ₁² + σ₂²)]
```

**Term 1: Mahalanobis-like Distance**
```
-Σ[(μ₁ - μ₂)² / (σ₁² + σ₂²)]
```
- Penalizes mean differences, weighted by combined uncertainty
- If both faces are confident (low σ²), small differences matter
- If either face is uncertain (high σ²), differences are discounted

**Term 2: Uncertainty Penalty**
```
-Σ[log(σ₁² + σ₂²)]
```
- Penalizes high uncertainty to prevent degenerate solutions
- Without this term, setting σ² → ∞ would make everything match
- Acts as a regularizer for calibrated uncertainty

### Key Properties

1. **Higher MLS = More Likely Match**
   - MLS is a log-likelihood, so higher is better

2. **Increasing σ² Lowers MLS** (when embeddings are similar)
   - This is critical: uncertain matches should score lower than confident matches
   - The uncertainty penalty term ensures this

3. **Symmetric**
   - MLS(f₁, f₂) = MLS(f₂, f₁)

4. **Not Bounded**
   - Unlike cosine similarity ∈ [-1, 1], MLS ∈ (-∞, 0]
   - This is intentional: we work with log-likelihoods, not probabilities

### Deriving σ² from Image Quality

InsightFace's ArcFace models produce normalized embeddings (‖μ‖ = 1), so the embedding norm is not a quality signal. We derive σ² from:

1. **Detection Score (det_score)**: Confidence of face detection
2. **Face Area**: Larger faces have more pixels, less uncertainty
3. **Image Quality Metrics**: Blur, noise, exposure (future enhancement)

The uncertainty mapping function:

```python
def compute_sigma_sq(det_score: float, face_area: float,
                     min_sigma_sq: float = 0.01,
                     max_sigma_sq: float = 1.0) -> np.ndarray:
    """
    Compute per-dimension uncertainty from quality signals.

    Returns σ² ∈ ℝ^512 (same shape as μ).
    """
    # Quality score: combine detection confidence and face size
    # det_score ∈ [0, 1], higher = better
    # face_area: normalized by image size

    quality = det_score * min(face_area / 10000, 1.0)  # Heuristic

    # Inverse relationship: high quality = low uncertainty
    # σ² = max_σ² - (max_σ² - min_σ²) * quality
    sigma_sq_scalar = max_sigma_sq - (max_sigma_sq - min_sigma_sq) * quality

    # Apply uniformly across all 512 dimensions
    # (Future: could use dimension-specific uncertainty)
    return np.full(512, sigma_sq_scalar, dtype=np.float32)
```

### Implementation

```python
def mutual_likelihood_score(mu1: np.ndarray, sigma_sq1: np.ndarray,
                            mu2: np.ndarray, sigma_sq2: np.ndarray) -> float:
    """
    Compute MLS between two probabilistic face embeddings.

    Args:
        mu1, mu2: Mean embeddings, shape (512,)
        sigma_sq1, sigma_sq2: Variance vectors, shape (512,)

    Returns:
        MLS score (higher = more likely match)
    """
    combined_var = sigma_sq1 + sigma_sq2

    # Term 1: Weighted squared difference
    diff_sq = (mu1 - mu2) ** 2
    mahalanobis_term = -np.sum(diff_sq / combined_var)

    # Term 2: Uncertainty penalty
    uncertainty_penalty = -np.sum(np.log(combined_var))

    return mahalanobis_term + uncertainty_penalty
```

## Alternatives Considered

### 1. Cosine Similarity
**Rejected.** Produces single scalar with no uncertainty quantification. A 0.85 score could mean "definitely 85% similar" or "somewhere between 70% and 95%". We cannot distinguish confident matches from uncertain ones.

### 2. Euclidean Distance
**Rejected.** Same problem as cosine similarity—no uncertainty modeling. Also, Euclidean distance is sensitive to embedding scale.

### 3. Bayesian Neural Network Uncertainty
**Considered for future.** Would require retraining the face encoder with dropout at inference time (MC Dropout) or a full BNN. More principled but significantly more complex.

### 4. Ensemble Uncertainty
**Considered for future.** Run multiple face models and compute variance across predictions. Principled but expensive and requires multiple model weights.

## Consequences

### Positive
- Uncertainty is explicit and interpretable
- Match probabilities are calibrated (can be converted to confidence intervals)
- Historical photo degradation naturally increases σ², lowering false positive rates
- Forensically defensible: we report ranges, not point estimates

### Negative
- Requires storing 2x the data (μ and σ² per face)
- MLS is not intuitive like "85% similar"—requires explanation
- Quality-to-uncertainty mapping is heuristic, not learned

### Risks
- If σ² derivation is poorly calibrated, MLS may not reflect true uncertainty
- Users may expect cosine similarity and be confused by MLS scores

## Open Questions

1. **Dimension-specific σ²**: Should different embedding dimensions have different uncertainties? Some dimensions may be more robust to noise.

2. **Learned uncertainty**: Can we train a small network to predict σ² from image quality features? This would replace the heuristic mapping.

3. **Threshold selection**: What MLS threshold corresponds to "same person"? Requires empirical calibration on labeled data.

4. **Era-specific priors**: Should σ² be higher for all photos from earlier eras (1890-1910)? This is addressed in ADR-002.

## References

- Shi & Jain, "Probabilistic Face Embeddings" (ICCV 2019)
- MagFace: A Universal Representation for Face Recognition and Quality Assessment
- AdaFace: Quality Adaptive Margin for Face Recognition
