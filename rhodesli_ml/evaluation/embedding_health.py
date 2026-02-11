"""Embedding health checks: detect drift, outliers, and distribution shifts.

Monitors the embedding space for signs of degradation:
- Distribution shift (mean/variance of pairwise distances)
- Outlier faces (embeddings far from any cluster)
- Norm anomalies (embeddings with unusual L2 norms)
"""

# Placeholder — will be implemented when embedding monitoring is needed.
#
# Checks:
# - mean_pairwise_distance: should be stable across ingestion batches
# - outlier_count: faces > 2 stddev from nearest cluster centroid
# - norm_distribution: L2 norms should cluster around 1.0 for normalized embeddings
