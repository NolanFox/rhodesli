# ML Model Inventory

## Current Models

| Component | Model | Details |
|-----------|-------|---------|
| Face Detection | InsightFace (RetinaFace/SCRFD) | Detects faces + bounding boxes in photos |
| Face Embedding | AdaFace PFE (512-dim) | Probabilistic Face Embeddings with mu + sigma |
| Clustering | Agglomerative (MLS + temporal) | Complete linkage with era-based priors |
| Similarity | Mutual Likelihood Score (MLS) | Probability-based, not cosine distance |

## Embedding Details

- **Dimensions**: 512
- **Type**: Probabilistic Face Embedding (PFE) — each face has mu (mean) and sigma_sq (variance)
- **Normalization**: L2-normalized mean vectors
- **Storage**: `data/embeddings.npy` (NumPy array of dicts, ~2.4 MB for ~550 faces)
- **Fields per entry**: `filename`, `bbox`, `face_id` (optional), `embeddings` (512-dim), `det_score`, `quality`
- **ID mapping**: Face IDs generated from filename + face index, or explicit `face_id` for inbox entries

## Key ADRs

Detailed algorithmic design records exist in `docs/`:
- `docs/adr_001_mls_math.md` — MLS mathematical derivation
- `docs/adr_003_identity_clustering.md` — Clustering algorithm design
- `docs/adr_006_scalar_sigma_fix.md` — Scalar sigma MLS fix

## Upgrade Path

Any model upgrade MUST:
1. Re-embed ALL existing faces (not just new ones)
2. Run golden set evaluation before AND after: `python scripts/evaluate_golden_set.py`
3. Compare precision/recall metrics
4. Get explicit approval before deploying
5. Add an entry to `docs/ml/ALGORITHMIC_DECISIONS.md`
