# ADR-002: Temporal Priors for Era-Constrained Matching

**Status:** Accepted
**Date:** 2026-01-28
**Author:** Rhodesli Project
**Depends On:** ADR-001 (MLS)

## Context

Historical photo matching faces a fundamental constraint: people cannot appear in photographs taken before their birth or after their death. Two faces from incompatible eras (e.g., 1895 and 1945) cannot be the same person unless we're matching across a 50+ year lifespan—which is possible but increasingly improbable.

Without temporal constraints, MLS can produce false positives between visually similar faces from different eras. A young man from 1900 may closely resemble an unrelated young man from 1940.

We need temporal priors that:
1. Estimate the era of each photograph
2. Apply Bayesian penalties for cross-era matches
3. Treat era constraints as HARD priors, not cosmetic filters

## Decision

We implement **CLIP-based era classification** with **Bayesian temporal penalties** integrated into the MLS scoring pipeline.

### Era Bins

We define three discrete era bins based on photographic technology and fashion changes:

| Era | Years | Visual Characteristics |
|-----|-------|----------------------|
| Victorian-Edwardian | 1890–1910 | Sepia tones, formal dress, stiff poses, carte de visite format |
| Interwar Early | 1910–1930 | Black & white, WWI/1920s fashion, some candid shots |
| Interwar Late | 1930–1950 | Improved contrast, 1930s-40s fashion, war photography |

### Era Classification with CLIP

We use CLIP (Contrastive Language-Image Pre-training) to classify photographs into era bins. CLIP can match images to text descriptions without fine-tuning.

**Text Prompts for Era Classification:**
```python
ERA_PROMPTS = {
    "1890-1910": [
        "a Victorian era photograph from the 1890s",
        "an Edwardian era photograph from the 1900s",
        "a sepia toned formal portrait from the late 1800s",
        "a carte de visite photograph",
    ],
    "1910-1930": [
        "a photograph from the 1910s or 1920s",
        "a World War I era photograph",
        "a 1920s flapper era photograph",
        "a black and white photograph from the interwar period",
    ],
    "1930-1950": [
        "a photograph from the 1930s or 1940s",
        "a World War II era photograph",
        "a 1940s photograph",
        "a Great Depression era photograph",
    ],
}
```

**Classification Output:**
```python
@dataclass
class EraEstimate:
    era: str                    # "1890-1910", "1910-1930", or "1930-1950"
    probabilities: dict[str, float]  # P(era) for each bin
    confidence: float           # max(probabilities) - second highest
```

### Bayesian Temporal Penalty

The temporal penalty modifies MLS based on era compatibility:

```
MLS_temporal(f₁, f₂) = MLS(f₁, f₂) + log(P(same_person | era₁, era₂))
```

Since MLS is a log-likelihood, we add the log of the temporal prior.

**Penalty Matrix:**

| era₁ \ era₂ | 1890-1910 | 1910-1930 | 1930-1950 |
|-------------|-----------|-----------|-----------|
| 1890-1910   | 0.0       | -2.0      | -10.0     |
| 1910-1930   | -2.0      | 0.0       | -2.0      |
| 1930-1950   | -10.0     | -2.0      | 0.0       |

**Interpretation:**
- **Same era (0.0):** No penalty—normal MLS applies
- **Adjacent eras (-2.0):** Mild penalty—possible if person spans eras (e.g., photo at age 20 and age 40)
- **Non-adjacent eras (-10.0):** Severe penalty—60+ year span is extremely unlikely

The log-space penalty of -10.0 corresponds to a probability multiplier of ~0.00005, effectively eliminating matches.

### Uncertainty-Aware Era Matching

Era classification has uncertainty. When era confidence is low, we should not aggressively penalize:

```python
def compute_temporal_penalty(era1: EraEstimate, era2: EraEstimate) -> float:
    """
    Compute expected temporal penalty under era uncertainty.

    Returns weighted average of penalties based on era probabilities.
    """
    penalty = 0.0
    for e1, p1 in era1.probabilities.items():
        for e2, p2 in era2.probabilities.items():
            penalty += p1 * p2 * PENALTY_MATRIX[e1][e2]
    return penalty
```

This marginalization ensures:
- High-confidence era estimates → sharp penalties
- Low-confidence era estimates → smoothed penalties

### Integration with MLS

The final temporal-aware MLS:

```python
def mls_with_temporal(
    mu1, sigma_sq1, era1,
    mu2, sigma_sq2, era2
) -> float:
    base_mls = mutual_likelihood_score(mu1, sigma_sq1, mu2, sigma_sq2)
    temporal_penalty = compute_temporal_penalty(era1, era2)
    return base_mls + temporal_penalty
```

## Alternatives Considered

### 1. Hard Era Filtering
**Rejected.** Simply filtering out cross-era matches loses nuance. A person photographed in 1908 and 1932 would be rejected despite a plausible 24-year gap.

### 2. Metadata-Based Dating
**Rejected for now.** Requires structured metadata that historical photos often lack. CLIP provides visual dating when metadata is absent.

### 3. Continuous Year Estimation
**Considered for future.** Instead of discrete bins, estimate a continuous year with uncertainty (e.g., 1925 ± 10 years). More principled but harder to calibrate.

### 4. No Temporal Constraints
**Rejected.** Leads to false positives between visually similar faces from incompatible eras.

## Consequences

### Positive
- Eliminates impossible matches (1895 ↔ 1945)
- Maintains probabilistic framework (soft penalties, not hard filters)
- Uncertainty-aware: low-confidence era estimates don't over-penalize
- Works without metadata using visual features

### Negative
- CLIP adds computational cost and model weight dependency
- Era classification may fail on unusual photographs
- Discrete bins lose precision (1909 and 1911 are in different bins)

### Risks
- CLIP may hallucinate era for photos with ambiguous visual cues
- Penalty matrix values are heuristic, may need calibration

## Open Questions

1. **Penalty calibration:** Are -2.0 and -10.0 the right values? Need empirical testing on labeled data.

2. **Lifespan modeling:** Should we model plausible age ranges? A 1890 baby photo matching a 1940 adult is possible; two 1890 and 1940 baby photos are not.

3. **Regional variation:** Fashion/photography evolved differently across regions. A 1920 photo from rural America may look like 1900 from urban Europe.

4. **CLIP model selection:** Which CLIP variant (ViT-B/32, ViT-L/14, etc.) works best for historical photos?

## References

- OpenAI CLIP: Learning Transferable Visual Models From Natural Language Supervision
- ADR-001: Mutual Likelihood Score for Probabilistic Face Matching
