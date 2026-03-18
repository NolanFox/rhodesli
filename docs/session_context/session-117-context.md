# Session 117 Context — Wire Upload Pipeline to ML Service (TOOLS-002 Phase 3)

**Predecessor:** [Session 116 Context](session-116-context.md) (ML Service Deployment)
**Assessment:** [Session 116 Assessment](../assessments/session-116-assessment.md)
**Architecture:** [ML_SERVICE.md](../architecture/ML_SERVICE.md)

## Problem Statement

The ML service is deployed and running on Railway (Session 116). The ML client is complete and tested. But the upload pipeline still calls local InsightFace directly via `extract_faces()` in `core/ingest_inbox.py`. This session wires the pipeline to use the ML service with automatic fallback to local detection.

## Integration Point

The call chain is:
```
upload_routes.py → _background_ingest() → process_directory() → process_single_image() → extract_faces()
```

**Exact insertion point:** `core/ingest_inbox.py` line 698 in `process_single_image()`:
```python
result = extract_faces(filepath, prefer_hybrid=prefer_hybrid)
```

Replace with ML service call + fallback:
```python
result = detect_faces(filepath, prefer_hybrid=prefer_hybrid)  # tries ML service first
```

## Data Shape Contract

`extract_faces()` returns a tuple: `(faces_list, image_width, image_height)`

Each face in `faces_list`:
```python
{
    "mu": ndarray(512,),         # Normalized 512-dim embedding
    "sigma_sq": float,           # Uncertainty
    "det_score": float,          # [0-1] detection confidence
    "bbox": [x1, y1, x2, y2],   # Pixel coordinates
    "filename": str,
    "filepath": str,
    "quality": float,            # L2 norm of raw embedding
}
```

The ML service returns:
```json
{
    "faces": [{"bbox": [...], "det_score": 0.95, "quality": 0.82, "embedding": [...]}],
    "image_size": [width, height],
    "processing_time_ms": 1234
}
```

**Transformation needed:** Convert ML service response to the PFE format expected by downstream pipeline.

## Scope

### In Scope
1. Add `detect_faces()` wrapper in `core/ingest_inbox.py` that tries ML service then falls back
2. Transform ML service response to match `extract_faces()` output format
3. Log detection source via `core/ml_run_logger.py`
4. Tests for ML service path, fallback path, and format conversion
5. Deploy and verify

### Out of Scope
- Modifying the ML service itself (already working)
- Removing local InsightFace from web Dockerfile (future optimization)
- Clustering automation (TOOLS-002 Phase 4)

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Format mismatch breaks downstream | Test that converted format matches extract_faces() output |
| ML service timeout on large images | 60s timeout in client, fallback to local on any error |
| Embedding values differ between local and service | Both use same buffalo_l model + PFE — values should be identical |
| Modifying ingest_inbox.py breaks existing pipeline | Add wrapper function, don't modify extract_faces() itself |

## Breadcrumbs
- TOOLS-002: ROADMAP.md (Phase 1-2 done, Phase 3 this session)
- AD-110: Serving path contract
- AD-228: ML run provenance
- PRD-046: ML run tracking
- Session 115: ML service skeleton
- Session 116: ML service deployed, client complete
