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
- **Scalar sigma fix**: When sigma_sq is uniform across dimensions, MLS uses a single-term formula to avoid the log penalty from drowning the discriminative signal. See `docs/adr_006_scalar_sigma_fix.md`.
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
- **Temporal priors**: Era-based penalties adjust MLS scores based on photo metadata. See `docs/adr_003_identity_clustering.md`.
- **Affects**: `core/clustering.py`, `core/temporal.py`.

### AD-006: Provenance Hierarchy — Human Overrides Model
- **Date**: 2026-02-06
- **Context**: When a human confirms or rejects a face match, how does this interact with ML-proposed matches?
- **Decision**: `provenance="human"` always overrides `provenance="model"`. Human decisions are final and cannot be reversed by re-running the ML pipeline.
- **Affects**: Identity state machine (INBOX → PROPOSED → CONFIRMED), merge/detach operations in `app/main.py`.

## Adding New Decisions

When making any algorithmic choice in the ML pipeline:
1. Add a new entry here with the AD-XXX format
2. Include the rejected alternative and WHY it was rejected
3. List all files/functions affected
4. If the decision came from a user correction, note that explicitly
