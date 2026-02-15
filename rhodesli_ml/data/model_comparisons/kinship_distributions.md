# Kinship Distance Distributions

**Date:** 2026-02-15 | **Decision:** AD-067

## Summary

Empirical distance distributions computed from 46 confirmed identities
in the Rhodesli face archive (512-dim PFE embeddings, Euclidean distance).

## Three Distributions

### SAME PERSON (n=959 pairs, 18 multi-face identities)

Intra-identity face pairs: faces confirmed to be the same person.

```
Distance:  0.2    0.4    0.6    0.8    1.0    1.2    1.4
           |------|------|------|------|------|------|
           ▓                                              min=0.21
                         ▓▓▓▓▓                            P5=0.71
                               ▓▓▓▓▓▓▓▓▓                 P25=0.88
                                       ████               P50=1.01
                                           ▓▓▓▓▓▓▓       P75=1.16
                                                  ▓▓▓     P95=1.31
                                                    ▓     max=1.41

Mean: 1.01  Std: 0.19
```

Wide spread reflects 60+ year age spans (child/adult photos of the same person).
Pairs near 0.2-0.4 are same-era, similar-pose photos. Pairs near 1.3-1.4 are
extreme age differences (e.g., Big Leon Capeluto as a young man vs elderly).

### SAME FAMILY (n=385 pairs, 13 surname groups)

Cross-identity pairs sharing a surname variant group (e.g., Capeluto family).

```
Distance:  0.2    0.4    0.6    0.8    1.0    1.2    1.4
           |------|------|------|------|------|------|
                                            ▓▓             P5=1.21
                                              ▓▓▓▓▓       P25=1.30
                                                ████      P50=1.35
                                                  ▓▓▓     P75=1.39
                                                    ▓     P95=1.43

Mean: 1.34  Std: 0.07
```

### DIFFERENT PERSON (n=605 pairs, different surname groups)

Cross-identity pairs from different families.

```
Distance:  0.2    0.4    0.6    0.8    1.0    1.2    1.4
           |------|------|------|------|------|------|
                                             ▓▓            P5=1.26
                                              ▓▓▓▓▓       P25=1.33
                                                ████      P50=1.37
                                                  ▓▓▓     P75=1.40
                                                    ▓▓    P95=1.45

Mean: 1.37  Std: 0.06
```

## Key Finding: Family Resemblance is Weak

**Cohen's d (same_person vs different_person): 2.54** — very strong separation.
Same-person pairs are clearly distinguishable from different people.

**Cohen's d (same_family vs different_person): 0.43** — small effect size.
Family resemblance is barely detectable in embedding space. The same_family
and different_person distributions overlap almost completely.

This means:
- Face embeddings are excellent at identity matching (d=2.54)
- Face embeddings are poor at detecting family relationships (d=0.43)
- Claiming "family resemblance" based on embedding distance alone would
  produce many false positives (precision < 60%)

## Recommended Thresholds

Based on the same_person distribution (where we have strong signal):

| Tier | Threshold | Source | Interpretation |
|------|-----------|--------|----------------|
| Strong Match | < 1.163 | same_person P75 | Very likely the same person |
| Possible Match | < 1.315 | same_person P95 | Likely same person (age/pose variation) |
| Similar Features | < 1.365 | different_person P25 | Similar features, identity uncertain |

Above 1.365: no meaningful facial similarity signal.

## Comparison with Existing Thresholds (AD-013)

| AD-013 Tier | Distance | Kinship-Calibrated Equivalent |
|-------------|----------|------------------------------|
| VERY HIGH | < 0.80 | Within same_person P5-P25 (definite match) |
| HIGH | < 1.05 | Near same_person P50 (strong match) |
| MODERATE | < 1.15 | Near same_person P75 (good match with variation) |
| LOW | < 1.25 | Near same_person P90 (possible with extreme variation) |

The AD-013 thresholds (from golden set precision/recall) are more conservative
than the kinship-calibrated thresholds, which is appropriate for automated
merge suggestions. The compare tool can use the wider thresholds because
a human is always reviewing the results.

## Methodology

1. Load all 46 confirmed, non-merged identities
2. For each multi-face identity (18 of 46), compute all intra-identity pairwise
   Euclidean distances — these are SAME_PERSON pairs (959 total)
3. For each cross-identity pair with matching surname variant group, compute
   best-linkage (min) distance — these are SAME_FAMILY pairs (385 total)
4. For each cross-identity pair with different surname groups, compute
   best-linkage distance — these are DIFFERENT_PERSON pairs (605 total)
5. Compute distribution statistics and derive thresholds

**Assumptions:**
- Shared surname ≈ same family (heuristic, not always true for married names)
- Surname variants from data/surname_variants.json (13 groups)
- Best-linkage (min distance) between identity pairs
- Heritage archive context: photos span 1900s-2000s

**Script:** `python -m rhodesli_ml.analysis.kinship_calibration`
**Output:** `rhodesli_ml/data/model_comparisons/kinship_thresholds.json`
