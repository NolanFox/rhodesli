# ADR 006: Scalar Sigma Fix for MLS Formula

## Status

Accepted

## Context

The Mutual Likelihood Score (MLS) formula was derived assuming per-dimension variance vectors σ²:

```
MLS(f₁, f₂) = -Σᵢ[(μ₁ᵢ - μ₂ᵢ)² / (σ₁ᵢ² + σ₂ᵢ²)] - Σᵢ[log(σ₁ᵢ² + σ₂ᵢ²)]
```

However, our implementation derives σ² from quality signals (detection confidence, face area) and applies it uniformly across all 512 dimensions:

```python
# From compute_sigma_sq()
return np.full(512, sigma_sq_scalar, dtype=np.float32)
```

This creates a critical bug: when σ² is a scalar `s` repeated 512 times:

- **Mahalanobis term**: `-Σᵢ[(μ₁ᵢ - μ₂ᵢ)² / 2s]` = `-||μ₁ - μ₂||² / 2s` (correct)
- **Log penalty term**: `-Σᵢ[log(2s)]` = `-512 × log(2s)` (INCORRECT!)

### Impact

With typical σ² values (0.05 - 0.2), the log penalty term becomes:

- σ² = 0.05 → `-512 × log(0.1)` ≈ **+1180** (constant for all pairs)
- σ² = 0.1 → `-512 × log(0.2)` ≈ **+824** (constant for all pairs)

Meanwhile, the discriminative Mahalanobis term only varies by ~30-40 points between same-person and different-person pairs. Result: **the discriminative signal is drowned by a constant offset**.

This caused catastrophic clustering failures where all faces merged into a single "super-cluster" because MLS scores were essentially uniform.

## Decision

When σ² is detected to be a scalar (uniform across all dimensions), use a single-term MLS formula:

```python
# Scalar sigma: single log term, not 512
combined_sigma_sq = sigma1_sq + sigma2_sq  # scalar
squared_distance = np.sum((mu1 - mu2) ** 2)
mls = -squared_distance / combined_sigma_sq - np.log(combined_sigma_sq)
```

This produces:
- **One log term** instead of 512
- **Score range** where discriminative signal dominates
- **Proper uncertainty weighting** (higher σ² still reduces discrimination)

### Detection of Scalar Sigma

We use `np.allclose()` to check if all elements of σ² are equal:

```python
def _is_scalar_sigma(sigma_sq: np.ndarray, rtol: float = 1e-5) -> bool:
    return np.allclose(sigma_sq, sigma_sq[0], rtol=rtol)
```

If both σ₁² and σ₂² are scalars, use the single-term formula. Otherwise, fall back to the per-dimension formula for true PFE implementations.

## Expected Score Ranges (Post-Fix)

| Comparison Type | Squared Distance | MLS Score (σ²=0.05) |
|-----------------|------------------|---------------------|
| Identical faces | 0 | ~+2.3 (just log term) |
| Same person | 5-20 | -50 to -200 |
| Different person | 50-100+ | -500 to -1000+ |

The new score distribution should be **bimodal**: same-identity pairs cluster near 0, different-identity pairs cluster below -500.

## Clustering Threshold Adjustment

With the fixed MLS formula, clustering thresholds need recalibration:

- **Reference MLS**: `-log(2 × avg_σ²)` (single term, ~2 for σ²=0.05)
- **MLS_DROP_THRESHOLD**: 50 (faces must have MLS within 50 of identical-face score)

This means faces with MLS > (ref_mls - 50) ≈ -48 cluster together.

## Alternatives Considered

### 1. Switch to Cosine Similarity

Rejected. MLS with proper uncertainty weighting is the forensic standard. The bug was in implementation, not the algorithm choice.

### 2. Fix σ² to be Per-Dimension

Would require significant changes to the embedding pipeline (training a variance prediction head). Future consideration, but scalar σ² from quality signals is a valid approach.

### 3. Remove Log Penalty Entirely

Rejected. The log penalty prevents the trivial solution σ² → ∞. It must be present, just not multiplied by 512.

## Consequences

### Positive

- Clustering now correctly separates different identities
- MLS scores have meaningful interpretation
- Uncertainty weighting still functional (high σ² reduces discrimination appropriately)

### Negative

- All existing clustering thresholds need recalibration
- Must regenerate `identities.json` after this fix

### Neutral

- Per-dimension σ² path preserved for future true PFE implementation
