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

---

## Adding New Decisions

When making any algorithmic choice in the ML pipeline:
1. Add a new entry with AD-XXX format (next: AD-050)
2. Include the rejected alternative and WHY it was rejected
3. List all files/functions affected
4. If the decision came from a user correction, note that explicitly
5. Cross-reference config files that encode the decision's parameters
