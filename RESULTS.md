# LoRA Training Data Audit Results

**Date:** 2026-02-25
**Full report:** `docs/analysis/lora_training_data_audit.md`

## Summary

| Metric | Value |
|--------|-------|
| Total identity records | 775 (662 active, 113 merged) |
| Confirmed identities | 54 (8 with 2+ anchors) |
| Total anchor faces | 573 |
| Same-identity positive pairs | **221** |
| Cross-identity negative pairs | **3,033** |
| Embedding quality (confirmed) | 100% in medium band (17.9-27.9) |
| Missing embeddings | 0 |
| Class imbalance (Gini) | 0.505 (moderate) |

## Verdict: MARGINAL -- Proceed with Caution

The dataset **meets minimum thresholds** (100+ positive, 100+ negative) but falls
short of ideal (500+) on positive pairs. Three identities (Big Leon, Moise,
Victoria Cukran) contribute 80% of positive pairs.

## Key Findings

1. **221 positive pairs** from 8 multi-anchor identities, all from unique photos.
2. **3,033 negative pairs** (251 explicit + 2,782 cross-identity) -- strong.
3. **PFE embeddings** (mu + sigma_sq, 512-dim) -- uncertainty estimates available
   for weighted contrastive loss.
4. **Class imbalance** is the primary risk -- pair sampling strategy needed.

## Recommendations Before Training

1. **Admin review priority**: Confirm candidates for Victor Capelluto (+28 pairs),
   Vida Capeluto (+105 pairs), Big Leon candidates (+up to 300 pairs).
2. Use inverse-frequency pair sampling and per-identity pair caps (20-25).
3. Freeze all but final 2-3 InsightFace blocks.
4. Recalibrate isotonic regression after training.

## Quick-Win Actions (Admin Review)

Confirming candidates for just 3 identities could boost positive pairs from
221 to ~500+, crossing the ideal threshold:
- Vida Capeluto: 15 candidates -> +105 pairs
- Big Leon Capeluto: 12 candidates -> +up to 300 pairs
- Victor Capelluto: 7 candidates -> +28 pairs
