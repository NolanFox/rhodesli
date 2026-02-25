# LoRA Training Data Audit

**Date:** 2026-02-25
**Context:** Session 68 prep -- assess readiness for InsightFace LoRA fine-tuning
**Data snapshot:** identities.json (775 records), embeddings.npy (1061 entries)

---

## 1. Identity State Breakdown

| State | Count | Notes |
|-------|-------|-------|
| INBOX | 403 | New, unreviewed |
| SKIPPED | 203 | Deferred during triage |
| CONFIRMED | 54 | Admin-verified |
| CONTESTED | 2 | Conflicting assignments |
| MERGED (inactive) | 113 | Merged into other identities |
| **Total** | **775** | 662 active |

## 2. Face Assignment Summary (non-merged identities)

| Category | Count |
|----------|-------|
| Anchor faces (confirmed) | 573 |
| Candidate faces (proposed) | 284 |
| Negative faces (rejected) | 54 |
| Total embeddings in .npy | 1061 |

Note: 573 anchor faces across 31 confirmed identities. Remaining 23 confirmed
identities have 0 anchors (name confirmed but no face confirmed).

## 3. Positive Pair Analysis

Positive pairs come from confirmed identities with 2+ anchor faces. Each pair
of anchors within the same identity is one positive training pair.

**Identities with 2+ anchors (8 of 54 confirmed):**

| Identity | Anchors | Photos | Positive Pairs | Candidates |
|----------|---------|--------|----------------|------------|
| Big Leon Capeluto | 13 | 13 | 78 | 12 |
| Moise Capeluto | 11 | 11 | 55 | 7 |
| Victoria Cukran Capeluto | 10 | 10 | 45 | 7 |
| Victoria Capuano Capeluto | 7 | 7 | 21 | 8 |
| Betty Capeluto | 5 | 5 | 10 | 7 |
| Selma Capeluto | 5 | 5 | 10 | 4 |
| Zeb Capuano | 2 | 2 | 1 | 0 |
| Esther Diana Taranto Capouano | 2 | 2 | 1 | 0 |
| **Total** | **55** | **55** | **221** | **45** |

Key positive: every anchor comes from a unique photo (no same-photo pairs,
which would be trivially similar). This means all 221 pairs represent genuine
cross-photo identity matching -- high-quality training signal.

## 4. Negative Pair Analysis

Negative pairs come from two sources:
1. **Explicit rejections**: faces in `negative_ids` paired with anchors of that identity
2. **Cross-identity**: anchors from different confirmed identities

| Source | Pairs | Notes |
|--------|-------|-------|
| Explicit (anchor x negative_id) | 251 | 54 rejected faces across 27 identities |
| Cross-identity (different confirmed people) | 2,782 | 31 identities with anchors |
| **Total** | **3,033** | |

Top identities with explicit negatives: Moise Capeluto (13), Victor Capelluto (6),
Big Leon Capeluto (4), Victoria Cukran Capeluto (2).

## 5. Face Quality Assessment

Embedding format: PFE (Probabilistic Face Embeddings) with `mu` (512-dim mean)
and `sigma_sq` (512-dim uncertainty). This is ideal for LoRA since uncertainty
estimates can weight training pairs.

**Confirmed anchor quality (n=78):**

| Metric | Value |
|--------|-------|
| Quality min | 17.87 |
| Quality max | 27.92 |
| Quality mean | 23.57 |
| Quality median | 23.71 |
| Quality stdev | 1.91 |
| High quality (>=30) | 0 (0%) |
| Medium quality (15-30) | 78 (100%) |
| Low quality (<15) | 0 (0%) |

All confirmed faces fall in the medium-quality band (15-30). No faces are below
the low-quality threshold. Detection scores range 0.65-0.92 (mean 0.85).

**All embeddings quality (n=1061):** min=11.63, max=30.40, mean=23.56.
Confirmed faces are representative of the overall quality distribution.

**Missing embeddings:** 0 of 78 confirmed anchor faces. All have valid embeddings.

## 6. Class Imbalance

**Anchor distribution across confirmed identities (31 with >=1 anchor):**

| Anchors | Identities | Cumulative Pairs |
|---------|------------|------------------|
| 1 | 23 | 0 |
| 2 | 2 | 2 |
| 5 | 2 | 22 |
| 7 | 1 | 43 |
| 10 | 1 | 88 |
| 11 | 1 | 143 |
| 13 | 1 | 221 |

**Gini coefficient: 0.505** -- moderate imbalance. Three identities (Big Leon,
Moise, Victoria Cukran) contribute 178 of 221 positive pairs (80.5%).

Imbalance mitigation for LoRA: pair sampling with inverse-frequency weighting
or capping pairs per identity at ~20.

## 7. Promotable Candidates (Quick Wins)

Confirming candidates for single-anchor identities would boost positive pairs:

| Identity | Current Anchors | Candidates | Pairs if Promoted |
|----------|----------------|------------|-------------------|
| Victor Capelluto | 1 | 7 | 28 |
| Laura Franco Capelluto | 1 | 4 | 10 |
| Betty Capeluto Fox | 1 | 2 | 3 |
| Rica Moussafer Pizante | 1 | 1 | 1 |
| Morris Franco | 1 | 1 | 1 |
| Isaac Franco | 1 | 1 | 1 |

Additionally, 23 confirmed identities have 0 anchors but have candidates
(Vida Capeluto: 15, Leon Capeluto: 4, Nace Capeluto: 3, etc.).

**If all 6 promotable single-anchor identities had candidates confirmed:**
+44 positive pairs -> 265 total.

**If Vida Capeluto's 15 candidates were anchored:** +105 pairs -> 370 total.

## 8. Future Potential from Non-Confirmed Identities

42 non-confirmed identities have 2+ faces (candidates or anchors combined).
If verified and confirmed: ~103 additional positive pairs.

Combined with current 221 + promotable 44 = ~368 achievable pairs with
moderate admin effort.

## 9. Comparison with Existing Calibration

The isotonic regression calibration (AD-149) was trained on 348 pairs
(221 match + 127 non-match) and achieved AUC=0.9577. LoRA fine-tuning
is more data-hungry than calibration since it modifies model weights
rather than fitting a post-hoc transform.

## 10. Readiness Verdict

| Criterion | Threshold | Current | Status |
|-----------|-----------|---------|--------|
| Positive pairs (minimum) | >= 100 | 221 | PASS |
| Positive pairs (ideal) | >= 500 | 221 | FAIL |
| Negative pairs (minimum) | >= 100 | 3,033 | PASS |
| Negative pairs (ideal) | >= 500 | 3,033 | PASS |
| Embedding quality | All >= 15 | 100% >= 15 | PASS |
| Missing embeddings | 0 | 0 | PASS |
| Cross-photo diversity | Each anchor from unique photo | YES | PASS |
| Class balance (Gini < 0.3) | < 0.3 | 0.505 | FAIL |

### VERDICT: MARGINAL -- Proceed with Caution

The dataset meets minimum thresholds for LoRA fine-tuning but has two concerns:

1. **Positive pairs below ideal**: 221 pairs is 2x the minimum but less than
   half the ideal. Risk of overfitting, especially with 3 identities dominating.

2. **Class imbalance**: 80% of pairs come from 3 of 8 multi-anchor identities.
   The model may learn family-specific features rather than general face recognition.

### Recommendations

**Before training:**
1. Admin review of Victor Capelluto (7 candidates) and Vida Capeluto (15 candidates)
   -- these two alone could add ~133 pairs, bringing total to ~354.
2. Review Big Leon's 12 candidates -- confirming even half adds 55+ pairs.

**During training:**
3. Use inverse-frequency pair sampling to mitigate class imbalance.
4. Cap pairs per identity at 20-25 to prevent overfitting to top identities.
5. Use PFE sigma_sq for uncertainty-weighted contrastive loss.
6. Apply heavy data augmentation (random crops, color jitter, horizontal flip).
7. Freeze all layers except final 2-3 blocks to prevent catastrophic forgetting.

**After training:**
8. Recalibrate isotonic regression on the new embedding space.
9. Compare AUC before/after on a held-out validation set (use 80/20 split).
10. Monitor for regression on low-representation identities.

**Data collection priority (sorted by expected pair yield):**
- Vida Capeluto: 15 candidates -> 105 pairs
- Big Leon candidates: 12 candidates -> up to 300 pairs (with existing 13 anchors)
- Victor Capelluto: 7 candidates -> 28 pairs
- Victoria Capuano candidates: 8 candidates -> up to 105 pairs (with existing 7)
