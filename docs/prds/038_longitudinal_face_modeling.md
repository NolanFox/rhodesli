# PRD-038: Longitudinal Face Modeling

**Status**: PLANNED
**Priority**: P2
**Estimated effort**: 4-6 sessions across 5 workstreams
**Source**: User feedback Session 96e-cont6 — "Roland Fox has lots of pictures across life stages, we should be taking advantage of this data"
**Predecessor research**: AD-001 (multi-anchor), AD-034 (centroid rejected), AD-115/145 (LoRA), AD-092 (active learning), AD-126/149 (calibration), ADR-002 (temporal priors), Session 68 LoRA audit

## Problem Statement

Rhodesli has growing photo collections spanning 100+ years (1890s-1990s). Fox Family alone has many photos of the same people (e.g., Roland Fox) across childhood to adulthood. Google Photos handles this well — as you add more photos, identification gets better at all life stages. Rhodesli's current multi-anchor approach helps (more confirmed photos = better min-distance matching) but leaves significant improvement on the table.

**Current state**: Multi-anchor best-linkage (AD-001) with frozen InsightFace embeddings. AUC 0.9577 via isotonic calibration on 348 pairs. No age-awareness, no active learning loop, no embedding fine-tuning.

**Gap**: Adding more photos improves matching linearly (more anchors to compare against) but not exponentially (no model improvement, no temporal reasoning, no confidence weighting).

## 5 Improvement Workstreams

### WS-1: Confidence-Weighted Matching (ML-110, ML-115)
**What**: Weight anchor comparisons by face quality (detection score, embedding norm, image sharpness). Higher-quality faces get more influence in matching decisions. Also recalibrate similarity thresholds with the current (larger) confirmed dataset.

**Current**: `min(euclidean(face, anchor_i))` — all anchors weighted equally.
**Proposed**: `min(euclidean(face, anchor_i) * quality_penalty_i)` where quality_penalty reduces distance for high-quality anchors.

**Why not centroid averaging (AD-034)**: Centroid averaging was explicitly rejected — it creates "ghost vectors" that don't match any real face. A 1920s young face averaged with a 1960s old face produces a vector that matches neither. Multi-anchor with quality weighting is strictly better for heritage archives. Google Photos likely uses centroids for fast initial search at billion-scale, then refines with exemplar comparison — we don't need the speed optimization at our scale (< 10K faces).

**Data**: Detection scores range 0.65-0.92 (mean 0.85). Embedding norm variance is high (9.63-34.5). Currently display-only (AD-118), never used in matching.

**Effort**: LOW (1 session). Modify `compute_min_distance()` in `cluster_new_faces.py`.
**Expected impact**: +2-5% recall on marginal matches, better threshold calibration.

### WS-2: Age-Aware Clustering (ML-113, ML-116)
**What**: Use photo date estimates + GEDCOM birth years to apply soft penalties for age-impossible matches and stratify anchors by decade.

**Two sub-features**:
1. **Age-gap penalty**: `penalty = exp(-gap_years / 50)` when gap > 80 years. Multiplies distance to make impossible matches (baby in 1890 ≠ adult in 1990) less likely to trigger.
2. **Longitudinal anchor stratification**: Use best-quality faces from EACH DECADE for matching, not just best overall. Young-Leon and old-Leon cluster differently; both should be anchor pools.

**Prior research**: ADR-002 designed full temporal era priors (Victorian/Interwar/WWII bins, Bayesian penalties) but was never implemented. This is a simplified version.

**Data available**: 271 photos have Gemini date estimates. 67 GEDCOM birth years. `gemini_api_calls.response_summary['estimated_year']` from AD-159.

**Effort**: MEDIUM (1-2 sessions). Modify `cluster_new_faces.py` and `collect_identity_embeddings()`.
**Expected impact**: Eliminate era-impossible false positives. Better matching for people photographed across 30+ year spans.

### WS-3: Active Learning Loop (ML-112)
**What**: Surface uncertain face pairs to admin for review. Use confirm/reject decisions to accumulate hard negatives and improve calibration model over time.

**Current**: `rhodesli_ml/active_learning.py` has `find_uncertain_pairs()` — finds pairs near the decision boundary (0.4-0.6 distance). Foundation exists but never wired to UI.

**Proposed flow**:
1. After each clustering run, find top 10 most uncertain pairs
2. Surface as "Help Review These" section in sidebar or discoveries
3. Admin confirms or rejects → updates `negative_ids` on identity
4. Accumulated labels feed into next calibration re-run (WS-1)
5. Over time, the decision boundary sharpens precisely where it matters

**Google Photos parallel**: This is essentially what Google does when it asks "Is this the same person?" — each answer trains the model.

**Effort**: LOW (1 session). Wire `find_uncertain_pairs()` to sidebar, add confirm/reject buttons.
**Expected impact**: Continuous improvement. Each admin session makes the model slightly better. Compounds over time.

### WS-4: Embedding Fine-Tuning / LoRA (ML-114)
**What**: Fine-tune the InsightFace backbone on Rhodesli's confirmed identity pairs using LoRA (Low-Rank Adaptation).

**Session 68 LoRA Audit Results**:
- 221 positive pairs (minimum threshold met, ideal >= 500)
- Class imbalance Gini = 0.505 (ideal < 0.3) — top 3 identities account for 80% of pairs
- Verdict: "MARGINAL" — proceed with caution
- Recommended: inverse-frequency pair sampling, freeze most layers, fine-tune final 2-3 blocks

**What's changed since Session 68**: Fox Family collection adds ~636 photos with many repeat people (Roland Fox across childhood). If we confirm even 20 Fox Family identities, that could add 100+ positive pairs, pushing past the 350+ threshold.

**Why not full fine-tuning (AD-035)**: LoRA works on attention/linear layers; ResNet backbone has different adaptation dynamics. Full fine-tuning risks catastrophic forgetting. LoRA with PFE sigma_sq uncertainty-weighted contrastive loss is the right approach.

**Sequence (AD-145)**:
1. Reach 350+ positive pairs via admin confirmations
2. Apply inverse-frequency pair sampling for class balance
3. LoRA on final 2-3 blocks, freeze rest
4. Recalibrate isotonic regression on new embedding space
5. Validate on held-out identities (prevent overfitting to Capeluto family)

**Effort**: HIGH (2-3 sessions). Requires data preparation, training infrastructure, validation.
**Expected impact**: 3-8% AUC gain if properly regularized. Risk of overfitting.

### WS-5: Metadata Feature Expansion (ML-111)
**What**: Add non-visual signals to the similarity calibration model: date proximity, name similarity, co-occurrence patterns, GEDCOM relationship proximity.

**Current calibrator features**: `|embedding_a - embedding_b|`, element-wise product, quality diff, same-collection indicator.
**Proposed additions**:
- `date_proximity_score` — photos taken close in time more likely same era/person
- `name_similarity` — GEDCOM name fuzzy match score (already computed for GEDCOM search)
- `co_occurrence_count` — how many photos contain both faces (positive signal when > 0 and identities are different)
- `gedcom_relationship_distance` — family closeness in GEDCOM tree

**Google Photos parallel**: Google uses location, mutual contacts, date proximity, etc. We have GEDCOM + date estimates as unique advantages.

**Effort**: LOW-MEDIUM (1 session). Extend `_featurize_pair()` in `rhodesli_ml/similarity_calibration.py`.
**Expected impact**: AUC 0.957 → 0.965+. Each feature provides incremental signal.

## Implementation Sequence

| Session | Work | Depends On |
|---------|------|------------|
| N | WS-1: Confidence weighting + threshold recalibration | Nothing |
| N | WS-3: Wire active learning to UI | Nothing |
| N+1 | WS-5: Metadata feature expansion | WS-1 (calibrator) |
| N+1 | WS-2: Age-aware distance modulation | Date estimates exist |
| N+2 | Admin confirmation sprint (data collection for WS-4) | WS-3 (active learning helps) |
| N+3-4 | WS-4: LoRA fine-tuning | 350+ positive pairs |

WS-1/3 can run in parallel (session N). WS-2/5 can run in parallel (session N+1).

## Acceptance Criteria

- [ ] Matching quality improves measurably (benchmark on golden test set)
- [ ] No regression on existing confirmed identities
- [ ] Admin review flow shows uncertain pairs for labeling
- [ ] Upload of new photos leads to better-quality suggestions over time
- [ ] Photo date estimates influence matching for 50+ year time spans

## Out of Scope

- Real-time face recognition (AD-110 serving path contract — web requests never run heavy ML)
- Migration to pgvector (deferred until 5K+ embeddings)
- Full transformer backbone replacement (InsightFace ResNet is adequate)
- Cross-archive face matching (e.g., matching Fox Family to external databases)

## Metrics

- AUC on golden test set (currently 0.9577)
- Precision@recall=0.8 (currently ~87%)
- Admin review efficiency (matches confirmed per session)
- False positive rate for cross-era matches
