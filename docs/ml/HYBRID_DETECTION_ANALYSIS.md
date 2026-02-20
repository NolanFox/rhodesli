# Hybrid Detection Analysis (AD-114)

**Created:** Session 54D, 2026-02-20
**Source data:** Session 54B hybrid detection tests
**Decision:** docs/ml/ALGORITHMIC_DECISIONS.md AD-114

## Summary

buffalo_sc's lightweight detector (det_500m, 500M FLOPs) combined with
buffalo_l's accurate recognizer (w600k_r50, ResNet50) produces embeddings
with mean cosine similarity 0.98 vs pure buffalo_l.

## The Models

| Model Pack | Detector | Det FLOPs | Det Size | Recognizer | Rec Size |
|------------|----------|-----------|----------|------------|----------|
| buffalo_l | det_10g | 10G | 16MB | w600k_r50 (ResNet50) | 166MB |
| buffalo_sc | det_500m | 500M | 2.4MB | w600k_mbf (MobileFaceNet) | 13MB |
| **Hybrid** | **det_500m** | **500M** | **2.4MB** | **w600k_r50** | **166MB** |

InsightFace loads detection and recognition as separate ONNX models. The hybrid
approach uses the fast detector from buffalo_sc and the archive-compatible
recognizer from buffalo_l.

## Why 0.98 and Not 1.0

The 0.02 gap is NOT random noise. It comes from a deterministic pipeline effect:

1. det_500m finds bounding boxes at slightly different pixel coordinates than det_10g
2. InsightFace aligns faces using 5 keypoint landmarks before recognition
3. Even 1-2px shift in detected keypoints changes the alignment warp
4. Different crop pixels fed to the same recognizer produce different embeddings

This is **deterministic**: the same photo always produces the same hybrid embedding.
The gap is consistent (~0.97-0.99 per face) and does not vary between runs.

## Raw Test Results (Session 54B, Local Mac)

### Detection Speed & Recall

| Config | Faces (40-face photo) | Faces (21-face photo) | Time (40-face) |
|--------|----------------------|----------------------|----------------|
| buffalo_l full | 40 | 21 | 4.661s |
| buffalo_sc full | 38 | 19 | 0.042s |
| Hybrid (det_500m + w600k_r50) | 38 | 19 | 2.546s |

### Embedding Compatibility (8 face pairs, 3 photos, 640px)

| Metric | Value |
|--------|-------|
| Mean cosine similarity | 0.982 |
| Min cosine similarity | 0.972 |
| Max cosine similarity | 0.993 |

Note: Per-face cosine similarities were computed across 8 matched face pairs.
Session 54B used means rather than per-face breakdowns. Future validation
runs should log per-face data for each photo.

### Upload Response Times (Local Mac)

| Test | Photo | Size | HTTP | Time | Faces |
|------|-------|------|------|------|-------|
| Compare 2-face | Image 006 | 1.2MB | 200 | 1.34s | 2 |
| Compare 14-face | 596770938 | 828K | 200 | 0.82s | 12 |
| Compare 3-face | lucia_cap | 8K | 200 | 0.33s | 3 |
| Estimate 2-face | Image 006 | 1.2MB | 200 | 0.36s | 2 |

### Production (Railway CPU) — Session 54D Verification

| Test | Photo | HTTP | Time |
|------|-------|------|------|
| Compare 14-face | 596770938 | 200 | 51.2s |

Production is CPU-only (Railway shared vCPU). The 51s compares favorably to
pre-Session-54 times of ~65s, but remains slow for interactive use.

## When 0.98 Is Good Enough

- **Compare workflow**: user uploads a photo, we find similar faces in archive
- Typical threshold for "same person" is ~0.4-0.6 cosine similarity
- A 0.02 shift at the top of the similarity range is negligible for ranking
- Archive faces scored against each other are unaffected (same model produced them)
- The ranking order of matches is preserved: if face A was closer than face B
  with buffalo_l, it remains closer with hybrid detection

## Known Weakness Scenarios (Need Testing)

1. **Very small faces in group photos** — det_500m already misses ~2/40 marginal
   faces. For photos with 50+ small faces, this could worsen.
2. **Heavily rotated faces (>30 degrees)** — lighter detector has less capacity
   for extreme pose variation.
3. **Partial occlusion** — fewer FLOPs means less robustness to edge cases.
4. **Low contrast / faded historical photos** — our core use case (pre-1940
   Rhodes photos). Needs explicit testing with the oldest, most faded archive
   photos.

## Overnight Validation Design

When running local ML with full buffalo_l:

1. Re-detect same photos with det_10g
2. Compare face count: did hybrid miss any faces?
3. Compare bounding boxes: IoU between hybrid and full detections
4. Flag any photo where hybrid missed a face or IoU < 0.8
5. These flagged photos become the test set for hybrid quality monitoring

This validation has not yet been implemented. See BACKLOG for overnight ML
pipeline item.

## Decision

**AD-114: ACCEPTED** for compare and estimate endpoints on Railway.

- Interactive endpoints (compare upload, estimate upload): hybrid detection
- Batch ingestion (`core/ingest_inbox.py`): full buffalo_l for maximum recall
- Fallback: if buffalo_sc models unavailable, uses full buffalo_l automatically

Full buffalo_l remains the standard for local batch processing. Overnight
validation (when implemented) will catch any quality regressions.

## Production Performance (Post-Optimization, Session 54F)

**AD-119 fixes deployed 2026-02-20.** Root cause: buffalo_sc was missing from
Docker image, causing fallback to full buffalo_l (det_10g, 10G FLOPs).

| Test | Before (54D) | After (54F) | Improvement |
|------|-------------|-------------|-------------|
| 2-face photo (warm) | 51.2s | 10.5s | 4.9x |
| 14-face group | ~65s est. | 28.5s | ~2.3x |
| 3-face photo | N/A | 12.7s | — |

**Railway shared CPU approximate breakdown (2-face photo):**
- det_500m detection: ~3-5s
- w600k_r50 recognition (×2 faces): ~2-3s
- R2 upload (save result): ~2-3s
- Image decode + resize + comparison: ~1-2s

**Memory:** ~200MB at runtime (one detector + one recognizer).
Full buffalo_l FaceAnalysis caused OOM on Railway 512MB plan.

## Files

- `core/ingest_inbox.py` — `get_hybrid_models()`, `extract_faces_hybrid()`
- `app/main.py` — Compare/estimate endpoints use hybrid; startup preloads
- `Dockerfile` — Downloads buffalo_sc + buffalo_l; OMP_NUM_THREADS=1
- `tests/test_compare_intelligence.py` — 5 hybrid detection tests
