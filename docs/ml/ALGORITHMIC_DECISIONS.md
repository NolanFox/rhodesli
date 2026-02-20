# ML & Algorithmic Decisions

All data science and algorithmic decisions for the Rhodesli face recognition pipeline.
**Claude Code: Read this ENTIRE file before modifying any ML code.**

## Decision Log

### AD-001: Multi-Anchor Identity Matching (NOT Centroid Averaging)
- **Date**: 2026-02-06 | **Updated**: 2026-02-08 (cluster_new_faces.py fixed for compliance)
- **Context**: When merging face clusters (e.g., child + adult photos), how should the identity's embedding representation be updated?
- **Decision**: Multi-Anchor — each identity retains ALL individual face embeddings as separate anchors. "Find Similar" computes min-distance across all anchors (Best-Linkage / Single Linkage).
- **Rejected**: Centroid averaging — creates "ghost vector" that matches neither age. A face close to one anchor (distance 0.1) could be far from centroid (distance 0.9).
- **Why**: Heritage archives span decades. Averaging destroys signal from both age groups.
- **Implementation**: `core/neighbors.py` (FROZEN), `core/clustering.py`, `scripts/cluster_new_faces.py` (fixed 2026-02-08 from centroid to multi-anchor using `scipy.cdist`).
- **Tests**: `tests/test_cluster_new_faces.py` — 5 tests verify multi-anchor, threshold, co-occurrence exclusion.

### AD-002: Embedding Generation — Once, Never Regenerated
- **Date**: 2026-02-06
- **Decision**: Embeddings generated ONCE during face detection (InsightFace → 512-dim PFE vectors). Never regenerated — they're deterministic for a given crop. Only re-embed if switching models entirely.
- **Affects**: `core/pfe.py`, `core/embeddings_io.py`, ML pipeline scripts.

### AD-003: Distance Metric — MLS (with Euclidean Runtime Divergence)
- **Date**: 2026-02-06 | **Updated**: 2026-02-11 (divergence documented)
- **Decision**: Mutual Likelihood Score (MLS) from PFE. Each embedding has mean (mu, 512-dim) and variance (sigma_sq). MLS accounts for embedding uncertainty.
- **Runtime divergence**: `core/neighbors.py`, `scripts/cluster_new_faces.py`, and `core/grouping.py` ALL use **Euclidean distance** (not MLS). MLS is only used in `core/temporal.py` and `scripts/seed_registry.py`. sigma_sq is computed but ignored at runtime.
- **Implication**: The entire runtime matching pipeline ignores face quality uncertainty. Whether MLS improves results over Euclidean is an open experiment (see AD-022).
- **Scalar sigma fix**: When sigma_sq is uniform, MLS uses single-term formula. See `docs/adr/adr_006_scalar_sigma_fix.md`.

### AD-004: Rejection Memory
- **Date**: 2026-02-06
- **Decision**: Rejected pairs stored in `negative_ids` and excluded from future "Find Similar" suggestions and clustering grouping. `group_all_unresolved()` checks `identity:{uuid}` prefixed entries.
- **Status**: Fully implemented in clustering, grouping, and neighbor search.
- **Affects**: `core/neighbors.py`, `core/grouping.py`, `scripts/cluster_new_faces.py`, identity schema.

### AD-005: Clustering — Complete Linkage with MLS and Temporal Priors
- **Date**: 2026-02-06
- **Decision**: Agglomerative clustering with complete linkage using MLS distance and temporal priors. Complete linkage prevents "chaining" — requires ALL pairs in a cluster to be similar.
- **Affects**: `core/clustering.py`, `core/temporal.py`. See `docs/adr/adr_003_identity_clustering.md`.

### AD-006: Provenance Hierarchy — Human Overrides Model
- **Date**: 2026-02-06
- **Decision**: `provenance="human"` always overrides `provenance="model"`. Human decisions cannot be reversed by re-running ML pipeline.
- **Affects**: Identity state machine, merge/detach operations.

### AD-007: Local-Only ML Inference
- **Date**: 2026-02-06
- **Decision**: ALL ML inference runs locally. Production (Railway) only serves pre-computed JSON/NPY/crops.
- **Rule**: NEVER add torch, tensorflow, dlib, insightface, onnxruntime to production `requirements.txt`.
- **Corollary**: `rhodesli_ml/` package dependencies are separate from the web app (`rhodesli_ml/pyproject.toml`).

### AD-008: Deterministic Crop Naming Convention (STRICT CONTRACT)
- **Date**: 2026-02-06
- **Decision**: Two patterns coexist: Legacy `{sanitized_stem}_{quality}_{face_index}.jpg` and Inbox `{face_id}.jpg`. R2 URLs are deterministic from these patterns.
- **Rule**: Changing the convention requires re-uploading ALL crops to R2.
- **Affects**: `core/crop_faces.py`, `core/storage.py`, R2 upload scripts.

### AD-010: No Hard Quality Filter — PFE Handles Quality
- **Date**: 2026-02-06
- **Decision**: Retain ALL detected faces. PFE sigma (uncertainty) mathematically prevents low-quality faces from dominating clusters. A blurry great-grandfather match > zero matches.

### AD-012: Golden Set — Dynamic User-Verified Truth
- **Date**: 2026-02-06
- **Decision**: Golden set auto-rebuilt from live database. Identities with ≥3 confirmed faces = ground truth. Grows as admin organizes. Current: 125 mappings, 23 identities, 4005 pairs.
- **Harness**: `scripts/build_golden_set.py`, `scripts/evaluate_golden_set.py`.

### AD-013: Five-Tier Threshold Calibration
- **Date**: 2026-02-09
- **Context**: Clustering used a single threshold. Need evidence-based tiers.
- **Evidence**: Golden set sweep (90 faces, 23 identities, 4005 pairs). 100% precision up to 1.05. First FP at 1.0502 (family resemblance: Rosa vs Sol Sedikaro). Optimal F1=0.871 at 1.15.
- **Thresholds** (in `core/config.py`):
  - `VERY_HIGH` (< 0.80): ~100% precision, ~13% recall. Auto-suggest prominently.
  - `HIGH` (< 1.05): 100% precision, ~63% recall. Zero-FP ceiling. Default clustering.
  - `MODERATE` (< 1.15): ~94% precision, ~81% recall. FPs are family resemblance only.
  - `MEDIUM` (< 1.20): ~87% precision, ~87% recall. Exploratory search.
  - `LOW` (< 1.25): ~69% precision, ~91% recall. Deep search only.
- **Caveat**: No real-world clustering validation yet. Re-calibrate after 50+ validated proposals.
- **Note**: `rhodesli_ml/config/base.yaml` uses more conservative thresholds (0.70/0.85/1.00) — these are intended for future calibrated model training, not current production.
- **Harness**: `scripts/evaluate_golden_set.py --sweep`, `scripts/calibrate_thresholds.py`

### AD-014: Phase Sequencing — Calibration Before Backbone
- **Date**: 2026-02-10
- **Decision**: Similarity calibration on frozen InsightFace embeddings FIRST. LoRA backbone adaptation ONLY if calibration plateaus. Full fine-tuning likely never needed.
- **Rationale**: Errors are at the decision boundary, not in the embedding space. A learned similarity function (small MLP) can shift the boundary without distorting embedding geometry. Lower risk, reversible, measurable.
- **Source**: Two independent expert reviews of the ML architecture plan.
- **Sequence**: Phase 1 = Date estimation (PyTorch entry point). Phase 2 = Similarity calibration. Phase 3 = LoRA (if needed).

### AD-015: Date Estimation via Ordinal Regression (CORAL Loss)
- **Date**: 2026-02-10
- **Decision**: Ordinal regression, NOT flat classification. Predicting 1940s when answer is 1950s is less wrong than predicting 2000s. Flat cross-entropy treats all misclassifications equally, which is incorrect for ordered decades.
- **Model**: EfficientNet-B0 backbone via transfer learning, PyTorch Lightning. 13 classes (1900s-2020s).
- **Config**: `rhodesli_ml/config/date_estimation.yaml` — batch 32, lr 0.001, cosine annealing, early stopping patience 10.
- **Affects**: `rhodesli_ml/models/date_classifier.py`, `rhodesli_ml/training/train_date.py`.

### AD-016: Silver-Standard Labels via Gemini Vision API
- **Date**: 2026-02-11
- **Context**: 92% of photos (143/155) have no date metadata. EXIF dates are scan timestamps, not original dates.
- **Decision**: Use Gemini Vision API (gemini-2.0-flash) to estimate decade from visual cues. Store as silver-standard labels with source="gemini", confidence, and reasoning. User corrections override silver labels (gold > silver).
- **Cost**: ~$0.15-0.50 for 155 photos. Prompt includes Sephardic Jewish heritage context.
- **Rule 4 compliance**: Date estimation is metadata enrichment, not identity matching. Falls outside "No Generative AI — forensic matching only" intent.
- **Affects**: `rhodesli_ml/scripts/generate_date_labels.py`, `data/date_labels.json`.

### AD-017: Framework Stack — PyTorch Lightning + MLflow
- **Date**: 2026-02-10
- **Decision**: PyTorch Lightning for training structure (no raw training loops). MLflow for experiment tracking. Both mandatory from day one.
- **Rationale**: Lightning enforces reproducibility. MLflow provides audit trail. Both industry standard.
- **Config**: `rhodesli_ml/config/base.yaml` → `mlflow_tracking_uri: ./mlruns`.
- **Affects**: All `rhodesli_ml/training/` scripts, `rhodesli_ml/pyproject.toml`.

### AD-018: Regression Gate — Mandatory Evaluation Before Production
- **Date**: 2026-02-10
- **Decision**: Nothing touches production without passing ALL of:
  1. Pairwise accuracy on confirmed matches/rejections (no regression)
  2. Hard negative performance (rejected suggestions specifically)
  3. Embedding collapse sentinel (mean random-pair distance must stay stable)
  4. Ranking stability (top-K neighbor overlap, Kendall τ)
  5. Zero-tolerance: ANY confirmed identity pair break blocks deployment
- **Source**: Expert review recommendation.
- **Affects**: `rhodesli_ml/evaluation/regression_gate.py`, `rhodesli_ml/evaluation/ranking_stability.py`, `rhodesli_ml/evaluation/embedding_health.py`.

### AD-019: Active Learning as First-Class Architecture
- **Date**: 2026-02-10
- **Decision**: Active learning woven into architecture from Phase 2 onward. System prioritizes suggestions by uncertainty, model disagreement (baseline cosine vs calibrated model), and expected information gain.
- **Key insight**: When baseline and calibrated model disagree on a pair, that pair is maximally informative for user review.
- **Affects**: Future UI suggestion ordering, similarity calibrator training loop.

### AD-020: Non-Destructive Embedding Management
- **Date**: 2026-02-10
- **Decision**: Original embeddings never overwritten. All model versions tracked alongside originals. All cluster state changes recorded with rollback. Embedding versions stored side-by-side.
- **Rationale**: Heritage archive — data loss is irreversible. Every decision must be undoable.
- **Affects**: `rhodesli_ml/models/registry.py`, embedding storage format.

### AD-021: Learned Similarity Model Architecture
- **Date**: 2026-02-10
- **Decision**: Small MLP: (embedding_a, embedding_b, metadata features) → calibrated match probability [0, 1]. This IS the multi-signal fusion component — grows as signals are added.
- **Config**: Hidden dims [256, 128, 64], dropout 0.3, hard negative weight 3.0x (`rhodesli_ml/config/calibration.yaml`).
- **Input features**: Embedding distance, cosine similarity, face quality diff, same-collection indicator. Future: date proximity, name similarity.
- **Training**: Binary cross-entropy on confirmed pairs (positive) + rejections + hard negatives (negative).
- **Affects**: `rhodesli_ml/models/similarity_calibrator.py`, `rhodesli_ml/training/train_calibrator.py`.

### AD-022: Signal Inventory Assessment
- **Date**: 2026-02-11
- **Findings**: 947 confirmed same-person pairs, 29 cross-identity rejections, 18 multi-face confirmed identities, 125 golden set mappings.
- **Verdict**: Sufficient for basic calibration model. Meets minimums (50+ pairs, 20+ rejections).
- **Risk — Skewed distribution**: Top 5 identities = 94% of pairs. Big Leon alone = 32%. Calibration may overfit to Capeluto family features.
- **Risk — Thin rejections**: 29 pairs meets minimum but boundary definition needs 50+.
- **Risk — Single-family corpus**: All subjects share family resemblance — no easy negatives.
- **Priority actions**: (1) Increase rejections to 50+ via ambiguous match triage, (2) Confirm identities with 1-3 faces for diversity, (3) Evaluate MLS vs Euclidean on golden set.
- **Source**: `docs/ml/current_ml_audit.md`

### AD-023: Ingestion-Time Grouping (Union-Find)
- **Date**: 2026-02-11 (Session 15)
- **Decision**: Faces within a single upload batch are grouped via Union-Find with Euclidean distance < `GROUPING_THRESHOLD` (0.95). Grouping is transitive. Co-occurrence check prevents merging faces from the same photo.
- **Design**: Conservative — under-grouping is better than over-grouping. Simple Union-Find, no clustering libraries.
- **Affects**: `core/grouping.py:group_faces()`.

### AD-024: Global Reclustering — SKIPPED Faces Participate
- **Date**: 2026-02-11 (Session 15)
- **Decision**: `group_all_unresolved()` includes BOTH INBOX and SKIPPED faces. SKIPPED means "deferred," NOT "excluded from ML forever." Every major photo system re-evaluates all unresolved faces as new data arrives.
- **Promotion types**: `new_face_match` (SKIPPED + INBOX grouped), `group_discovery` (SKIPPED + SKIPPED grouped). Promoted faces get state→INBOX with `promoted_from`, `promoted_at`, `promotion_reason`, `promotion_context` metadata.
- **Rejected**: INBOX-only grouping — excluded 196 SKIPPED faces that represent the largest unresolved pool.
- **Affects**: `core/grouping.py:group_all_unresolved()`, Focus mode priority sorting, triage bar filters.

### AD-025: Merge-Aware Data Push (Production Wins)
- **Date**: 2026-02-11 (Session 14)
- **Decision**: `push_to_production.py` fetches production state FIRST, compares, merges with production-wins-on-conflicts policy. Never blind-overwrite.
- **Conflict detection**: `_is_production_modified()` checks state changes, face count changes, name changes, merges, rejections. Production-modified identities are preserved.
- **Origin**: Zeb Capuano merge was reverted when pipeline pushed stale local data.
- **Affects**: `scripts/push_to_production.py`.

### AD-026: Heritage-Specific Augmentations
- **Date**: 2026-02-11
- **Decision**: Date estimation training uses domain-specific augmentations: sepia tone (p=0.3), Gaussian noise (p=0.2), resolution degradation (p=0.2), scanning artifacts (p=0.1), projective distortion (p=0.1).
- **Rationale**: Standard ImageNet augmentations don't model scanning artifacts, fading, or sepia toning common in 1920s-1970s heritage photos.
- **Config**: `rhodesli_ml/config/date_estimation.yaml`.
- **Affects**: `rhodesli_ml/data/augmentations.py` (placeholder, uses torchvision.transforms v2).

### AD-027: MLS vs Euclidean — Open Experiment
- **Date**: 2026-02-11
- **Context**: AD-003 specifies MLS as the distance metric, but the audit (docs/ml/current_ml_audit.md) found ALL runtime code uses Euclidean. sigma_sq is computed but ignored.
- **Status**: OPEN EXPERIMENT. Need golden set evaluation comparing MLS vs Euclidean to determine if sigma_sq actually helps for this archive's face quality distribution.
- **Hypothesis**: MLS may improve matching for low-quality heritage photos where sigma_sq should down-weight uncertain embeddings. But since all sigma_sq values are scalar-uniform (not per-dimension), the benefit may be minimal.
- **Affects**: `core/neighbors.py` (if MLS proves better), `scripts/cluster_new_faces.py`, `core/grouping.py`.

### AD-028: Surname Variant Matching — Bidirectional Lookup via Data Registry
- **Date**: 2026-02-11
- **Context**: Rhodes Jewish family names have many transliterations (Ladino/Turkish/Greek/Hebrew). "Capeluto", "Capelouto", "Capuano" are the same family. Search must bridge these variants.
- **Decision**: Maintain `data/surname_variants.json` with curated variant groups. Search expands query terms bidirectionally: searching any variant finds all members of the group. 13 groups covering ~50 variants.
- **Rejected**: (1) Fuzzy matching only (Levenshtein) — false positives for unrelated names within edit distance 2, false negatives when variants differ by >2 edits (e.g., "Capeluto" → "Capuano" is 4 edits). (2) Phonetic algorithms (Soundex, Metaphone) — designed for English; poor on Sephardic/Ladino names where pronunciation maps inconsistently to Latin script. (3) Database trigram matching — adds query latency for a static dataset.
- **Affects**: `core/registry.py` (search_identities expansion), `data/surname_variants.json`.

### AD-029: Search Ranking — State-Based Priority with Variant Expansion
- **Date**: 2026-02-11
- **Context**: Search must return identities across ALL states (CONFIRMED, PROPOSED, INBOX, SKIPPED) with useful ranking. Previously only CONFIRMED were searchable.
- **Decision**: Rank by state priority (CONFIRMED > PROPOSED > INBOX > SKIPPED > CONTESTED > REJECTED), then alphabetically. Variant expansion and alias search run before ranking. Fuzzy fallback (Levenshtein) only activates when exact + variant matching returns nothing.
- **Rejected**: (1) Chronological ranking — abandons semantic relevance. (2) Fuzzy-first — adds false positives to every search; better to only fuzzy when exact fails. (3) CONFIRMED-only filtering — hides 95% of identities from search, making the tool useless for identification work.
- **Affects**: `core/registry.py` (search_identities), `app/main.py` (/api/search, /api/tag-search).

---

## Detailed ADR Documents

| ADR | Title | Referenced By |
|-----|-------|---------------|
| `docs/adr/adr_001_mls_math.md` | MLS mathematical derivation | AD-003 |
| `docs/adr/adr_002_temporal_priors.md` | Temporal prior design | AD-005 |
| `docs/adr/adr_003_identity_clustering.md` | Identity clustering algorithm | AD-005 |
| `docs/adr/adr_004_identity_registry.md` | Identity registry design | AD-004 |
| `docs/adr/adr_006_scalar_sigma_fix.md` | Scalar sigma MLS fix | AD-003 |
| `docs/adr/adr_007_calibration_adjustment_run2.md` | Calibration adjustment run 2 | AD-003 |

---

## Undocumented / Known Unknowns

### TODO: AD-009 — Temporal Prior Penalty Values
- **Status**: Eras (Child, Adult, Elder) implemented but exact penalty values never formally decided.
- **Action**: Review `core/temporal.py` and document actual multipliers.

### TODO: AD-011 — Face Detection Parameters
- **Status**: InsightFace `buffalo_l`, detection size 640x640, CPUExecutionProvider. `det_thresh` and `nms_thresh` are likely library defaults (~0.5).
- **Action**: Confirm actual values from InsightFace source and document.

### Known Unknown: Cluster Size Limits
- No maximum cluster size or splitting logic. May need revisiting when identities accumulate 50+ faces.

### Known Unknown: Photo Enhancement Impact on Embeddings
- Does GFPGAN/CodeFormer face restoration before embedding extraction improve matching accuracy? UNTESTED. Flag as future experiment.

### Known Unknown: Mirrored/Rotated Photo Handling
- InsightFace uses face alignment (5-point landmark registration) which handles moderate rotations. Fully mirrored or inverted photos are untested. Some newspaper scans may have orientation issues.

### Known Unknown: Threshold Drift with Scale
- Current thresholds calibrated on 90 faces / 23 identities. As the archive grows (500+ photos, 100+ identities), the optimal thresholds may shift. Re-calibrate at each scale milestone.

---

## Rejected Approaches

### AD-030: [Rejected] Centroid Averaging for Multi-Anchor Identities
- **Date**: 2026-02-11
- **Context**: How to represent identities with multiple confirmed faces
- **Decision**: Rejected in favor of multi-anchor comparison (each face independently)
- **Reason**: Averaging embeddings creates "muddy" centroids that don't match any real face; multi-anchor preserves individual face quality
- **Revisit condition**: Never — multi-anchor is strictly superior for PFE embeddings
- **Affects**: `core/neighbors.py`

### AD-031: [Rejected] Full Fine-Tuning Before Calibration
- **Date**: 2026-02-11
- **Context**: Whether to fine-tune the base model on Rhodesli data before calibrating thresholds
- **Decision**: Rejected — calibrate thresholds on pretrained model first, then consider fine-tuning
- **Reason**: Fine-tuning with <1000 faces risks overfitting; calibration catches low-hanging fruit without model changes
- **Revisit condition**: If calibration + LoRA plateau below 90% accuracy on golden set
- **Affects**: `scripts/cluster_new_faces.py`

### AD-032: [Rejected] Training From Scratch
- **Date**: 2026-02-11
- **Context**: Whether to train a face recognition model from scratch on archive photos
- **Decision**: Rejected — use pretrained AdaFace/InsightFace as-is
- **Reason**: Dataset too sparse (<1000 unique faces); pretrained models have seen millions of faces
- **Revisit condition**: If archive exceeds 10,000 faces AND domain shift is demonstrated
- **Affects**: N/A (would be new infrastructure)

### AD-033: [Rejected] Flat Classification for Date Labels
- **Date**: 2026-02-11
- **Context**: How to predict photo dates from visual features
- **Decision**: CORAL ordinal regression chosen over flat multiclass classification
- **Reason**: Dates have natural ordering; flat classification ignores that "1940" is closer to "1945" than to "1980"
- **Revisit condition**: Never for ordered labels — CORAL is strictly superior
- **Affects**: `rhodesli_ml/models/date_labeler.py`

### AD-034: [Rejected] GEDCOM Relatedness as Matching Signal
- **Date**: 2026-02-11
- **Context**: Whether to use family tree data to boost face matching confidence
- **Decision**: Reframed as similarity explorer rather than matching signal
- **Reason**: Family resemblance doesn't equal same person; would create false positive bias
- **Revisit condition**: If kinship detection accuracy exceeds 90% on archive-specific pairs
- **Affects**: N/A (not implemented)

### AD-035: [Rejected] LoRA on Convolutional Layers
- **Date**: 2026-02-11
- **Context**: Whether to apply LoRA adaptation to convolutional backbone layers
- **Decision**: Rejected — ArcFace uses ResNet backbone where LoRA is less effective
- **Reason**: LoRA works best on attention/linear layers (Transformers); ResNet convolutions have different adaptation dynamics
- **Revisit condition**: If base model switches to Vision Transformer (ViT) architecture
- **Affects**: `rhodesli_ml/models/`

### AD-036: [Under Investigation] MLS vs Euclidean Distance Metric
- **Date**: 2026-02-11
- **Context**: Whether mutual likelihood score (MLS) is better than Euclidean for PFE embeddings
- **Decision**: Under investigation pending ML-052 experiment
- **Reason**: PFE embeddings include uncertainty estimates; MLS leverages these but is computationally more expensive
- **Revisit condition**: Active investigation — compare on golden set
- **Affects**: `core/neighbors.py`

### AD-037: [Rejected] Face Restoration as Preprocessing
- **Date**: 2026-02-11
- **Context**: Whether to apply GFPGAN/CodeFormer face restoration before embedding extraction
- **Decision**: Rejected — restoration changes identity features
- **Reason**: Restoration hallucinates details not in the original photo, shifting embeddings away from ground truth; hurts recognition more than it helps
- **Revisit condition**: If dual-branch adapter (original + restored) proves practical without identity drift
- **Affects**: `core/ingest.py`, `core/ingest_inbox.py`

### AD-038: Face Quality Scoring — Composite Display Score
- **Date**: 2026-02-12
- **Context**: Identity thumbnails showed first-in-list face, not best-quality. User feedback: "photos are very poor quality, you feel like keeping on scrolling."
- **Decision**: Composite quality score (0-100) combining three signals:
  - Detection confidence (0-30 pts): InsightFace SCRFD `det_score`
  - Face crop area (0-35 pts): from bounding box, normalized to 22500px² (150×150)
  - Embedding norm (0-35 pts): MagFace principle — higher norm = higher quality
- **Display only**: Score used to select best thumbnail for identity cards. Never used for ML matching, clustering, or filtering. Low-quality faces are deprioritized, never hidden.
- **Rejected**: (1) Sharpness (Laplacian variance) — requires loading original image crops at runtime, too expensive for on-demand computation. (2) Pose frontality — not available in current InsightFace output without additional model call. (3) Single signal (just det_score) — insufficient discrimination; many faces have high det_score but are tiny (newspaper thumbnails).
- **Affects**: `app/main.py` — `compute_face_quality_score()`, `get_best_face_id()`, identity card rendering, neighbor card thumbnails.
- **Tests**: `tests/test_quality_scoring.py` — 13 tests.

### AD-039: Gemini 3 Pro for Silver Labeling (NOT Cheaper Models)
- **Date**: 2026-02-13
- **Context**: Need to silver-label 155 undated photos. Multiple Gemini models available at different price points.
- **Decision**: Use `gemini-3-pro-preview` ($4.27 total) for production, `gemini-3-flash-preview` (free tier) for testing.
- **Rationale**: Cost difference between cheapest ($0.15) and best ($4.27) is negligible at 155 photos. Silver labels are the foundation for all downstream ML — quality matters more than saving $4. Gemini 2.0 Flash deprecated March 31, 2026.
- **Rejected**: Gemini 2.0 Flash (deprecated), GPT-4o (~$30+), Claude Vision (similar cost to GPT-4o).
- **Full analysis**: `docs/ml/DATE_ESTIMATION_DECISIONS.md` Decision 1.
- **Affects**: `rhodesli_ml/scripts/generate_date_labels.py`.

### AD-040: Two-Layer Date Estimation (Gemini Year + PyTorch Decade)
- **Date**: 2026-02-13
- **Context**: Whether to estimate at year or decade granularity.
- **Decision**: Gemini outputs year-level estimates for display ("circa 1937"). PyTorch trains on decade classes (10 classes, CORAL ordinal regression) for new uploads.
- **Rationale**: 155 photos / 10 decades = ~15 per class (viable). 155 / 100+ years = not viable. MyHeritage needed tens of thousands for year-level.
- **Rejected**: Year-level PyTorch training (insufficient data), decade-only Gemini output (less compelling UX).
- **Full analysis**: `docs/ml/DATE_ESTIMATION_DECISIONS.md` Decision 2.
- **Affects**: `rhodesli_ml/models/date_classifier.py`, `rhodesli_ml/scripts/generate_date_labels.py`.

### AD-041: Evidence-First Prompt Architecture
- **Date**: 2026-02-13
- **Context**: How to structure the Gemini Vision prompt for date estimation.
- **Decision**: Decomposed analysis with 4 independent evidence categories (print/format, fashion, environment, technology), per-cue strength ratings, structured JSON output with `decade_probabilities`.
- **Rationale**: Enables cross-querying ("all photos with scalloped borders"), contradiction detection (reprint vs original), retroactive re-scoring, and full audit trail.
- **Rejected**: Narrative-only reasoning (not queryable), forensic checklist without decomposition (encourages hallucinated specifics).
- **Full analysis**: `docs/ml/DATE_ESTIMATION_DECISIONS.md` Decision 3.
- **Affects**: `rhodesli_ml/scripts/generate_date_labels.py`.

### AD-042: Cultural Lag Adjustment for Sephardic Diaspora
- **Date**: 2026-02-13
- **Context**: Standard fashion-dating assumes Western mainstream timeline.
- **Decision**: Explicit prompt instruction accounting for 5-15 year fashion lag in Rhodes and immigrant communities. Studio portraits used conservative formal attire that appears older than actual date.
- **Rationale**: Without adjustment, model systematically estimates photos as older than they are.
- **Rejected**: No adjustment (systematic dating bias), fixed offset (too rigid for varying contexts).
- **Full analysis**: `docs/ml/DATE_ESTIMATION_DECISIONS.md` Decision 4.
- **Affects**: `rhodesli_ml/scripts/generate_date_labels.py` (prompt text).

### AD-043: Soft Label Training via KL Divergence
- **Date**: 2026-02-13
- **Context**: How to train PyTorch model using Gemini's probabilistic outputs.
- **Decision**: Use Gemini's `decade_probabilities` as soft labels via KL divergence auxiliary loss, weighted at 0.3 alongside CORAL primary loss.
- **Rationale**: Hard labels discard useful uncertainty. Soft distributions preserve calibrated signal. Standard knowledge distillation technique (Hinton et al., 2015).
- **Rejected**: Hard-label-only training (discards Gemini's uncertainty estimates).
- **Full analysis**: `docs/ml/DATE_ESTIMATION_DECISIONS.md` Decision 5.
- **Config**: `rhodesli_ml/config/date_estimation.yaml` → `soft_label_weight: 0.3`.
- **Affects**: `rhodesli_ml/models/date_classifier.py`, `rhodesli_ml/training/train_date.py`.

### AD-044: best_year_estimate Display Field
- **Date**: 2026-02-13
- **Context**: What granularity to show users in the photo viewer.
- **Decision**: Gemini outputs `best_year_estimate` (integer year). App displays as "circa 1937". Three granularity levels: year (display), range (uncertainty), distribution (full).
- **Rationale**: "circa 1937" more compelling than "1930s" for genealogy UX. Simpler than computing weighted average from probabilities in app layer.
- **Full analysis**: `docs/ml/DATE_ESTIMATION_DECISIONS.md` Decision 6.
- **Affects**: `rhodesli_ml/scripts/generate_date_labels.py`, future UX integration.

### AD-045: Heritage-Specific Augmentations for Date Estimation
- **Date**: 2026-02-13
- **Context**: Standard ImageNet augmentations don't model heritage photo degradation.
- **Decision**: Custom augmentation pipeline: sepia, resolution degradation, film grain, JPEG artifacts, scanning artifacts, geometric distortion (photos-of-photos), fading.
- **Rationale**: Heritage photos have domain-specific degradation absent from standard libraries. Expert review specifically recommended geometric distortion for photos-of-photos.
- **Config**: `rhodesli_ml/config/date_estimation.yaml` → augmentation section.
- **Affects**: `rhodesli_ml/data/augmentations.py`.

### AD-046: Adopt Spec-Driven Development for UX Work
- **Date**: 2026-02-13
- **Decision**: All sessions that change application behavior require a PRD and Playwright acceptance tests before implementation begins.
- **Rationale**: After 24 sessions, unit tests (1,845 passing) consistently failed to catch UX bugs that were obvious in 2 minutes of manual testing. The gap between "endpoint returns 200" and "human can complete flow" requires browser-level verification. SDD formalizes this with phase gates.
- **Alternatives rejected**:
  - Continue current approach: proven insufficient over 24 sessions
  - Full BDD framework (Cucumber/Gherkin): too heavy for solo project
  - Manual testing only: doesn't scale, not reproducible
- **Sources**: CodeRabbit 2025 analysis, METR trial, Takahashi SDD article (Jan 2026), Thoughtworks SDD analysis (Dec 2025)
- **Affects**: `.claude/rules/spec-driven-development.md`, `docs/process/DEVELOPMENT_PRACTICES.md`, `docs/templates/PRD_TEMPLATE.md`.

### AD-047: Preserve Community Contribution Data Across All Changes
- **Date**: 2026-02-13
- **Decision**: All sessions must back up JSON data files before any migration or schema change. Claude Benatar's real submissions are the first community data and must never be lost.
- **Rationale**: First real community contribution (poisson1957@hotmail.com suggesting "Sarina Benatar Saragossi") validated the entire contribution pipeline. This data has both sentimental and functional value as test fixtures for the approval flow.
- **Affects**: All data migration scripts, `scripts/backup_data.sh`.

### AD-048: Rich Photo Metadata Extraction in Single Gemini Pass
- **Date**: 2026-02-13
- **Context**: We're already paying ~$0.028 per photo for Gemini Vision date estimation. Image input tokens represent ~95% of API cost. Output tokens are nearly free (~$0.001 additional per photo).
- **Decision**: Expand the Gemini prompt to extract scene description, visible text (OCR), keywords, setting, photo type, people count, condition, and clothing notes alongside existing date estimation fields — all in a single API call.
- **Rationale**: For 157 photos, additional cost is pennies on a $4.27 total. Metadata enables semantic search ("wedding", "outdoor Rhodes"), automates OCR of handwritten inscriptions, and cross-validates face detection (Gemini people_count vs detected faces).
- **Fields included** (high value):
  - `scene_description`: 2-3 sentence natural language description for full-text search
  - `visible_text`: OCR of handwriting, captions, inscriptions (automates manual transcription)
  - `keywords`: 5-15 searchable tags for faceted search and filtering
  - `setting`: indoor_studio | outdoor_urban | outdoor_rural | indoor_home | indoor_other | outdoor_other | unknown
  - `photo_type`: formal_portrait | group_photo | candid | document | postcard | wedding | funeral | school | military | religious_ceremony | other
  - `people_count`: integer, cross-referenced against face detection count
  - `condition`: excellent | good | fair | poor
  - `clothing_notes`: fashion/attire description (cultural documentation + date cross-validation)
- **Fields excluded** (and why):
  - Emotion/mood analysis: unreliable on historical photos, low inter-rater agreement
  - Color palette: not useful for genealogy search
  - Detailed object bounding boxes: overkill, covered by scene_description
  - Artistic style classification: not actionable for users
- **Rejected alternatives**:
  - Separate API call for metadata: wasteful, pays for image tokens twice
  - Local model (BLIP-2, LLaVA): lower quality on historical photos, adds infra complexity
  - Manual tagging: doesn't scale past 50 photos
- **Affects**: `rhodesli_ml/scripts/generate_date_labels.py` (prompt + label construction), `rhodesli_ml/data/date_labels.py` (schema), test fixtures.
- **Full analysis**: `docs/ml/DATE_ESTIMATION_DECISIONS.md` Decision 8.

### AD-049: Pre-Labeling Prompt Refinements Based on External Review
- **Date**: 2026-02-13
- **Context**: Two external reviewers (an assistant and an ML expert) evaluated the AD-048 rich metadata schema before the first Gemini labeling run. Feedback evaluated against project constraints (157 photos, one developer, portfolio project, budget-conscious).
- **Accepted proposals**:
  - **Controlled tags**: Fixed enum `controlled_tags` field alongside free-text keywords. Prevents vocabulary drift ("hat" vs "headwear" vs "fedora"). Existing enums cover photo-level classification; controlled_tags covers scene/occasion categories for filtering.
  - **Ladino/Solitreo awareness**: Explicitly prime Gemini for Ladino (Judeo-Spanish), French, Italian, and Solitreo script. Prevent silent normalization of Ladino to standard Spanish.
  - **Subject ages**: Flat integer list `subject_ages`. Cheap output, enables future temporal cross-validation against known birth years.
  - **Prompt version tracking**: `prompt_version` string field for reproducibility.
- **Accepted but deferred** (needs Gemini data first):
  - Simple temporal impossibility check (photo_year < person_birth_year → flag)
  - People count discrepancy flag (gemini_people_count > face_detection_count → flag)
- **Rejected proposals** (with reasoning):
  - Full taxonomy expansion (cultural_elements, religious_indicators, military_indicators as separate arrays): Too granular for 157 photos. Most arrays empty. controlled_tags covers high-value categories.
  - Nested visible_text object: Already have flat fields. Nesting adds parsing fragility for zero benefit.
  - Per-person structured estimates (age_range, gender, role per person): Gemini's person indexing won't reliably map to InsightFace face ordering. Flat subject_ages captures useful signal.
  - Bayesian temporal plausibility scoring: Premature. ~46 identified people with unknown birth year coverage and zero date estimates. Can't build or validate without data.
  - Relationship detection from photos: Unreliable — positioning norms vary by culture and era.
  - Full model/prompt/schema version tracking infrastructure: Overkill at 157 photos. Simple prompt_version string sufficient.
  - 10-photo gold standard benchmark: Premature. Run Gemini first, spot-check, iterate.
  - Schema restructure to deep nesting: Increases Gemini JSON malformation risk.
  - Automatic English translation of visible text: Adds output tokens and cost for marginal value.
  - Uncertainty propagation system: Data structures already support it. Deferred until temporal validator exists.
- **Sources**: External review by ML expert (Feb 2026), assistant review (Feb 2026).
- **Affects**: `rhodesli_ml/scripts/generate_date_labels.py` (prompt + label construction), `rhodesli_ml/data/date_labels.py` (schema), test fixtures.

### AD-050: Reasoning-Before-Conclusion JSON Ordering
- **Date**: 2026-02-13
- **Context**: The Gemini prompt's JSON example placed `estimated_decade` and `best_year_estimate` BEFORE `evidence` and `reasoning_summary`. Since LLM token generation is sequential (earlier output influences later output), the model was committing to a date before generating its reasoning.
- **Decision**: Reorder JSON schema so `evidence` and `reasoning_summary` fields precede `estimated_decade`, `best_year_estimate`, `confidence`, `probable_range`, and `decade_probabilities`. The model now analyzes visual evidence as it generates those fields, then commits to a date estimate grounded in the analysis it just produced.
- **Rationale**: Multiple studies confirm JSON key ordering affects LLM output quality:
  - "Let Me Speak Freely?" (Tam et al., 2024): Forcing strict JSON during reasoning causes 10-15% performance degradation. Two-step approach improves accuracy from 48% to 61%.
  - Dataiku structured generation guide (2025): Recommends structuring JSON so reasoning is generated before outcomes.
  - "Thought of Structure" paradigm (Lu et al., 2025): 44.89% improvement by encouraging structural reasoning before generation.
  - ACL 2025 VLM CoT paper (Zhang et al.): Training on short answers without rationales degrades reasoning task performance.
- **Cost**: Zero. Same fields, same token count, different ordering.
- **Accepted**: JSON field reordering in prompt — evidence → cultural_lag → capture_vs_print → location → reasoning_summary → estimated_decade → confidence → probabilities.
- **Rejected**: Two-step approach (free reasoning then structured formatting) — adds complexity and doubles API calls. Single-pass with correct field ordering captures most of the benefit.
- **Rejected**: Removing JSON constraint entirely for free-form reasoning — loses structured extraction capability which is the whole point.
- **Affects**: `rhodesli_ml/scripts/generate_date_labels.py` (PROMPT constant).

### AD-051: Gemini 3 Flash Labeling Results and Post-Processing
- **Date**: 2026-02-14
- **Context**: Full labeling run of 157 photos using Gemini 3 Flash Preview, with one fallback to Gemini 2.5 Flash and post-processing cleanup.
- **Results**:
  - 157/157 photos labeled (156 via gemini-3-flash-preview, 1 via gemini-2.5-flash fallback)
  - Total cost: ~$2.22 (gemini-3-pro-preview for the main run)
  - The 1 failed photo (472157630...jpg) hit 504 DEADLINE_EXCEEDED on 3-flash consistently; 2.5-flash succeeded and found a dated inscription ("19 de Agosto 1928")
  - 67.4% decade agreement between 2.5 and 3.0 Flash across 43 overlapping photos (mean year diff: 3.6 years)
  - Systematic recency bias in 2.5 Flash: in ALL 14 decade disagreements, 2.5 dated photos LATER than 3.0 (directional, not random noise)
  - Max gap: 19 years on photo ab9cc3eb (baby portrait) — 3.0 identified Lower East Side studio stamp → 1916, 2.5 misread address → 1935
  - 3.0 Flash shows superior early-20th-century dating (studio stamps, fur rug props, specific fashion sub-cues)
- **Mixing models implication**: If combining labels from 2.5 and 3.0 models, the 2.5 labels will systematically skew newer. For the one 2.5-labeled photo (the 504 fallback), the "1928" date may be later than what 3.0 would estimate — though in this case the date is anchored by a handwritten inscription ("19 de Agosto 1928"), making the bias less relevant.
- **Post-processing**: 14 invalid `controlled_tags` stripped (13 "Formal_Portrait", 1 "Indoor_Other" — not in the valid enum). These tags were hallucinated by the model despite the strict list in the prompt.
- **Training**: CORAL model retrained on cleaned 157-photo dataset. Val accuracy 62.9%, MAE 0.486 decades (statistically equivalent to previous 65.7%/0.46 — random seed variation on n=35 val set).
- **Decision**: Gemini 3 Flash labels are sufficient for CORAL training as silver labels, not ground truth. The 2.5 Flash fallback is acceptable for photos that time out. Post-processing tag validation is mandatory.
- **Rejected**: Manual labeling — cost-prohibitive for 157+ photos. The Gemini labels provide a good enough signal for decade-level classification.
- **Affects**: `rhodesli_ml/data/date_labels.json`, `rhodesli_ml/scripts/generate_date_labels.py`, `rhodesli_ml/training/train_date.py`.

### AD-052: Batch Labeling Infrastructure and Data Provenance
- **Date**: 2026-02-14
- **Context**: After labeling 157 photos, need infrastructure for scaling to 500+ and tracking how each label was generated.
- **Decisions**:
  1. **`source_method` field**: Each label tracks generation method — `"api"` (Python script), `"web_manual"` (pasted from gemini.google.com), `"imported"` (bulk external). More extensible than a boolean flag. All 157 existing labels backfilled as `"api"`.
  2. **`clean_labels.py`**: Reusable validation script strips invalid controlled_tags, flags suspicious decades/ages/mismatches. Idempotent, `--dry-run` safe. Catches Gemini hallucinated enum values (AD-051 found 14).
  3. **`add_manual_label.py`**: Helper for web UI paste workflow. Validates schema, archives replaced labels, sets `source_method="web_manual"`. For photos that time out on the API (504 DEADLINE_EXCEEDED).
  4. **`batch_label.sh`**: Unattended overnight wrapper. Adaptive rate limiting (doubles sleep on >50% failure rate), 10-minute pause after 3 consecutive failures, Ctrl+C safe (incremental saves). Insurance for 500+ photo runs.
- **Rejected**: Simple retry loop without batching — no cost tracking, no rate limit adaptation, no logging.
- **Affects**: `rhodesli_ml/scripts/clean_labels.py`, `rhodesli_ml/scripts/add_manual_label.py`, `rhodesli_ml/scripts/batch_label.sh`, `rhodesli_ml/scripts/generate_date_labels.py`, `rhodesli_ml/data/date_labels.json`.

### AD-053: Scale-Up Labeling — 250 Photos with Multi-Pass Retry

- **Date**: 2026-02-14
- **Context**: Needed to label 116 newly uploaded community photos (total 271 photos in archive). Gemini 3 Flash API returned 504 DEADLINE_EXCEEDED errors for ~30% of requests.
- **Decisions**:
  1. **Multi-pass retry strategy**: Run labeling 3 times. Pass 1: 81/114 success (33 errors). Pass 2: 6 more (4 errors). Pass 3: 6 more (4 persistent failures). Total: 250/254 labeled (98.4%).
  2. **Accept 4 permanent failures**: Photos asher_touriel, isaac_jack_levy, morris_touriel, and one other consistently time out. These are likely large/complex images that exceed Gemini's processing window. Will retry in future sessions or use manual labeling (AD-052 add_manual_label.py).
  3. **Post-labeling validation**: `clean_labels.py` run after each pass. Removed 9 invalid Formal_Portrait tags hallucinated by Gemini. Flagged 3 people_count mismatches (pre-existing, not auto-fixed).
- **Rejected**: Single-pass with higher timeout — Gemini API doesn't expose timeout configuration.
- **Affects**: `rhodesli_ml/data/date_labels.json` (250 labels), `rhodesli_ml/scripts/generate_date_labels.py`.

### AD-054: Temporal Consistency Auditing

- **Date**: 2026-02-14
- **Context**: With 250 date labels and growing identity metadata (birth_year, death_year), need automated checks for impossible date combinations (e.g., photo dated before subject's birth).
- **Decisions**:
  1. **Three-tier flagging**: IMPOSSIBLE (photo before birth or after death), SUSPICIOUS (age mismatch >20 years), INFORMATIONAL (missed face counts). Different severity enables prioritized review.
  2. **People count discrepancy detection**: Compares Gemini's people_count with InsightFace's detected face_ids. Flags photos where Gemini sees more people than InsightFace detected — indicates missed faces that could be re-processed.
  3. **Identity-photo mapping**: Builds cross-reference from identities (anchor_ids + candidate_ids) through face_to_photo mapping to photo labels. Skips merged identities.
- **Rejected**: Manual spot-checking — doesn't scale. Embedding-based age estimation — out of scope for current pipeline.
- **Affects**: `rhodesli_ml/scripts/audit_temporal_consistency.py`, `rhodesli_ml/tests/test_audit_temporal.py` (31 tests).

### AD-055: Search Metadata Export for Full-Text Photo Search

- **Date**: 2026-02-14
- **Context**: 250 photos have rich metadata (scene descriptions, keywords, clothing notes, visible text, location estimates) from Gemini labeling. Need to make this searchable.
- **Decisions**:
  1. **Concatenated searchable_text field**: Scene description + visible text + keywords + clothing notes + location estimate, in that order. Single field enables simple full-text search without faceted indexing.
  2. **Controlled tags as structured facets**: Preserved separately from free text for future faceted filtering (e.g., "show all Studio photos from 1940s").
  3. **Schema version 1**: Output file includes `schema_version` for future format changes. Documents include photo_id, decade, people_count, tags, source_method alongside searchable text.
  4. **Dry-run mode**: Default behavior computes and displays summary without writing. Explicit flag required to write output.
- **Rejected**: Per-field search indices — over-engineered for 250 documents. Elasticsearch/Typesense — infrastructure overkill at current scale.
- **Affects**: `rhodesli_ml/scripts/export_search_metadata.py`, `data/photo_search_index.json`, `rhodesli_ml/tests/test_export_search.py` (22 tests).

### AD-056: In-Memory Photo Search (No External Engine)

- **Date**: 2026-02-14
- **Context**: Need search/filter for 250 photos with text descriptions, tags, decades.
- **Decision**: In-memory Python substring matching, no Elasticsearch/Typesense/Meilisearch.
- **Rationale**: At <1000 docs, in-memory search is <1ms with zero infrastructure. External engines add deployment complexity for no benefit at this scale.
- **Rejected**: Elasticsearch (overkill), SQLite FTS (adds persistence layer), client-side search (can't filter server-rendered HTML).
- **Affects**: `app/main.py` (`_search_photos`, `_load_search_index`).

### AD-057: Dual-Keyed Date Label Cache

- **Date**: 2026-02-14
- **Context**: photo_index.json uses inbox_* IDs for community photos, _photo_cache uses SHA256 IDs. Date labels reference photo_index IDs.
- **Decision**: Load date labels keyed by BOTH their original photo_index ID AND a computed SHA256 alias. Same object referenced by two keys.
- **Rationale**: Avoids changing upstream ID generation. O(1) lookup from either ID system. Memory overhead negligible (pointer aliasing, not duplication).
- **Rejected**: Converting all IDs to one format (breaks backward compat), lookup fallback chains (O(n) worst case).
- **Affects**: `app/main.py` (`_load_date_labels`, `_load_search_index`).

### AD-058: Per-Field Provenance Tracking

- **Date**: 2026-02-14
- **Context**: When admin corrects a date, the label source changes to "human". But other AI fields (scene, tags, evidence) should still show AI provenance.
- **Decision**: Track provenance per field, not per label. Currently using field_key parameter in `_field()` renderer. `corrections_log.json` records which specific field was corrected.
- **Rationale**: A date correction doesn't validate the scene description. Users need to know which fields are AI vs verified.
- **Rejected**: Global label-level source (all fields show as verified after any correction).
- **Affects**: `app/main.py` (`_build_ai_analysis_section`, `_field`).

### AD-059: Correction Priority Scoring for Active Learning

- **Date**: 2026-02-14
- **Context**: 250 photos with varying AI confidence. Admin time is limited. Need to prioritize which photos to review first.
- **Decision**: Priority = (1 - confidence_numeric) * range_width_normalized * (1 + temporal_conflict_flag). Low confidence + wide range = high priority.
- **Rationale**: Active learning principle: human corrections are most valuable where the model is least certain. Wide date ranges indicate the model couldn't narrow down.
- **Rejected**: Random order (wastes admin time), chronological (ignores model uncertainty), pure confidence sort (ignores range width information).
- **Affects**: `app/main.py` (`_compute_correction_priority`, `/admin/review-queue`).

### AD-060: Hash-Based Train/Val Split (NOT Sequential RNG)

- **Date**: 2026-02-15
- **Context**: Model metrics degraded 73.2% → 60.3% when adding 21 labels (250 → 271). Investigation revealed the rng-based stratified split produced only 19% val set overlap between runs — metrics were incomparable.
- **Decision**: Use `md5(photo_id:seed)` hash to deterministically assign each photo to train or val. Each photo's assignment is independent of dataset size.
- **Rejected**: `np.random.RandomState(42)` with per-decade shuffle — adding labels to ANY decade shifts the RNG state for all subsequent decades, causing massive val set churn.
- **Trade-off**: Hash split is not stratified by decade (1920s has 37% val vs 20% target). But stability across dataset changes is more important than perfect stratification at n=271.
- **Result**: With stable split, 250 labels → acc=67.9%, MAE=0.358; 271 labels → acc=55.4%, MAE=0.607. Confirmed the 21 new labels genuinely hurt (not split noise). 9 gemini-2.5-flash labels are primary suspects.
- **Affects**: `rhodesli_ml/data/date_dataset.py` (`create_train_val_split`).

### AD-061: Model-Gated Training Eligibility (2.5-flash Labels Display-Only)

- **Date**: 2026-02-15
- **Context**: 9 photos that failed on `gemini-3-flash-preview` (504 timeouts) were labeled with `gemini-2.5-flash` fallback. Adding these 9 labels (plus 12 new 3-flash labels) degraded model accuracy from 67.9% → 55.4% (−12.5 pp) and MAE from 0.358 → 0.607 (+69%). Hash-based split (AD-060) confirmed this is real degradation, not split noise.
- **Decision**: Labels have a `training_eligible` field. `gemini-2.5-flash` labels are `training_eligible: false` — displayed in the UI for date context but excluded from CORAL model training by default. `load_labels_from_file()` filters by `training_eligible=True` unless `training_only=False` is passed.
- **Rejected**: (a) Re-labeling all 9 with gemini-3-flash — would fix training but doesn't prevent future fallback labels from contaminating training; (b) Removing 2.5-flash labels entirely — loses useful display data for 9 photos that have no other date estimate.
- **Rationale**: Different Gemini models have systematic biases in decade estimation. Mixing model outputs creates label noise that degrades ordinal regression. The `training_eligible` gate allows 100% photo coverage in the UI while maintaining training data consistency.
- **Implementation**: `training_eligible` field in `data/date_labels.json`; `--exclude-models` and `--include-all` flags in `train_date.py`; `training_only` param in `load_labels_from_file()`; `generate_date_labels.py` sets `training_eligible` based on model.
- **Affects**: `rhodesli_ml/data/date_dataset.py`, `rhodesli_ml/training/train_date.py`, `rhodesli_ml/scripts/generate_date_labels.py`, `data/date_labels.json`.

### AD-062: Timeline Data Model — Merged Photo + Context Event Stream
- **Date**: 2026-02-15
- **Context**: How to present 271 dated photos alongside Rhodes historical events on a vertical timeline.
- **Decision**: Merge photo search index entries and historical context events into a single chronological stream, sorted by year, grouped by decade. Photos use `best_year_estimate` from Gemini date labels; context events come from curated `rhodes_context_events.json`. Person filter uses face-to-photo reverse lookup.
- **Rejected**: (1) Separate photo timeline + event timeline side-by-side — too complex for mobile, and the interleaving is the whole point. (2) D3/JS-based horizontal timeline — violates the FastHTML/server-side rendering constraint. (3) Swimlane layout by person — requires relationship data not yet available.
- **Implementation**: `/timeline` route in `app/main.py`, `_load_context_events()`, `data/rhodes_context_events.json`.
- **Affects**: `app/main.py`, `data/rhodes_context_events.json`.

### AD-063: Historical Context Events — Rhodes-Specific, Source-Verified
- **Date**: 2026-02-15
- **Context**: What historical events to include alongside family photos, and how to verify accuracy.
- **Decision**: 15 curated events spanning 1522–1997 with explicit source citations (Yad Vashem, Jewish Community of Rhodes, Rhodes Jewish Museum, Cambridge UP, HistoryLink). Categories: holocaust, persecution, liberation, immigration, community, political. Each event has a distinct visual style by category.
- **Rejected**: (1) Auto-generated events from Wikipedia — accuracy for heritage projects requires human curation. (2) Fine-grained daily timeline — too sparse at 271 photos. (3) Generic world history events — irrelevant to the Rhodesli diaspora story.
- **Key facts verified**: 1,673 deported July 23 1944 (not July 24), ~151 survived, 24-day journey to Auschwitz (longest of any community), arrival August 16 1944.
- **Affects**: `data/rhodes_context_events.json`.

### AD-064: Context Event Era Filtering — Person-Scoped Timeline
- **Date**: 2026-02-15
- **Context**: When a person filter is active on the timeline, context events from centuries before their lifetime are irrelevant (e.g., 1522 Ottoman Conquest on Big Leon Capeluto's 1920s-1970s timeline).
- **Decision**: When person filter active, compute the photo date range (earliest_year - 30, latest_year + 10) and only show context events within that window. When no person filter, show all events (full community history).
- **Rejected**: (1) Always show all events — distracting when focused on one person. (2) Filter by identity birth_year only — not all identities have birth_year, and photo dates are more reliable. (3) Hard-coded era windows — doesn't adapt to the actual photo distribution.
- **Rationale**: -30 years before earliest photo accounts for events that shaped the person's childhood/parents. +10 years after latest photo accounts for events shortly after their last photograph.
- **Affects**: `app/main.py` (timeline route context event filtering).

### AD-065: Face Comparison Similarity Engine — Face-Level vs Identity-Level
- **Date**: 2026-02-15
- **Context**: The existing `find_nearest_neighbors()` works at the identity level (comparing all faces of one identity against all faces of another). The comparison tool needs face-level matching — comparing a single face embedding against all faces in the archive.
- **Decision**: New `find_similar_faces()` function in `core/neighbors.py` that operates on individual face embeddings, not identity aggregates. Uses the same Euclidean distance metric and confidence tiers (VERY HIGH <0.80, HIGH <1.00, MODERATE <1.20, LOW ≥1.20) as the existing pipeline. Returns face_id, distance, confidence, and identity info when registry is provided.
- **Rejected**: (1) Reuse `find_nearest_neighbors()` with a fake identity wrapper — adds unnecessary complexity and breaks the identity-level co-occurrence check. (2) Cosine similarity instead of Euclidean — the entire pipeline uses Euclidean and thresholds are calibrated for it (AD-013). (3) Approximate nearest neighbors (FAISS/Annoy) — 775 embeddings is trivial for brute force (<10ms), ANN overhead not justified.
- **Affects**: `core/neighbors.py`, `app/main.py` (/compare route, /api/compare endpoint).

### AD-067: Kinship Calibration — Empirical Distance Thresholds
- **Date**: 2026-02-15
- **Context**: The compare tool used hardcoded distance thresholds (AD-013 golden set) without empirical calibration against confirmed identity clusters. We have 46 confirmed identities, 18 with multiple faces (959 same-person pairs), and 13 surname variant groups.
- **Decision**: Compute three distance distributions from confirmed data: SAME_PERSON (intra-identity pairs), SAME_FAMILY (cross-identity, shared surname group), DIFFERENT_PERSON (cross-identity, different surname groups). Derive thresholds from the same_person distribution: strong_match < P75 (1.163), possible_match < P95 (1.315), similar_features < different_person P25 (1.365).
- **Key finding**: Family resemblance is NOT reliably separable from different-person distances (Cohen's d = 0.43, small effect). Same-person vs different is strongly separable (d = 2.54). The compare tool uses same-person-derived thresholds, not a kinship model.
- **Rejected**: (1) Kinship-based tiers (identity/family/community) — family resemblance signal too weak in embedding space (d=0.43) to be useful. (2) Hardcoded thresholds without calibration — no empirical basis. (3) MLS-based calibration — runtime pipeline uses Euclidean, thresholds should match.
- **Assumptions**: Shared surname ≈ same family (heuristic via surname_variants.json). Heritage archive context (photos span 60+ years).
- **Affects**: `rhodesli_ml/analysis/kinship_calibration.py`, `rhodesli_ml/data/model_comparisons/kinship_thresholds.json`, `core/neighbors.py` (threshold loading).

### AD-068: Compare Result Tiering — Same-Person-Derived Model
- **Date**: 2026-02-15
- **Context**: Compare results were a flat list with confidence badges. Users need grouped sections to quickly identify strong matches vs exploratory results.
- **Decision**: Four-tier model: STRONG MATCH (< P75 same_person), POSSIBLE MATCH (< P95 same_person), SIMILAR (< P25 different_person), WEAK (above all thresholds). CDF-based confidence percentages using sigmoid approximation of the empirical same_person distribution. Results grouped into titled sections with tier-specific styling and cross-links.
- **Rejected**: (1) "Family Resemblance" tier — Cohen's d = 0.43 means labeling results as "possible relative" would have >40% false positive rate. Scientifically dishonest. (2) Linear similarity percentage — doesn't reflect the actual probability distribution. (3) Flat result list — forces users to manually scan for strong matches.
- **Affects**: `core/neighbors.py` (find_similar_faces), `app/main.py` (_compare_results_grid, _compare_result_card).

### AD-069: Upload Persistence — R2 Storage with Local Fallback
- **Date**: 2026-02-15 | **Updated**: 2026-02-15 (upgraded from local-only to R2-first)
- **Context**: Compare uploads were ephemeral (temp files deleted after comparison). Users lose results on page navigation, and admins can't review uploaded photos. Local filesystem doesn't survive Railway restarts.
- **Decision**: Persist uploads to R2 under `uploads/compare/{uuid}.{ext}` with metadata JSON. Falls back to local filesystem when R2 write credentials are unavailable. On production without InsightFace, accepts uploads to R2 and shows "saved, processing pending" message. Metadata includes status field (uploaded/awaiting_analysis/pending/approved/rejected/processed). "Contribute to Archive" creates entry in admin moderation queue (pending_uploads.json).
- **Rejected**: (1) Local-only storage — doesn't survive Railway restarts. (2) Session-based persistence — cookies expire. (3) Client-side storage — can't persist embeddings in browser. (4) Supabase storage — adds another service dependency when R2 already handles photos.
- **Affects**: `core/storage.py` (R2 write helpers), `app/main.py` (_save_compare_upload, /api/compare/upload, /api/compare/upload/select, /api/compare/contribute).

### AD-070: Future Architecture Directions
- **Date**: 2026-02-15
- **Context**: Capturing architectural directions for upcoming features to inform future sessions. These are planned approaches, not yet implemented.
- **Decisions**:
  1. **Social graph from photo co-occurrence** — Edges already exist in data (face_to_photo mapping). Co-occurrence = two identities appearing in the same photo. Weight by frequency. This is a novel signal that no genealogy tool combines with family relationships.
  2. **"Six degrees" connection finder** — Combine GEDCOM familial edges with photo co-occurrence edges into a unified graph. BFS/Dijkstra finds shortest path between any two people. Edge types: parent/child, sibling, spouse (GEDCOM) + appears_together (photos).
  3. **Geographic migration analysis** — Geocode Gemini location estimates, then trace community dispersal patterns (Rhodes → Montgomery, Atlanta, Asheville, Seattle, Havana, Buenos Aires, Congo, Rhodesia). Map view with migration arrows.
  4. **Kinship recalibration after GEDCOM** — Current AD-067 used surname heuristics for "same family." With actual GEDCOM relationships, can compute true parent-child, sibling, cousin distributions. Expect much stronger signal than surname-based grouping.
  5. **Database migration deferred** — JSON + R2 is sufficient for current scale (~500 photos, ~800 identities). Postgres migration (Phase F) only needed when: (a) concurrent writes become an issue, (b) >10,000 faces, or (c) complex queries exceed JSON traversal performance.
  6. **R2 as upload staging layer** — Compare uploads now persist to R2 instead of local filesystem. This pattern extends to all user uploads (photos, GEDCOMs, corrections) without requiring a database.
- **Affects**: Future sessions 34-40 and corresponding PRDs.

---

## Adding New Decisions

When making any algorithmic choice in the ML pipeline:
### AD-071: Birth Year Estimation — Weighted Aggregate with Robust Outlier Filtering
- **Date**: 2026-02-15
- **Context**: Inferring birth years for confirmed identities by cross-referencing photo dates (Gemini best_year_estimate) with per-face age estimates (Gemini subject_ages, left-to-right ordering). Faces matched to ages via bounding box x-coordinate sorting.
- **Decision**: Median + MAD (Median Absolute Deviation) for outlier detection before weighted averaging. Single-person photos get 2x weight. Confidence tiers: HIGH (std<3, n>=3), MEDIUM (std<5 or n=2), LOW (otherwise).
- **Rejected**: Simple weighted average without outlier filtering — bbox mismatches in group photos caused 5-15 year errors. Also rejected InsightFace age estimation — Gemini sees full photo context (clothing, setting) which is critical for historical photos.
- **Results**: 32 estimates from 46 confirmed identities (3 HIGH, 6 MEDIUM, 23 LOW). Big Leon Capeluto: 1907 (expected ~1903), medium confidence. Single-person photos give 1903/1905 — the noise comes from group photos.
- **Key finding**: Face-to-age matching via bbox x-sorting works well when face count matches Gemini people_count (90% of photos). The 10% mismatch cases are skipped. Primary error source is Gemini age estimation variance (±5 years typical).
- **Affects**: `rhodesli_ml/pipelines/birth_year_estimation.py`, `rhodesli_ml/scripts/run_birth_estimation.py`, `rhodesli_ml/data/birth_year_estimates.json`

### AD-072: Birth Year UI Integration — ML Estimates as Fallback
- **Date**: 2026-02-15
- **Context**: How to display ML-inferred birth years alongside human-confirmed metadata.
- **Decision**: `_get_birth_year(identity_id, identity)` checks metadata.birth_year first, then birth_year_estimates.json. ML estimates shown with "~" prefix and confidence-based styling. Timeline age badges: HIGH=solid, MEDIUM=dashed, LOW=faded. Person page shows "Born ~1907 (estimated)".
- **Rejected**: Writing ML estimates directly to identity metadata — violates non-destructive principle. ML outputs stay in separate file, human overrides stay in metadata.
- **Affects**: `app/main.py` (_get_birth_year, _load_birth_year_estimates, timeline route, person page, _identity_metadata_display)

### AD-073: GEDCOM Parsing — Custom Date Parser over Library Defaults
- **Date**: 2026-02-15
- **Context**: GEDCOM 5.5.1 date strings use non-standard formats (ABT, BEF, AFT, BET...AND, FROM...TO, INT, partial dates). Need reliable year extraction for identity matching.
- **Decision**: Custom `parse_gedcom_date()` handles all GEDCOM date modifiers with confidence levels (HIGH for exact, MEDIUM for ABT/approximate, LOW for range/interpreted). Month names are 3-letter uppercase per GEDCOM spec. Uses python-gedcom v1.1.0 for tree traversal but custom parsing for dates.
- **Rejected**: python-gedcom's built-in date parsing — only extracts year as integer, loses modifier information (ABT vs exact) and confidence signaling. Also rejected dateutil — doesn't understand GEDCOM-specific modifiers.
- **Affects**: `rhodesli_ml/importers/gedcom_parser.py` (ParsedDate, parse_gedcom_date, GedcomIndividual, GedcomFamily)
- **Tests**: 40 tests in `rhodesli_ml/tests/test_gedcom_parser.py`

### AD-074: Identity Matching — Layered Name + Date Strategy
- **Date**: 2026-02-15
- **Context**: Matching GEDCOM individuals (e.g., "Victoria Cukran") to archive identities (e.g., "Victoria Cukran Capeluto") across Sephardic naming conventions (maiden names, transliteration variants, generation qualifiers).
- **Decision**: Three-layer matching: (1) Exact surname match via surname_variants.json expansion + maiden name matching across all name words, (2) Fuzzy name matching (Levenshtein ≤ 2) + date proximity bonus, (3) Future: relationship inference. Maiden name matching: check if GEDCOM given+surname both appear in archive identity's canonical name parts. Contains-match bonus (+0.02) breaks ties between substring and exact matches.
- **Rejected**: Simple string matching — fails on "Mosafir" vs "Capeluto" (same person, maiden vs married). Also rejected auto-merge — all matches are proposals requiring admin confirmation. Centroid-based name similarity — doesn't handle Sephardic naming conventions (multiple surnames, transliteration groups).
- **Key finding**: Maiden name matching is the critical innovation — 4 of 14 test individuals (Hanula Mosafir, Victoria Cukran, Boulissa Pizanti, Felicita Russo) only match via maiden name in the archive's multi-part names.
- **Affects**: `rhodesli_ml/importers/identity_matcher.py`, `data/surname_variants.json`
- **Tests**: 21 tests in `rhodesli_ml/tests/test_identity_matcher.py`

### AD-075: Graph Schemas — Dual Graph Architecture
- **Date**: 2026-02-15
- **Context**: Need to represent both genealogical relationships (from GEDCOM) and photographic co-occurrence (from existing photo data) as separate but complementary graphs.
- **Decision**: Two separate graph files: `data/relationship_graph.json` (GEDCOM-derived family relationships with types: parent-child, spouse) and `data/co_occurrence_graph.json` (photo-derived co-appearance edges with shared photo lists). Relationship graph only creates edges where BOTH endpoints are matched to confirmed archive identities. Co-occurrence graph built independently from photo_index.json + identities.json, no GEDCOM required.
- **Rejected**: Single unified graph — relationship types are fundamentally different (genealogical vs photographic). Separate files enable independent updates and different query patterns. Also rejected NetworkX serialization — JSON is human-readable, auditable, and consistent with existing data model.
- **Affects**: `rhodesli_ml/graph/relationship_graph.py`, `rhodesli_ml/graph/co_occurrence_graph.py`, `data/relationship_graph.json`, `data/co_occurrence_graph.json`
- **Tests**: 20 tests in `rhodesli_ml/tests/test_graphs.py`

### AD-076: GEDCOM Enrichment — Source Priority for Identity Metadata
- **Date**: 2026-02-15
- **Context**: When a GEDCOM match is confirmed, which fields should be written to identity metadata? How does GEDCOM data interact with existing ML estimates?
- **Decision**: GEDCOM enrichment writes birth_year, death_year, birth_place, death_place, gender, birth_date_full, death_date_full to identity metadata via `set_metadata()`. GEDCOM birth_year becomes the "confirmed" birth year in metadata, taking priority over ML estimates (which remain in separate birth_year_estimates.json). `_get_birth_year()` already checks metadata first, so GEDCOM data automatically takes precedence. Gender "U" (unknown) is skipped.
- **Rejected**: Writing GEDCOM data to a separate file (like ML estimates) — GEDCOM data is human-verified genealogical data, not ML inference. It belongs in identity metadata alongside other confirmed facts. Also rejected auto-enrichment on match proposal — enrichment only happens on admin confirmation, maintaining the proposal workflow.
- **Affects**: `rhodesli_ml/importers/enrichment.py`, `core/registry.py` (metadata allowlist), `app/main.py` (confirm route)
- **Tests**: 12 tests in `rhodesli_ml/tests/test_enrichment.py`

### AD-077: D3 Tree Layout — Hierarchical Reingold-Tilford
- **Date**: 2026-02-17
- **Context**: The /connect page uses a force-directed D3 layout which doesn't convey generational hierarchy. We need a family tree that visually shows parent→child depth.
- **Decision**: Use `d3.tree()` (Reingold-Tilford hierarchical layout) with `nodeSize([280, 140])`. D3 v7 already loaded on /connect, includes `d3-hierarchy` module. Vertical layout with elbow connectors for parent-child links and dashed horizontal lines for spouse links.
- **Rejected**: Force-directed layout (d3.forceSimulation) — doesn't convey generations, nodes jumble across depth levels. Also rejected dagre.js — adds another dependency when d3.tree() is already available.
- **Affects**: `app/main.py` (/tree route), inline D3 script

### AD-078: Couple-Based Hierarchy — Family Units as Nodes
- **Date**: 2026-02-17
- **Context**: In a family tree, married couples should appear together with their children below. Standard d3.tree() treats each person as a separate node.
- **Decision**: Each "family unit" (married couple + children) is a logical node in the d3 hierarchy. Visually rendered as two side-by-side rounded rects with a horizontal dashed pink spouse connector. Children hang below the midpoint. Single parents (no spouse in data) render as a single card.
- **Rejected**: One-person-per-node with separate spouse edges — makes layout messy, unclear which children belong to which couple.
- **Affects**: `rhodesli_ml/graph/relationship_graph.py` (`build_family_tree()`, `find_root_couples()`), `app/main.py` (D3 render script)
- **Tests**: 10 tests in `tests/test_family_tree.py`

### AD-079: FAN Relationship Model — Friends, Associates, Neighbors
- **Date**: 2026-02-17
- **Context**: Beyond biological family (parent-child, spouse), genealogical research uses the FAN principle (Friends, Associates, Neighbors) to establish indirect connections.
- **Decision**: Extend `relationships.json` schema with `confidence` field ("confirmed"/"theory") and new `type` values ("fan_friend", "fan_associate", "fan_neighbor"). Backward compatible — missing `confidence` defaults to "confirmed". `get_relationships_for_person()` returns FAN types in a separate `fan` key. `include_theory` parameter filters speculative connections.
- **Rejected**: Separate fan_relationships.json — adds complexity. One schema handles all relationship types with type-based filtering.
- **Affects**: `rhodesli_ml/graph/relationship_graph.py` (add/update/remove functions, get_relationships_for_person), `app/main.py` (API endpoints, tree page theory toggle)
- **Tests**: 15 tests in `tests/test_relationship_editing.py`

### AD-080: Inline JSON for Tree Data — Same Pattern as /connect
- **Date**: 2026-02-17
- **Context**: How to deliver tree data to the D3 visualization? Options: inline JSON in page, separate API endpoint, WebSocket.
- **Decision**: Embed tree data as inline JSON in the page HTML (same pattern as /connect's `d3_json`). Data is small (~15-50 people × ~100 bytes = <5KB). Avoids extra API round-trip and loading states.
- **Rejected**: Separate `/api/tree` endpoint — adds loading state complexity, CORS considerations, and extra request for small data. WebSocket — massive overkill for static genealogical data.
- **Affects**: `app/main.py` (/tree route — `tree_json = json.dumps(tree_data)` embedded in Script tag)

### AD-081: Shareable Identification Pages — Crowdsource-First Architecture
- **Date**: 2026-02-17
- **Status**: ACCEPTED
- **Context**: The archive has ~135 unidentified faces. Family members who could identify them are non-technical users on Facebook groups and WhatsApp. Requiring login or account creation to contribute identifications creates too much friction.
- **Decision**: Create public pages at `/identify/{id}` (single face) and `/identify/{a}/match/{b}` (side-by-side comparison) that require no authentication. Visitors submit a name/relationship via a simple form. Responses are stored in `data/identification_responses.json` for admin review. Identified persons redirect to `/person/{id}`. OG tags enable rich social sharing previews.
- **Alternatives Considered**: Require login for submissions — eliminates spam but creates prohibitive friction for elderly family members. Google Forms — easy but disconnected from the archive data, no auto-linking to identities. Email-based workflow — no structured data, manual admin processing.
- **Rationale**: The primary goal is maximizing identification coverage. A 70-year-old aunt sharing a photo in a family WhatsApp group should be one tap away from contributing. Admin moderation handles quality control post-hoc rather than pre-submission.
- **Affects**: `app/main.py` (`/identify/{id}`, `/identify/{a}/match/{b}`, `/api/identify/respond`), `data/identification_responses.json`, `tests/test_identify.py` (15 tests)

### AD-082: Unauthenticated Person Page Comments with Admin Moderation
- **Date**: 2026-02-17
- **Status**: ACCEPTED
- **Context**: Person pages (`/person/{id}`) display identity information but offer no way for visitors to share memories, corrections, or context. Family members have stories that don't fit structured fields (birth year, maiden name).
- **Decision**: Add a comments section to `/person/{id}` that accepts submissions without login. Comments have an optional author name field. Stored in `data/person_comments.json`. Admin can hide inappropriate comments via `POST /api/person/{id}/comment/{id}/hide` (soft delete, not hard delete — consistent with "never delete data" invariant). Comments display in reverse chronological order.
- **Alternatives Considered**: Require login — same friction problem as AD-081. Disqus or third-party comment system — adds external dependency, data leaves the archive. Structured annotation system only — already exists (AN-001+) but requires login and field-specific submissions. Comments serve a different, freeform purpose.
- **Rationale**: Freeform comments capture stories and context that structured fields cannot. "Aunt Rosa always wore that brooch — it was from her mother in Rhodes" is valuable provenance that has no structured field. Admin moderation (hide, not delete) provides quality control without losing data.
- **Affects**: `app/main.py` (`_person_comments_section()`, `POST /api/person/{id}/comment`, `POST /api/person/{id}/comment/{id}/hide`), `data/person_comments.json`, `tests/test_person_comments.py` (9 tests)

### AD-083: Automated Data Integrity Checker — 18-Check Validation Suite
- **Date**: 2026-02-17
- **Status**: ACCEPTED
- **Context**: After Session 40 discovered 114 photos with wrong collection metadata and a corrupted `_photo_cache`, it became clear that data consistency checks were only happening ad hoc. JSON files can silently drift (missing keys, orphan references, schema violations) without any automated detection.
- **Decision**: Create `scripts/verify_data_integrity.py` with 18 checks: JSON parse validity for all data files, expected collections exist, photo count stability, `identities.json` has required `history` key, `relationships.json` schema validation, face-to-photo referential integrity, identity state enum validity, and more. Exit code 0/1 for CI integration. Run after test changes (`CLAUDE.md` Rule #14) and before deployments.
- **Alternatives Considered**: Database constraints (Postgres) — correct long-term solution (Phase F) but premature for JSON-based storage. Per-file JSON Schema validation — covers structure but not cross-file referential integrity. Manual spot-checks — how we got 114 misassigned photos.
- **Rationale**: The system uses 8+ JSON files with cross-references (face IDs span identities.json, photo_index.json, and embeddings.npy). Without automated integrity checks, corruption is discovered by users seeing wrong data on production. 18 checks run in <1 second and catch the classes of corruption seen in Sessions 25-40.
- **Affects**: `scripts/verify_data_integrity.py`, `tests/test_critical_routes.py` (10 route smoke tests), referenced by `CLAUDE.md` Rule #14

### AD-084: Person Page Action Bar — Cross-Feature Navigation Hub
- **Date**: 2026-02-17
- **Status**: ACCEPTED
- **Context**: The `/person/{id}` page showed identity information and photos but had no way to navigate to related features (timeline filtered to this person, map showing their photos, family tree centered on them, social connections). Users had to manually navigate to each feature and re-select the person.
- **Decision**: Add a horizontal pill-button bar below the share button on `/person/{id}` with deep links: Timeline (`/timeline?people={id}`), Map (`/map?person={id}`), Family Tree (`/tree?person={id}`), and Connections (`/connect?from={id}`). Each link pre-filters the target page to the current person. For unidentified persons, show a "Help Identify" CTA linking to `/identify/{id}`.
- **Alternatives Considered**: Sidebar navigation — takes horizontal space on a page that's already content-dense. Dropdown menu — hides discoverability. Tab-based layout with all features on one page — massive page weight, duplicates code from 4 separate routes.
- **Rationale**: The person page is the natural hub for identity-centric exploration. Deep links with pre-populated query params leverage existing feature pages without duplicating code. The action bar makes the archive feel interconnected rather than siloed.
- **Affects**: `app/main.py` (`_person_page()` action bar section, `/identify/{id}` Help Identify CTA)

### AD-085: Collection Data Provenance — Batch Correction over Individual Edits
- **Date**: 2026-02-17
- **Status**: ACCEPTED
- **Context**: 114 community photos from Session 26 batch ingestion were all assigned to "Community Submissions" regardless of actual source. The real source was "Jews of Rhodes: Family Memories & Heritage" from a Facebook group. Correcting one-by-one through the UI would require 114 individual edits.
- **Decision**: Write a migration script (`scripts/fix_collection_metadata.py`) with `--dry-run`/`--execute` safety flags that batch-reassigns photos based on source patterns. The script reports what would change before executing. Only 2 photos (Claude Benatar's actual community uploads) correctly remain as "Community Submissions." This follows the established data safety pattern: never edit JSON directly, always use scripts with dry-run.
- **Alternatives Considered**: Manual UI edits — 114 clicks, error-prone, no audit trail. Direct JSON editing — violates data safety rules. Retroactive fix in ingest_inbox.py — doesn't fix already-ingested data, only prevents future occurrences.
- **Rationale**: Batch ingestion errors require batch correction tools. The dry-run pattern provides a preview and audit trail. The root cause (ingest_inbox.py defaulting to "Community Submissions") should also be fixed to prevent recurrence, but the immediate need is correcting existing data.
- **Affects**: `scripts/fix_collection_metadata.py`, `data/photo_index.json` (114 photos updated)

### AD-086: Photo Carousel — Collection-Scoped Sequential Navigation
- **Date**: 2026-02-17
- **Status**: ACCEPTED
- **Context**: The public photo viewer (`/photo/{id}`) showed a single photo with no way to browse adjacent photos. Users clicking through from a collection page had to go back to the grid and click the next photo. This breaks the browsing flow, especially for family members reviewing a batch of related photos.
- **Decision**: Add prev/next arrow buttons and a "Photo X of Y in [Collection]" position indicator to `/photo/{id}`. Navigation is scoped to the current photo's collection, with photos sorted by filename for consistent ordering. Keyboard left/right arrow keys also navigate. The collection name is a clickable link back to the collection page.
- **Alternatives Considered**: Global photo ordering (all photos, not collection-scoped) — loses the contextual grouping that makes browsing meaningful. Infinite scroll — changes the page architecture from single-photo to feed. Lightbox overlay from collection grid — already exists for admin view but doesn't work for public shareable URLs.
- **Rationale**: Heritage photo collections are inherently sequential (same album, same event, same era). Navigating within a collection preserves this context. Filename sorting provides a stable, deterministic order that matches the original album sequence in most cases.
- **Affects**: `app/main.py` (`/photo/{id}` route — carousel nav section), `tests/test_public_photo_viewer.py`

### AD-087: Face Overlay Click Targets — Navigate to Person or Identify Pages
- **Date**: 2026-02-17
- **Status**: ACCEPTED
- **Context**: On the photo viewer page, clicking a face overlay scrolled down to the person card below the photo, and clicking the person card scrolled back up to the overlay. This circular scroll behavior provided no useful action — it just bounced the user between two representations of the same information.
- **Decision**: Replace circular scroll with outbound navigation. Clicking a face overlay or person card for an identified person navigates to `/person/{id}`. For an unidentified person, it navigates to `/identify/{id}`. This makes every click productive — it either shows the person's full profile or invites identification help.
- **Alternatives Considered**: Keep scroll behavior and add a separate "View Profile" button — adds UI clutter, two ways to do the same thing. Open person page in modal — adds complexity, modals within the photo viewer are already used for other purposes. Do nothing (remove click handlers) — wastes the most obvious interaction point on the page.
- **Rationale**: The photo viewer's face overlays are the primary discovery surface. Every click should advance the user's journey: either learning more about a known person or contributing to identification of an unknown one. Circular scroll is a dead end.
- **Affects**: `app/main.py` (`_build_photo_view_content()` overlay click handlers, person card click handlers), `tests/test_public_photo_viewer.py`

### AD-088: Face Overlay Alignment — Position Relative on Inner Image Wrapper
- **Date**: 2026-02-17
- **Status**: ACCEPTED
- **Context**: Face bounding box overlays on the photo viewer were misaligned — they appeared offset from the actual faces in the photo. The overlays use `position: absolute` with percentage-based coordinates derived from the original image dimensions. For absolute positioning to work correctly, the overlays must be positioned relative to the image element, not the outer container.
- **Decision**: Add `position: relative` to the inner image wrapper `div` that contains both the `<img>` element and the overlay `div`s. This establishes the correct containing block for absolute positioning, ensuring overlays align with the image regardless of container padding, margins, or responsive scaling.
- **Alternatives Considered**: Use pixel-based coordinates recalculated on resize — complex JS, race conditions with image load. Use CSS `object-fit` with matching overlay transforms — brittle, breaks when image aspect ratio changes. Use `<canvas>` overlay — heavyweight, loses CSS styling for overlay labels and hover effects.
- **Rationale**: The fix is a single CSS property addition. Percentage-based absolute positioning within a `position: relative` parent is the standard web pattern for image overlays. All modern browsers handle responsive scaling of percentage-positioned children correctly.
- **Affects**: `app/main.py` (`_build_photo_view_content()` image wrapper div)

### AD-089: Search Result Routing — State-Based Destination
- **Date**: 2026-02-17
- **Status**: ACCEPTED
- **Context**: Search results linked to Focus Mode (`/focus?identity={id}`) regardless of identity state. For confirmed identities with public person pages, this sent users into an admin-oriented triage workflow instead of the informational person page. For unidentified faces, Focus Mode was also wrong — the identification page is more appropriate for crowdsourcing.
- **Decision**: Route search results based on identity state. CONFIRMED identities link to `/person/{id}` (public profile page). INBOX and SKIPPED identities link to `/identify/{id}` (crowdsource identification page). PROPOSED identities link to `/identify/{id}` as well, since they are not yet confirmed. This uses the existing `_section_for_state()` pattern (Lesson 46) applied to search result link generation.
- **Alternatives Considered**: Always link to Focus Mode — forces all users through admin workflow. Always link to `/person/{id}` — unidentified persons have sparse pages with no useful content. Link to `/identify/{id}` for all — confirmed persons don't need identification help, their profile page is more useful.
- **Rationale**: Search is the primary discovery mechanism for non-admin users. Every search result click should lead to the most useful page for that identity's current state. Confirmed persons have rich profile pages; unidentified persons benefit from the crowdsource identification flow.
- **Affects**: `app/main.py` (search result link generation, `_search_results()`), consistent with `_section_for_state()` helper

### AD-090: Gemini-InsightFace Face Alignment via Coordinate Bridging
- **Date**: 2026-02-17
- **Context**: Current face-to-description alignment in `match_faces_to_ages()` uses left-to-right x-coordinate sorting. This FAILS for ~40% of group photos where Gemini describes N people but InsightFace detects M faces (M != N). The mismatch occurs because InsightFace detects background faces (newspaper clippings, posters, reflections, tiny occluded faces) that Gemini does not describe. When counts differ, the pipeline returns `"count_mismatch"` and discards all age data for that photo. This caused Vida Capeluto (15 photos, most prominent identity) to get zero birth year estimates.
- **Decision**: Approach B — feed InsightFace bounding box coordinates TO Gemini as labeled regions in the prompt text. Each detected face gets a letter label (Face A, B, C...) with pixel coordinates. Gemini describes each labeled face, marking non-subject faces (background, artifacts) as `is_subject: false`. The face labels map directly to InsightFace face_ids, providing guaranteed 1:1 mapping with no post-hoc matching needed.
- **Rejected**: Approach A — Gemini provides its own bounding boxes (`box_2d` in `[y_min, x_min, y_max, x_max]` format, normalized 0-1000). This requires IoU or center-point distance matching to pair Gemini boxes with InsightFace detections, introduces threshold tuning (what IoU counts as a match?), suffers from coordinate misalignment (Gemini may box the full head while InsightFace crops the tight face region), and adds a matching layer that can fail silently. The coordinate bridging approach (B) is strictly simpler and eliminates the matching problem entirely.
- **Novelty**: First known application of VLM spatial coordinate bridging for heritage photo analysis. Existing approaches (GLIP, Grounding DINO, Set-of-Mark) either have the VLM produce coordinates or overlay visual markers on images. Feeding detector coordinates as text tokens to the VLM and asking it to describe each region is a novel inversion that avoids both IoU matching and image modification.
- **EXIF caveat**: InsightFace bounding boxes are computed on the raw pixel grid. If the image has EXIF orientation metadata (rotation/flip), coordinates must be normalized to the visual orientation before inclusion in the Gemini prompt. `core/exif.py` already extracts orientation data.
- **Data model**: Extends `date_labels.json` with `face_descriptions` dict (keyed by face_id), `face_alignment_method` string, and updated `prompt_version`. Backward compatible — old labels without `face_descriptions` fall back to x-sort matching.
- **Cost**: ~$0.50-$1.00 to re-process all 271 photos (Gemini Flash pricing). Coordinate text adds ~100-200 tokens per photo.
- **Status**: PROPOSED (not yet implemented)
- **PRD**: `docs/prds/015_gemini_face_alignment.md`
- **Affected files**: `rhodesli_ml/scripts/generate_date_labels.py` (coordinate bridging prompt variant), `rhodesli_ml/pipelines/birth_year_estimation.py` (use `face_descriptions` before x-sort fallback), `rhodesli_ml/data/date_labels.py` (schema validation), `rhodesli_ml/scripts/clean_labels.py` (validate face_descriptions), `rhodesli_ml/scripts/audit_temporal_consistency.py` (direct face-to-age mapping), `rhodesli_ml/data/date_labels.json` (schema extension)

### AD-091: Calibrated Match Confidence Labels
- **Date**: 2026-02-17
- **Context**: Compare results displayed tier labels ("Very likely the same person") based on distance tiers (STRONG MATCH <1.05), but a result at 57% confidence could appear under "Very likely" because the tier threshold and the human-readable label were conflated. Users reported this as misleading.
- **Decision**: Decouple tier (section grouping) from confidence label (per-card text). Section headers use neutral names ("Strong Matches", "Possible Matches"). Per-card labels use calibrated percentage thresholds: ≥85% → "Very likely same person", 70-84% → "Strong match", 50-69% → "Possible match", <50% → "Unlikely match". Percentages are computed from CDF-based confidence (AD-067 kinship calibration).
- **Rejected**: Using tier names as labels (conflates grouping with confidence), using raw distance values (meaningless to non-technical users), binary same/different threshold (loses nuance).
- **Affected files**: `app/main.py` (`_compare_result_card()`, `_compare_results_grid()`), `tests/test_face_comparison.py` (TestCalibratedLabels)

### AD-092: Dual Photo Context in Help Identify Focus Mode
- **Date**: 2026-02-18
- **Context**: The Help Identify focus mode showed a "Photo Context" section with only the "Who is this?" source photo. Users couldn't see the best match's source photo for comparison.
- **Decision**: Show both source photos side by side in the Photo Context section. Each photo card shows collection name, thumbnail, and "View Photo Page" link. Share button shares the photo page URL (not the match comparison URL).
- **Rejected**: Single photo with tab toggle (adds unnecessary interaction), opening full photo modal (too disruptive in focus flow).
- **Affected files**: `app/main.py` (`_build_skipped_photo_context()`, `_build_skipped_suggestion_with_strip()`)

### AD-093: Face Carousel for Multi-Face Identities
- **Date**: 2026-02-18
- **Context**: On match comparison pages, only the best-quality face crop was shown for each person. Users with multiple appearances across different photos had no way to see alternative angles or contexts.
- **Decision**: Add left/right arrow navigation when an identity has multiple face crops. Pure JS with event delegation (`data-action="face-carousel-prev/next"`). Face data encoded as JSON in `data-faces` attribute. Counter shows "1 of N". Source photo cards remain static (would require HTMX swap to update).
- **Rejected**: Auto-playing slideshow (distracting), thumbnail grid below face (clutters comparison layout), HTMX-based carousel (adds server round-trips for a client-side concern).
- **Affected files**: `app/main.py` (`_face_card()`, `_face_carousel_script()`)

### AD-094: Year Estimation V1 — Gemini-First Approach
- **Date**: 2026-02-18
- **Context**: Most archive photos have no date. Existing Gemini labels include `subject_ages` (apparent ages left-to-right) and scene-based decade estimates. Birth year data exists from GEDCOM and ML pipeline. These can be combined without any new model training.
- **Decision**: V1 uses pre-computed data only (no real-time Gemini API calls). Pipeline: (1) load subject_ages from date_labels.json, (2) match faces to identities via bbox x-coordinate sorting, (3) compute estimated_year = birth_year + apparent_age for identified faces, (4) weighted aggregation (confirmed=2x, ML=1x), (5) scene evidence as supporting context. Falls back to scene-only when no identified faces.
- **Rejected**: Real-time Gemini API calls per request (cost, latency, API key requirement), dedicated age estimation model (requires training infrastructure, V2 goal), storing estimates in photo_index.json (computed on-the-fly from existing data is simpler).
- **Affected files**: `core/year_estimation.py`, `app/main.py` (`/estimate` route)

### AD-095: Multi-Face Probabilistic Aggregation for Year Estimation
- **Date**: 2026-02-18
- **Context**: When multiple identified faces have known birth years, their individual year estimates may disagree due to age estimation noise. Need a principled way to combine them.
- **Decision**: Weighted average with confirmed birth years weighted 2x vs ML-inferred at 1x. Margin computed from spread between estimates (min 3, max 15 years). Confidence tiered: 2+ confirmed = high, 1 confirmed = medium, ML-only = medium, scene-only = low. This is intentionally simple for V1.
- **Rejected**: Bayesian posterior with Gaussian likelihoods (over-engineering for V1), median instead of weighted mean (loses birth year source information), fixed margin regardless of agreement (doesn't reflect actual estimation quality).
- **Affected files**: `core/year_estimation.py` (`estimate_photo_year()`)

### AD-096: Lightbox Face Overlays on Match Page
- **Date**: 2026-02-18
- **Context**: The match page lightbox showed only the photo image with face chip thumbnails below. Users couldn't see exactly where faces were detected in the full-size photo view.
- **Decision**: Add face bounding box overlays to the match page lightbox using percentage-based CSS positioning. Highlighted face (the one being compared) gets amber border + glow. Other faces get state-based colors (green=confirmed, gray=other). Overlays are clickable, navigating to /person or /identify pages. Name labels shown below each box. Metadata bar (collection + date) and "View Photo Page" link added below the image.
- **Rejected**: Using the HTMX photo modal instead (would require restructuring the match page's lightbox system), canvas-based overlays (more complex, no benefit for static overlays).
- **Affected files**: `app/main.py` (`_match_lightbox_script()`, `_match_source_photo_card()`, lightbox HTML)

### AD-097: ML Gatekeeper Pattern — Staged Review Before Public Display
- **Date**: 2026-02-18
- **Context**: Session 34 built a birth year estimation pipeline with 32 ML estimates, but they were displayed directly to the public on person pages and timelines without admin review. This created "phantom features" — data visible to users before validation.
- **Decision**: All ML outputs are PROPOSALS, not facts. They must pass through an admin review gate before entering canonical identity data. Implementation: `_get_birth_year(include_unreviewed=False)` for public views, `True` for admin. Review decisions stored in `data/ml_review_decisions.json` with accept/reject/edit actions. Accepted values are written to identity metadata via `set_metadata()`. Rejected values are filtered from all views including admin.
- **Rejected**: (1) Auto-publish high-confidence estimates (even 95% confidence can be wrong for heritage photos), (2) User voting on estimates (too few users currently), (3) Separate "ML estimates" UI section (adds complexity, still shows unverified data to public).
- **Pattern**: This generalizes to ANY future ML output — relationship predictions, auto-tags, date estimates, etc. All must go through admin review before becoming canonical.
- **Affected files**: `app/main.py` (`_get_birth_year()`, `_load_ml_review_decisions()`, `_save_ml_review_decisions()`, review API endpoints, bulk review page, person page, timeline), `data/ml_review_decisions.json`, `data/ground_truth_birth_years.json`
- **Tests**: `tests/test_ml_gatekeeper.py` — 23 tests covering gatekeeper filtering, suggestion card visibility, review endpoints, bulk review, cache invalidation.
- **See also**: `docs/session_context/session_47_planning_context.md` for full research context.

### AD-098: Feature Reality Contract
- **Date**: 2026-02-18
- **Context**: The Year Estimation Tool V1 (/estimate) was built in Session 46 but returned 404 on production — a "phantom feature" that passed all tests locally but didn't exist for users. The birth year data was also partially visible without review gating.
- **Decision**: A feature is NOT done unless it satisfies the full reality chain: (1) Data file exists, (2) App loads it at startup, (3) Route exposes it, (4) UI renders correctly, (5) Test verifies the chain end-to-end. Every session must run a production verification step (curl rendered HTML, not just check local files). Phantom features are categorized as: Ghost Routes (404 on production), Ungated Data (ML output shown without review), Dead Wiring (data loaded but never rendered).
- **Enforcement**: `.claude/rules/feature-reality-contract.md` path-scoped rule.
- **Affected files**: `.claude/rules/feature-reality-contract.md`, verification workflow.

### AD-099: Confirmed Data → ML Feedback Loop
- **Date**: 2026-02-18
- **Context**: When admins confirm, reject, or correct ML birth year estimates, this creates high-value ground truth data. Each confirmed birth year + photo dates = labeled training sample (face_embedding, true_age). This data should feed back into future ML model retraining.
- **Decision**: Admin review decisions are persisted to `data/ground_truth_birth_years.json` with provenance (ml_accepted vs admin_correction), the original ML estimate, reviewer identity, timestamp, and face appearances (face_id + photo_id + photo_date for each appearance). This enables semi-supervised learning: small labeled set (confirmed identities) anchors learning from large unlabeled set (all detected faces).
- **Data schema**: `{identity_id, birth_year, source, original_ml_estimate, reviewed_at, reviewed_by, face_appearances: [{face_id, photo_id, photo_date}]}`
- **Affected files**: `app/main.py` (`_save_ground_truth_birth_year()`), `data/ground_truth_birth_years.json`

### AD-100: User Input Taxonomy — Seven Data Flow Categories
- **Date**: 2026-02-18
- **Context**: Rhodesli accepts user input through many channels. Understanding the taxonomy helps ensure each type gets appropriate validation and provenance tracking.
- **Decision**: Seven categories of user input, from lowest to highest trust: (1) Anonymous annotations — guest comments, no auth, rate-limited. (2) Authenticated suggestions — logged-in users propose identifications, pending admin review. (3) Admin confirmations — merge/confirm/reject identity decisions, immediate effect. (4) ML review decisions — accept/reject/edit ML estimates (AD-097). (5) Metadata corrections — admin edits birth year, place, name, with provenance tracking. (6) Photo uploads — staged, admin-moderated before public. (7) GEDCOM import — batch family data with match review. Each category has different trust levels, validation requirements, and provenance tracking.
- **Affected files**: `app/main.py` (various endpoints), `core/registry.py`, `data/annotations.json`, `data/ml_review_decisions.json`

### AD-101: Gemini 3.1 Pro for All Vision Work
- **Date**: 2026-02-19
- **Context**: Gemini 3.1 Pro released Feb 19, 2026 with 77.1% ARC-AGI-2 (2x improvement over 3 Pro), improved vision and bounding box capabilities, 1M token context. Same pricing as 3 Pro ($2.00/$12.00 per 1M tokens).
- **Decision**: Use `gemini-3.1-pro-preview` for ALL vision tasks: date estimation, face alignment (PRD-015), evidence extraction, location analysis. Evidence quality is a core UX differentiator — the "wow factor" of Gemini describing "1920s Marcel wave hairstyle, hand-tinted coloring typical of Rhodes studios" is what makes users share the tool.
- **Rejected**: Flash models for vision work (cheaper but worse evidence quality for the key differentiating feature); keeping 3 Pro when 3.1 Pro is available at same price with 2x reasoning improvement.
- **Cost**: ~$7.60 for full library (271 photos), ~$15.20 for complete re-analysis (date + face alignment).
- **Affected files**: `rhodesli_ml/scripts/generate_date_labels.py` (MODEL_COSTS), `rhodesli_ml/scripts/cost_tracker.py` (MODEL_PRICING), `docs/prds/015_gemini_face_alignment.md`

### AD-102: Progressive Refinement — Re-Run VLM on Verified Facts
- **Date**: 2026-02-19
- **Context**: Initial Gemini analysis runs with zero context about a photo. But as community members identify people, confirm dates, provide location info, and upload GEDCOM data, we accumulate verified facts that could dramatically improve the analysis. Example: a postcard from Rhodes — initial estimate "1920s-1940s, low confidence." After confirming the location is Rhodes, Gemini can narrow to "1925-1935" using region-specific hairstyles and studio conventions.
- **Decision**: Fact-Enriched Re-Analysis architecture. When a verified fact is confirmed (identity, date, location, event), trigger re-analysis: (1) Gather verified context (confirmed identities + birth years, confirmed location, confirmed events, GEDCOM data, previous analysis). (2) Build enriched prompt with known facts. (3) Call Gemini 3.1 Pro with enriched prompt + image. (4) Compare old vs new results quantitatively. (5) Stage for admin review via Gatekeeper pattern (AD-097). Key principles: ALWAYS log all API results; ALWAYS compare old vs new estimates; NEVER overwrite without admin review; build analytical dataset of which facts improve estimates most. Combined API call: date + faces + location in ONE Gemini call (more cost-efficient AND better results due to cross-referencing evidence).
- **Rejected**: Separate API calls for date, faces, and location (3x cost, loses cross-referencing); automatic overwrite without review (violates AD-097 Gatekeeper pattern); self-generated feedback (SELF-REFINE pattern) — our approach uses external verified facts from community, which is more reliable.
- **Academic context**: Closest to SELF-REFINE (Madaan et al. 2023) but with external verified facts rather than self-generated feedback. Also parallels DeepMind's Ithaca for dating ancient inscriptions using geographic + temporal context.
- **Status**: Architecture documented. Implementation deferred to Session 52+ when Gemini API calls are enabled.
- **Affected files**: Future — `rhodesli_ml/pipelines/progressive_refinement.py`, `data/api_logs/`, `app/main.py` (admin review routes)

### AD-103: Comprehensive API Result Logging
- **Date**: 2026-02-19
- **Context**: To build an analytical dataset for understanding model performance, comparing model versions, and identifying which verified facts improve estimates most, every Gemini API call must be comprehensively logged.
- **Decision**: Log every Gemini call to `rhodesli_ml/data/api_logs/YYYY-MM-DD_HH-MM-SS_{photo_id}.json` with: timestamp, photo_id, model, prompt_version, input_context (verified facts, previous estimate), full response, cost (input/output tokens + USD), comparison (if re-analysis: old vs new estimate, confidence change, delta years). Periodic analysis via `rhodesli_ml/scripts/analyze_api_logs.py`: cost per photo, accuracy improvement from verified facts, which fact types help most, model comparison. Automated eval suite on model upgrade: select 20 photos with known dates, run new model, compare to previous logged results, report accuracy/evidence/cost deltas.
- **Rejected**: Logging only cost (misses analytical value); logging to database (premature — JSON files sufficient at current scale of ~300 photos); skip logging for re-analysis (loses the most valuable data about progressive improvement).
- **Status**: Schema defined. Implementation with first API calls in Session 52+.
- **Affected files**: Future — `rhodesli_ml/data/api_logs/`, `rhodesli_ml/scripts/analyze_api_logs.py`

### AD-104: Quick-Identify Architecture — Admin-Only Sequential Tagging
- **Date**: 2026-02-19
- **Context**: Community sharing on Facebook produced identifications faster than the admin could enter them (Carey Franco's 8 names in one comment). Needed: inline face naming without page navigation.
- **Decision**: P0 (inline tag dropdown on face click) was already implemented. For P1 (sequential "Name These Faces" mode): admin-only, uses same merge/create code paths as existing tag flow, HTMX `seq=1` parameter propagated through tag/create/tag-search endpoints, photo view re-renders with seq_mode to auto-open next unidentified face's dropdown. Faces ordered left-to-right by bbox x1 coordinate. Non-admin users continue to use existing /identify/{id} page and annotation suggestion flow.
- **Rejected**: Client-side-only sequential mode (fragile, loses state on re-render); separate quick-identify API endpoint (duplicate code path, invariant risk per Session 11); non-admin inline identification (requires building second approval flow, out of scope).
- **Status**: IMPLEMENTED (Session 51).
- **Affected files**: `app/main.py` (photo_view_content, /api/face/tag, /api/face/create-identity, /api/face/tag-search), `docs/prds/021_quick_identify.md`

### AD-110: Hybrid ML Architecture — Serving Path Contract + Cloud Lightweight + Local Heavy
- **Date**: 2026-02-20
- **Status**: ACCEPTED
- **Source**: Comprehensive ML architecture review, Session 54. Research: Immich (docs.immich.app/developer/architecture), PhotoPrism, Facebook DeepFace. Previous discussions: Sessions 4-8 (local-only), Session 32 (compare introduced), Session 52 (ML to cloud).

**The Serving Path Contract (Non-Negotiable Invariant):**
The user-facing request path MUST NEVER run heavy ML processing. Every successful photo system (Facebook, Immich, PhotoPrism) enforces this. All of Rhodesli's architectural drift occurred because this invariant was never named or locked. This invariant is the foundation — everything else is implementation detail.

**Hard Product Constraints (derived from the contract):**
1. Upload returns immediately
2. Photo is visible immediately
3. Enrichment arrives progressively
4. All interactive features use precomputed data

**Context:**
Session 52 moved InsightFace into the Docker image (PROCESSING_ENABLED=true), making the web app a monolith that serves pages AND runs ML. This causes: 65-second compare times on Railway shared CPU (19-face group photo), 3-4GB Docker image (was 200MB), unpredictable CPU availability on shared Railway hosting.

**Decision:** Adopt a hybrid architecture:

CLOUD (Railway web app):
- Serve pages, handle auth, manage data
- Compare: use pre-computed archive embeddings for matching (0.4s)
- Compare face detection: resize to 640px (matching InsightFace det_size), target <15s
- Estimate: Gemini API calls (already cloud-native, fast)
- Upload: save to R2 immediately, show photo, queue for local processing
- NO heavy batch processing on Railway

LOCAL (Nolan's machine):
- Batch face detection with buffalo_l (highest quality)
- Embedding generation for new photos
- Clustering / reclustering (DBSCAN)
- Quality scoring
- Batch Gemini enrichment
- Ground truth pipeline

FUTURE EVOLUTION (Session 56+):
- Move face detection to client-side JS (MediaPipe Face Detection)
- Server only does embedding comparison (numpy, no InsightFace)
- Remove InsightFace from Docker image entirely (return to ~200MB)

**buffalo_sc Investigation Result (Session 54):**
buffalo_sc uses MobileFaceNet recognition backbone; buffalo_l uses ResNet50. Embeddings are NOT interchangeable — different embedding spaces despite same 512 dimensions and same training data. Switching would require re-embedding all ~550 faces. buffalo_m shares buffalo_l's recognition model (w600k_r50) but lighter detection model — potential future optimization. For now, 640px resize is the primary performance lever.

**Note on test pyramid inversion:** 2480 tests validate data logic in isolation, but production failures are cross-service, async, environment, and UX-timing issues. Future sessions should prioritize observability and integration tests over unit test count.

**Rationale:**
- At 271 photos and single-admin scale, a full job queue (Redis/BullMQ) is overkill
- The hybrid approach gives instant interactive responses while keeping quality high for batch
- Removing InsightFace from Docker is the end goal but requires client-side face detection work
- 640px resize alone estimated 5-15s vs 65s

**Tradeoffs:**
- New photos don't get full ML processing until local pipeline runs
- Compare quality slightly lower with 640px resize (acceptable for interactive use)
- Two processing paths to maintain (cloud lightweight vs local heavy)

**Enforcement:**
- Compare endpoint MUST resize to 640px for ML (original to R2 for display)
- Batch ingestion MUST use buffalo_l locally
- Upload endpoint MUST return within 5 seconds (save to R2, no ML blocking)
- Docker image size should be monitored — target <2GB, goal <500MB

**Affected files:** `app/main.py` (compare upload, estimate upload), `core/ingest_inbox.py` (get_face_analyzer), `Dockerfile`, `scripts/push_to_production.py`

### AD-111: [Future Design] Face Processing Lifecycle States
- **Date**: 2026-02-20
- **Status**: DOCUMENTED (implement with Postgres migration, Phase F)
- **Source**: External expert review of Session 54 architecture
- **Concept**: Every face moves through: UPLOADED → DETECTED → EMBEDDED → IDENTIFIED → VERIFIED. These must be separate lifecycle states, not conflated. Currently Rhodesli mixes "photo exists" / "face detected" / "embedding exists" / "identity known" without clear state boundaries. This causes fragile features.
- **Why not now**: Rhodesli uses JSON files. Proper lifecycle states require a relational data layer. Save for Postgres migration (Phase F).
- **When**: Phase F (Postgres migration) or when face count exceeds JSON performance limits.

### AD-112: [Rejected] Serverless GPU (Modal) in Session 56
- **Date**: 2026-02-20
- **Status**: REJECTED (for now)
- **Source**: External assistant review of Session 54 architecture
- **Proposal**: Deploy InsightFace to Modal.com serverless GPU for <2s face detection.
- **Why rejected**: Scale mismatch. 271 photos, 3 community users, single admin. Modal adds API key management, cross-service networking, cold starts (10-30s on free tier), cost monitoring, and a new deployment target. This solves a 10x-scale problem today.
- **The right move**: 640px resize gets compare to ~5-10s. Acceptable for a heritage archive at current scale. Modal is the correct evolution AFTER client-side face detection and AFTER community scale justifies distributed systems complexity.
- **Revisit**: When community grows to 50+ active users or photo count exceeds 2000.

### AD-113: [Rejected] Remove ML from Serving Path Immediately
- **Date**: 2026-02-20
- **Status**: REJECTED (premature)
- **Source**: External expert review of Session 54 architecture
- **Proposal**: Remove ALL ML execution from request/response flow immediately.
- **Why rejected**: This breaks compare today. Compare NEEDS face detection to work. The intermediate step (640px resize) makes compare usable while we build toward the pure architecture (client-side detection in Session 56+).
- **The right path**: 640px resize NOW → MediaPipe client-side NEXT → then remove InsightFace from Docker entirely.

### AD-114: Hybrid Detection — buffalo_sc Detector + buffalo_l Recognizer
- **Date**: 2026-02-20
- **Status**: ACCEPTED
- **Source**: External review correction of Session 54's buffalo_sc investigation. Session 54 concluded buffalo_sc was fully incompatible. This was partially correct (recognition models ARE incompatible) but missed that detection and recognition are separate ONNX files that can be mixed.

**The Models:**
- buffalo_l: det_10g.onnx (10G FLOPs, 16MB) + w600k_r50.onnx (ResNet50, 166MB)
- buffalo_sc: det_500m.onnx (500M FLOPs, 2.4MB) + w600k_mbf.onnx (MobileFaceNet, 13MB)

**Key Insight:** InsightFace loads detection and recognition as separate ONNX models. We can use det_500m (fast, 20x less compute) for detection and w600k_r50 (archive-compatible) for recognition.

**Empirical Results (Session 54B, local Mac):**

| Config | Detection Time | Faces (40-face photo) | Embedding Compat |
|--------|---------------|----------------------|-----------------|
| buffalo_l full | 4.661s | 40 | baseline |
| buffalo_sc full | 0.042s | 38 | 0.0 (incompatible) |
| Hybrid (det_500m + w600k_r50) | 2.546s | 38 | 0.98 mean cosine sim |

Multi-photo validation (8 face pairs across 3 photos): mean 0.982, min 0.972, max 0.993.

**Detection Recall Tradeoff:** det_500m misses ~2 faces on large group photos (38/40, 19/21). These are marginal faces (small, low quality) that the heavier detector finds. This is acceptable for interactive compare where speed matters more than marginal face detection. Batch ingestion continues to use buffalo_l for maximum recall.

**Decision:** Use hybrid for interactive endpoints (compare upload, estimate upload). Keep buffalo_l for batch pipeline (ingest_inbox). Hybrid falls back to buffalo_l if buffalo_sc models aren't available.

**Performance Impact on Railway (estimated):**
- det_10g on shared CPU: ~15-25s (the bottleneck in 65s compare times)
- det_500m on shared CPU: ~1-3s (estimated from 20x FLOP reduction)
- Expected compare total: 5-15s (down from 15-25s)

**Files Affected:**
- `core/ingest_inbox.py`: Added `get_hybrid_models()`, `extract_faces_hybrid()`
- `app/main.py`: Compare and estimate upload endpoints use `extract_faces_hybrid()`
- `app/main.py`: Startup preloads hybrid models alongside buffalo_l

**Alternatives Considered:**
- Full buffalo_sc replacement: REJECTED — recognition embeddings incompatible (cosine ~0.0), would require re-embedding all 550 faces
- buffalo_m (medium): Not investigated — buffalo_sc detector is sufficient
- Client-side detection (MediaPipe): Deferred to Session 56 — eliminates server detection entirely

### AD-115: Memory Infrastructure Evaluation — Current In-Repo Harness Sufficient
- **Date**: 2026-02-20
- **Session**: 54c
- **Status**: Decided — no external memory tools adopted
- **Context**: As ML pipeline complexity grows (face detection, kinship calibration, date estimation, similarity calibration, future LoRA), evaluated whether external memory tooling would improve decision recall, cross-session context, or cross-project reuse.
- **Decision**: Continue with existing in-repo documentation (ALGORITHMIC_DECISIONS.md, DECISION_LOG.md, session_context files, .claude/rules/). No external memory tools adopted.

**Alternatives Evaluated and Rejected:**

1. **NotebookLM MCP** — Community-built MCP using browser automation (headless Chrome) to drive NotebookLM. Fragile: session cookies expire every 2-4 weeks. One implementation provides 29 tools (massive context window cost). Uses undocumented internal APIs. Good as manual interview prep explainer, not as primary system.
2. **Mem0 / Vector Memory MCP** — Semantic memory layer via embeddings (free tier: 10k memories/month). No explicit reasoning chain — can't audit WHY a decision was made. Terrible for interviews. Structured ALGORITHMIC_DECISIONS.md with context/alternatives/tradeoffs is MORE useful for both agent recall and interview prep.
3. **Notion MCP** — Lets Claude query Notion databases. Creates second source of truth that drifts from repo. Changes in Notion don't get committed. Better for product planning than system memory.
4. **LangChain memory modules** — Solves a different problem (LLM app orchestration, not dev workflow documentation).

- **Rationale**: Context rot in Rhodesli is primarily session-level (addressed by prompt decomposition/verification gates from Session 48), not project-level. Existing docs handle project-level knowledge preservation well. Vector stores add infrastructure maintenance without proportional benefit at current scale (~115 AD entries, 1 project).
- **Revisit conditions**: (a) 500+ decisions across 5+ projects → semantic search becomes valuable (b) Google ships proper NotebookLM API (c) Project grows to need cross-tool memory
- **Breadcrumbs**: docs/session_context/session_54c_planning_context.md (Part 1: full research)

### AD-116: MLflow Integration Strategy — Targeted, Starting with CORAL Training
- **Date**: 2026-02-20
- **Session**: 54c
- **Status**: Accepted — targeted integration
- **Context**: Needed to decide whether formal experiment tracking infrastructure was warranted for a solo developer with ~155 photos and <50 total expected experiment runs.
- **Decision**: Add MLflow with minimal overhead. Start with `mlflow.pytorch.autolog()` in CORAL training (~10 lines of code). Run locally via `mlflow ui`. Expand to Gemini prompt tracking and local-vs-web ML benchmarking as those features mature.

**Alternatives Considered:**
1. Manual EXPERIMENTS.md markdown log — sufficient at current scale, but no portfolio talking point
2. Weights & Biases — cloud-hosted, more polished UI, but adds external dependency and cost
3. Full MLflow server deployment — overkill for solo developer

- **Rationale**: Primary value is portfolio demonstration ("Do you have MLflow experience?" → "Yes, here's my tracking UI"), not operational necessity. Secondary value: tracking Gemini API prompt iterations to see if different prompts yield better photo labeling. Minimal code overhead with autolog.
- **Affects**: rhodesli_ml/ training scripts, local development environment
- **Breadcrumbs**: docs/session_context/session_54c_planning_context.md (Part 1B: MLflow section)

### AD-117: Face Compare Product Architecture — Three-Tier Plan
- **Date**: 2026-02-20
- **Session**: 54c
- **Status**: Accepted — Tier 1 prioritized for near-term build
- **Context**: Competitive analysis of 7+ existing face comparison tools revealed all provide single percentage scores with no kinship context, no cross-age capability, and no calibration against real genealogical data. Rhodesli's Session 32 kinship calibration (AD-067) and multi-face detection (AD-069) already exceed the capabilities of every free tool surveyed.

**Decision: Three-tier product plan.**

**Tier 1 — Minimal Viable Standalone (1-2 sessions):**
- New FastHTML app at subdomain (TBD: facecompare.nolanandrewfox.com or similar)
- Same InsightFace backend + kinship calibration from Session 32
- Stripped-down UI: upload two photos → tiered results → no persistence
- Mobile-responsive, privacy-first (photos deleted after comparison)
- Differentiation: "Calibrated against real genealogical data"

**Tier 2 — Shared Backend Architecture (2-3 sessions):**
- Shared comparison engine between standalone and Rhodesli
- Rhodesli path adds: archive identity matching, upload persistence, date context
- Public path: compare and discard

**Tier 3 — Product Grade (deferred post-employment):**
- User accounts, saved comparisons, API access, batch comparison

**Key Differentiators vs. Competition:**
- Empirically calibrated kinship thresholds from confirmed genealogical identities
- Tiered results (identity match / possible relative / similar features) instead of single score
- Multi-face detection on group photos
- Cross-age matching capability
- Scientifically honest about limitations (Cohen's d=0.43 for family resemblance)

**Alternatives Considered:**
- Build only within Rhodesli (no standalone) — misses opportunity for portfolio piece and potential product
- Jump straight to Tier 3 — scope creep, months of work, distracts from job search

- **Affects**: New deployment (subdomain TBD), shared code with Rhodesli compare route
- **Breadcrumbs**: docs/session_context/session_54c_planning_context.md (Part 2: full competitive analysis), AD-067, AD-068, AD-069

### AD-118: [Deferred] LangChain NL Archive Query
- **Date**: 2026-02-20
- **Session**: 54c
- **Status**: Deferred — future product feature after core ML is solid
- **Context**: Identified that LangChain's orchestration capabilities map well to a natural language interface for the photo archive: "Show me photos of people who look like my grandmother from the 1930s" → chain face detection → embedding search → date filtering → NL response.
- **Decision**: Document as future initiative. Do not build until similarity calibration, LoRA, and core UX are stable. Estimated 2-3 sessions for basic MVP once prerequisites are met.
- **Why deferred**: LangChain adds complexity (extra abstraction layers, frequent breaking changes, steep learning curve). Core ML capabilities it would chain together don't all exist yet. Portfolio value is high but only after the underlying ML is demonstrably strong.

**Prerequisite milestones:** Similarity calibration complete, CORAL date estimation deployed, identity matching reliable

- **Affects**: Future new module, would chain existing Rhodesli ML capabilities
- **Breadcrumbs**: docs/session_context/session_54c_planning_context.md (Part 1B: LangChain section)

1. Add a new entry with AD-XXX format (next: AD-119)
2. Include the rejected alternative and WHY it was rejected
3. List all files/functions affected
4. If the decision came from a user correction, note that explicitly
5. Cross-reference config files that encode the decision's parameters
