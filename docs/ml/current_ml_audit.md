# Current ML Audit

**Generated**: 2026-02-11 | **Scope**: Face detection, embeddings, similarity, signal inventory

---

## 1. Face Detection Model

**Model**: InsightFace `buffalo_l` (RetinaFace/SCRFD detector + recognition backbone)
**Source**: `core/ingest.py:90`, `core/ingest_inbox.py:228`
**Embedding dim**: 512-D L2-normalized vectors (`face.normed_embedding`)
**Detection size**: 640x640 (configurable) | **Provider**: CPUExecutionProvider

The ingestion pipeline extracts faces via InsightFace, then wraps each in a Probabilistic
Face Embedding (PFE) via `core/pfe.py:create_pfe()`, adding sigma_sq (uncertainty) derived
from detection confidence and face area. Despite docs referencing "AdaFace PFE", the actual
model is InsightFace `buffalo_l`. The PFE layer is custom, not a separate AdaFace model.

---

## 2. Embedding Storage

**File**: `data/embeddings.npy` (NumPy array of dicts, `allow_pickle=True`)
**Total entries**: 654 | **Schema**: 7-8 keys per entry

| Field | Type | Description |
|-------|------|-------------|
| `mu` | float32[512] | L2-normalized mean embedding (norm = 1.0000) |
| `sigma_sq` | float32[512] | Uncertainty vector (uniform scalar broadcast to 512-D) |
| `det_score` | float | Detection confidence [0, 1] |
| `bbox` | list[4] | Bounding box [x1, y1, x2, y2] in pixels |
| `filename` | string | Source photo filename |
| `filepath` | string | Relative path to source photo |
| `quality` | float | Raw embedding norm (pre-normalization) |
| `face_id` | string (optional) | Explicit ID for inbox entries (368 of 654 have this) |

All sigma_sq vectors are scalar-uniform. The MLS code has a `_is_scalar_sigma()` fast path.
286 legacy entries lack `face_id` (generated at load via `filename:faceN`).

---

## 3. Similarity and Matching

### Distance Metric (Runtime)

**`core/neighbors.py`**: **Euclidean distance** via `scipy.spatial.distance.cdist`.
Does NOT use MLS from `core/pfe.py` -- sigma_sq is ignored at runtime.

**`scripts/cluster_new_faces.py`**: Also **Euclidean** via `cdist`. Loads mu only.

**`core/grouping.py`**: **Euclidean** via `cdist`, threshold `GROUPING_THRESHOLD = 0.95`.

**Where MLS IS used**: `core/temporal.py` and `scripts/seed_registry.py` (initial seeding only).

### Matching Strategy

- **Single linkage** (AD-001): min distance between any face pair, no centroid averaging
- **Co-occurrence blocking**: Faces from same photo cannot match
- **Rejection memory** (AD-004): Rejected pairs skipped
- **Ambiguity detection** (ML-006): Flagged when margin < 15% between top two matches

### Calibrated Thresholds (AD-013)

From golden set evaluation (125 mappings, 23 identities, 4005 pairs):

| Label | Threshold | Precision | Recall | Use Case |
|-------|-----------|-----------|--------|----------|
| VERY HIGH | < 0.80 | ~100% | ~13% | Auto-suggest prominently |
| HIGH | < 1.05 | 100% | ~63% | Default clustering threshold |
| MODERATE | < 1.15 | ~94% | ~81% | "Likely match" label |
| MEDIUM | < 1.20 | ~87% | ~87% | Exploratory search |
| LOW | < 1.25 | ~69% | ~91% | "Possible match" |

---

## 4. Signal Counts

### Confirmed Identities

- **Active identities**: 266 (369 total, 103 merged) | **By state**: 44 CONFIRMED, 221 SKIPPED, 1 CONTESTED
- **Confirmed with >1 face**: 18 identities | **Total confirmed same-person pairs**: 947

| Identity | Faces | Pairs |
|----------|-------|-------|
| Big Leon Capeluto | 25 | 300 |
| Moise Capeluto | 18 | 153 |
| Victoria Cukran Capeluto | 17 | 136 |
| Victoria Capuano Capeluto | 15 | 105 |
| Vida Capeluto | 15 | 105 |
| Betty Capeluto | 12 | 66 |
| Selma Capeluto | 8 | 28 |
| Victor Capelluto | 8 | 28 |
| Laura Franco Capelluto | 5 | 10 |
| Leon Capeluto | 4 | 6 |

### Rejection Signal

- **Total rejection entries**: 58 (31 identities) | **Unique cross-identity rejection pairs**: 29

### Golden Set & Total Faces

- **Golden set**: 125 mappings, 23 identities, 4005 evaluation pairs
- **Embeddings file**: 654 entries | **Faces in active identities**: 450

---

## 5. Assessment: Calibration Training Feasibility

| Signal | Needed | Available | Status |
|--------|--------|-----------|--------|
| Confirmed same-person pairs | 50+ | 947 | SUFFICIENT |
| Cross-identity rejections | 20+ | 29 | SUFFICIENT (barely) |
| Distinct confirmed identities | 10+ | 18 (multi-face) | SUFFICIENT |
| Golden set size | 50+ mappings | 125 | SUFFICIENT |

**Verdict**: Signal is **sufficient for a basic calibration model** (e.g., logistic
regression on distance features).

### Key Risks

1. **Skewed pair distribution**: Top 5 identities produce 94% of pairs. Big Leon alone
   is 32%. Risk of overfitting to Capeluto family features.
2. **MLS unused at runtime**: sigma_sq infrastructure exists but `neighbors.py` and
   `cluster_new_faces.py` use raw Euclidean. Could improve low-quality face matching.
3. **Thin rejection signal**: 29 pairs meets minimum but more would strengthen boundaries.
4. **Single-family corpus**: All subjects share family resemblance, making the calibration
   harder than typical face verification (no easy negatives).

### Priority Improvements

1. **Increase rejection signal** to 50+ pairs by triaging ambiguous matches
2. **Diversify positive signal**: Confirm identities with 1-3 faces rather than adding
   more faces to already-large identities
3. **Evaluate MLS vs Euclidean** on the golden set to determine if sigma_sq helps
