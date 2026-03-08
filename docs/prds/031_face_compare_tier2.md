# PRD-031: Face Compare Tier 2 — Shared Comparison Engine

**Author:** Session 92
**Date:** 2026-03-07
**Status:** Draft
**Session:** 92 (PRD + stub only)
**Predecessor:** PRD-026 (Universal Comparison Workspace)

---

## Problem Statement

The current face comparison system (Tier 1) only works with pre-computed archive
embeddings stored in `embeddings.npy`. This means:

1. **No real-time inference** — uploaded photos must go through the full ingest
   pipeline (InsightFace detection + embedding) before comparison is possible.
2. **Coupled to archive** — the comparison engine cannot be used outside the
   Rhodesli archive context (e.g., as a standalone tool or API).
3. **No GPU on Railway** — Railway hobby plan runs CPU only, making real-time
   InsightFace inference slow (~3-5s per photo).

Users who upload a photo for comparison currently wait for a background
processing pipeline. A shared comparison engine would enable instant results.

## Who This Is For

| Role | Need |
|------|------|
| **Community member** | Upload a photo and get instant similarity results |
| **Admin** | Compare any two faces without pre-ingestion |
| **External API consumer** | Use face comparison as a standalone service |
| **Future products** | Standalone face comparison tool (PRODUCT-005) |

## Architecture

### Current (Tier 1)
```
Upload → Background ingest → embeddings.npy → Neighbor lookup → Results
         (10-30s delay)       (pre-computed)   (NumPy cosine)
```

### Proposed (Tier 2)
```
Upload → Real-time embed → Compare against archive → Results
         (ONNX or GPU)     (pgvector or NumPy)       (instant)
```

### Key Components

1. **Shared Embedding Service** — Extracts face embeddings on demand.
   Options: ONNX Runtime (CPU, ~1-2s), or GPU service (Railway Pro / separate).
2. **Comparison Engine** — Accepts two sets of embeddings, returns similarity.
   Reuses existing `neighbors.py` distance math (FROZEN, read-only).
3. **API Layer** — RESTful endpoints for embed + compare operations.

## User Flows

### Flow 1: Upload-to-Archive Comparison (Enhanced)
1. User navigates to `/compare/v2`
2. User uploads a photo (drag-and-drop or file picker)
3. System extracts faces in real-time via ONNX (~1-2s)
4. System compares each face against all archive embeddings
5. Results displayed with confidence scores, calibrated per AD-149

### Flow 2: Two-Photo Comparison
1. User uploads two photos
2. System extracts faces from both
3. System compares all face pairs across photos
4. Results displayed as a similarity matrix

### Flow 3: API Comparison
1. Client POSTs two images to `/api/v2/compare`
2. Response: JSON with face bounding boxes, embeddings, similarity scores

## Acceptance Criteria

```
TEST 1: Stub endpoint returns not_implemented
  - GET /api/v2/compare/status
  - Assert: 501 status with JSON {"status": "not_implemented", "version": "v2"}

TEST 2: Real-time embedding (future)
  - POST image to /api/v2/compare/embed
  - Assert: Returns 512-dim embedding vector within 3s

TEST 3: Archive comparison (future)
  - POST image to /api/v2/compare
  - Assert: Returns ranked list of similar archive faces
```

## Technical Constraints

- **Railway CPU only** — ONNX Runtime is the viable path for CPU inference.
  InsightFace buffalo_l model can be exported to ONNX (~200MB).
- **AD-110 Serving Path Contract** — Web requests NEVER run heavy ML.
  Tier 2 requires either: (a) ONNX export for lightweight CPU inference,
  or (b) separate ML service (see ML_SERVICE.md).
- **neighbors.py is FROZEN** — Distance computation logic cannot change.
  Tier 2 must use the same distance math.
- **Calibration** — All scores must go through isotonic calibration (AD-149).

## Blocker Analysis

| Blocker | Severity | Resolution Path |
|---------|----------|-----------------|
| No GPU on Railway | HIGH | ONNX export or separate GPU service |
| InsightFace ONNX export | MEDIUM | buffalo_l supports ONNX; needs validation |
| Cold start latency | LOW | Model warm-up on service start |

## Data Model Changes

No changes to existing data model. New endpoints are stateless — they accept
images and return results without persisting anything.

Future: comparison results could be cached in a `compare_results` Supabase
table for sharing and analytics.

## Out of Scope

- Modifying existing Tier 1 comparison flow
- GPU infrastructure provisioning
- Production deployment of real-time inference
- Changes to `neighbors.py` (FROZEN)
- Billing or rate limiting for API

## Priority Order

1. PRD document (this session)
2. API stub with not_implemented response (this session)
3. ONNX model export + validation (future session)
4. Real-time embedding endpoint (future session)
5. Full Tier 2 integration (future session)

## Implementation Plan

### Phase 1: Foundation (This Session)
- PRD document
- Stub route file `app/compare_v2_routes.py`
- Tests for stub

### Phase 2: ONNX Export
- Export InsightFace buffalo_l to ONNX
- Validate embedding consistency (cosine similarity > 0.999 vs PyTorch)
- Benchmark CPU inference time

### Phase 3: Real-Time Endpoint
- Wire ONNX model into compare_v2_routes
- Add face detection + embedding extraction
- Calibrated scoring via existing pipeline

### Phase 4: Integration
- Replace background processing with real-time for compare flows
- Archive search with pgvector (if migrated) or NumPy fallback

## References

- AD-110: Serving Path Contract
- AD-117: Face Compare Tier 2 architecture
- AD-149: Similarity calibration
- PRD-026: Universal Comparison Workspace
- `docs/architecture/ML_SERVICE.md`: ML service extraction plan
