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

### AD-027: MLS vs Euclidean — RESOLVED: Euclidean Wins
- **Date**: 2026-02-11 (opened), 2026-03-04 (resolved)
- **Context**: AD-003 specifies MLS as the distance metric, but the audit (docs/ml/current_ml_audit.md) found ALL runtime code uses Euclidean. sigma_sq is computed but ignored.
- **Status**: RESOLVED. Euclidean is the correct metric for this archive.
- **Hypothesis**: MLS may improve matching for low-quality heritage photos where sigma_sq should down-weight uncertain embeddings. But since all sigma_sq values are scalar-uniform (not per-dimension), the benefit may be minimal.
- **Evaluation** (scripts/evaluate_mls_vs_euclidean.py, seed=42):
  - Dataset: 221 same-identity pairs (10 confirmed identities, 8 with 2+ valid faces), 500 cross-identity pairs
  - All 1,061 embeddings have scalar/uniform sigma_sq (not per-dimension)
  - **ROC AUC**: Euclidean=0.9903, MLS=0.9454 (Euclidean wins by +0.0449)
  - **Precision@Recall=0.95**: Euclidean=0.8367, MLS=0.5966
  - **Optimal F1**: Euclidean=0.9464, MLS=0.8040
  - **Separation (d')**: Euclidean=3.13, MLS=2.25
  - MLS same-identity scores have high variance (std=0.94) due to the scalar sigma path amplifying distance differences through the 1/(sigma1+sigma2) term, which makes MLS less discriminative when sigma values vary across face quality levels.
- **Decision**: Keep Euclidean distance in `core/neighbors.py`. MLS with scalar sigma_sq provides no benefit and actively degrades discrimination. The sigma_sq values computed by `core/pfe.py:compute_sigma_sq()` remain available if per-dimension PFE embeddings are added in the future.
- **Affects**: No production code changes. `core/neighbors.py` remains frozen with Euclidean metric.

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

### AD-089: Pre-Emptive Full Graph Generation
- **Date**: 2026-02-27 (Session 74)
- **Status**: ACCEPTED
- **Context**: The `build_relationship_graph` logic previously filtered out all connections unless BOTH endpoints existed as confirmed archive identities. This meant the tree viz naturally collapsed into fragments.
- **Decision**: Refactoring `build_relationship_graph.py` to output a unified graph merging confirmed identity UUIDs with raw GEDCOM `xref_id` fallback nodes. Replaced the `relationships.json` output pattern to just output the pure graph list directly, bypassing `data/relationships.json` metadata wrapper to remain consistent.
- **Rationale**: The visualization of a family tree requires the entire tree skeleton to remain unbroken to see pathways between archive identities.
- **Affects**: `rhodesli_ml/graph/relationship_graph.py`, `scripts/rebuild_full_graph.py`

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

### AD-119: Compare Performance Optimization — Model Lifecycle

- **Date**: 2026-02-20
- **Session**: 54F
- **Status**: ACCEPTED — deployed and verified in production

**Problem:** Compare upload took 51.2s on Railway production (Session 54D). Local Mac: 0.3-1.3s. The 40-50x gap was not normal CPU speed difference.

**Root causes found:**
1. **buffalo_sc not in Docker image** (PRIMARY — ~30-40s impact): Dockerfile only downloaded buffalo_l. On Railway, `get_hybrid_models()` returned (None, None), falling back to full buffalo_l with all 5 ONNX models via `FaceAnalysis`. det_10g (10G FLOPs) on Railway shared CPU ≈ 30-40s for detection alone.
2. **Unnecessary models loaded**: buffalo_l FaceAnalysis loaded all 5 models (1k3d68, 2d106det, det_10g, genderage, w600k_r50). Only detection + recognition needed.
3. **No ONNX thread optimization**: ONNX defaults to threads = physical cores with spin-waiting, causing contention on shared vCPU.
4. **No model warmup**: First ONNX inference pays JIT compilation cost (3.78s → 0.34s locally).
5. **OOM from dual FaceAnalysis** (discovered during deploy): Loading both buffalo_l FaceAnalysis AND hybrid models exceeded Railway 512MB.

**Fixes applied:**
1. Added buffalo_sc to Dockerfile (separate RUN step to avoid build OOM)
2. `allowed_modules=['detection', 'recognition']` for buffalo_l fallback
3. `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1` in Dockerfile
4. Dummy warmup inference at startup
5. Startup loads ONLY hybrid models; buffalo_l FaceAnalysis lazy-loaded as fallback

**Performance results:**

| Environment | Before | After | Improvement |
|-------------|--------|-------|-------------|
| Local first (cold) | 3.78s | 0.34s | 11x |
| Local warm | 0.50s | 0.19s | 2.6x |
| Production 2-face (warm) | 51.2s | 10.5s | 4.9x |
| Production 14-face | ~65s est. | 28.5s | ~2.3x |

**Remaining bottleneck (production):**
- det_500m detection on shared CPU: ~3-5s
- w600k_r50 recognition: ~1-1.5s per face
- R2 upload (save result): ~2-3s
- Further improvement requires GPU or client-side detection (MediaPipe, Session 56)

**ONNX Runtime configuration:**
- intra_op_num_threads: 1 (via OMP_NUM_THREADS env var)
- Hybrid: det_500m + w600k_r50 (via get_model, not FaceAnalysis)
- Warmup: yes (dummy 640x640 image at startup)
- Startup memory: ~200MB (one detector + one recognizer)

- **Affects**: Dockerfile, app/main.py (startup), core/ingest_inbox.py (get_face_analyzer, get_hybrid_models, extract_faces_hybrid)
- **Rejected**: Loading full buffalo_l FaceAnalysis at startup (OOM on Railway 512MB)
- **Breadcrumbs**: docs/session_context/session_54f_log.md, AD-110, AD-114

### AD-120: ML Model Loading Observability — Silent Fallbacks Are Bugs

- **Date**: 2026-02-20
- **Session**: 54G (generalized from 54F root cause)
- **Status**: ACCEPTED — principle, not code change

**Problem:** Session 54F discovered that hybrid face detection silently fell back from buffalo_sc (500M FLOPs) to buffalo_l (10G FLOPs) because buffalo_sc wasn't in the Docker image. The singleton was working correctly — it was loading the wrong (heavier) model. Smoke tests all passed because output format was identical between models. Only latency revealed the issue (51.2s vs expected ~10s).

**Generalizable principle:** Silent ML model fallbacks are bugs, not features. When a fallback produces correct-looking output from the wrong model, it is invisible to functional tests. Only latency or resource metrics reveal the problem.

**Decision:** All ML model loading in Rhodesli must:
1. Log which model was actually loaded at INFO level (model name, path, size)
2. Log WARNING if any fallback occurred (intended model, actual model, reason for fallback)
3. Include model name in singleton cache keys so fallbacks don't silently replace the intended model
4. Never swallow ImportError or FileNotFoundError during model loading without WARNING

**Applies to:** Face detection (buffalo_sc/buffalo_l), CORAL age estimation, future similarity calibration, LoRA training, Gemini API calls (model version logging), any new model integration.

**Why this matters beyond Rhodesli:** Any ML system with fallback chains (common in production — GPU → CPU, large → small model, local → API) is vulnerable to this class of bug. The fix is always the same: instrument the loading, not just the output.

- **Rejected**: Relying on output format differences to detect fallbacks (buffalo_sc and buffalo_l produce identically-shaped outputs — 512-dim embeddings)
- **Rejected**: Only logging at startup (some models are lazy-loaded on first request; must log at actual load time)
- **Affects**: All files that call `get_model()`, `FaceAnalysis()`, `get_hybrid_models()`, or load ONNX/PyTorch models
- **Breadcrumbs**: AD-119 (specific fix), HD-012 (harness decision), docs/PERFORMANCE_CHRONICLE.md, Session 54F

### AD-121: Interactive Upload UX — SSE Progress Streaming Architecture

- **Date**: 2026-02-20
- **Session**: 54G (design only — not yet implemented)
- **Status**: DESIGN ONLY — implementation is a 2-3 session epic

**Problem:** Compare/estimate uploads take 10-28s on Railway shared CPU with zero user feedback. Users think the page is broken. The current UX is: click upload → stare at nothing → maybe results appear.

**Nolan's UX specification:**
1. Photo preview appears immediately after upload
2. Progress bar with text summarizing current step, face count, and pipeline stage
3. Faces populate below one-by-one as detection completes
4. Face overlays on photo change colors through pipeline stages (detection → embedding → comparison)
5. Fully interactive when complete (same as other photo views)
6. Transition between compare and estimate views with same photo
7. Every uploaded photo saved as if submitted through main upload flow (gatekeeper pattern)
8. Support 2-3 concurrent uploads via server-side queue
9. Multi-photo upload required for compare; TBD for estimate
10. Progress text: "distilled for non-technical person that a technical person could still use to figure out what part of the ML pipeline it was at"

**Decision:** Use Server-Sent Events (SSE) for server→client progress streaming.
- POST upload returns job_id immediately (202 Accepted)
- Client opens SSE connection to `/api/upload/progress/{job_id}`
- Server emits events: `face_detected`, `embedding_computed`, `comparison_result`, `complete`
- HTMX partial swaps render faces progressively as each event arrives
- `asyncio.Queue` for concurrent upload management (Railway single-worker)

**Why SSE over WebSockets:**
- One-way server→client only needed for progress updates
- SSE auto-reconnects on connection drop (browser-native)
- FastHTML compatible (no WebSocket library needed)
- No bidirectional overhead
- HTMX has native SSE extension support

**Why asyncio.Queue over Redis:**
- Railway single-worker would timeout without serialization
- Queue allows 2-3 concurrent uploads to process sequentially while showing progress for all
- asyncio.Queue is simplest (no Redis dependency, no external service)
- Can upgrade to Redis-backed if Railway adds workers later

**Multi-photo design:** Required for compare (upload reference + candidates). Single photo for estimate. TBD: unified upload zone that switches mode based on photo count.

**Every uploaded photo enters gatekeeper pipeline** (same as main upload flow) — no photo enters the archive without face detection + embedding + quality check.

**Research references:**
- FastHTML SSE example: fabge/fasthtml-sse (GitHub) — chatbot pattern, adaptable
- "SSE: The Streaming Protocol" (Medium, Jan 2026) — exact pattern for long-running AI tasks
- HTMX SSE extension: `hx-ext="sse"`, `sse-connect`, `sse-swap` attributes

- **Rejected**: WebSockets (bidirectional overhead unnecessary for one-way progress)
- **Rejected**: Polling (higher latency, more server load, worse UX than SSE)
- **Rejected**: Long-polling (complex, no advantage over SSE for this use case)
- **Affects**: app/main.py (new routes), core/ingest_inbox.py (gatekeeper), compare/estimate handlers
- **Breadcrumbs**: Session 54G planning context, BACKLOG SSE epic, docs/PERFORMANCE_CHRONICLE.md (latency context)

### AD-122: Silent Failures Are Bugs — General Principle

- **Date**: 2026-02-20
- **Session**: 49B-Deploy (generalized from AD-120 + two subprocess instances)
- **Status**: ACCEPTED — principle, not code change

**Problem:** Three separate instances of silent failure found across sessions:
1. AD-120: ML model silently falls back to wrong model (Session 54F)
2. Session 49B triage Bug 1: Upload subprocess uses `stderr=DEVNULL`, dies silently
3. Session 49B-Audit M3: Approve handler uses `stderr=DEVNULL`, same class

**Decision:** No error output may be silently discarded anywhere in the codebase:
1. Every subprocess must log stderr (to file or capture in variable)
2. Every ML model load must log which model loaded (AD-120)
3. Every error path must produce a visible signal (log, UI message, or status file)
4. Never swallow exceptions without logging
5. `subprocess.DEVNULL` for stderr is banned — use file logging instead

**Enforcement:** grep for `DEVNULL|devnull` in code review. CLAUDE.md rule.

- **Rejected**: Using DEVNULL as "intentional silence" — even intentional silence needs a comment explaining WHY the output is discarded and WHAT would fail silently
- **Affects**: All subprocess calls in app/main.py, any future subprocess usage
- **Breadcrumbs**: AD-120 (ML-specific), HD-012, HD-013, Session 49B triage, Session 49B-Audit

### AD-123: Similarity Calibration — Siamese MLP on Frozen Embeddings

- **Date**: 2026-02-21
- **Session**: 55
- **Status**: ACCEPTED — implementation in progress
- **Context**: With 46 confirmed identities (18 multi-face, 959 same-person pairs), needed to choose between (A) Siamese MLP that directly predicts P(same_person) from embedding pairs, and (B) Metric Learning Head that learns a new embedding space via contrastive/triplet loss.
- **Decision**: Siamese MLP (Option A). Input: concat(a, b, |a-b|, a*b) = 2048-dim → FC layers → P(same_person).
- **Rejected**: Metric Learning Head — requires more identities to learn a generalizable embedding space. With only 18 multi-face identities, the Siamese approach is more sample-efficient because it directly models the comparison task.
- **Affects**: rhodesli_ml/calibration/model.py, core/neighbors.py (integration)
- **Breadcrumbs**: PRD-023, SDD-023, AD-067 (kinship calibration baseline)

### AD-124: Pair Generation — Hard Negative Mining

- **Date**: 2026-02-21
- **Session**: 55
- **Status**: ACCEPTED
- **Context**: For training the calibration model, negative pairs (different-person) could be sampled randomly or mined for difficulty. Random sampling produces mostly "easy" negatives (very different faces) that the model learns quickly but doesn't help with the hard cases.
- **Decision**: Use hard negative mining — cross-identity pairs where Euclidean distance < 1.2 (within "possible match" zone). These are the false positives the model must learn to reject. Supplement with random easy negatives for balance.
- **Ratio**: 1:3 positive:negative (hyperparameter). 959 positives → ~2877 negatives.
- **Affects**: rhodesli_ml/calibration/data.py

### AD-125: Train/Eval Split — Identity-Level Stratification

- **Date**: 2026-02-21
- **Session**: 55
- **Status**: ACCEPTED
- **Context**: When splitting data for training and evaluation, splitting at the face level would leak information — a model could memorize individual faces and score well on eval by recognizing faces seen during training.
- **Decision**: Split at the identity level. 80% train / 20% eval. No identity's faces appear in both sets. Stratify to ensure eval contains at least 4 multi-face identities.
- **Rejected**: Face-level split — creates data leakage. Random pair-level split — same leakage risk.
- **Affects**: rhodesli_ml/calibration/data.py

### AD-126: Simplified CalibrationModel Architecture (33K params)

- **Date**: 2026-02-21
- **Session**: 55
- **Status**: ACCEPTED
- **Context**: Initial Siamese MLP (AD-123) used 4-feature input (a, b, |a-b|, a*b = 2048-dim) with hidden_dim=256, producing ~540K params. With only 3304 training pairs, this overfits catastrophically — train loss 0.003 but eval loss increasing after epoch 5. Hyperparameter sweep (4 configs) showed the same pattern. Baseline Euclidean AUC (0.9493) beat calibrated AUC (0.7854).
- **Decision**: Simplified to 2-feature input (|a-b|, a*b = 1024-dim), hidden_dim=32, dropout=0.5, weight_decay=1e-2. Total ~33K params. This achieves:
  - F1@0.5: 0.6042 (vs baseline 0.1268 — **4.8x improvement**)
  - Recall@0.5: 0.4361 (vs baseline 0.0677 — **6.4x improvement**)
  - Precision@0.5: 0.9831 (vs baseline 1.0 — virtually unchanged)
  - AUC: 0.9391 (vs baseline 0.9493 — comparable)
  - Trains 153 epochs with early stopping (patience=20), no overfitting
- **Rejected**: 4-feature 540K model — overfits on 3304 samples. Raw embedding concat (a, b) adds 512 redundant dims already captured by interaction features.
- **Key insight**: With 46 identities and ~3K training pairs, the model must be small enough to generalize. The difference and product features (|a-b|, a*b) capture all pairwise interaction without redundant capacity.
- **Affects**: rhodesli_ml/calibration/model.py, rhodesli_ml/calibration/train.py (defaults)
- **Config**: embed_dim=512, hidden_dim=32, dropout=0.5, lr=5e-4, weight_decay=1e-2, epochs=200, patience=20

### AD-127: Calibration Results Interpretation — AUC Drop and Precision Tradeoff

- **Date**: 2026-02-21
- **Session**: 55b
- **Status**: DOCUMENTED (analysis, not a code change)
- **Context**: Session 55 calibration showed AUC drop 0.9493→0.9391 (-0.0102) and baseline precision=1.0 at threshold 0.5. Both need honest interpretation for documentation and interviews.

**AUC drop analysis:**
- Eval set: 9 identities, 532 pairs (133 positive, 399 negative). Only 4 multi-face identities in eval.
- Hanley-McNeil standard error: SE=0.0146, 95% CI = ±0.0287
- AUC drop (0.0102) < SE (0.0146) — **statistically insignificant**. Well within noise for this dataset size.
- With only 4 multi-face eval identities, a single identity's face distribution can swing AUC by ~2%.
- Expected to stabilize (and likely improve) as more identities are confirmed via gatekeeper.

**Baseline precision = 1.0 at ALL thresholds — the conservative baseline story:**
- Raw Euclidean distance converted via sigmoid: `1/(1+exp((d-0.8)/0.3))`
- At threshold 0.5: baseline predicts "match" for only 9/133 true positives (recall=6.8%)
- When it predicts match, it's always right (precision=1.0) — but it misses 93% of true matches
- This is "correct but useless" — a model that never predicts match also has 0 false positives
- The calibration model trades 1.7% precision for 6.4x recall at threshold 0.5
- At threshold 0.6: calibrated precision is also 1.0 with recall 36.1% (vs baseline 2.3%)

**The right tradeoff for community archives:**
- Missing a family connection (false negative) is worse than showing a false match (false positive)
- Admin gatekeeper reviews all suggestions — false positives get caught at review time
- More discovered matches → more community engagement → more confirmations → better model

**Full metrics table (eval set, 532 pairs):**

| Threshold | Baseline P/R/F1 | Calibrated P/R/F1 |
|-----------|----------------|-------------------|
| 0.3 | 1.00/0.36/0.53 | 0.82/0.70/0.75 |
| 0.4 | 1.00/0.14/0.25 | 0.92/0.52/0.66 |
| 0.5 | 1.00/0.07/0.13 | 0.98/0.44/0.60 |
| 0.6 | 1.00/0.02/0.04 | 1.00/0.36/0.53 |
| 0.7 | 1.00/0.01/0.01 | 1.00/0.29/0.45 |

**Interview framing:**
- Lead with F1 improvement (4.8x at default threshold) — the aggregate metric
- Explain precision/recall tradeoff: "traded 1.7% precision for 6.4x recall improvement"
- AUC: "stable within noise for a 9-identity eval set; expect improvement with more data"
- The real signal is F1 and recall, not AUC, because the baseline's conservative nature makes AUC artificially high

**Future improvements that will strengthen eval:**
- Active learning: each gatekeeper accept/reject adds training data
- k-fold cross-validation over identities for more robust AUC estimate
- Threshold tuning per use case (compare tool vs. auto-clustering)
- More confirmed identities → larger eval set → tighter confidence intervals

### AD-128: ONNX Runtime for Production Calibration Serving

- **Date**: 2026-02-21
- **Session**: 55b
- **Status**: ACCEPTED
- **Context**: The calibration model (AD-126) is trained with PyTorch but PyTorch is ~500MB installed. Railway production needs lightweight inference. ONNX Runtime is ~15MB and purpose-built for inference.
- **Decision**: Export calibration model to ONNX via `torch.onnx.export()`. Serve in production using `onnxruntime.InferenceSession`. Keep PyTorch for local development/training only.
- **Architecture — fallback chain**: (1) ONNX model via onnxruntime → (2) PyTorch model via torch → (3) raw Euclidean similarity. Per AD-120, each level logs which backend loaded.
- **Numerical validation**: 100 random samples, max difference = 0.00e+00 between PyTorch and ONNX outputs. Exact match.
- **Artifact sizes**: calibration_v1.pt = 131KB, calibration_v1.onnx = 129KB. Both committed to git (well under 5MB threshold).
- **Rejected alternatives**:
  1. Add PyTorch to production requirements — 500MB+ dependency for a 129KB model. Conflicts with Docker slimming goals.
  2. Keep calibration local-only, pre-compute scores — breaks real-time compare tool. Community users uploading photos need live calibrated scoring.
  3. TorchScript export — still requires torch runtime (~500MB). ONNX Runtime is strictly smaller.
  4. Serverless function for ML inference — over-engineered for current scale (271 photos, single-digit concurrent users).
- **Applies to future models**: CORAL date estimation → same pattern (train PyTorch, serve ONNX). Active learning retrains should auto-export ONNX.
- **Affects**: rhodesli_ml/calibration/inference.py (updated fallback chain), rhodesli_ml/calibration/inference_onnx.py (new), rhodesli_ml/calibration/export_onnx.py (new), rhodesli_ml/artifacts/calibration_v1.onnx (new)
- **Tests**: rhodesli_ml/tests/test_calibration_onnx.py — 15 tests covering export, inference, fallback chain, numerical validation

### AD-129: ONNX Export for CORAL Date Estimation Model

- **Date**: 2026-02-21
- **Session**: 57
- **Status**: ACCEPTED
- **Context**: The CORAL date estimation model (EfficientNet-B0 + ordinal head) is trained locally as a PyTorch Lightning checkpoint (52 MB). Following the proven pattern from AD-128 (calibration model), export to ONNX for production serving.
- **Decision**: Export `DateEstimationModel` to ONNX via `torch.onnx.export()`. Input: (batch, 3, 224, 224) float32. Output: (batch, 10) ordinal logits. Serve with `onnxruntime.InferenceSession`.
- **Model details**: Best checkpoint = epoch 26, val MAE = 0.36 decades, adjacent accuracy ~96%. ONNX artifact = 16.5 MB.
- **Numerical validation**: 100 random samples, max logit diff = 3.4e-2. 50/50 decade predictions match exactly — logit diffs never change argmax.
- **Tolerance rationale**: EfficientNet-B0 (4.3M params, deep BN+conv) accumulates more FP error than a 33K-param MLP. 0.034 on logits in [-5,5] = ~0.7% relative. Tolerance = 0.05.
- **Preprocessing**: Resize(257) → CenterCrop(224) → /255 → ImageNet normalize. Must match val transforms.
- **Rejected alternatives**:
  1. Tighter tolerance (1e-5) — impossible for deep CNN ONNX. Standard: 1e-3 to 1e-1 for ResNet/EfficientNet.
  2. Export backbone+head separately — unnecessary complexity.
  3. TorchScript — still needs PyTorch runtime (500MB).
- **Affects**: rhodesli_ml/scripts/export_date_onnx.py (new), rhodesli_ml/artifacts/date_estimation_v1.onnx (new)
- **Tests**: rhodesli_ml/tests/test_date_export_onnx.py — 11 tests

### AD-130: MLflow Model Registry with Alias-Based Promotion
- **Date**: 2026-02-21 | **Session**: 58
- **Decision**: Use MLflow Model Registry with `@champion`/`@candidate` aliases to manage model versions. Automated promotion pipeline: regression gate → register version → tag with gate results → assign @champion if passed.
- **Rationale**: Provides version history, regression gate audit trail, and automated promotion. Modern pattern (aliases replaced deprecated stages in MLflow 2.9+). Enables future A/B testing and rollback.
- **Rejected alternatives**:
  1. Manual ONNX file versioning — no audit trail, no gate integration
  2. MLflow Stages (Staging/Production/Archived) — deprecated in MLflow 2.9+
  3. W&B Model Registry — additional dependency, heavier than needed
- **Registered models**: `rhodesli-date-estimation` (CORAL, 16.5MB), `rhodesli-similarity-calibration` (Siamese MLP, 129KB)
- **Workflow**: Train → Export ONNX → `promote_model.py` (gate → register → alias → copy to artifacts/) → git push → production
- **Affects**: rhodesli_ml/config/mlflow_config.py (new), rhodesli_ml/scripts/register_models.py (new), rhodesli_ml/scripts/promote_model.py (new)
- **Tests**: rhodesli_ml/tests/test_mlflow_registry.py (12 tests), rhodesli_ml/tests/test_promote_model.py (8 tests)

### AD-131: Standalone /facecompare Separate from /compare
- **Date**: 2026-02-21 | **Session**: 59
- **Context**: Need a viral entry point for face comparison that works for people who've never heard of Rhodesli.
- **Decision**: New `/facecompare` route with standalone design (no archive nav), separate from the existing `/compare` (archive-integrated tool).
- **Rationale**: `/compare` = "tool for residents" (users already in the archive). `/facecompare` = "front door for strangers" (entry point for discovery). Both coexist, sharing ML logic but with different UX goals.
- **Rejected**: Separate service (code duplication, double infrastructure). Shared library extraction (premature — only one community exists). Modifying existing `/compare` (would compromise the archive-integrated UX).
- **Affects**: app/main.py (new routes: /facecompare, /api/facecompare/upload, /api/facecompare/select, /facecompare/result/{uuid})
- **Tests**: tests/test_facecompare.py (34 tests)

### AD-132: Community-Agnostic Language in Compare UX
- **Date**: 2026-02-21 | **Session**: 59
- **Context**: The standalone compare tool should be reusable for other community archives.
- **Decision**: Use "historical archive" not "Jews of Rhodes" in the compare UI. Collection name appears only in results: "Jews of Rhodes Community Archive".
- **Rationale**: Enables future expansion to other communities without UI rewrite. A future dropdown can select which archive to search.
- **Affects**: _fc_result_card(), _fc_results_section() in app/main.py

### AD-133: Three ML Systems in One User Flow
- **Date**: 2026-02-21 | **Session**: 59
- **Context**: Sessions 55-58 built individual ML systems. Need to showcase them working together.
- **Decision**: Single upload triggers all three: InsightFace (face detection + embeddings), similarity calibration (confidence tiers), CORAL (date estimation). Results show all three in a unified presentation.
- **Rationale**: Portfolio impact — "Upload a photo and my system detects faces, finds matches with calibrated confidence, and estimates the decade — all local ONNX models on a $5/month server."
- **Affects**: /api/facecompare/upload handler, _fc_results_section()

### AD-134: Deploy Data Safety Gate — Triple Protection Against Volume Overwrite
- **Date**: 2026-02-21 | **Session**: 59b (emergency recovery)
- **Context**: 5th occurrence of deploy overwriting user-entered production data. Session 49B entered 9 identity confirmations + names + birth years + merges through the web UI on production. Sessions 55-59 pushed code, triggering Railway redeploys. The `init_railway_volume.py._sync_essential_files()` function compared bundle hash (46 confirmed) to volume hash (55 confirmed), found they differed, and overwrote the volume with the stale bundle data. Previous occurrences: Session 12, Session 16, annotations.json incident, Lesson 78.
- **Decision**: Triple protection in init_railway_volume.py:
  - **Protection A — Count-based safety gate**: `_is_volume_user_modified()` checks if the volume has MORE confirmed identities (or more photos) than the bundle. If so, refuses to overwrite. This catches the exact failure pattern.
  - **Protection B — Auto-backup before sync**: `_auto_backup_volume()` saves all critical data files to `auto_backups/<timestamp>/` before any sync operation. Keeps last 10 backups. Ensures recovery is always possible.
  - **Protection C — Per-file .bak timestamps**: Existing behavior preserved — individual .bak files created before each overwrite. This was already present and enabled the 49B recovery.
- **Rejected alternatives**:
  1. "Just fix the init script again" — tried 4+ times, keeps regressing because the fundamental design (bundle overwrites volume) is wrong for user-modified files
  2. "Move to Supabase/Postgres" — correct long-term fix but too large a migration for emergency session
  3. "Pre-push hook requiring sync_from_production" — helps but doesn't protect against direct git push or CI-triggered deploys
  4. "Split identities.json into seed + mutable" — architectural debt, defer to Postgres migration
- **Recovery**: Data recovered from Railway volume backup file `identities.json.bak.1771662663` (created by the overwrite that lost the data). 55 confirmed → merged into local → pushed to production.
- **Affects**: scripts/init_railway_volume.py (_sync_essential_files, _auto_backup_volume, _is_volume_user_modified, _count_confirmed_identities)
- **Tests**: tests/test_deploy_safety_gate.py (21 tests including Session 49B regression test)
- **Note**: This is a band-aid. See AD-135 for the structural fix (Supabase migration).

### AD-135: Migrate User-Entered Data to Supabase (Structural Fix for Deploy Data Loss)
- **Date**: 2026-02-21 | **Session**: 59B follow-up | **Status**: IMPLEMENTED (Session 59C, 2026-02-22)
- **Context**: 5th data loss incident from deploy overwriting Railway volume. Triple safety gate (AD-134) is a band-aid. Problem history:
  - Session 12: Data integrity fix not pushed to production, stale data served for weeks
  - Session 16: Overnight session overwrote web triage work (Zeb Capuano regression)
  - Session 25: annotations.json overwritten by deploy (Claude Benatar inscription nearly lost)
  - Session 49B/59B: Full interactive session lost — 9 identity confirmations, 3 birth years, 2 merges overwritten by subsequent deploys. Recovered from .bak file.
  - Lessons: 43, 56, 69, 78, 85 | Decisions: AD-134 (band-aid)
  - Issue tracker: DATA-001 in docs/ISSUES_LOG.md
- **Root cause**: User-entered data lives in JSON files on a Railway persistent volume. Every deploy bundles stale copies of these files into the Docker image. The init script has been patched 5+ times to avoid overwriting, but the architecture is fundamentally fragile — it couples deployment with data storage.
- **Decision**: Migrate all user-entered/user-modified data to Supabase Postgres (project already configured for auth, ID: fvynibivlphxwfowzkjl).
  - **Data to migrate** (user-entered, mutable): Identity confirmations, merges, annotations, GEDCOM match decisions, birth year corrections, match responses, tags/labels entered through web UI
  - **Data that stays in JSON + git** (ML-generated, immutable): photo_index.json, embeddings.npy, base identity proposals, face crop metadata
  - **Architecture after migration**: Supabase = source of truth for all user decisions. JSON files = read cache rebuilt from Supabase on deploy. Deploy can never destroy data because it doesn't own it. Eliminates sync_from_production/push_to_production dance.
- **Rejected alternatives**:
  1. "Just fix the init script" — tried 5 times, keeps regressing (AD-134 is the 5th attempt)
  2. "R2 backup + restore" — recovery mechanism, not prevention
  3. "Git-track data files" — merge conflicts, stale bundles
  4. "Delete volume seeding entirely" — breaks fresh deploys
  5. "Move everything to Supabase" — too large; ML data doesn't belong in a DB
- **Schema design**: See docs/design/FUTURE_COMMUNITY.md (profiles, invites, annotations, photo_uploads, activity_log tables)
- **Depends on**: Supabase project staying active (keepalive ping mechanism needed)
- **Enables**: Multi-user collaboration, community data safety, elimination of sync scripts
- **Implementation notes (Session 59C)**:
  - **4 Supabase tables**: identity_overrides (372 rows — confirmations, merges, renames, birth years), annotations (8 rows), relationships (19 rows), gedcom_matches (33 rows)
  - **Dual-write pattern**: save_registry() and _save_annotations() sync to Supabase after JSON save. Every user action persists to both JSON cache and Supabase Postgres.
  - **Startup sync**: App startup rebuilds JSON cache from Supabase, ensuring deploys never lose user data even if Docker bundle overwrites volume files.
  - **Deploy safety**: Deploys can never destroy user data because Supabase is the source of truth, not the Railway volume.
  - **27 new tests**: Supabase persistence + deploy safety regression tests
- **Breadcrumbs**: AD-134, DATA-001, Lessons 43/56/69/78/85, docs/design/FUTURE_COMMUNITY.md, BACKLOG BE-040-042

### AD-139: Gemini 3.1 Pro Model Upgrade
- **Date**: 2026-02-22 | **Session**: 61
- **Context**: Gemini 3.1 Pro released Feb 19, 2026 with improved reasoning capabilities. Our existing pipeline used gemini-2.5-pro-preview-05-06 for all vision analysis, which was both slower and less accurate on evidence extraction tasks.
- **Decision**: Upgrade default from gemini-2.5-pro-preview-05-06 to gemini-3.1-pro-preview for detailed analysis (date estimation, evidence extraction, progressive refinement). Use gemini-3-flash for batch/realtime tasks (quick labeling, low-confidence re-checks).
- **Rejected alternatives**:
  1. "Use only Pro for everything" — cost prohibitive for batch labeling (~$0.05/photo vs ~$0.005/photo with Flash); batch runs of 250+ photos would exceed budget
  2. "Use only Flash for everything" — quality insufficient for evidence analysis; Flash misses subtle fashion/technology cues that Pro catches, especially in degraded heritage photos
- **Affects**: rhodesli_ml/gemini_config.py (default model strings, pricing table)
- **Breadcrumbs**: AD-101 (original Gemini 3.1 Pro adoption), AD-051 (Flash labeling results)

### AD-140: MLflow Experiment Tracking
- **Date**: 2026-02-22 | **Session**: 61
- **Context**: Need systematic model comparison across Flash vs Pro, different prompt versions, and progressive refinement stages. Ad-hoc logging in JSON files was not reproducible or queryable. MLflow already used for CORAL training (AD-116) and model registry (AD-130).
- **Decision**: MLflow for local experiment tracking with file store at rhodesli_ml/mlruns/. Supabase-backed api_logger for persistent API call logs (model, prompt hash, latency, cost, result quality). Experiment runs track: model version, prompt version, input photo set, output quality metrics, cost.
- **Rejected alternatives**:
  1. "NotebookLM MCP" — fragile, single point of failure, no programmatic access
  2. "LangChain" — overkill for our scale; adds massive dependency tree for what is essentially prompt → response → log
  3. "Manual spreadsheets" — not reproducible, no programmatic querying, drift-prone
- **Affects**: rhodesli_ml/tracking.py, rhodesli_ml/utils/api_logger.py
- **Breadcrumbs**: AD-116 (MLflow integration strategy), AD-130 (model registry), AD-103 (API result logging)

### AD-141: Multi-Photo Compare Architecture
- **Date**: 2026-02-22 | **Session**: 61
- **Context**: PRD-021 — users comparing family photos need batch upload. Current /compare page accepts a single photo. Community members (Jews of Rhodes Facebook group) frequently have 2-5 photos of the same person across decades and want to verify identity across all of them simultaneously.
- **Decision**: Extend existing /compare page with /api/compare/upload-multiple endpoint accepting 2-5 photos. Cross-match all uploaded faces pairwise (are these the same person?), then compare each face against the full archive. Results page shows: intra-upload similarity matrix + per-face archive matches. Reuses existing InsightFace detection + calibration (AD-123) + CORAL date estimation (AD-129).
- **Rejected alternatives**:
  1. "Separate microservice" — code duplication of ML loading, deployment complexity, latency from network hops between services
  2. "Single-photo only forever" — competitive gap vs other face comparison tools; users already ask for batch in community feedback
- **Affects**: app/main.py (/api/compare/upload-multiple endpoint)
- **Breadcrumbs**: AD-117 (Face Compare product architecture), AD-131 (standalone /facecompare), PRODUCT-001

### AD-142: Photo Detective UX Pattern
- **Date**: 2026-02-22 | **Session**: 61
- **Context**: PRD-022 — Gemini's evidence analysis for date estimation is valuable but currently hidden in raw JSON responses. Users see only a year estimate without understanding the reasoning. The evidence (print technology, fashion details, environmental cues, technology markers) is what makes our tool trustworthy and educational.
- **Decision**: Evidence card UI with category icons (Print, Fashion, Environment, Technology), strength badges (strong/moderate/weak), model badge showing which Gemini version produced the analysis, and progressive refinement indicator showing which pass generated each piece of evidence. Cards are collapsible, sorted by confidence, and link back to the specific image region when bounding box data is available.
- **Rejected alternatives**:
  1. "Simple year badge only" — hides the value Gemini provides; users cannot verify or learn from the estimate; reduces trust
  2. "Full separate report page" — too heavy for inline use, fragments the UX by requiring navigation away from the photo; users want evidence alongside the photo, not on a separate page
- **Affects**: app/main.py (_evidence_card, _detective_evidence_section, _progressive_refinement_badge, _build_photo_date_badge)
- **Breadcrumbs**: AD-102 (progressive refinement), AD-094 (year estimation V1), AD-041 (evidence-first prompt architecture)

### AD-143: Unified Gemini Extraction Architecture — One Call Per Photo
- **Date**: 2026-02-22 | **Session**: 61B
- **Context**: Rhodesli's Gemini integration had separate prompt patterns for date estimation (AD-094), face analysis (PRD-015), location identification, cultural markers, and text/signage detection. Each required a separate API call, resulting in 3-5x cost overhead and inability to cross-reference evidence across extraction types. AD-102 (progressive refinement) called for a combined API call but the architecture didn't exist.
- **Decision**: Single configurable prompt architecture with presets. One API call per photo extracts everything needed. Three presets: "full" (all 10 extraction types — batch analysis), "quick" (date + location + text — interactive upload), "compare" (date + faces + ages — face comparison). `include`/`exclude` parameters allow per-call customization. Face coordinates injected via `face_coordinates` parameter. Verified facts injected via `verified_facts` parameter for progressive refinement (AD-102).
- **Rejected alternatives**:
  1. "Separate prompts per extraction type" — 3-5x cost, loses cross-referencing (fashion evidence informs both date estimation AND cultural marker detection), requires multiple API round-trips
  2. "Single monolithic prompt with no presets" — wastes tokens on interactive queries that only need date estimation; "quick" preset saves ~80% on per-upload costs
  3. "Client-side prompt assembly" — fragile, no schema validation, no preset management, harder to version
- **10 extraction types**: date_estimation, face_analysis, location, cultural_markers, clothing_era, photo_technique, text_signage, group_composition, photo_condition, subject_ages
- **Affects**: `rhodesli_ml/gemini_extraction.py` (EXTRACTION_PRESETS, build_extraction_prompt, get_active_extractions), `scripts/batch_analyze.py` (cost estimation, batch API stub)
- **Tests**: `rhodesli_ml/tests/test_gemini_extraction.py` (16 tests — presets, prompt building, face coordinates, verified facts, schema)
- **Breadcrumbs**: AD-102 (progressive refinement), AD-139 (Gemini 3.1 Pro), AD-142 (Photo Detective UX), PRD-015 v2, PRD-022

### AD-144: Face Alignment Coordinate Bridging v2 — Integrated with Unified Extraction
- **Date**: 2026-02-22 | **Session**: 61B
- **Context**: PRD-015 v1 (Session 53 design) proposed feeding InsightFace bounding box coordinates TO Gemini to solve the face count mismatch problem (~40% of group photos). Session 61B built the unified extraction architecture (AD-143) which makes face alignment a built-in extraction type rather than a separate prompt variant.
- **Decision**: Face alignment is the `face_analysis` extraction type in the unified prompt. When `face_coordinates` is provided to `build_extraction_prompt()`, the coordinates are injected into the face analysis section as labeled regions ("Face 0: bbox=[x1,y1,x2,y2]"). Gemini describes each labeled face, marks non-subjects as `is_subject: false`. This eliminates the need for a separate coordinate bridging pipeline — it's part of every "full" or "compare" preset extraction.
- **What changed from v1**:
  1. No separate "coordinate bridging prompt variant" — integrated into unified extraction
  2. Face labels use 0-indexed integers (Face 0, 1, 2) not letters (A, B, C)
  3. Schema is part of the unified JSON response, not a standalone format
  4. Batch processing via `scripts/batch_analyze.py`, not a separate script
  5. Cost is amortized across all extraction types in the unified call
- **Rejected alternatives**:
  1. "Separate coordinate bridging pipeline" (PRD-015 v1 approach) — duplicates prompt engineering, separate API cost, no cross-referencing with other extraction types
  2. "Approach A: Gemini provides its own coordinates" — requires IoU matching, threshold tuning, EXIF coordinate misalignment (see PRD-015 v1 detailed analysis)
- **Affects**: `rhodesli_ml/gemini_extraction.py` (_PROMPT_SECTIONS["face_analysis"], face_coordinates parameter), `rhodesli_ml/tests/test_gemini_extraction.py` (coordinate injection tests)
- **Breadcrumbs**: PRD-015 v2, AD-143 (unified extraction), AD-101/139 (Gemini 3.1 Pro spatial reasoning)

### AD-145: Similarity Calibration Strategy — Platt Scaling First, LoRA Later
- **Date**: 2026-02-22 | **Session**: 61B
- **Context**: Session 55 built a Siamese MLP (33K params) that improved F1@0.5 from 0.13 to 0.60 on heritage photo face matching. Question: what's the next step? Options ranged from simple score calibration to full LoRA fine-tuning of the InsightFace backbone.
- **Decision**: Three-stage calibration ladder, stopping when results are sufficient:
  - **Stage 1 — Platt scaling** on raw Euclidean distances using confirmed pairs as ground truth. Scikit-learn, no model retraining. Expected: better threshold selection, meaningful probability scores.
  - **Stage 2 — Siamese MLP refinement** (current model). Proper train/val/test split with held-out identities. Hard negative mining. Expected: F1 0.60 → 0.70+.
  - **Stage 3 — LoRA fine-tuning** of w600k_r50 backbone. Only pursue if Stage 1+2 combined F1 < 0.75. Requires re-embedding all 550+ faces. Expected: 5-15% improvement but high cost.
- **Rejected alternatives**:
  1. "Jump straight to LoRA" — insufficient labeled data for backbone fine-tuning (55 identities, ~1200 positive pairs); risk of catastrophic forgetting on general faces; re-embedding cost is high
  2. "Stick with current calibration" — F1 0.60 leaves room for improvement; precision@0.5=98% is good but recall is low (too many missed matches)
  3. "Train from scratch on heritage photos" — utterly insufficient data (need 100K+ images); existing pretrained embeddings are a strong foundation
  4. "Multi-model ensemble" — complexity not justified at 550-face scale; single model with calibration is simpler and faster
- **Success gate**: F1@0.5 ≥ 0.70, precision@0.5 ≥ 95%, no regression on 55 confirmed identities
- **Affects**: Future — `rhodesli_ml/calibration/platt_scaling.py`, existing `rhodesli_ml/calibration/` module
- **Breadcrumbs**: AD-123-128 (calibration pipeline), PRD-023 (LoRA research), ML-076 (ROADMAP)

### AD-146: Face Alignment Implementation — Coordinate Bridging End-to-End
- **Date**: 2026-02-22 | **Session**: 62
- **Context**: PRD-015 v2 designed the coordinate bridging approach (Approach B) in Session 61B. Session 62 implements it end-to-end: EXIF handler, face alignment module, API endpoint, photo page UI.
- **Decision**: Implemented Approach B (feed InsightFace coordinates TO Gemini) as a standalone `app/face_alignment.py` module with:
  - FaceDetection/AlignedFaceDescription/AlignmentResult dataclasses
  - format_faces_for_gemini() sorts faces left-to-right by x1, assigns 0-indexed labels
  - build_alignment_prompt() builds full prompt with coordinate block + JSON schema
  - parse_alignment_response() handles perfect match, partial match, Gemini-only faces
  - EXIF orientation normalization ensures Gemini and InsightFace see same pixel layout
  - JSON-based storage (data/face_alignments.json) with in-memory cache
  - Admin-only POST /api/face-alignment/{photo_id} triggers per-photo alignment
  - Public GET endpoint returns cached results
  - Photo page UI shows per-face description cards with mismatch warnings
- **Rejected alternatives**:
  1. "Integrate into rhodesli_ml/gemini_extraction.py directly" — would mix app-level orchestration (image loading, auth checks, storage) into the ML extraction module. Better separation: extraction module builds prompts, app module orchestrates the pipeline.
  2. "Store in Supabase only" — would require Supabase to be available for any alignment to work. JSON storage matches existing data patterns and degrades gracefully.
  3. "Batch-only alignment" — no per-photo trigger. Admin needs ability to test individual photos before committing to batch re-run (~$7.60 for 271 photos).
- **Results**: 54 new tests (10 EXIF + 30 alignment + 8 API + 6 UI). 3373 total tests passing. Real Gemini API testing deferred (no local API key; needs production verification).
- **Affects**: `app/face_alignment.py` (new), `app/exif_handler.py` (new), `app/main.py` (API endpoints + UI section), tests/test_face_alignment*.py, tests/test_exif_handler.py
- **Breadcrumbs**: AD-143 (unified extraction), AD-144 (coordinate bridging design), PRD-015 v2

---

### AD-147: GEDCOM-Enriched Analysis — Comparison Results
- **Date**: 2026-02-23 | **Session**: 61C
- **Context**: Does feeding genealogical (GEDCOM) data into Gemini photo analysis prompts improve date/location accuracy? Which enrichment level is optimal? Which model?
- **Decision**: Use `gemini-3.1-pro-preview` + `curated` GEDCOM variant as default.
  - Two-pass workflow: baseline (no GEDCOM) first, then enriched with curated context using baseline date estimate as window center.
  - Cost: ~$0.04/photo for two-pass with Pro.
- **Evidence**: 11 runs × 20 photos across 3 models × 5 GEDCOM variants ($2.46 total).
  - GEDCOM context transforms location from vague → city-level in 4/5 cases
  - Date estimates narrow by 3-7 years with GEDCOM context
  - Confidence jumps from 60% "high" to 80-100% "high" with GEDCOM
  - Token cost of GEDCOM context is negligible (80-800 tokens vs 2200+ total)
  - **Flash 2.0 GEDCOM confusion bug**: misinterprets death dates as photo dates (year=1999 for ~1905 photo)
  - **Flash-3-preview unreliable**: 13% failure rate (503 high demand)
  - **Pro: 0 errors in 100 calls**
- **Rejected alternatives**:
  1. "Flash 2.0 for all runs" — 25x cheaper but misinterprets GEDCOM data, less detailed output
  2. "Full GEDCOM (all events)" — no advantage over curated for identified photos, and includes irrelevant events
  3. "co_occurrence variant" — no marginal improvement over first_order, same token cost
  4. "first_order variant as default" — 2x token cost vs curated, marginal quality improvement
- **Affects**: `rhodesli_ml/gedcom_context.py`, `rhodesli_ml/gemini_extraction.py`, `scripts/compare_models.py`
- **Breadcrumbs**: AD-143 (unified extraction), results/gedcom_enrichment_comparison_report.md, Session 61C planning context

### AD-148: GEDCOM Storage Architecture — Supabase Tables
- **Date**: 2026-02-23 | **Session**: 61C
- **Context**: GEDCOM data (21,809 individuals, 6,680 families, 12,449 events) needs persistent storage for web queries. Currently parsed on-demand from .ged file.
- **Decision**: Store in Supabase Postgres (4 tables: gedcom_individuals, gedcom_events, gedcom_relationships, gedcom_face_links). Parse once, store, query fast.
  - Import script: `scripts/import_gedcom_supabase.py` (idempotent, upsert on gedcom_id)
  - Tables not yet created — needs SQL migration via Supabase Dashboard
  - Face links stored separately to preserve identity→GEDCOM mapping
- **Rejected alternatives**:
  1. "Keep parsing from .ged file on every request" — 4.8s parse time, not acceptable for web
  2. "Store as JSON file like other data" — works for offline but doesn't support web queries or joins
  3. "Separate Postgres instance" — unnecessary, Supabase already in use for auth
- **Affects**: `scripts/import_gedcom_supabase.py` (new), `rhodesli_ml/importers/gedcom_parser.py` (extended with life events)
- **Breadcrumbs**: Session 61C planning context, AD-135 (Supabase migration)

### AD-149: Isotonic Regression for Similarity Calibration
- **Date**: 2026-02-23 | **Session**: 63
- **Context**: Raw InsightFace cosine similarity (0-1) doesn't map linearly to P(same person). Heritage photos span decades — match scores range 0.11-0.98, with mean 0.54. Need calibrated probabilities for user-facing "85% match" display.
- **Decision**: Isotonic regression (sklearn.IsotonicRegression) fit on 348 ground truth pairs (221 match, 127 non-match). Chose isotonic over logistic/Platt because it handles non-standard score distributions without assuming a functional form.
- **Results**: AUC=0.9577. Threshold@90% precision: 0.268. Match scores above 0.3 map to ~100% probability (clean separation between match/non-match populations).
- **Rejected**: Logistic regression (Platt scaling) — assumes sigmoid relationship, which may not hold for heritage photos with extreme age variance.
- **Affects**: `rhodesli_ml/similarity_calibration.py` (new), `scripts/extract_calibration_pairs.py` (new)
- **Breadcrumbs**: AD-145 Stage 1, Session 63 planning context

### AD-150: Continuous Recalibration with Non-Match Spike Handling
- **Date**: 2026-02-23 | **Session**: 63
- **Context**: When "Not the same person" UX launches, explicit non-match pairs could spike 10-50x. Calibration curve will shift significantly. System must handle this gracefully.
- **Decision**: Event hooks (on_face_merge, on_match_reject, on_identity_confirm) auto-insert calibration pairs. Recalibration triggers: >20 new pairs, class ratio shift >50%, model age >30 days. Safety: rate limit 1/hr, drift >0.1 flags for review, never retroactive.
- **Rejected**: Manual recalibration only — too slow for active community use. Fully automatic without safety rails — dangerous during non-match spike.
- **Affects**: `rhodesli_ml/recalibration_hooks.py` (new), `rhodesli_ml/similarity_calibration.py`
- **Breadcrumbs**: Session 63 planning context §3

### AD-151: GEDCOM Face Linking — Sephardic Surname Variant Matching
- **Date**: 2026-02-23 | **Session**: 63
- **Context**: Rhodesli's confirmed identities use various surname spellings (Capeluto/Capelluto/Capelouto/Capouano/Capuano). GEDCOM uses yet another variant. Need fuzzy matching that handles Sephardic naming conventions.
- **Decision**: Surname variant clusters (hardcoded for known families) + given name scoring (exact=1.0, prefix=0.8, first-name=0.9). Auto-link at confidence >=0.8, review at 0.5-0.8.
- **Results**: 39 auto-linked, 4 for review, 12 no match (out of 55 confirmed identities). 71% automatic linkage rate.
- **Rejected**: Pure edit distance — fails on Sephardic transliterations (Capeluto→Capouano is distance 4 but same family). ML name matching — overkill for ~50 identities.
- **Affects**: `scripts/link_faces_to_gedcom.py` (new), `gedcom_face_links` Supabase table
- **Breadcrumbs**: Session 61C U2, AD-148

### AD-152: Supabase-First Data Layer + Centralized Gemini Pipeline
- **Date**: 2026-02-23 | **Session**: 64
- **Context**: Session 63 left face alignment data in JSON only, hardcoded model strings across 5+ files, no API call logging, recalibration hooks as dead code, and calibrated scores not wired to UI.
- **Decision**: Multi-part architectural decision:
  1. **Supabase-first data layer**: Face alignment data migrated to `face_gemini_alignments` table. Pattern: write to Supabase first, JSON as cache fallback. `save_alignment()` and `load_alignments()` try Supabase, fall back to JSON.
  2. **Centralized model config**: All Gemini API calls use `GEMINI_MODEL` from `rhodesli_ml/gemini_config.py`. No hardcoded `"gemini-3.1-pro-preview"` in function defaults.
  3. **API call logging**: Every `call_gemini_alignment()` logs to `gemini_api_calls` table via `log_gemini_call()` — photo_id, model, tokens, cost, latency, status (success/rate_limited/error), batch_id.
  4. **Combined pipeline**: `scripts/run_combined_pipeline.py` merges face alignment + GEDCOM context injection. Supports `--retry-failed`, `--photo-ids`, `--no-gedcom`.
  5. **Calibrated scores in UI**: `neighbor_card()` displays "85% match" via isotonic regression (AD-149) instead of raw threshold labels.
  6. **Recalibration hooks wired**: Merge/reject/confirm endpoints fire `_fire_recalibration_hook()` (best-effort, non-blocking).
- **Results**: 127/271 photos aligned (122 batch + 5 prior). 144 rate-limited, retry ready. ~50 new tests.
- **Rejected**: Keep JSON as primary store — fragile, no concurrency, no query support. Per-file model config — leads to drift. Inline cost estimation — pricing changes break all callers.
- **Affects**: `app/face_alignment.py`, `app/supabase_data.py`, `app/main.py`, `scripts/run_batch_alignment.py`, `scripts/run_combined_pipeline.py` (new), `scripts/sql/create_face_gemini_alignments.sql` (new), `scripts/sql/create_gemini_api_calls.sql` (new)
- **Breadcrumbs**: AD-149 (calibration), AD-150 (recalibration), Session 64 context

### AD-153: Gemini API Call Tracking Infrastructure
- **Date**: 2026-02-23 | **Session**: 64b
- **Context**: Session 63 showed cost discrepancy ($0.78 actual vs $2.50 expected). No way to determine which model was used per photo, or whether calls succeeded.
- **Decision**: Every Gemini API call logged to `gemini_api_calls` Supabase table with: photo_id, model_used, call_type, tokens (prompt/completion/total), cost_usd, latency_ms, status (success/rate_limited/error), batch_id.
- **Enables**: Cost analysis per model, rate limit detection, model drift tracking, batch auditing.
- **Rejected**: In-memory logging only — lost on restart, not queryable. File-based logging — doesn't support concurrent access or web queries.
- **Affects**: `app/face_alignment.py` (_log_call), `app/supabase_data.py` (log_gemini_call), `scripts/sql/create_gemini_api_calls.sql`
- **Breadcrumbs**: Session 63 assessment concern #7, AD-152

### AD-154: Face Alignment Storage Migration JSON → Supabase
- **Date**: 2026-02-23 | **Session**: 64b
- **Context**: Session 63 stored 127 face alignment results in `data/face_alignments.json`. Not queryable via API, not accessible on production, drifts from database.
- **Decision**: `face_gemini_alignments` Supabase table is source of truth. JSON is cache-only. `load_alignments()` reads Supabase first, falls back to JSON. 127 records migrated successfully.
- **Rejected**: Keep JSON as primary — no concurrency, no query support, can't access from web app on Railway.
- **Affects**: `app/face_alignment.py` (load_alignments, save_alignment), `app/supabase_data.py`, `scripts/sql/create_face_gemini_alignments.sql`, `scripts/migrate_alignments_to_supabase.py`
- **Breadcrumbs**: Session 63 concern #1, AD-135, AD-152

### AD-155: GEDCOM Context Builder — Supabase to ParsedGedcom Reconstruction
- **Date**: 2026-02-23 | **Session**: 64b
- **Context**: Session 64 left `_build_parsed_gedcom_from_supabase()` as a stub returning None. Without it, the combined pipeline sent coordinates WITHOUT genealogical context, losing the winning combination from Session 61C.
- **Decision**: Full reconstruction of `ParsedGedcom` object from Supabase tables (gedcom_individuals, gedcom_events, gedcom_relationships). Paginated loading (21,809 individuals, 40,140 events, 145K+ relationships). Reconstructs family units and all relationship methods (get_parents, get_spouses, get_children, get_siblings, get_marriages).
- **Results**: Dry-run on 3 photos confirmed GEDCOM context appears in Gemini prompts. GEDCOM-linked photo shows `+GEDCOM` flag and `call_type=combined`.
- **Bugs fixed**: (1) Column name: `gedcom_xref` → `gedcom_id`, (2) Supabase default 1000-row limit hit, (3) identities JSON envelope not unwrapped.
- **Rejected**: Parse from .ged file on demand — 4.8s parse time, not acceptable. Load only linked individuals — loses family context needed for curated variant.
- **Affects**: `scripts/run_combined_pipeline.py` (_build_parsed_gedcom_from_supabase, load_gedcom_data, build_gedcom_context)
- **Breadcrumbs**: AD-147 (GEDCOM enrichment winner), AD-148 (Supabase tables), Session 61C

### AD-156: Harness Architecture — Skills, Hooks, Rules
- **Date**: 2026-02-23 | **Session**: 64
- **Context**: CLAUDE.md was 4922 chars. Session prompts re-explained architecture every time. No reusable workflow knowledge.
- **Decision**: Move repeatable workflow knowledge to `.claude/skills/` (5 skills), hard constraints to hooks (3 hooks), domain rules to `.claude/rules/` (3+ rule files). CLAUDE.md trimmed to 1952 chars — pointers only.
- **Result**: Skills: session-run, deploy-verify, ml-pipeline, assess-session, build-prompt. Rules: ml-development, data-layer, session-protocol. Hooks: pre-commit test gate, ML file AD reminder, session completion notification.
- **Rejected**: Keep everything in CLAUDE.md — too large for context. Per-session prompt templates — not reusable. External documentation only — not loaded into context.
- **Breadcrumbs**: docs/HARNESS_DECISIONS.md, Session 64 context

### AD-157: Gemini Batch API for Bulk Photo Processing
- **Date**: 2026-02-23 | **Session**: 64/64b | **Updated**: 2026-02-23 (Session 65a — actual results)
- **Context**: 144 photos rate-limited during Session 63 batch run. Synchronous calls hit RPM/RPD limits.
- **Original Decision**: Use Gemini Batch API (50% discount, 24h SLO) for remaining 144+ photos.
- **Actual Result (Session 64d)**: Batch API was extremely slow (>20 min for 1 request, no results returned). Synchronous pipeline with retry completed 142 photos in ~20 min at $1.19 total ($0.0084/photo). Batch API cancelled in favor of sync retry.
- **Revised Decision**: Batch API not worth it for <500 photos. Sync pipeline with `--retry-failed` is faster and cheaper than estimated. Reserve Batch API only for 500+ photo runs where 24h SLO is acceptable.
- **Rejected**: Batch API for small batches — too slow, no cost benefit realized at this scale.
- **Affects**: `scripts/run_combined_pipeline.py`, `rhodesli_ml/gemini_config.py`
- **Breadcrumbs**: Session 63 concern #2, AD-152, Session 64d assessment

### AD-158: Session Roadmap — UX → Portfolio → LoRA Sequence
- **Date**: 2026-02-23 | **Session**: 64c
- **Context**: Three major workstreams remain: (1) UX polish + Help Identify mode, (2) portfolio documentation for job search, (3) LoRA fine-tuning. Need to sequence them correctly.
- **Decision**: Session 65 = UX walkthrough + Help Identify, Session 66 = portfolio documentation + LoRA prep, Session 67+ = LoRA fine-tuning.
- **Rationale**:
  - **UX first**: Community identifications from Help Identify mode generate confirmed pairs needed for LoRA training data. Currently at 55 confirmed identities — need 100+ for meaningful fine-tuning.
  - **Portfolio before LoRA**: Job search is active. ML pipeline (InsightFace → CORAL → isotonic calibration → Gemini alignment → GEDCOM enrichment) is already interview-worthy. Documenting it has immediate career value.
  - **LoRA last**: Requires 50-100+ confirmed pairs minimum. Benefits from all upstream improvements being stable. Needs recalibration of the entire similarity pipeline post-fine-tuning.
- **Rejected**: LoRA first — insufficient training pairs. Portfolio first — UX improvements generate data that makes the portfolio stronger.
- **Affects**: ROADMAP.md (session planning), BACKLOG.md (FE-041 priority)
- **Breadcrumbs**: Session 64c, PRD-023 Stage 2

### AD-159: Prompt Fidelity Audit — 64d GEDCOM Enrichment Verified + Fixed
- **Date**: 2026-02-23 (audit), 2026-02-24 (fix) | **Sessions**: 65a, 65b
- **Context**: Session 64d ran 136 Gemini alignment calls. Investigation found GEDCOM context too thin (~106 tokens vs 400-1000 target).
- **Root Cause**: Pipeline used `variant="curated"` which only includes the person's own birth/death/events/marriages. Does NOT include parents, spouses, children, siblings — the key disambiguating context.
- **Fix (Session 65b)**:
  1. Changed default variant from `"curated"` to `"first_order"` — now includes parents, spouses, children, siblings.
  2. Added `gemini_config` and `response_summary` fields to API call logging. Previously NULL for all records.
  3. Added `gedcom_token_count` and `enrichment_level` (full/partial/thin/none) tracking per call.
  4. Logging in `build_gedcom_context()` reports token count and enrichment level per photo.
- **Original Findings (65a)**:
  - 17/136 (12.5%) calls received GEDCOM enrichment — correct, reflects confirmed+linked identities.
  - GEDCOM added only ~106 tokens with "curated" variant. With "first_order", expect 400-1000+ tokens.
  - 46/55 confirmed identities have GEDCOM links.
- **Rejected Alternative**: `"co_occurrence"` variant (includes people sharing any photo). Too expensive for routine pipeline use — save for targeted re-analysis.
- **Affects**: `scripts/run_combined_pipeline.py`, `app/face_alignment.py`, `gemini_api_calls` table
- **Breadcrumbs**: `docs/analysis/prompt_fidelity_64d.md`, AD-152, AD-146, Session 65b

### AD-160: GEDCOM ↔ Identity Linking — Admin-Only Post-Identification Step
- **Date**: 2026-02-24 | **Session**: 65b
- **Context**: Linking photo identities to GEDCOM records required direct database inserts via Claude Code. Needed an in-app UX for admins.
- **Decision**: Admin-only GEDCOM linking step after identity confirmation. Fuzzy name search on in-memory GEDCOM cache (21,809 individuals). Sephardic surname variant matching (Capeluto/Capuano/Capelluto etc.).
- **UX Flow**: Confirm identity → "Link to Family Tree" panel → auto-search by name → click to link → auto-enrich birth/death from GEDCOM → success feedback. "No match — skip" always available.
- **Data Model**: Uses existing `gedcom_face_links` table. Maps `identity_id` → `gedcom_id`. Soft-delete unlink (sets `unlinked_at`). Confidence=1.0 for admin links.
- **Auto-enrichment**: On link, copies birth_year and death_year from GEDCOM individual to identity record (additive only, never overwrites existing data).
- **Rejected Alternative**: Real-time Supabase queries per search. Too slow for interactive UX — cache all 21,809 individuals in memory instead.
- **Affects**: `app/main.py` (search/link/unlink routes, confirm flow, person page), `gedcom_face_links` table
- **Breadcrumbs**: `tests/test_gedcom_routes.py` (20 tests), Session 65b Phase 2

### AD-161: Thread-Based Upload Processing — Shared Hybrid Models
- **Date**: 2026-02-24 | **Session**: 65c
- **Context**: Upload broken since Feb 23. Subprocess loaded full buffalo_l model (~300-500MB) in separate process alongside main app's hybrid models (~100-200MB), exceeding Railway's 512MB RAM. Session 65a added PID tracking (symptom fix). Session 65b skipped verification.
- **Root Cause**: `subprocess.Popen("python -m core.ingest_inbox")` created a new process that loaded its own copy of buffalo_l FaceAnalysis. Main app already had hybrid models (det_500m + w600k_r50). Combined: 500-800MB > 512MB Railway limit → guaranteed OOM.
- **Decision**: Replace subprocess with `threading.Thread`. Thread shares main process memory → uses already-loaded hybrid models via `prefer_hybrid=True` parameter → no double loading → no OOM. 5-minute timeout retained as safety net for stuck threads.
- **Changes**:
  1. Added `prefer_hybrid` parameter to `extract_faces()`, `process_single_image()`, `process_directory()`, `_process_zip_file()`
  2. When `prefer_hybrid=True`, `extract_faces()` delegates to `extract_faces_hybrid()` if hybrid models available
  3. Upload handler: `threading.Thread(target=_background_ingest, daemon=True)` replaces `subprocess.Popen`
  4. Status poller: removed PID-based alive check, kept timeout-only detection
  5. R2 crop upload: fixed to use `face_ids` from status file (was searching by identity UUID)
  6. Admin pending upload approval: also converted from subprocess to thread
- **Secondary Fix**: R2 crop upload searched for crops by `identity_id` (UUID) but crops are named by `face_id` (inbox_*). Added `face_ids` tracking to `write_status_file()` and all process functions.
- **Production Evidence**: Upload with real face photo → "1 face extracted, 1 added to Inbox". Compare/pair → face detected. Estimate → date returned. All without OOM.
- **Rejected Alternative**: Keep subprocess but load lighter model. Not viable — any separate process loading InsightFace models doubles memory.
- **Affects**: `app/main.py` (upload handler, status poller, pending approval), `core/ingest_inbox.py` (prefer_hybrid parameter, face_ids tracking)
- **Breadcrumbs**: `tests/test_session_65a_upload_fix.py` (rewritten for timeout-based detection), `tests/test_session_52_fixes.py` (updated for thread), SESSION_LOG.md

### AD-162: Disk Space Cleanup — Temp Files, Backups, Docker Image
- **Date**: 2026-02-24 | **Session**: 65d
- **Context**: Upload returned Errno 28 (No space left on device) on Railway. RAM fix (AD-161) worked, but disk was full.
- **Root Cause**: Docker image bundled 393MB of unnecessary backup files from `data/backups/`. Push endpoint created unbounded `.bak.{timestamp}` files. No staging/inbox cleanup after upload processing.
- **Decision**: Multi-layer disk cleanup — Docker image reduction, startup cleanup, runtime pruning, health monitoring.
- **Fixes**:
  1. `.dockerignore`: exclude `data/backups/`, `data/auto_backups/`, `data/staging/`, `raw_photos/` (~400MB savings)
  2. `_startup_disk_cleanup()`: removes stale staging dirs (>1hr), old inbox files (>24hr), `.tmp` files
  3. `_prune_bak_files()`: keeps only 3 most recent `.bak` files per type, runs at startup + after push
  4. `_background_ingest` `finally` block: removes staging dir after upload processing
  5. Health endpoint `/health` reports `disk.total_mb`, `disk.free_mb`, `disk.used_pct`
  6. Startup logs disk usage, warns if <200MB free
- **Production Evidence**: Health shows 1.6TB free (45.2% used). All 3 upload surfaces verified working in browser.
- **Previous**: 65a (PID tracking), 65c (RAM/OOM fix via thread), 65d (disk space)
- **Affects**: `app/main.py` (startup, health, push endpoint, upload), `.dockerignore`
- **Tests**: `tests/test_session_65d_disk_cleanup.py` (10 tests)

### AD-163: GEDCOM Temporal Versioning — Change Tracking and Re-Enrichment Queue
- **Date**: 2026-02-24 | **Session**: 65d
- **Context**: When Nolan updates Ancestry and re-exports GEDCOM, the system needs to merge changes without losing history.
- **Decision**: Temporal versioning — every import creates a new version. Old data never deleted, only superseded. App reads "current" state via Postgres views.
- **Schema**:
  1. `gedcom_versions`: version metadata per import (community_id, source_hash for dedup)
  2. `gedcom_individuals/events/relationships`: added `version_id`, `superseded_by`, `is_current` columns
  3. `gedcom_change_log`: field-level change tracking between versions
  4. `gedcom_enrichment_queue`: photos needing re-enrichment after GEDCOM changes (Gatekeeper pattern)
  5. `current_gedcom_individuals` view: always shows latest state (is_current=TRUE)
- **Import Flow**: Parse → hash file (skip if duplicate) → diff against current → insert/supersede/mark-removed → log changes → queue enrichments
- **Multi-Community Ready**: `community_id` field enables separate version chains per community
- **Rejected**: Overwrite-on-import (loses history), soft-delete without version chain (can't track what changed when)
- **Affects**: `scripts/import_gedcom_version.py`, `scripts/supabase_migration_002_gedcom_versioning.sql`, `app/main.py` (reads from view)
- **Tests**: `tests/test_gedcom_versioning.py` (20 tests)

### AD-164: GEDCOM Admin UI — Version Management via Web
- **Date**: 2026-02-24 | **Session**: 66 (agent)
- **Context**: GEDCOM versioning infrastructure (AD-163) exists in CLI only. Admin must SSH or run local scripts to import GEDCOM files and see version history. Web UI needed for self-service admin operations.
- **Decision**: Enhance existing `/admin/gedcom` page with Supabase-backed version management panels:
  1. **Info Panel**: Current GEDCOM version number, import date, individual/family counts from `gedcom_versions` table
  2. **Versioned Upload**: Upload .ged file, parse with `gedcom_parser`, diff against current DB state via `import_versioned()`, show diff summary, require explicit "Apply" confirmation (Gatekeeper pattern)
  3. **Version History**: Table of all past imports with dates and change summaries from `gedcom_versions`
  4. **Re-Enrichment Queue**: Count of pending photos needing re-processing from `gedcom_enrichment_queue`
- **Why web UI over CLI**: (a) Admin may not have SSH access to Railway, (b) reduces bus factor for Nolan, (c) consistent with admin-panel-first approach for all data operations, (d) leverages existing auth guards and dark theme UI
- **Rejected**: Separate `/admin/gedcom-versions` page (fragmenting related functionality), auto-apply on upload without diff preview (violates Gatekeeper pattern), client-side GEDCOM parsing (python-gedcom is server-side only)
- **Affects**: `app/main.py` (new route sections + helpers), `tests/test_gedcom_admin.py` (new tests)
- **Tests**: `tests/test_gedcom_admin.py`

### AD-165: Upload Silent Data Loss — Cache Invalidation + R2 Upload Ordering
- **Date**: 2026-02-25 | **Session**: 66b
- **Context**: Upload shows "✓ 3 faces extracted, 3 added to Inbox" but data not visible in UI. Bug persisted through sessions 65a, 65c, 65d, 66. Root cause: TWO bugs working together.
- **Bug 1: Cache staleness**: Background upload thread writes to identities.json, photo_index.json, embeddings.npy on disk. Web app has global caches (`_photo_cache`, `_face_data_cache`, `_face_to_photo_cache`, `_photo_registry_cache`) that are built once and never invalidated after upload. Health endpoint (reads disk) showed 273 photos; sidebar (reads stale cache) showed 271.
- **Bug 2: R2 upload race**: Background thread deletes staging directory in `finally` block. Status endpoint tried to upload photos to R2 on first success poll — but staging directory was already deleted. Photos never uploaded to R2 → 404.
- **Fix**: (1) Move R2 upload INSIDE the background thread, BEFORE staging cleanup. (2) Invalidate all caches in the background thread after successful processing. (3) Remove R2 upload from status polling endpoint.
- **Rejected**: (a) Invalidating caches in the status endpoint (too late — user sees stale data on poll), (b) Not deleting staging dir (AD-162 disk space concern), (c) Re-reading from disk on every request (too slow for photo_cache with embeddings.npy)
- **Why previous fixes didn't catch this**: All sessions verified `status == "success"` but never checked if data appeared in UI. "Chrome can't handle file dialogs" was used as excuse to skip real upload testing.
- **Affects**: `app/main.py` (`_background_ingest`, `/upload/status/{job_id}`)
- **Tests**: `tests/test_upload_cache_invalidation.py`

### AD-166: Hook-Enforced Harness — Deterministic Session Quality Gates
- **Date**: 2026-02-25 | **Session**: 67
- **Context**: 7 subagent files created across sessions 65d-66 (ux-reviewer, session-evaluator, fix-prompt-writer, etc.) but ZERO were ever invoked. Subagents are suggestions — Claude consistently chose not to use them. Hooks are enforcement.
- **Decision**: Replace informational-only hooks with blocking enforcement hooks in `.claude/settings.json`:
  - **Stop hook**: Command hook reads `current_session.txt`, checks assessment file exists, phase verdicts in SESSION_LOG.md, screenshots have UX review, b-path exists if failures. Blocks via `{"decision": "block"}` if missing. `stop_hook_active` prevents infinite loops.
  - **PreCompact (manual)**: Exit code 2 blocks `/compact` — use `/clear` instead.
  - **PreCompact (auto)**: Injects recovery instructions with session-specific context.
  - **UserPromptSubmit**: Injects parallelization reminder before every prompt.
  - **PreToolUse (Bash)**: Runs pytest before any `git commit`.
  - **PostToolUse (Edit|Write)**: Warns to update AD when editing ML/core files.
- **Rejected**: (a) Agent-type Stop hook — fires every response, too expensive (spawns LLM subagent per turn). (b) Prompt-type UX review hook — prompt hooks cannot read files, can't check screenshot directories. (c) Keeping subagent-only approach — 3 sessions proved LLM voluntarily ignores them.
- **Key insight**: Hooks that use `exit 2` or `{"decision": "block"}` are DETERMINISTIC. No LLM involved in the enforcement decision. The check is code, not inference.
- **Caveat**: PreCompact "Can Block?" is listed as No in Claude Code docs. The `exit 2` approach may or may not work — testing in Phase 2.
- **Affects**: `.claude/settings.json`, `.claude/hooks/session-stop-gate.sh`, `.claude/hooks/recovery-instructions.sh`
- **Tests**: Manual verification in Phase 2 of session 67.

### AD-167: Hook Upgrade — Python Stop Gate, PreCompact Recovery Strategy
- **Date**: 2026-02-25 | **Session**: 68
- **Context**: Session 67's bash stop gate used grep patterns which caused false positive (matched "FAIL" in test description text). PreCompact `exit 2` confirmed to NOT block compaction per Claude Code docs.
- **Decision**: Two upgrades:
  1. **Python stop gate** (`.claude/hooks/session-stop-gate.py`): Replaces bash grep with structural regex that only matches FAIL in phase header lines (`^###?\s+Phase\s+\d+.*?FAIL`). Avoids false positives from FAIL appearing in arbitrary text content.
  2. **PreCompact recovery strategy**: Since `exit 2` cannot block compaction, changed approach — PreCompact manual now warns (exit 0) instead of false blocking (exit 2). Added `SessionStart` hook with "compact" matcher that re-injects all context from disk after compaction occurs.
- **Rejected**: (a) Keeping bash grep — already produced false positive. (b) Agent-type stop hook — fires every turn, too expensive. (c) Doing nothing about PreCompact — leaving broken exit 2 is misleading.
- **Key insight**: /compact cannot be mechanically blocked. The ban is enforced by convention (CLAUDE.md rule) + assessment RED FLAG (session-evaluator checks).
- **Affects**: `.claude/settings.json`, `.claude/hooks/session-stop-gate.py` (new), `.claude/hooks/post-compact-recovery.sh` (new)
- **Tests**: 4 scenarios verified — no assessment (block), with assessment (approve), FAIL without b-path (block), screenshots without UX review (block).

### AD-168: BUG-1 Create Identity 500 Error — Missing user_source Parameter
- **Date**: 2026-02-25 | **Session**: 69
- **Context**: Dogfooding found "Create [Name]" in tag dropdown silently fails. HTMX shows nothing (500 errors not rendered). Railway logs revealed: `TypeError: IdentityRegistry.rename_identity() missing 1 required positional argument: 'user_source'`.
- **Root cause**: `rename_identity()` at line 20006 was called with only `(identity_id, name)` but the method signature requires `(identity_id, name, user_source)`. Other callers (line 21339, 23998) correctly pass `user_source="web"`.
- **Fix**: Added `user_source="face_tag"` to the call. Added try/except for `KeyError`/`ValueError` returning a user-visible error toast instead of 500.
- **Secondary fix**: Hyperscript parse error on tag search input — `if firstBtn click firstBtn` needed `end` keyword per Hyperscript syntax.
- **Rejected**: (a) Making `user_source` optional with default — provenance tracking is a core invariant (AD-006), all callers should be explicit. (b) Client-side error handling only — the root cause was server-side.
- **Affects**: `app/main.py` (create-identity route, tag search input hyperscript)
- **Tests**: `test_create_identity_passes_user_source` — verifies `user_source="face_tag"` is passed and `confirm_identity` is called.

### AD-169: Gatekeeper Pattern Confirmation — Clustering Intentionally Offline
- **Date**: 2026-02-25 | **Session**: 69
- **Context**: Dogfooding found new faces appear as "Unidentified Person 768" with no cluster assignment. Similar Identities shows matches (Big Leon Capeluto at Dist: 0.91). Question: is auto-clustering broken or by design?
- **Decision**: CONFIRMED BY DESIGN. The Gatekeeper pattern (AD-006, AD-001) intentionally separates upload from clustering:
  - Stage 1 (Upload): Face detection → INBOX identities (no matching)
  - Stage 2 (Offline): `cluster_new_faces.py --execute` → generate proposals
  - Stage 3 (Review): Admin reviews proposals → confirms/rejects
  - `cluster_new_faces.py` header explicitly states "NEVER auto-merges"
  - AD-110 Serving Path Contract: web requests NEVER run heavy ML
- **UX gap identified**: High-confidence matches aren't surfaced prominently. Discovery notification system (Session 69 Phase 4) addresses this.
- **Rejected**: Auto-clustering on upload — violates AD-110 (no heavy ML in web requests) and Gatekeeper principle (human must review before assignment).
- **Affects**: No code changes. Documentation only.

### AD-170: ML Match Banner Vocabulary — System Labels to User-Friendly Prose
- **Date**: 2026-02-26 | **Session**: 71 (Track C)
- **Context**: Session 70 Subagent A (commit 103b6de) changed the proposal banner
  vocabulary from raw system confidence tiers to user-friendly language. The banner
  on inbox/proposed identity cards previously displayed `"ML Match: MODERATE"`,
  `"ML Match: HIGH"`, etc. — mixing system vocabulary with prose.
- **Old vocabulary** (displayed directly in banner):
  - `ML Match: VERY HIGH` (distance < 0.80)
  - `ML Match: HIGH` (distance < 1.00)
  - `ML Match: MODERATE` (distance < 1.20)
  - `ML Match: LOW` (distance >= 1.20)
- **New vocabulary** (via `_CONFIDENCE_LABEL` dict in app/main.py):
  - `Strong match` (VERY HIGH, distance < 0.80)
  - `Good match` (HIGH, distance < 1.00)
  - `Possible match` (MODERATE, distance < 1.20)
  - `Weak match` (LOW, distance >= 1.20)
- **Threshold mapping**: The confidence tiers themselves are unchanged. Only the
  display labels changed. The `_confidence_tier()` function and `core/config.py`
  thresholds (MATCH_THRESHOLD_VERY_HIGH=0.80, MATCH_THRESHOLD_HIGH=1.05,
  MATCH_THRESHOLD_MODERATE=1.15, MATCH_THRESHOLD_MEDIUM=1.20) are unmodified.
  Note: the proposal banner uses hardcoded 0.80/1.00/1.20 breakpoints (from the
  neighbor computation in `_get_best_proposal_for_identity`), which differ slightly
  from the calibrated `core/config.py` thresholds. This is an existing discrepancy
  predating the vocabulary change.
- **Risk assessment**: "Possible match" for MODERATE confidence (distance < 1.20,
  ~94% precision) could cause users to dismiss what is actually a likely match.
  However, the old "ML Match: MODERATE" was equally ambiguous to non-technical
  community users. The calibrated compare pages separately use "Very likely same
  person" / "Strong match" / "Possible match" / "Unlikely match" based on
  percentage scores (85%/70%/50% thresholds), which is a DIFFERENT vocabulary
  from the proposal banner. This creates two label systems operating simultaneously.
- **Decision**: ACCEPT the new vocabulary. The user-friendly labels are a clear UX
  improvement over raw system tiers. The minor risk of "Possible match" for ~94%
  precision matches is offset by the colored badge styling (amber for moderate)
  which provides additional visual signal. The dual-vocabulary issue (proposal
  banner vs compare page) should be tracked as a future UX consistency item.
- **Rejected**: Reverting to system labels — raw confidence tiers like "ML MATCH:
  MODERATE" are meaningless to community members who will use this archive.
- **Affects**: `app/main.py` `_CONFIDENCE_LABEL` dict, `_render_proposal_banner()`.
  No ML logic, threshold, or distance calculation changes.

### AD-171: Worktree Enforcement — Mechanical Script Replacing Behavioral Rules

- **Date**: 2026-02-26
- **Session**: 71D
- **Status**: ACCEPTED

**Problem:** Parallel session tracks were observed running directly on main branch despite written instructions in CLAUDE.md and LESSONS_LEARNED requiring worktree usage. Session 71 Track A ran on main — this is the 4th+ instance of behavioral rules failing under context window pressure.

**Decision:** Scripts that verify branch name (`enforce_worktree.sh`) and enforce ordered merge ceremony with test gates (`merge_tracks.sh`). Scripts exit non-zero on violation, which is mechanically enforced — unlike behavioral rules that degrade with context.

- **Rejected**: Adding another line to CLAUDE.md or LESSONS_LEARNED — proven to fail (4+ instances of tracks running on main despite written instructions).
- **Rejected**: Hook-based enforcement (too complex for shell scripts, harder to debug).
- **Why**: Behavioral rules don't survive context window pressure. Scripts that exit non-zero are mechanically enforced.
- **Affects**: scripts/enforce_worktree.sh, scripts/merge_tracks.sh, .claude/rules/worktree-enforcement.md
- **Breadcrumbs**: HD-021, docs/session_context/session-71d-context.md Section 6

### AD-172: Review Section Architecture — Fix Discoveries, Don't Merge
- **Date**: 2026-02-26 | **Session**: 71D
- **Context**: Dogfooding found Discoveries page is broken: no navigation from face images, misleading 54% display, only 1 of 2 matching faces shown. Three sections (New Matches / Discoveries / Help Identify) are confusing. See `docs/session_context/session-71d-context.md`.
- **Decision**: **Option A — Fix Discoveries as a separate section.** Keep the three-section architecture but fix the bugs:
  1. Replace misleading percentage with confidence labels (AD-173)
  2. Add clickable navigation (source face → person page, view photo link)
  3. Widen discovery threshold from 1.0 to 1.05 to catch borderline HIGH matches
  4. Add photo context (collection, co-occurring faces)
- **Rejected alternatives**:
  - **Option B (Merge into New Matches)**: Would simplify to two sections but requires extensive triage bar refactoring, risks conflicts with concurrent Track A work on templates/CSS, and loses the "proactive notification" UX concept.
  - **Option C (Notification banner)**: Lower risk but doesn't address the fundamental navigation and display issues; banner is less actionable than a full card.
- **Rationale**: The three-section funnel (Discoveries → New Matches → Help Identify) is architecturally sound. The problems are bugs in the Discoveries implementation, not a flawed architecture. Fixing is more surgical than restructuring, and keeps file changes contained to `app/main.py` discoveries code paths.
- **Affects**: `app/main.py` (discovery route, API endpoint, sidebar), `DISCOVERY_DISTANCE_THRESHOLD`

### AD-173: Match Confidence Display — Labels Replace Percentages
- **Date**: 2026-02-26 | **Session**: 71D
- **Context**: Discoveries page shows "54% match" for a distance-0.91 match. Formula `(1 - distance/2.0) * 100` produces numbers that contradict user intuition: 54% sounds uncertain, but distance 0.91 is a HIGH confidence match. The system already has `_CONFIDENCE_LABEL` mapping tiers to human-readable labels.
- **Decision**: Replace percentages with confidence tier labels on the Discoveries page:
  - VERY HIGH (<0.80): "Strong match"
  - HIGH (0.80-1.00): "Good match"
  - MODERATE (1.00-1.20): "Possible match"
  - LOW (>1.20): "Weak match"
  Uses the existing `_CONFIDENCE_LABEL` dict already defined in app/main.py. Admin tooltip shows raw distance for debugging.
- **Rejected alternatives**:
  - **Fixed percentage formula** (e.g., calibrated probability): Would require calibration pipeline changes and still risks user confusion since "percentage" implies "probability" which our distances are not.
  - **No display at all**: Removes useful information. Labels give the admin quick confidence assessment.
- **Rationale**: UX Principle #8: "Quality Scores are for Engineers." Labels are universally understood. Admin tooltip preserves debugging info. Consistent with how New Matches already shows confidence tiers.
- **Affects**: `app/main.py` discovery card rendering (line ~23741 and ~23809-23813)

### AD-174: Similarity Calibration — Siamese MLP on Frozen Embeddings
- **Date**: 2026-02-27 | **Session**: 72
- **Context**: The existing threshold system uses hard distance cutoffs (0.80/1.00/1.20) to classify match confidence. This ignores metadata signals and produces cliff effects at boundaries.
- **Decision**: Train a Siamese MLP calibrator on frozen InsightFace embeddings using |a-b| and a*b interaction features. The model outputs P(same_person) in [0,1].
- **Architecture**: 512→1024→32→1 (32K params). Dropout 0.5. BCE loss. Adam lr=5e-4, weight_decay=1e-2.
- **Training data**: 54 confirmed identities, 20 multi-face. 3804 train pairs (951 pos, 2853 neg), 40 eval pairs. Hard negatives: distance < 1.2 cross-identity pairs.
- **Results**: AUC 0.84, best F1 0.75, precision=1.0 at threshold 0.5. Beats baseline on AUC (+0.013) and precision@90%recall (+0.037). ECE slightly worse (+0.013) on small eval set.
- **Regression gate**: NO-SHIP on ECE (0.108 vs 0.095 baseline). All three metrics must beat baseline to ship. ECE regression is expected noise on 40 eval pairs.
- **Shadow scoring**: 2025 comparisons, 96.3% agreement. 74 disagreements ALL in MODERATE tier — calibrator is more conservative, demoting borderline matches. Zero false promotions.
- **Deployment**: Shadow mode only (Session 72). Not wired to production scoring. Will ship after: (1) more eval data, (2) ECE regression resolved, (3) admin review of shadow disagreements.
- **Rejected**: LoRA backbone fine-tuning (deferred per roadmap — 221 positive pairs marginal, calibration simpler).
- **Rejected**: Threshold tuning alone (ignores embedding interaction features, can't learn from data).
- **Rejected**: Full embedding concatenation (2x params, overfitting risk on small dataset).
- **Affects**: rhodesli_ml/calibration/, rhodesli_ml/artifacts/calibration_v1.pt, rhodesli_ml/scripts/extract_pairs.py, rhodesli_ml/scripts/evaluate_calibrator.py, rhodesli_ml/scripts/shadow_score.py

---

### AD-175: GEDCOM Date Parsing — Regex vs [:4] Slice
- **Date**: 2026-02-28 | **Session**: 75
- **Context**: Session 74 (Gemini) used `date_str[:4]` to extract years from GEDCOM dates. This fails catastrophically on day-first formats: `"21 SEP 1887"[:4]` = `"21 S"`, `"ABT 1900"[:4]` = `"ABT "`.
- **Accepted**: Regex extraction with `re.search(r'\b(\d{4})\b', date_str)` plus qualifier handling (ABT→~, AFT→aft., BEF→bef., BET...AND→range).
- **Rejected**: `[:4]` slice — produces garbage for all non-year-first GEDCOM formats.
- **Rejected**: dateutil parsing — overkill for year extraction, doesn't handle GEDCOM qualifiers.
- **Affects**: `rhodesli_ml/graph/relationship_graph.py` (parse_gedcom_year, format_lifespan), `app/main.py` (tree route GEDCOM date handling)

### AD-176: Relationship Data Merge — UUID + GEDCOM Coexistence
- **Date**: 2026-02-28 | **Session**: 75
- **Context**: Session 74 (Gemini) replaced 19 UUID-based relationships (linking confirmed photo identities to GEDCOM family structure) with 1,000 GEDCOM-xref-only relationships. UUID relationships are MORE authoritative because they link actual photos to people.
- **Accepted**: Merge both sets. Keep all 19 UUID-based + all 1,000 GEDCOM-xref relationships. Deduplicate by (person_a, person_b, type). UUID takes priority on conflict.
- **Rejected**: Replace old with new — loses identity-to-family links that took admin work to establish.
- **Rejected**: Keep only UUID — loses structural GEDCOM family data.
- **Affects**: `data/relationships.json`, `scripts/rebuild_full_graph.py`

### AD-177: family-chart CardHtml vs SVG Cards
- **Date**: 2026-02-28 | **Session**: 75
- **Context**: Session 74 used SVG-based cards with D3 post-render styling overlays. CardHtml is the library's modern API that renders HTML cards with native avatar support.
- **Accepted**: CardHtml via `f3.createChart().setCard(f3.CardHtmlWrapper)`. Supports avatar photos, HTML styling, and clean card display configuration.
- **Rejected**: SVG cards with D3 overlays — cannot render photos, requires fragile post-render DOM manipulation, dark theme overlay hides built-in features.
- **Affects**: `app/static/js/family-tree.js`, `app/main.py` (tree route template)

### AD-178: xdist Route Reordering — Atomic Slice vs Pop/Insert
- **Date**: 2026-02-28 | **Session**: 75
- **Context**: `routes.pop(i)` + `routes.insert(0, route)` caused race conditions under pytest-xdist parallel imports. Tests showed 9-13 intermittent timeouts per run. Root cause: non-atomic list mutations during concurrent module imports, plus 10s timeout too tight for heavy imports.
- **Accepted**: Atomic `routes[:] = priority + other` via `_reorder_routes_atomic()`. Combined with timeout increase from 10s to 30s.
- **Rejected**: threading.Lock — module-level code runs during import, lock adds complexity.
- **Rejected**: xdist_group markers — requires annotating every affected test.
- **Affects**: `app/main.py` (all route reordering blocks), `Makefile` (test-fast timeout)

### AD-179: Two-Tier Auto-Clustering at Upload Time
- **Date**: 2026-02-28 | **Session**: 76a
- **Context**: 775 identities (60 CONFIRMED, 472 INBOX, 215 SKIPPED). Manual review of all unresolved faces is impractical. Within-cluster distance stats: mean=1.01, std=0.19, p5=0.70, p25=0.88. 57 duplicate face IDs exist where the same face appears in both a confirmed identity AND a separate inbox identity.
- **Decision**: Auto-add faces to confirmed clusters when Euclidean distance < 0.85 (Tier 1). Surface as Discovery suggestion when 0.85 <= distance < 1.10 (Tier 2). Dedup pass removes inbox identities whose faces are already in confirmed clusters (exact face_id match).
- **Thresholds**: Tier 1 = 0.85 (well below p25=0.88 of same-person pairs, near-zero FP risk), Tier 2 = 1.10 (covers bulk of same-person distribution). Validated against 982 same-person pairs: mean=1.01, std=0.19, p5=0.70, p25=0.88.
- **Safety**: Tier 1 faces added to candidate_ids (NOT anchor_ids) with provenance="model". Admin must still confirm. All actions logged to data/discovery_log.json for threshold recalibration.
- **Rejected**: All-suggestion model (current cluster_new_faces.py) — produces 400+ manual review items, no prioritization.
- **Rejected**: Single threshold — doesn't capture the confidence gradient between "definitely same person" and "worth investigating".
- **Rejected**: Auto-add to anchor_ids — violates Gatekeeper pattern (provenance="human" > provenance="model").
- **ML Signal**: Every Discovery action logged to discovery_log.json. Schema includes face_id, distance, tier, action, user_decision fields. Enables future threshold recalibration from admin feedback.
- **Affects**: `core/auto_cluster.py`, `scripts/backfill_auto_cluster.py`, `scripts/process_uploads.py` (new step 5)

---

## How to Add New Entries

1. Add a new entry with AD-XXX format (next: AD-183)
2. Include the rejected alternative and WHY it was rejected
3. List all files/functions affected
4. If the decision came from a user correction, note that explicitly
5. Cross-reference config files that encode the decision's parameters

### AD-181: Pair Compare Must Include Archive Context
- **Date**: 2026-02-28
- **Context**: Two-photo compare produced an isolated similarity score but did not help users bridge discoveries back into archive identities.
- **Decision**: In `/api/compare/pair/match`, compute top archive matches for each selected face and render two archive-context sections under the pair score.
- **Rejected**: (1) Pair-only score (no next action). (2) Automatic identity assignment from pair score alone.
- **Why**: Rhodesli is an archive tool first; pair compare should be a discovery bridge, not a dead-end diagnostic.
- **Affects**: `app/main.py` pair compare match handler and compare result rendering path reuse.
- **Revisit condition**: If pair mode expands to N-photo graph compare, replace dual-section output with a unified ranked graph view.


### AD-182: Compare Uploads Auto-Queue + Pair All-Face Summaries
- **Date**: 2026-02-28
- **Context**: Session 77 prompt requires compare uploads to persist and enter admin review, and pair compare to evaluate all faces across both photos plus archive context.
- **Decision**: Automatically queue each compare upload in `pending_uploads.json` from `_save_compare_upload`; extend `/api/compare/pair/match` to publish top cross-photo face pairs and per-face archive best-hit summaries.
- **Rejected**: (1) Manual contribute-only queueing (drops uploads when user skips CTA). (2) Selected-face-only pair output (misses additional face evidence in multi-face photos).
- **Why**: Guarantees moderation visibility for uploads and aligns pair compare output with multi-face archive discovery goals.
- **Affects**: `app/main.py` (`_save_compare_upload`, `_queue_compare_upload_for_review`, `/api/compare/pair/match`), `tests/test_compare.py`.
- **Revisit condition**: If compare uploads move fully to Supabase tables, migrate queue write-path and keep JSON as fallback only.

### AD-183: Tier 2 Threshold Raise from 1.10 to 1.30
- **Date**: 2026-02-28
- **Context**: Session 78 threshold analysis proved 1.10 too low — 52% of same-person cluster distances exceed 1.10. Big Leon max=1.38, Nace max=1.41. Heritage photos span decades; aging causes large legitimate distances.
- **Decision**: Raise TIER_2_THRESHOLD from 1.10 to 1.30, DISCOVERY_DISTANCE_THRESHOLD from 1.05 to 1.30. Nolan explicitly approved. Backfill yielded 617 Tier 2 suggestions (vs 7 at 1.10), 137 unique discoveries visible in UI.
- **Rejected**: (1) Keep 1.10 — misses majority of legitimate same-person pairs. (2) Raise to 1.40+ — too many false positives for admin review.
- **Why**: Tier 2 only surfaces suggestions for admin review (no auto-action), so false positives are caught by human. Missing real matches (52%) was a worse trade-off.
- **Affects**: `core/auto_cluster.py` (TIER_2_THRESHOLD), `app/main.py` (DISCOVERY_DISTANCE_THRESHOLD), all threshold tests updated.
- **Revisit condition**: When enough admin decisions accumulate, use accept/reject rates to recalibrate.

### AD-184: family-chart CardSvg Replaces CardHtml
- **Date**: 2026-02-28
- **Context**: Session 79 tree debugging revealed CardHtml creates SVG skeleton but never populates cards_view with foreignObject elements. Zero cards rendered for any dataset size. CardSvg correctly renders rect+text cards.
- **Decision**: Switch from f3.CardHtml to f3.CardSvg in family-tree.js. Remove setStyle('default') call (not available on CardSvg).
- **Rejected**: (1) Keep CardHtml + debug — silently fails with no errors, would require library source investigation. (2) Custom HTML tree — over-engineering for current needs.
- **Why**: CardSvg works immediately with the current family-chart library build. Avatar support is lost but names/lifespans render correctly.
- **Affects**: `app/static/js/family-tree.js`.
- **Revisit condition**: If a newer family-chart version fixes CardHtml, or if avatar display in tree becomes a priority.

### AD-185: API-Driven Lazy Loading Tree with Search
- **Date**: 2026-02-28
- **Context**: Tree showed 13 of 718 people. 114 disconnected clusters. Dropdown navigation didn't scale. No search, no expand/collapse, no zoom controls, no click-to-navigate.
- **Decision**: Replace inline JSON tree with API-driven lazy loading. Three endpoints: `/api/tree/data` (focal person + depth), `/api/tree/expand` (directional expansion), `/api/tree/search` (type-ahead). JS rewritten for fetch-based loading with node action popup (View Profile / Focus Tree / Expand).
- **Rejected**: (1) BALKAN FamilyTreeJS — superior features but commercial license required for production. (2) Full tree dump — 718 nodes fine now but doesn't scale, and bad UX (shows one component only). (3) React/Next.js tree — overkill given FastHTML + HTMX constraint.
- **Library**: Kept donatso/family-chart with CardSvg. Library's `updateData()` + `updateTree()` support dynamic data replacement without chart recreation.
- **Affects**: `app/main.py` (3 API endpoints + page rewrite), `app/static/js/family-tree.js` (full rewrite).
- **Tests**: 18 new tests in `tests/test_tree_api.py`.

### AD-186: Find Similar Full-Page Layout + Face Card Click-to-Photo
- **Date**: 2026-02-28
- **Context**: Find Similar rendered as badly-formatted vertical column inside card. Face images not clickable. No share or quick actions visible. Prompt: "hero face + responsive grid below."
- **Decision**: (1) New `/people/{id}/similar` route — hero face (300-400px) + responsive grid of results with confidence tiers. (2) Face card images now clickable → navigate to full photo. (3) Quick action links visible below name (Similar, Profile). (4) Face count badge on multi-face cards.
- **Rejected**: (1) Keep inline neighbors sidebar — cramped, poor UX. (2) Modal overlay — loses URL sharability.
- **Affects**: `app/main.py` (new route + card changes).
- **Tests**: 8 new tests in `tests/test_find_similar_page.py`.

### AD-187: Compare Upload — Async Batch Processing, Not CPU Inference
- **Date**: 2026-02-28
- **Context**: Compare upload deferred 7+ sessions. Blocker: InsightFace needs GPU, Railway has no GPU. AD-007 prohibits adding ML deps to production.
- **Decision**: Ship the current async workflow as the official experience. Uploaded photos queue to R2 for batch processing on local hardware. Improved messaging explains the 24h turnaround. Archive-face comparison (using pre-computed embeddings) works immediately.
- **Rejected**: (1) ONNX Runtime CPU inference — violates AD-007, adds ~500MB to Docker image. (2) Proxy to external GPU service — adds dependency, cost, complexity. (3) MediaPipe/dlib — different embedding space from InsightFace, can't compare with existing archive embeddings.
- **Concrete plan for real-time compare**: When Railway adds GPU support OR a lightweight embedding model compatible with existing PFE vectors becomes available, implement: (a) ONNX export of InsightFace model, (b) onnxruntime-cpu inference for single uploaded face, (c) cosine distance against pre-cached archive embeddings.
- **Affects**: `app/main.py` (upload response messaging).

### AD-188: Photo/Face Ordering Controls on Public Person Page
- **Date**: 2026-02-28
- **Source**: OpenAI Codex (automated task, PR #2)
- **Accepted**: Yes, merged to main during Session 80.
- **Decision**: sort_by query parameter with 4 modes (date_asc, date_desc, uploaded_desc, uploaded_asc). Default: date_asc (earliest → latest). Shared sort-key logic across Faces/Photos views. Dropdown UI preserving sort across view toggles.
- **Rationale**: Straightforward UI/sorting feature. Codex was used because this was a well-scoped, isolated feature (sort parameter + dropdown UI + tests) that didn't touch ML pipelines or core architectural patterns. It ran in parallel with Session 80 (Claude Code) to test multi-agent development workflow.
- **Sort-key fallback chain**: best_year_estimate → date_taken → upload timestamp. Aligns with the ML roadmap's date estimation pipeline.
- **What Codex produced**: +144/-16 lines across app/main.py and tests/test_public_person_page.py. 3 new test methods.
- **Review notes**: Tests pass. No changes to ML code or Supabase schema.
- **Affects**: `app/main.py` (/person/{person_id} route), `tests/test_public_person_page.py`.

### AD-189: Photo-Dominant Tree v3 — 144px Faces + Timeline Scrubber
- **Date**: 2026-02-28
- **Context**: User feedback: "faces are too small", "lines too faint", "no easy way to expand". Floating-face v2 (DD-004) used 96px photos which were still insufficient.
- **Decision**: Increase to 144px diameter faces (PHOTO_R=72), 200x260px cards. Connection lines opacity 0.35→0.55 and stroke 1.5→2.5. Expand arrows pill-shaped with text labels ("Parents", "Children", "Siblings") instead of tiny arrow icons. Added timeline photo scrubber bar at bottom — CSS crossfade between multiple face crops per person when scrubbing through years.
- **Research**: Analyzed Google Photos timeline, MyHeritage family tree timeline, Clyfford Still Museum interactive exhibit, AgeLapse face scrubber, FamilySearch timeline. Docs: docs/research/timeline-slider-research.md, docs/research/reactive-tree-patterns.md.
- **Rejected**: (1) WebGL canvas rendering — overengineered for current scale. (2) Fixed photo size with zoom-to-see — defeats purpose of face-dominant design. (3) Auto-play animation — distracting, user-controlled scrubbing is superior.
- **Affects**: `app/static/js/family-tree.js`, `app/main.py` (tree page HTML/CSS, tree API face data).

### AD-190: GEDCOM Relationship Import — Fox/Capeluto/Fogel/Waldorf Tree
- **Date**: 2026-02-28
- **Session**: 80 continuation
- **Context**: Previous `relationships.json` had ~1000 xref-based relationships from wrong GEDCOM import. Abraham showed only 3 children instead of 7. Relationships used GEDCOM xref IDs (`@I123@`) instead of Rhodesli UUIDs, causing broken tree rendering.
- **Decision**: Parse Fox/Capeluto/Fogel/Waldorf GEDCOM file, BFS 3-deep from 35 matched identities, extract HUSB/WIFE/CHIL relationships from FAMS/FAMC records, convert xrefs to UUIDs.
- **Method**: GEDCOM parser reads FAM records for HUSB/WIFE/CHIL links. BFS traversal from matched identities captures 708 relevant people across 3 generations. Relationships mapped to UUID pairs via gedcom_matches.json lookup.
- **Result**: 1221 correct GEDCOM-sourced relationships replacing 1000 incorrect xref-based ones. Abraham now shows all 7 children (Zeb, Victoria, David, Matilda, Morris, Lenora, Rachel). Tree renders correctly with proper parent-child and spouse connections.
- **Affects**: `data/relationships.json`, `data/gedcom_matches.json`, tree API endpoints.

### AD-191: Best-Face Selection for Tree Nodes and Identity Cards
- **Date**: 2026-02-28
- **Session**: 80 continuation
- **Context**: User reported Big Leon showing worst quality photo instead of best. Photos varied significantly in quality (detection scores range from ~0.3 to ~0.99). First-face selection was arbitrary — depended on ingestion order, not quality.
- **Decision**: Tree node avatars and identity card heroes use `get_best_face_id()` instead of first face in the anchor/candidate list.
- **Method**: `get_best_face_id()` iterates through all face IDs for an identity, looks up each face's detection quality score from the embeddings cache, and returns the face with the highest score. Falls back to first face if no quality data is available.
- **Result**: All tree nodes and identity cards now show the best available photo. Big Leon shows his clearest portrait instead of a low-quality newspaper crop.
- **Affects**: `app/main.py` (`identity_card()`, tree API face data), `app/static/js/family-tree.js` (node avatar rendering).

### AD-192: GEDCOM-Enriched Location Prompting
- **Date**: 2026-02-28
- **Session**: 81 Act 4
- **Context**: Manual Gemini conversation identified Asheville photo (746dd11e5b4d86a1) as 33 Elizabeth Street using GEDCOM residence data + visual analysis. The automated extraction prompt lacked biographical cross-referencing for location. Location section was visual-only (architecture, vegetation, signage) with no instruction to use GEDCOM data.
- **Decision**: Enhance location prompt section to instruct Gemini to cross-reference visual clues with GEDCOM biographical data (residential addresses, children's birth places, occupation locations). Enhance GEDCOM context builder to emit residential history prominently and include children's birth months, spouse events (RESI/OCCU/IMMI/EMIG), and a "Children" subsection with explicit location-dating guidance.
- **Method**: (1) Location prompt section now has 3 steps: Visual Analysis, Biographical Cross-Reference, Confidence Assessment. Cross-reference step instructs "missing child" test and migration pattern analysis. (2) GEDCOM context builder separates RESI events into "Residential History" subsection, emits children under "Children (birth dates help narrow photo date and location)" heading with month precision when available, and propagates spouse RESI/OCCU events. (3) Location schema now has `visual_evidence`, `biographical_evidence`, and `missing_child_analysis` fields.
- **Result**: Asheville dry-run prompt contains all ground-truth-relevant data: Victoria's residence at 33 Elizabeth Street (1930-1940), Leon's occupation in Asheville, children Selma (b.1926 Asheville), Anita (b.1931 NC), Nace (b.1933 Mar Asheville), Betty (b.1950 Miami), Vida (b.1945 NY). Context is 654 tokens, total prompt 2021 tokens.
- **Affects**: `rhodesli_ml/gemini_extraction.py` (location prompt + schema), `rhodesli_ml/gedcom_context.py` (residential history, children context, spouse events).

### AD-193: Photo Location Data Model and UX
- **Date**: 2026-03-01
- **Session**: 81 Act 3
- **Context**: Location estimates were displayed as free text from Gemini but had no structured schema for geocoding, confidence, or provenance. Needed structured data to support embedded maps and admin corrections.
- **Decision**: Define `photo_locations.json` schema with per-photo location records containing: `location_name` (string), `region` (string), `country` (string), `lat`/`lng` (float), `confidence` (high/medium/low), `source` (gemini/human/geocoded), `evidence` (string). UI renders embedded Leaflet.js map when lat/lng present, location label with confidence badge, evidence text, and admin-only correction form.
- **Schema**:
  ```json
  {
    "version": 1,
    "photos": {
      "<photo_id>": {
        "photo_id": "<photo_id>",
        "location_name": "Rhodes, Greece",
        "region": "Mediterranean",
        "country": "Greece",
        "lat": 36.4413,
        "lng": 28.2261,
        "confidence": "high",
        "source": "gemini",
        "location_estimate": "Visual evidence text from Gemini",
        "all_matches": [{"key": "rhodes", "name": "Rhodes, Greece"}]
      }
    }
  }
  ```
- **UX patterns**: Embedded mini-map (Google Photos), confidence badge (internal date estimate pattern), evidence text (original to Rhodesli). Research: `docs/session_context/session_81_location_ux_research.md`.
- **Rejected**: (1) Google Maps API — requires API key and billing. (2) Storing locations in Supabase only — premature, JSON file matches current date-labels pattern. (3) Full-page map only — embedded mini-map provides context without navigation.
- **Affects**: `app/main.py` (`_build_ai_analysis_section`, `_load_photo_locations`), `data/photo_locations.json`, `tests/test_location_ux.py`.

### AD-194: Inline Find Similar Expansion Panel
- **Date**: 2026-03-01
- **Session**: 82d
- **Context**: Find Similar navigated to a full page (`/people/{id}/similar`), losing browse context. Admin loses scroll position and must use back button. Codex PR attempted to add expansion panels but never shipped.
- **Decision**: Admin mode uses HTMX inline expansion panels. "Similar" button uses `hx-get` to fetch `/api/find-similar/{identity_id}` which returns an HTML fragment with hero face, scrollable similar face tiles (160px wide), and action buttons (Compare, Merge, Not Same). Panel spans full grid width via `grid-column: 1 / -1`. Multiple panels can be open simultaneously. Public visitors still get full-page link to `/people/{id}/similar`.
- **Animation**: CSS `@keyframes panel-fade-in` (opacity 0→1, translateY -8px→0, 300ms cubic-bezier). Pure CSS approach chosen over animate-css-grid (4KB library overhead unnecessary) and View Transitions API (not supported in all browsers).
- **Rejected**: (1) View Transitions API — browser support too limited (Chrome/Edge only). (2) animate-css-grid — unnecessary dependency for a simple fade-in. (3) CSS grid-template-rows 0fr→1fr — doesn't work well with dynamic HTMX content swaps.
- **Affects**: `app/main.py` (new endpoint, expansion panel CSS, card grid rendering), `tests/test_inline_find_similar.py`.

### AD-195: Person Page Gallery HTMX Partial Swap
- **Date**: 2026-03-01
- **Session**: 82d
- **Context**: Person page Faces/Photos toggle used full page navigation (`<a href="/person/{id}?view=...">`), causing slow switching due to rebuilding the entire page (hero, metadata, connections, etc.).
- **Decision**: Convert toggle to HTMX partial swap via new endpoint `GET /api/person/{id}/gallery?view=&sort_by=`. Returns toggle buttons + sort dropdown + gallery grid. Container div with `id="person-gallery-container"` is the swap target. Only the gallery section is rebuilt, not the entire page.
- **Rejected**: (1) Tab preloading (load both views on initial render) — doubles initial page size. (2) Client-side DOM show/hide — requires all face and photo data in initial HTML. (3) JavaScript tab switching — goes against HTMX-first architecture.
- **Affects**: `app/main.py` (new gallery endpoint, person page toggle refactoring).

### AD-196: Display Name as Primary Identity Field
- **Date**: 2026-03-02
- **Session**: 83a
- **Context**: Only name field in Edit Details was "Maiden Name" which prepended "née". Admin literally could not set a primary display name — confirmed people appeared nameless or as "née Isaac Cohen". First real user (Claude Benatar) hit this trying to identify Isaac Cohen.
- **Decision**: Add "Display Name" / "Full Name" as the FIRST field in Edit Details metadata form. Posts to `/api/identity/{id}/metadata` with `display_name` param. Calls `registry.rename_identity()` to set the identity's primary name. OOB swap updates name header in real-time. "Maiden Name" remains as secondary/optional field.
- **Rejected**: (1) Repurposing Maiden Name field — loses maiden name functionality for female identities. (2) Inline rename on face card — too complex for initial fix, Edit Details form is the right place.
- **Affects**: `app/main.py` (Edit Details form, metadata endpoint), `core/registry.py`.

### AD-197: Help Identify Submissions Wired to Annotations System
- **Date**: 2026-03-02
- **Session**: 83a
- **Context**: `/api/identify/{person_id}/respond` saved to `identification_responses.json` (a separate file) but admin approvals read from `annotations.json`. Submissions silently disappeared — users got "Thank you!" but nothing reached admin. Claude Benatar was affected.
- **Decision**: Help Identify now creates proper annotation entries in the annotations system (Supabase + JSON). Submissions appear in admin Approvals tab. Admin users submitting get direct apply option (skip approval queue). Email field hidden for logged-in users. Error shown on failure instead of false "Thank you!" success. Legacy `identification_responses.json` still written as audit trail.
- **Rejected**: (1) Fixing identification_responses.json reader — wrong approach, annotations system is the canonical path. (2) Auto-approving all submissions — violates Gatekeeper pattern (AD-097).
- **Affects**: `app/main.py` (identify respond endpoint, identify page template), `data/annotations.json`.

### AD-198: Compare Result Storage Fix
- **Date**: 2026-03-02
- **Session**: 83a
- **Context**: SSE compare handler called `_save_compare_upload()` (R2/local metadata) but never `_save_comparison_result()` (comparison_results.json). Result page looked up results in comparison_results.json → not found → 404. Every compare analysis completed successfully but results were unretrievable.
- **Decision**: SSE handler now calls `_save_comparison_result()` with full result data (faces, matches, date estimate) at pipeline completion. UUID format fixed: `str(uuid4())[:12]` included hyphens → `uuid4().hex[:12]` for clean IDs. 404 page updated with "expired" messaging instead of generic "not found".
- **Rejected**: (1) In-memory result cache only — wouldn't survive Railway restarts. (2) Database storage — premature, JSON file matches current pattern.
- **Affects**: `app/main.py` (SSE compare handler, compare result page), `data/comparison_results.json`.

### AD-199: Admin Face Card Search Filter
- **Date**: 2026-03-02
- **Session**: 83a
- **Context**: Admin had to Cmd+F through hundreds of face cards to find a specific person by number or name. No built-in search/filter in Browse view.
- **Decision**: Client-side search filter input in admin Browse view header. Filters cards by name (case-insensitive substring) or person number. Uses `data-name` and `data-number` attributes on card elements. Pure JavaScript, no server round-trip needed for responsive filtering. Hides non-matching cards via display:none.
- **Rejected**: (1) Server-side search with HTMX — adds latency for a simple filter. (2) Full-text search with Supabase — overkill for ~660 cards. Client-side is instant and simple.
- **Affects**: `app/main.py` (Browse view card rendering, search input component).

### AD-200: Unified Confidence Scoring
- **Date**: 2026-03-04
- **Session**: 87
- **Context**: 6+ divergent scoring paths produced different confidence percentages for the same Euclidean distance. Distance 1.13 showed 62% in archive compare (neighbors.py CDF), 48% in vs-person compare (sigmoid fallback), and 43% in pair compare (linear). Users saw "Possible match" in one place and "Unlikely match" in another for the same match. Root cause: 3 different formulas (isotonic calibrator, sigmoid CDF, linear), 3 different tier systems (distance-based vs pct-based), and inline code duplication across 12+ locations.
- **Decision**: Single `core/confidence.py` module with `compute_face_confidence(distance)` as sole entry point. Returns `{confidence_pct, tier, label, short_label, tier_color, dots}`. Priority chain: (1) isotonic calibrator via SimilarityCalibrator, (2) sigmoid CDF with same_person stats, (3) linear fallback `(2-d)/2*100`. Tier boundaries based on confidence_pct (85%+ Strong, 70%+ Possible, 50%+ Similar, &lt;50% Weak) per AD-091.
- **Rejected**: (1) Keeping distance-based tiers alongside pct-based — creates exactly the inconsistency we're fixing. (2) Always using linear — loses calibration model quality. (3) Removing fallbacks — calibrator may not be available in all environments.
- **Affects**: `core/confidence.py` (new), `core/neighbors.py`, `app/compare_routes.py`, `app/main.py`. Removed all `SimilarityCalibrator` imports from compare_routes. Removed 3 local `_confidence_tier()` definitions from main.py.
- **Tests**: 35 tests in `tests/test_confidence.py` covering all priority paths, boundary conditions, and consistency invariant.
- **Session 88 Update**: Isotonic calibrator `f_=None` crash fixed (rebuild interp1d from stored thresholds in similarity_calibration.py). However, isotonic too coarse (10 breakpoints → 99% for everything above dist ~1.22). Priority chain changed to: (1) sigmoid CDF with auto-loaded same_person_stats (n=959, mean=1.0148, std=0.187 from kinship_thresholds.json), (2) linear fallback. Batch NN override in neighbors.py removed entirely — single scoring path via `compute_face_confidence()`. Tests updated to 39.

### AD-201: Unified Gemini Prompt — Interactive Route Uses Enriched Prompt
- **Date**: 2026-03-04
- **Session**: 89
- **Context**: Interactive estimate route (`app/estimate_routes.py`) used `_GEMINI_DATE_PROMPT` — a stripped-down visual-only prompt from Feb 14. It didn't ask for location and didn't accept GEDCOM context. The batch pipeline (`rhodesli_ml/gemini_extraction.py`) had the full enriched prompt with location, GEDCOM, face analysis — but the two were never unified. This caused photo 746dd11e5b4d86a1 (Victoria Capuano, Asheville ~1934) to show "Brooklyn, New York" because Gemini only had visual cues.
- **Decision**: Replace `_GEMINI_DATE_PROMPT` with `build_extraction_prompt(preset="quick")`. The "quick" preset includes date_estimation + location + text_signage (no face_analysis or cultural_markers, keeping it fast). Added `gedcom_context` parameter that is forwarded to `build_extraction_prompt()`. Every interactive Gemini call now logged to Supabase `gemini_api_calls` via `log_gemini_call()` with full provenance: model, tokens, cost, latency, gemini_config JSONB (enrichment_level, prompt_version, gedcom_variant, temperature, trigger, model_generation).
- **Rejected**: (1) Using "full" preset for interactive — too slow (includes face_analysis, cultural_markers). (2) Creating a third prompt variant — prompt divergence was the root cause. (3) Not logging interactive calls — violates AD-152 mandate.
- **Breadcrumbs**: AD-148 (curated GEDCOM variant optimal), AD-152 (API call logging), AD-192 (GEDCOM-enriched location prompting), AD-193 (location data model).
- **Affects**: `app/estimate_routes.py` — `_call_gemini_date_estimate()` rewritten. `_GEMINI_DATE_PROMPT` removed.
- **Tests**: 10 tests in `tests/test_estimate_gemini.py`.

### AD-202: Admin Re-analyze — One-Click Gemini Re-Run on Photo Page
- **Date**: 2026-03-04
- **Session**: 89
- **Context**: After uploading a photo and linking GEDCOM records via admin UI, there was no way to re-run Gemini to account for the new biographical context. Owner workflow: upload → link GEDCOM → want updated analysis.
- **Decision**: POST `/api/photo/{photo_id}/reanalyze` endpoint (admin-only). Loads photo from R2/local, builds GEDCOM context for identified faces, calls Gemini via `_call_gemini_date_estimate()` with `call_type='re_analysis'` and `trigger='admin_rerun'`. Updates `date_labels.json` and `photo_locations.json`. Returns HTMX partial showing diff ("Brooklyn → Asheville") and cost. "Re-analyze" button in AI Analysis section header (admin-only). Inline geocoder for common locations. Batch script `scripts/reprocess_with_gedcom.py` for multi-photo reprocessing.
- **Rejected**: (1) Auto-trigger on GEDCOM link — too expensive for exploratory linking. (2) Full page reload after re-analyze — HTMX partial is smoother. (3) Client-side geocoding API — adds dependency, inline dict is sufficient for known communities.
- **Breadcrumbs**: AD-152 (API logging), AD-192 (location prompting), AD-201 (unified prompt).
- **Affects**: `app/estimate_routes.py` (reanalyze endpoint + helpers), `app/main.py` (button in `_build_ai_analysis_section`), `scripts/reprocess_with_gedcom.py` (batch script).
- **Tests**: 14 tests in `tests/test_reanalyze.py`.

### AD-203: Commit Counter Stale Detection Threshold — 120s → 3600s + Git-Clean Heuristic
- **Date**: 2026-03-05
- **Session**: 90 (harness fix)
- **Context**: The `commits_since_clear.txt` counter (Lesson 103, HD-024) uses file mtime to detect stale state from a prior conversation. The original 120s threshold was too aggressive — starting a new conversation within 2 minutes of a previous one ending would inherit the old counter and immediately hard-block. This happened in practice when the user started a new prompt shortly after a prior session ended cleanly.
- **Decision**: Two changes to both `UserPromptSubmit` and `PreToolUse` hooks in `.claude/settings.json`:
  1. **Stale threshold 120s → 3600s**: A counter file older than 1 hour is definitively from a prior session. 1 hour is generous — conversations rarely span that gap without activity.
  2. **Git-clean secondary check**: If counter ≥ 3 (UserPromptSubmit) or ≥ 4 (PreToolUse) BUT `git status --porcelain` is empty (no uncommitted changes), auto-reset the counter with a warning instead of hard-blocking. Rationale: if the commits all landed cleanly and there's no dirty state, the counter is residual from a completed session, not evidence of context degradation in the current one.
- **Rejected**: (1) Removing the counter entirely — the /clear enforcement has genuine value within a single session. (2) Using conversation ID — not available in hook environment. (3) Shorter threshold like 300s — still risks false positives during quick session transitions.
- **Affects**: `.claude/settings.json` (UserPromptSubmit hook, PreToolUse Bash hook).
- **Tests**: Manual verification — start new conversation with stale counter file.

### AD-204: Collection Metadata + Location Disambiguation in Gemini Prompt
- **Date**: 2026-03-06
- **Session**: 90c
- **Context**: Leon's Restaurant photo (3192877a90a174e9) from "Nace Capeluto Tampa Collection" was estimated as San Francisco/NYC by Gemini. The collection name — a strong location signal — was never passed to the prompt. Additionally, GEDCOM immigration records list ports of entry (like San Francisco) which are transit points, not residences.
- **Decision**: Three prompt improvements:
  1. **Photo Metadata Context section**: New optional `photo_metadata` dict param to `build_extraction_prompt()` — injects collection name, source, filename, visible text as context. Prompt tells Gemini the collection name often indicates geographic origin.
  2. **Business Name Cross-Reference (Step 2b)**: Cross-reference visible signage with family member names. "LEON'S RESTAURANT" + Leon Capeluto → strong location evidence for Leon's known locations.
  3. **Immigration & Transit Disambiguation (Step 2c)**: Ports of entry are transit points, not residences. Residence events, occupation, and children's birth places are more reliable. Visual evidence preferred over transit records.
- **Result**: After re-analysis, Gemini says "Tampa, Florida, USA" (high confidence) with genealogical context explicitly mentioning Leon Capeluto's restaurant and the Tampa Collection. Cost: $0.037.
- **Rejected**: (1) Hardcoding location hints per collection — doesn't generalize. (2) Removing immigration data from GEDCOM context — throws away useful data, just needs disambiguation.
- **Affects**: `rhodesli_ml/gemini_extraction.py` (build_extraction_prompt), `app/estimate_routes.py` (reanalyze route).
- **Tests**: 10 new tests in `rhodesli_ml/tests/test_gemini_extraction.py`.

### AD-205: Keep Face Alignment and Geo/Date as Separate Gemini Calls
- **Date**: 2026-03-06
- **Session**: 90c
- **Context**: Face alignment (per-face descriptions from bounding boxes) and geo/date estimation (location, date, scene analysis) are currently two separate Gemini API calls. Research whether combining them saves cost or improves quality.
- **Decision**: Keep them separate. Reasons:
  1. **Different output schemas**: Face alignment returns per-face structured data (age, gender, attire, position). Geo/date returns location, date, scene, evidence. Combined schema would be complex and fragile.
  2. **Different trigger patterns**: Geo/date runs automatically on upload. Face alignment is on-demand (admin clicks "Detect Faces"). Combining would force both to run together.
  3. **Minimal cost savings**: Each call is ~$0.02-0.04. Combined would save one image upload (~$0.01). Not worth the complexity.
  4. **Quality risk**: Combining multiple tasks in one prompt can reduce accuracy on each individual task.
- **Rejected**: Combined single call — complexity outweighs the ~$0.01 savings per photo.
- **Affects**: No code changes. Documents the architectural decision to maintain separate pipelines.
- **Also added**: `analyzed_at` timestamp field to AlignmentResult dataclass, displayed in Face Analysis section UI.

### AD-206: GlobalPersonID Schema — Cross-Community Identity Linking
- **Date**: 2026-03-07 | **Session**: 91/91b
- **Context**: As Rhodesli scales to multiple communities (Fox family, other archives), identities may appear across collections. Need a way to link the same person across communities without merging their per-community identity records.
- **Decision**: Three-table schema: `communities` (registry of archives), `global_person_links` (maps local identity → global person across communities), plus `community_id` foreign key on identities and photos tables. Each community maintains its own identity namespace; global links are admin-created.
- **Implementation**: `scripts/sql/create_communities.sql`, `scripts/sql/create_global_person_links.sql`. Tables created in Supabase. Rhodes community seeded as first entry.
- **Affects**: Future multi-tenant features. No app code wired yet — schema-only.

### AD-207: Postgres as Source of Truth — DATA_SOURCE Feature Flag
- **Date**: 2026-03-07 | **Session**: 91/91b
- **Context**: Moving from JSON files to Postgres (Supabase) as the canonical data store. Need a gradual migration path that doesn't break production.
- **Decision**: `DATA_SOURCE` environment variable controls read path. `json` (default) reads from JSON files with shadow-writes to Supabase. `postgres` reads directly from Supabase. This allows testing the Postgres path on staging before flipping production.
- **Implementation**: `app/supabase_data.py` has `load_from_postgres()`. `save_registry()` handles both paths. Shadow writes are fire-and-forget via background threads.
- **Status**: JSON is still default. Postgres path code-complete but not yet tested on Railway.

### AD-208: Observability — Sentry + PostHog + structlog
- **Date**: 2026-03-07 | **Session**: 91/91b
- **Context**: Production errors are invisible unless users report them. Need structured logging, error tracking, and product analytics.
- **Decision**: Three-layer observability, all env-gated (no-ops when env vars absent):
  1. **Sentry** (`SENTRY_DSN`): Error tracking + performance monitoring
  2. **PostHog** (`POSTHOG_API_KEY`): Product analytics (page views, feature usage)
  3. **structlog**: Structured JSON logging for all app events
- **Implementation**: Packages in requirements.txt. Init code in app startup. All gated on environment variables — zero cost when not configured.
- **Status**: Code in place, env vars not yet set on Railway. User will create Sentry/PostHog accounts.

## AD-209: Collection Name as Weak Provenance, Not Location Signal

**Date**: 2026-03-07 | **Session**: 91b | **Supersedes**: Part of AD-204

**Problem**: AD-204 introduced collection name as a strong location signal. This caused Leon's Restaurant photo (3192877a90a174e9, "Nace Capeluto Tampa Collection") to be estimated as Tampa instead of Asheville, NC.

**Ground truth**: GEDCOM shows Leon Capeluto residence at 33 Elizabeth St, Asheville, NC (1928-1940). Family moved to Tampa after 1940. Collection named after Nace who ended up in Tampa.

**Decision**: Collection name is WEAK provenance context (who had the photos), not location evidence. Visual evidence and GEDCOM residence data at the time are stronger signals.

**Eval**: Leon's Restaurant must return Asheville. Tampa photos with Tampa evidence must still return Tampa.

### AD-210: Business Name → Owner GEDCOM Lookup
- **Date**: 2026-03-07 | **Session**: 92
- **Context**: Leon's Restaurant photo (3192877a90a174e9) shows a business with "LEON'S" in the name. Leon Capeluto owned the restaurant and lived in Asheville, NC. However, build_photo_context() only includes GEDCOM data for people whose faces are identified in the photo. Leon isn't pictured, so his residential history (Asheville) was missing from the prompt.
- **Decision**: Add `find_business_owner_context()` that searches GEDCOM individuals for name matches in visible text/signage. When text like "LEON'S RESTAURANT" is detected, find GEDCOM individuals named Leon and include their residential history in the prompt. This provides location signal from business ownership even when the owner isn't pictured.
- **Alternatives considered**: Manual per-photo override (rejected: doesn't scale, requires admin to know the connection). Hard-coding known business-person mappings (rejected: brittle, not generalizable).
- **Implementation**: `rhodesli_ml/gedcom_context.py` — `find_business_owner_context()`. Caller in `app/estimate_routes.py` passes `visible_text` from photo metadata. Also adds full API call logging (prompt_text, full_response, gedcom_context) to gemini_api_calls table.
- **Risk**: False positive name matches (e.g., common names). Mitigated by requiring 3+ character matches and labeling as "candidate" rather than confirmed owner.
