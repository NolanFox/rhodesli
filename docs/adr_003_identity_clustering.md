# ADR-003: Identity Clustering with MLS and Temporal Priors

**Status:** Accepted
**Date:** 2026-01-28
**Author:** Rhodesli Project
**Depends On:** ADR-001 (MLS), ADR-002 (Temporal Priors)

## Context

With Probabilistic Face Embeddings (PFE) and temporal priors in place, we need to cluster faces into Identity Groups. Each group represents faces believed to be the same person across different photographs.

Requirements:
1. Use MLS + temporal penalty as the similarity metric
2. Produce stable clusters across re-runs (deterministic)
3. Express match confidence as probability ranges, not point estimates

## Decision

We implement **Agglomerative Hierarchical Clustering** with MLS-based distance and a fixed linkage threshold.

### Distance Metric

We convert MLS (higher = more similar) to a distance metric:

```python
distance(f1, f2) = -mls_with_temporal(f1, f2)
```

Negation converts similarity to distance (higher MLS → lower distance).

### Clustering Algorithm

**Agglomerative clustering** with:
- **Linkage:** Complete (maximum distance within cluster)
- **Threshold:** Fixed at -500 (corresponds to MLS > 500 for same identity)
- **Deterministic:** No random initialization, sorted input order

Complete linkage ensures all members of a cluster are mutually similar, preventing "chaining" where distant faces connect through intermediates.

### Match Probability Ranges

For each identity cluster, we compute the range of pairwise MLS scores:

```python
def compute_match_range(cluster_faces: list[PFE]) -> tuple[float, float]:
    """Return (min_mls, max_mls) for all pairs in cluster."""
    scores = []
    for i, f1 in enumerate(cluster_faces):
        for f2 in cluster_faces[i+1:]:
            score = mls_with_temporal(f1, f2)
            scores.append(score)
    return (min(scores), max(scores)) if scores else (0, 0)
```

We then convert MLS to approximate match probability using a calibrated sigmoid:

```python
def mls_to_probability(mls: float) -> float:
    """Convert MLS to [0, 1] probability estimate."""
    # Calibration: MLS=0 → 50%, MLS=-500 → ~1%, MLS=500 → ~99%
    return 1 / (1 + np.exp(-mls / 100))
```

This produces ranges like "82%-91%" for uncertain matches.

### Stability Guarantee

To ensure clusters are identical across re-runs:
1. Sort faces by filepath before clustering
2. Use deterministic distance matrix computation
3. No random seeds or stochastic algorithms

## Alternatives Considered

### 1. DBSCAN
**Rejected.** Sensitive to epsilon parameter, can produce varying cluster counts. Not suitable for small datasets where we want explicit control.

### 2. K-Means
**Rejected.** Requires specifying k (number of identities) upfront, which is unknown. Also non-deterministic due to random initialization.

### 3. Cosine Similarity Threshold
**Rejected per ADR-001.** Cosine similarity hides uncertainty. MLS with PFE is required.

## Consequences

### Positive
- Deterministic, reproducible clusters
- Complete linkage prevents false groupings via chaining
- Probability ranges communicate uncertainty honestly
- Integrates naturally with MLS + temporal priors

### Negative
- Complete linkage can be conservative (may under-cluster)
- Fixed threshold may not suit all datasets
- Probability calibration is heuristic, not learned

### Risks
- Threshold of -500 is a guess; may need tuning on labeled data
- Small clusters (2-3 faces) have high variance in match ranges

## Open Questions

1. **Threshold calibration:** What MLS threshold optimally separates same-person from different-person pairs?

2. **Singleton handling:** How to display faces that don't cluster with anyone? (Show as "Unmatched" or "Unique Identity")

3. **Cluster merging:** Should we allow user feedback to merge/split clusters?
