# ML Run Comparison: Baseline vs Reranker (longitudinal-shadow)

## Summary
| Metric | Baseline | Reranker (longitudinal-shadow) |
|--------|---------|---------|
| Total proposals | 470 | 470 |
| Target changes | — | 0 |
| New proposals | — | 0 |
| Removed proposals | 0 | — |
| Tier changes | — | 0 |

## Score Changes (same target)
- Proposals with identical scores: 470
- Proposals with score changes: 0

## Assessment
**Neutral** — Runs produce identical proposals. The reranker agrees with the baseline.

## Detailed Analysis

### Reranker Training Results
- **Best variant**: `distance_only` (temporal/kinship features did not improve)
- **Dataset**: 1,975 rows from 99 confirmed identities
- **Baseline top-1 recall**: 99.17% — already near-ceiling
- **Reranker top-1 recall**: 99.17% — no improvement possible
- **Phase 2 gate**: FAILED (age-gap ≥20yr improvement = 0.0%, needs ≥5%)
- **Reason**: Baseline is already too good for the reranker to improve on

### FB-147: Big Leon False Positives for Fox Family
- Only 1 Leon-related proposal exists: `Unidentified Person 0c75b968 → Big Leon Capeluto` at distance 0.9455 (HIGH)
- This proposal appears in BOTH baseline and reranker — the reranker did not suppress it
- **Verdict**: The reranker cannot address FB-147 because it reranks the top-5 candidates but doesn't filter cross-community proposals. Cross-community false positives need a community-aware filter (Phase 4 scope), not a reranker.

### Recommendation
**Do NOT activate the reranker** at this time:
1. The phase 2 gate failed — no measurable improvement
2. The `distance_only` feature set won, meaning temporal/kinship features add noise rather than signal
3. The baseline is already at 99.17% top-1 recall with only 99 confirmed identities
4. More confirmed identities (especially across age gaps) are needed before reranking can differentiate
5. Cross-community false positives like FB-147 require community-scoped filtering, not score reranking

### When to Revisit
- When confirmed identity count exceeds 200+ with age-gap diversity
- When Phase 5 (PRD-038) collects more Fox-family labels
- When cross-community matching becomes a priority
