# PRD-053: Face Compare Real-Time

**Status:** Planning
**Author:** Session 121
**Date:** 2026-03-19
**References:** PRD-034 (tool suite master plan), PRD-031 (Tier 2 architecture), AD-110 (serving path contract), AD-117 (tier architecture), AD-229 (ML service graduation)
**Depends on:** TOOLS-002 Phase 4 (ML service deployed and verified)

---

## Problem

The Compare tool (`/tools/compare`) only works with pre-computed embeddings from the archive. Users cannot upload a new photo and get instant face comparison results against the archive. The standalone `/facecompare` page exists but is limited to archive-vs-archive comparison. Real-time upload-and-compare was previously blocked on ONNX export (PRD-031), but the ML service (TOOLS-002, Session 116-119) now provides a simpler path: the existing `/api/v1/detect-and-embed` endpoint already returns 512-dim PFE embeddings suitable for comparison.

## Solution

Extend the web app to proxy uploaded photos to the ML service for embedding extraction, then compare each detected face against the archive's cached embeddings using the existing isotonic-calibrated similarity pipeline.

**Key insight:** No new ML service endpoint is needed. The existing `/api/v1/detect-and-embed` already returns everything required (bounding boxes, detection scores, quality metrics, 512-dim embeddings, and landmarks). The work is entirely on the web app side.

## User Flow

1. User navigates to `/tools/compare`
2. Uploads a photo (drag-and-drop or file picker)
3. Web app sends photo to ML service via `/api/v1/detect-and-embed`
4. ML service returns face bounding boxes + 512-dim embeddings
5. Web app compares each embedding against archive embeddings (L2 distance + isotonic calibration)
6. Shows top 10 matches per face with calibrated confidence scores, within 5 seconds
7. Each match links to the person detail page in the archive

## Technical Design

### Web App Changes

**New endpoint:** `POST /api/compare/upload`
- Accepts multipart image upload
- Proxies to ML service `POST /api/v1/detect-and-embed` (via `rhodesli_ml/ml_client.py`)
- For each returned face embedding:
  - Computes L2 distance against all archive embeddings (using `core/neighbors.py:find_nearest_neighbors_fast()`)
  - Applies isotonic calibration (AD-149) for confidence scores
  - Returns top 10 matches with: identity name, crop URL, calibrated score, photo source
- Returns HTMX partial with results grid

**Frontend changes:**
- Add upload dropzone to `/tools/compare` page (reuse existing upload UI patterns from `/tools/estimate`)
- HTMX form posts to `/api/compare/upload`, swaps results into target div
- Loading skeleton during ML service processing
- Per-face results tabs when multiple faces detected

### ML Service

No changes needed. The existing endpoint returns all required data:
```json
{
  "faces": [
    {
      "bbox": [x1, y1, x2, y2],
      "det_score": 0.95,
      "quality": 18.2,
      "embedding": [512 floats]
    }
  ],
  "image_size": {"width": 1024, "height": 768},
  "processing_time_ms": 450.0
}
```

### Fallback Behavior

If `ML_SERVICE_URL` is not set or the ML service is unreachable:
- Show a graceful error: "Real-time comparison requires the ML service. Contact admin."
- Do not fall back to local InsightFace (AD-110: no heavy ML on web requests)

### Performance Target

| Step | Target | Current Capability |
|------|--------|--------------------|
| Upload + transfer | <500ms | Standard web upload |
| ML service detect+embed | <2s | Measured ~450ms per photo (Session 119) |
| Archive comparison | <500ms | `find_nearest_neighbors_fast()` ~142ms for 2957 embeddings |
| Calibration + rendering | <200ms | Isotonic transform is O(1) per score |
| **Total** | **<5s** | **Achievable** |

## Acceptance Criteria

- [ ] Upload a photo with 1 face, see top 10 archive matches within 5 seconds
- [ ] Upload a photo with 5+ faces, see matches per face in tabbed view
- [ ] Calibrated confidence scores displayed (not raw L2 distances)
- [ ] Each match links to the person detail page
- [ ] No database writes during comparison (read-only operation)
- [ ] Graceful error when ML service is unavailable
- [ ] Works on mobile (responsive upload + results)
- [ ] Admin-only initially (behind `_check_admin`), public after validation

## Out of Scope

- ONNX export (ML service makes this unnecessary)
- Batch comparison of multiple photos in one request
- Saving comparison results to database
- Shareable result URLs (future enhancement)
- Cross-community comparison (uses active community's embeddings only)

## Dependencies

- TOOLS-002 Phase 4 (ML service deployed): COMPLETE (Session 118)
- AD-110 (no heavy ML on web requests): ML service handles all detection
- `rhodesli_ml/ml_client.py`: HTTP client already exists for ML service calls
- `core/neighbors.py`: `find_nearest_neighbors_fast()` already exists
- Isotonic calibration model: already loaded at startup

## Effort Estimate

| Phase | Effort | Details |
|-------|--------|---------|
| Web app endpoint + proxy | 0.5 session | Wire ml_client to compare pipeline |
| Frontend upload UI | 0.5 session | HTMX upload form + results grid |
| Tests | Included | Unit + integration tests per phase |
| Browser verification | Included | Production deploy + Chrome verification |
| **Total** | **1 session** | Single session is feasible given existing infrastructure |

## Migration from Standalone `/facecompare`

Once real-time compare is live on `/tools/compare`:
1. `/facecompare` already 301-redirects to `/tools/compare` (ROUTE-001, shipped)
2. Remove `app/match_facecompare_routes.py` (1700 lines of duplicated code)
3. Update `app/compare_v2_routes.py` stub to return real results instead of 501

## References

- PRD-034: `docs/prds/034_standalone_tool_suite.md` (master tool suite plan, Phase 3)
- PRD-031: `docs/prds/031_face_compare_tier2.md` (original ONNX-based Tier 2 plan, superseded)
- ML service: `ml_service/detect.py` (existing detect-and-embed endpoint)
- ML client: `rhodesli_ml/ml_client.py` (HTTP client for ML service)
- Compare routes: `app/compare_routes.py` (existing compare UI)
- Neighbors: `core/neighbors.py` (fast embedding comparison)
- AD-110: Serving path contract (no heavy ML on web requests)
- AD-117: Face Compare tier architecture
- AD-149: Isotonic similarity calibration
