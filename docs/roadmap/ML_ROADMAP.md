# ML Roadmap

ML-specific development plan for Rhodesli. For overall priorities, see [ROADMAP.md](../../ROADMAP.md).

---

## Current ML Stack

| Component | Technology | Status |
|-----------|------------|--------|
| Face detection | InsightFace (buffalo_l) | Production |
| Face embeddings | AdaFace (PFE, 512-dim) | Production |
| Face matching | Cosine distance + calibrated thresholds | Production |
| Date estimation | CORAL + EfficientNet-B0 | Production (decade-level) |
| Date labeling | Gemini 3 Flash (evidence-first prompt) | 250 photos labeled |
| Birth year estimation | Weighted aggregation + MAD outlier filtering | Production (32/46 identities) |
| Year estimation tool | core/year_estimation.py (scene + face evidence) | Production V1 |
| Experiment tracking | MLflow | Initialized |

---

## Completed ML Work

### Face Matching Pipeline
- [x] ML-004: Dynamic threshold calibration from confirmed/rejected pairs (2026-02-09, AD-013)
- [x] ML-005: Post-merge re-evaluation -- inline suggestions for nearby faces (2026-02-10)
- [x] ML-006: Ambiguity detection -- margin-based flagging when top matches within 15% (2026-02-10)
- [x] ML-010: Golden set rebuild (90 mappings, 23 identities) (2026-02-09)
- [x] ML-011: Golden set diversity analysis -- script + dashboard section (2026-02-10)
- [x] ML-012: Golden set evaluation (4005 pairs, sweep 0.50-2.00) (2026-02-09)
- [x] ML-013: Evaluation dashboard at /admin/ml-dashboard (2026-02-10)
- [x] ML-021: Calibrated confidence labels (VERY HIGH/HIGH/MODERATE/LOW) (2026-02-09)
- [x] ML-065: Kinship calibration -- empirical thresholds from 959 same-person, 385 same-family, 605 different-person pairs (2026-02-15)

### Date Estimation Pipeline
- [x] ML-040: CORAL ordinal regression training on EfficientNet-B0 backbone (2026-02-13, AD-039-045)
- [x] ML-041: Gemini evidence-first date labeling with cultural lag adjustment (2026-02-13, AD-041-042)
- [x] ML-042: Regression gate -- adjacent accuracy >=0.70, MAE <=1.5 (2026-02-13)
- [x] ML-043: MLflow experiment tracking initialized (2026-02-13)
- [x] ML-044: Scale-up Gemini labeling -- 250 photos with multi-pass retry (2026-02-14, AD-053)
- [x] ML-045: Temporal consistency auditor -- birth/death/age cross-checks (2026-02-14, AD-054)
- [x] ML-046: Search metadata export -- full-text search index from labels (2026-02-14, AD-055)
- [x] ML-047: CORAL model retrain -- 250 labels (+59% data), MLflow tracked (2026-02-14)
- [x] ML-050: Date UX integration -- decade + confidence on photo viewer, admin override (2026-02-14)

### Birth Year & Year Estimation
- [x] Birth year estimation pipeline (Session 34): median + MAD outlier filtering, bbox x-coordinate sorting
- [x] 32 estimates from 46 confirmed identities (3 HIGH, 6 MEDIUM, 23 LOW) (2026-02-15)
- [x] Year Estimation Tool V1 at /estimate (Session 46): per-face evidence, scene evidence, confidence (2026-02-18)
- [x] core/year_estimation.py -- weighted aggregation, bbox ordering, scene fallback (2026-02-18)

---

## Open ML Work

### Date Pipeline Integration (Priority: HIGH)
- [ ] ML-051: Date label pipeline -- integrate generate_date_labels.py into upload orchestrator
- [ ] ML-052: New upload auto-dating -- run date estimation on newly uploaded photos
- [ ] ML-053: Multi-pass Gemini -- low-confidence re-labeling with Flash model

### User Feedback Loop (Priority: MEDIUM)
- [ ] ML-001: User actions feed back to ML predictions
- [ ] FE-040-043: Skipped faces workflow for non-admin users

### Model Improvements (Priority: LOW, Phase F)
- [ ] ML-030: ArcFace evaluation against current AdaFace
- [ ] ML-031: Ensemble approach (multi-model voting)
- [ ] ML-032: Fine-tuning on domain-specific heritage photos

---

## Key ML Findings

### Kinship Calibration (AD-067, Session 32)
- Same-person pairs: mean distance 0.18, n=959
- Same-family pairs: mean distance 0.43, n=385
- Different-person pairs: mean distance 0.52, n=605
- Family resemblance NOT reliably separable from different-person in embedding space
- Conclusion: face matching works for identity, NOT for family relationship detection

### Date Estimation Accuracy
- CORAL model: decade-level accuracy, heritage-specific augmentations help
- Gemini labeling: evidence-first prompt with cultural lag produces reasonable estimates
- Birth year estimates: 32/46 identities, confidence correlates with number of photo appearances
- Year estimation V1: weighted aggregation of face-level and scene-level evidence

### Threshold Calibration (AD-013)
- Optimal distance threshold: 1.00 for 100% precision on golden set
- 4005 evaluation pairs from sweep 0.50-2.00
- Confidence labels: VERY HIGH (<0.6), HIGH (0.6-0.8), MODERATE (0.8-1.0), LOW (1.0-1.2)

---

## Decision Provenance
All ML decisions documented in `docs/ml/ALGORITHMIC_DECISIONS.md`:
- AD-001 through AD-012: Core ML pipeline decisions
- AD-013: Threshold calibration
- AD-039 through AD-045: Date estimation pipeline
- AD-053 through AD-055: Scale-up labeling
- AD-060-061: Training fixes
- AD-067-069: Compare intelligence
- AD-071-072: Birth year estimation
- AD-090: Gemini face alignment research (PROPOSED)
- AD-091: Calibrated confidence labels
- AD-092-096: Year estimation tool
