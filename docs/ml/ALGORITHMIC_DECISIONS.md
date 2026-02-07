# ML & Algorithmic Decisions

This document records all data science and algorithmic decisions for the Rhodesli face recognition pipeline.
**Claude Code: Read this ENTIRE file before modifying any ML code.**

## Decision Log

### AD-001: Multi-Anchor Identity Matching (NOT Centroid Averaging)
- **Date**: 2026-02-06
- **Context**: When merging face clusters (e.g., child photos + adult photos of the same person), how should the identity's embedding representation be updated?
- **Decision**: Use Multi-Anchor — each identity retains ALL individual face embeddings as separate anchors. "Find Similar" computes min-distance across all anchors (Single Linkage / Best-Linkage strategy).
- **Rejected Alternative**: Centroid averaging (computing mean of all embeddings). This creates a "ghost vector" — averaging a 4-year-old and 24-year-old produces a 14-year-old that matches neither.
- **Why**: Heritage archives span decades. The same person at different ages has drastically different embeddings. Averaging destroys the signal from both age groups.
- **Implementation**: `core/neighbors.py` — `get_identity_embeddings()` returns ALL anchor + candidate embeddings, `find_nearest_neighbors()` uses best-linkage (minimum pairwise distance).
- **Affects**: `core/neighbors.py` (FROZEN — find_similar logic), `core/clustering.py`, `core/fusion.py`, any future clustering code.
- **Test**: Golden set should include identities with age-diverse photos. Matching must work for BOTH the youngest and oldest photo of the same person.

### AD-002: Embedding Generation Strategy
- **Date**: 2026-02-06
- **Context**: When are face embeddings generated?
- **Decision**: Embeddings are generated ONCE during initial face detection (via InsightFace/AdaFace producing 512-dim PFE vectors). They are never regenerated or updated after creation.
- **Rationale**: Embeddings are deterministic for a given crop. Re-generating would produce identical results. Only re-embed if switching to a different model entirely.
- **Affects**: `core/pfe.py`, `core/embeddings_io.py`, ML pipeline scripts.

### AD-003: Distance Metric — Mutual Likelihood Score (MLS)
- **Date**: 2026-02-06
- **Context**: How to measure similarity between face embeddings?
- **Decision**: Mutual Likelihood Score (MLS) from Probabilistic Face Embeddings. Each embedding has both a mean vector (mu, 512-dim) and variance (sigma_sq). MLS accounts for uncertainty in the embedding.
- **Rationale**: MLS is superior to cosine distance for PFE embeddings because it incorporates confidence (sigma). Low-quality faces get wider sigma, naturally down-weighting uncertain matches.
- **Scalar sigma fix**: When sigma_sq is uniform across dimensions, MLS uses a single-term formula to avoid the log penalty from drowning the discriminative signal. See `docs/adr/adr_006_scalar_sigma_fix.md`.
- **Affects**: `core/pfe.py` (MLS computation), `core/neighbors.py` (similarity search), `core/clustering.py` (cluster formation).

### AD-004: Rejection Memory
- **Date**: 2026-02-06 (design phase)
- **Context**: When a user clicks "Not Same", should this information be stored and used?
- **Decision**: YES — store rejected pairs in `negative_ids` and exclude them from future "Find Similar" suggestions.
- **Status**: Designed, partially implemented. `negative_ids` exists in identity schema.
- **Affects**: `core/neighbors.py` (find_similar), identity data schema in `data/identities.json`.

### AD-005: Clustering — Complete Linkage with MLS
- **Date**: 2026-02-06
- **Context**: How should initial identity clusters be formed from detected faces?
- **Decision**: Agglomerative clustering with complete linkage using MLS distance and temporal priors.
- **Why complete linkage**: Prevents "chaining" — where two unrelated faces get merged through a chain of intermediate matches. Complete linkage requires ALL pairs in a cluster to be similar.
- **Temporal priors**: Era-based penalties adjust MLS scores based on photo metadata. See `docs/adr/adr_003_identity_clustering.md`.
- **Affects**: `core/clustering.py`, `core/temporal.py`.

### AD-006: Provenance Hierarchy — Human Overrides Model
- **Date**: 2026-02-06
- **Context**: When a human confirms or rejects a face match, how does this interact with ML-proposed matches?
- **Decision**: `provenance="human"` always overrides `provenance="model"`. Human decisions are final and cannot be reversed by re-running the ML pipeline.
- **Affects**: Identity state machine (INBOX → PROPOSED → CONFIRMED), merge/detach operations in `app/main.py`.

### AD-007: Local-Only ML Inference
- **Date**: 2026-02-06
- **Context**: Where does face detection and embedding generation run?
- **Decision**: ALL ML inference runs locally on the developer's machine. Production (Railway) only serves pre-computed results (JSON, NPY, crops).
- **Rule**: NEVER add heavy ML libraries (torch, tensorflow, dlib, insightface, onnxruntime) to production `requirements.txt`. These would bloat the Docker image and aren't needed at runtime.
- **Affects**: `requirements.txt`, Dockerfile, any new ML scripts.

### AD-008: Deterministic Crop Naming Convention
- **Date**: 2026-02-06
- **Context**: How are face crop filenames generated for R2 storage?
- **Decision**: Two deterministic patterns coexist:
  - **Legacy crops**: `{sanitized_stem}_{quality}_{face_index}.jpg` where `sanitized_stem` is the photo filename lowercased with non-alphanumeric chars replaced by underscores, `quality` is the float detection quality score (e.g., `22.17`), and `face_index` is the 0-based face number within the photo.
  - **Inbox crops**: `{face_id}.jpg` where face_id is the inbox-format ID (e.g., `inbox_739db7ec49ac`).
- **Why**: R2 URLs are constructed deterministically from these patterns. Changing the naming convention breaks ALL existing crop URLs across the entire archive.
- **Rule**: This naming convention is a STRICT CONTRACT. Any change requires re-uploading all crops to R2.
- **Affects**: `scripts/regenerate_crops.py`, `core/crop_faces.py`, `core/storage.py` (URL generation), R2 upload scripts, `app/main.py` (`resolve_face_image_url`).
- **Cross-reference**: See `docs/architecture/PHOTO_STORAGE.md` for URL generation details.

### AD-010: No Hard Quality Filter
- **Date**: 2026-02-06
- **Context**: Should blurry or low-res crops be discarded to improve cluster purity?
- **Decision**: NO. Retain ALL detected faces.
- **Mechanism**: We rely on PFE (Probabilistic Face Embeddings). Low-quality faces generate high `sigma` (uncertainty) values, which mathematically prevents them from dominating a cluster or creating false positives via MLS scoring.
- **Why**: Heritage photos are often scarce and low-quality. A blurry match of a great-grandfather is better than zero matches. PFE handles quality weighting automatically.
- **Affects**: Face detection pipeline, clustering logic.

### AD-012: Golden Set Methodology
- **Date**: 2026-02-06
- **Context**: How do we establish "Ground Truth" for ML regression testing?
- **Decision**: Dynamic User-Verified Truth. The Golden Set is rebuilt automatically from the live database. Any Identity with >=3 "Confirmed" faces (provenance="human") is treated as a ground-truth cluster.
- **Why**: Allows the test suite to grow organically as the admin organizes the library, without maintaining a separate lab dataset. Ground truth comes from human verification, not external labels.
- **Affects**: `scripts/build_golden_set.py`, `scripts/evaluate_golden_set.py`, `data/golden_set.json`.

---

## Detailed ADR Documents

These appendix documents contain mathematical derivations and extended rationale:

| ADR | Title | Referenced By |
|-----|-------|---------------|
| `docs/adr/adr_001_mls_math.md` | MLS mathematical derivation | AD-003 |
| `docs/adr/adr_002_temporal_priors.md` | Temporal prior design | AD-005 |
| `docs/adr/adr_003_identity_clustering.md` | Identity clustering algorithm | AD-005 |
| `docs/adr/adr_004_identity_registry.md` | Identity registry design | AD-004 |
| `docs/adr/adr_006_scalar_sigma_fix.md` | Scalar sigma MLS fix | AD-003 |
| `docs/adr/adr_007_calibration_adjustment_run2.md` | Calibration adjustment run 2 | AD-003 |

---

## Undocumented Decisions (Require Code Review)

### TODO: AD-009 — Temporal Prior Penalty Values
- **Status**: Eras (Child, Adult, Elder) are implemented but exact penalty values were never formally decided.
- **Action**: Review `core/temporal.py` to extract actual penalty multipliers and document them.
- **Cross-reference**: `docs/adr/adr_002_temporal_priors.md` may contain the values.

### TODO: AD-011 — Face Detection Parameters
- **Status**: InsightFace `buffalo_l` model selected, but `det_thresh` and `nms_thresh` are likely library defaults (~0.5 confidence).
- **Action**: Check face detection code. If using defaults, document as "InsightFace defaults" and note the actual values.
- **Cross-reference**: `docs/ml/MODEL_INVENTORY.md` for model details.

### Known Unknown: Cluster Size Limits
- **Status**: No discussion or implementation of maximum cluster size or splitting logic.
- **Action**: Not urgent. May become relevant when identities accumulate 50+ faces. Revisit if clustering produces suspiciously large groups.

---

## Adding New Decisions

When making any algorithmic choice in the ML pipeline:
1. Add a new entry here with the AD-XXX format
2. Include the rejected alternative and WHY it was rejected
3. List all files/functions affected
4. If the decision came from a user correction, note that explicitly
