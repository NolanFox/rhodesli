# PRD-038: Implementation Specs per Workstream

**Parent**: [docs/prds/038_longitudinal_face_modeling.md](../038_longitudinal_face_modeling.md)

---

## WS-1: Confidence-Weighted Matching (ML-110, ML-115)

### Code Changes
**File**: `scripts/cluster_new_faces.py`
- **Function**: `compute_min_distance()` (line ~85)
- **Current**: `min(euclidean(face, anchor_i))` — all anchors equal weight
- **Change**: `min(euclidean(face, anchor_i) / quality_weight_i)` where:
  ```python
  def quality_weight(det_score, emb_norm, avg_det=0.85, avg_norm=22.0):
      """Higher quality faces get weight > 1.0 (reduce effective distance)."""
      score_factor = det_score / avg_det  # range ~0.76-1.08
      norm_factor = min(emb_norm / avg_norm, 1.5)  # cap at 1.5x
      return (score_factor * norm_factor) ** 0.5  # sqrt dampening
  ```
- **Data source**: `det_score` and embedding norm from `embeddings.npy`
- **Current stats**: det_score range 0.65-0.92 (mean 0.85), norm range 9.63-34.5

**File**: `scripts/recalibrate.py` (NEW)
- Pull `calibration_pairs` from Supabase
- Retrain isotonic regression
- Export to `rhodesli_ml/artifacts/calibration_v1.pt`
- Report: pair count, AUC, threshold@90p, drift from previous

### Tests
- `test_quality_weighted_distance_prefers_high_quality_anchor`
- `test_quality_weight_range_bounded` (never < 0.5 or > 2.0)
- `test_recalibrate_cli_dry_run`
- `test_recalibrate_produces_valid_model`

### Acceptance Criteria
- [ ] High-quality anchors reduce effective distance by up to 30%
- [ ] Low-quality anchors increase effective distance by up to 50%
- [ ] No regression on existing golden test set (AUC >= 0.9577)
- [ ] `scripts/recalibrate.py --check` reports model freshness

---

## WS-2: Age-Aware Clustering (ML-113, ML-116)

### Code Changes
**File**: `scripts/cluster_new_faces.py`
- **Function**: `compute_min_distance()` — add age penalty term
- **New helper**:
  ```python
  def age_penalty(photo_year_a, photo_year_b, birth_year=None):
      """Soft penalty for large age gaps. Returns multiplier >= 1.0."""
      if photo_year_a is None or photo_year_b is None:
          return 1.0  # No penalty if dates unknown
      gap = abs(photo_year_a - photo_year_b)
      if gap <= 30:
          return 1.0  # Same generation, no penalty
      if gap <= 60:
          return 1.0 + (gap - 30) * 0.005  # Gradual: 1.0-1.15
      return 1.15 + (gap - 60) * 0.01  # Steeper: 1.15-1.55
      # Note: NOT exponential — heritage photos span 100+ years,
      # we don't want to kill matches entirely, just penalize
  ```
- **Data source**: `gemini_api_calls.response_summary['estimated_year']` (271 photos), GEDCOM birth years (67 people)

**File**: `scripts/cluster_new_faces.py` — `collect_identity_embeddings()`
- **Current**: Returns all anchors flat
- **Change**: Group anchors by decade, return best-quality per decade
  ```python
  def collect_identity_embeddings_stratified(identity, embeddings, photo_dates):
      """Return best-quality anchor per decade for longitudinal matching."""
      by_decade = defaultdict(list)
      for anchor_id in identity['anchor_ids']:
          emb = get_embedding(anchor_id, embeddings)
          year = photo_dates.get(anchor_id)
          decade = (year // 10) * 10 if year else 'unknown'
          by_decade[decade].append((anchor_id, emb, quality_score(emb)))
      # Return best quality per decade
      return [max(group, key=lambda x: x[2]) for group in by_decade.values()]
  ```

### Tests
- `test_age_penalty_no_dates_returns_1`
- `test_age_penalty_same_decade_returns_1`
- `test_age_penalty_80_year_gap_significant`
- `test_stratified_embeddings_one_per_decade`
- `test_stratified_prefers_high_quality`

### Acceptance Criteria
- [ ] Cross-era false positives reduced (1890s baby != 1990s adult)
- [ ] Roland Fox photos across life stages still cluster correctly
- [ ] Anchors stratified by decade (visual: identity page shows per-decade best)

---

## WS-3: Active Learning Loop (ML-112)

### Code Changes
**File**: `rhodesli_ml/active_learning.py` — `find_uncertain_pairs()` (exists, line ~45)
- **Current**: Finds pairs near decision boundary (distance 0.4-0.6)
- **Change**: Also rank by information gain (prefer pairs from under-represented identities)

**File**: `app/discoveries_routes.py` (or new section in sidebar)
- **New endpoint**: `GET /api/active-learning/pairs` → returns top 10 uncertain pairs
- **New UI**: "Help Review These" card in Discoveries or sidebar
- **Each pair shows**: Two face crops side by side, similarity score, "Same Person" / "Different Person" buttons
- **On action**: Calls `recalibration_hooks.on_face_merge()` or `on_match_reject()`

### User Flow
1. Admin opens Discoveries page
2. Below main discoveries, sees "Help Improve Matching" section
3. Shows pairs of faces the model is most uncertain about
4. Admin clicks "Same Person" or "Different Person"
5. Pair is logged to `calibration_pairs` table
6. Next clustering run benefits from this label
7. After 20+ new labels, local recalibration is recommended (Sentry alert)

### Tests
- `test_active_learning_returns_uncertain_pairs`
- `test_active_learning_excludes_already_labeled`
- `test_confirm_pair_inserts_calibration_pair`
- `test_reject_pair_inserts_with_weight_1_5`

### Acceptance Criteria
- [ ] Active learning pairs visible in UI
- [ ] Confirm/reject actions persist to `calibration_pairs`
- [ ] Pairs ordered by uncertainty (closest to decision boundary first)
- [ ] Already-labeled pairs excluded from future suggestions

---

## WS-4: LoRA Fine-Tuning (ML-114) — Data Growth Strategy

### Current Data Assessment
- 221 positive pairs (Session 68 audit) — MARGINAL
- Class imbalance Gini 0.505 (top 3 identities = 80% of pairs)
- Fox Family: ~636 photos, many repeat people (Roland Fox across decades)
- Threshold for confident training: 350+ pairs, Gini < 0.3

### Data Growth Strategy (3 phases)

**Phase 1: Grow from existing collections** (Nolan-driven)
- Confirm 20+ Fox Family identities → est. 100-150 new positive pairs
- Add more Rhodes community photos from online sources
- Add additional family branch archives (new communities)
- **Target**: 500+ positive pairs, 10+ identities with 5+ anchors each
- **Milestone check**: Run `python scripts/lora_data_audit.py` to assess readiness

**Phase 2: Initial LoRA training** (when data milestones met)
- Inverse-frequency pair sampling for class balance
- LoRA on final 2-3 ResNet blocks, freeze rest
- PFE sigma_sq uncertainty-weighted contrastive loss
- Train/val split: 80/20 stratified by identity
- Validation on held-out identities (not just held-out pairs)
- **Golden rule**: AUC on held-out set must be >= pre-LoRA baseline

**Phase 3: Continuous improvement** (as data grows)
| Data Milestone | Action | Expected Gain |
|---------------|--------|---------------|
| 350 pairs | First LoRA training (conservative, 2 blocks) | +2-4% AUC |
| 500 pairs | Retrain with more layers (3 blocks) | +1-2% AUC |
| 1000 pairs | Full LoRA with aggressive augmentation | +2-3% AUC |
| 2000 pairs | Evaluate full fine-tuning vs LoRA | Decision point |
| 5000+ pairs | Consider domain-specific backbone pre-training | Research |

**Continuous improvement workflow**:
```
Admin confirms identities → calibration_pairs grows
→ When milestone hit, `lora_data_audit.py` reports "READY for level N"
→ Run LoRA training locally (30-60 min)
→ Evaluate on golden test set
→ If AUC improved: deploy new embeddings, re-cluster, recalibrate
→ If AUC regressed: rollback, log finding, wait for more data
```

### Why NOT use external face datasets
- Our value IS our photos — heritage photos from 1890s-1990s have unique characteristics (fading, damage, formal poses, aging across decades) that standard face datasets (LFW, VGGFace2) don't capture
- External datasets would help with general face recognition but not with the specific domain shifts in heritage archives
- Risk of catastrophic forgetting: training on modern selfies could hurt performance on 1920s portraits
- **Exception**: If an open-source historical photo dataset exists (e.g., historical portrait collections), it could be valuable for pre-training before fine-tuning on our data

### Tests
- `test_lora_data_audit_reports_pair_count`
- `test_lora_data_audit_reports_gini`
- `test_lora_training_preserves_baseline_auc`
- `test_lora_rollback_on_regression`

### Acceptance Criteria
- [ ] `lora_data_audit.py` reports data readiness with clear READY/NOT_READY
- [ ] LoRA training script with automated golden test set evaluation
- [ ] Rollback mechanism if AUC regresses
- [ ] Continuous improvement milestones documented and alertable

---

## WS-5: Metadata Feature Expansion (ML-111)

### Code Changes
**File**: `rhodesli_ml/similarity_calibration.py` — `_featurize_pair()` (line ~120)
- **Current features**: `|emb_a - emb_b|`, element-wise product, quality diff, same-collection indicator
- **New features**:
  ```python
  def _featurize_pair_extended(emb_a, emb_b, meta_a, meta_b):
      base = _featurize_pair(emb_a, emb_b)  # existing
      extended = {
          'date_proximity': 1.0 / (1.0 + abs(meta_a.year - meta_b.year) / 10),
          'name_similarity': fuzzy_name_score(meta_a.name, meta_b.name),
          'co_occurrence': count_shared_photos(meta_a.id, meta_b.id),
          'gedcom_distance': gedcom_path_length(meta_a.id, meta_b.id),
          'same_community': int(meta_a.community == meta_b.community),
      }
      return {**base, **extended}
  ```
- **Data sources**: `date_labels` table, `gedcom_individuals`, `photo_communities`

### Tests
- `test_date_proximity_same_year_returns_1`
- `test_date_proximity_50_years_returns_low`
- `test_metadata_features_graceful_when_missing`
- `test_calibrator_with_metadata_features_trains`

### Acceptance Criteria
- [ ] At least 3 new features added to calibrator
- [ ] Features gracefully degrade when metadata is missing (return 0 or neutral)
- [ ] AUC improvement on golden test set (target: 0.957 → 0.965+)
