# Session 78 — Threshold Analysis: Big Leon, Nace, and Tier 2 Ceiling

## Context

AD-179 (Session 76a) established two-tier auto-clustering thresholds:
- Tier 1 (< 0.85): Auto-add to confirmed cluster as candidate
- Tier 2 (0.85 - 1.10): Surface as Discovery suggestion for admin review
- No match (>= 1.10): Ignore

These were calibrated against 982 within-cluster same-person pairs:
  mean=1.01, std=0.19, p5=0.70, p25=0.88

Session 76a noted that Big Leon's closest non-duplicate inbox match was
1.13+ and Nace's was 1.18+, both above Tier 2 ceiling. This analysis
investigates whether the Tier 2 ceiling should be raised.

## Per-Identity Within-Cluster Distance Analysis

Computed pairwise Euclidean distances for all confirmed identities with
2+ faces with embeddings (21 clusters, 982 total pairs).

### All Confirmed Clusters (sorted by max distance)

| Identity | Faces | Max Dist | Mean Dist | % > 1.10 |
|----------|-------|----------|-----------|----------|
| Victoria Capuano Capeluto | 15 | 1.4124 | 1.0842 | 45.7% |
| Nace Capeluto | 3 | 1.4095 | 1.2454 | 66.7% |
| Betty Capeluto | 12 | 1.3891 | 1.2172 | 78.8% |
| Big Leon Capeluto | 25 | 1.3824 | 1.0550 | 47.3% |
| Victoria Cukran Capeluto | 17 | 1.3312 | 1.0137 | 26.5% |
| Selma Capeluto | 9 | 1.2982 | 1.0111 | 22.2% |
| Anita Capeluto Franco | 3 | 1.2970 | 1.1377 | 66.7% |
| Vida Capeluto | 15 | 1.2621 | 0.9545 | 15.2% |
| Victor Capelluto | 8 | 1.2236 | 1.0288 | 60.7% |
| Leon Capeluto | 4 | 1.1874 | 1.0718 | 16.7% |
| Moise Capeluto | 18 | 1.1255 | 0.8479 | 0.7% |
| Laura Franco Capelluto | 5 | 1.0918 | 0.9223 | 0.0% |
| Regina Reina Israel Capeluto | 7 | 1.0860 | 0.8181 | 0.0% |
| Morris Mazal | 2 | 1.0093 | 1.0093 | 0.0% |
| Rica Moussafer Pizante | 2 | 1.0085 | 1.0085 | 0.0% |
| Isaac Franco | 2 | 0.9661 | 0.9661 | 0.0% |
| Betty Capeluto Fox | 3 | 0.9299 | 0.8891 | 0.0% |
| Zeb Capuano | 2 | 0.8863 | 0.8863 | 0.0% |
| Rosa Sedikaro | 2 | 0.8801 | 0.8801 | 0.0% |
| Morris Franco | 2 | 0.8651 | 0.8651 | 0.0% |
| Esther Diana Taranto Capouano | 2 | 0.2112 | 0.2112 | 0.0% |

### Key Finding

**11 of 21 confirmed clusters (52%) have max within-cluster distance
above the current Tier 2 ceiling of 1.10.** The Tier 2 ceiling is
provably too low for the majority of confirmed clusters.

### Big Leon Deep Dive (25 faces, 300 pairs)

- Max: 1.3824 (inbox_dd93163579df <-> Brass_Rail_Restaurant...)
- Mean: 1.0550
- Median: 1.0866
- Pairs > 1.10: 142/300 (47.3%)
- Top outlier pair: Image 031_compress:face1 is consistently the
  most distant face, appearing in all 10 largest within-cluster pairs

The face at Image 031_compress:face1 is likely a very different angle
or age from the other faces, but is confirmed as the same person.
Best-linkage distance from that face to the nearest other Big Leon face
is 1.13+, which means it would never be suggested by the current Tier 2.

### Nace Deep Dive (3 faces, 3 pairs)

- Max: 1.4095 (Image 983_compress:face0 <-> Image 961_compress:face1)
- Mean: 1.2454
- Only 1 of 3 pairs is below 1.10 (0.9641)
- The cluster is very spread, consistent with historical photos spanning
  decades (young vs old)

### Overall Distribution Summary

- Total within-cluster pairs: 982
- Mean: 1.0103, Std: 0.1882
- p95: 1.3144
- p99: 1.3764
- Max: 1.4124

## Recommendation

### Option A: Raise Tier 2 Ceiling to 1.30

**Rationale:**
- Covers p95 of within-cluster distances (1.3144)
- Would surface Big Leon's outlier face (1.13+) and Nace's (1.18+)
- 11 additional confirmed clusters' outlier pairs would be captured
- Still below max (1.41), so some legitimate pairs remain uncaptured

**Risk:**
- More false positives in suggestions (admin burden)
- Need to verify cross-person distance distribution doesn't overlap

### Option B: Raise to 1.40 (p99+)

**Rationale:**
- Captures nearly all legitimate within-cluster pairs
- Maximum within-cluster distance is 1.4124

**Risk:**
- Cross-person pairs at this distance are likely common
- Would flood admin with false-positive suggestions

### Option C: Keep at 1.10, Use Per-Identity Adaptive Thresholds

**Rationale:**
- 10 of 21 clusters have max <= 1.10 (tight clusters)
- Raising ceiling globally increases noise for tight clusters
- Per-identity thresholds based on existing cluster spread would be
  more precise

**Risk:**
- More complex implementation
- New clusters start with no spread data

### Recommended: Option A (Raise to 1.30)

The current ceiling misses 47% of Big Leon's within-cluster pairs.
A ceiling of 1.30 would capture p95 of the known same-person
distribution while keeping the suggestion volume manageable. This is
a Discovery suggestion (Tier 2), not an auto-add, so false positives
are reviewed by admin.

The per-identity adaptive approach (Option C) is technically superior
but premature given the current scale (60 confirmed identities).

## Data Provenance

- Source: data/identities.json (775 identities, 60 confirmed)
- Source: data/embeddings.npy (1061 face entries)
- Analysis date: 2026-02-28
- Session: 78, Track 3B
- Related: AD-179 (Two-Tier Auto-Clustering)
