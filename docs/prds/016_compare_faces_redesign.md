# PRD-016: Compare Faces Redesign

**Status:** IN PROGRESS
**Priority:** HIGH
**Session:** 44
**Date:** 2026-02-17

## Problem Statement

The Compare Faces page (/compare) buries the upload action below 46 face thumbnails,
lacks clear CTAs after matches, uses misleading match labels ("very likely" at 57%),
doesn't save uploaded photos, and has no sharing for comparison results.

User research (docs/research/compare_faces_competitive.md) shows every competitor
puts upload above the fold. Rhodesli's unique differentiator — searching an existing
archive — is lost because users don't discover the upload feature.

## Use Cases

**UC-1: "I have a photo, who is this?"**
Upload one photo, search the archive for matches. Primary use case.

**UC-2: "Are these two people the same person?"**
Upload two photos (or one upload + one archive person), get similarity score.

**UC-3: "Person X looks like Person Y in the archive"**
Select two people from the archive, compare their faces.

## Redesigned Layout

### Above the Fold: Upload Section
- Two drag-and-drop zones side by side
- Smart behavior: one photo → "Search Archive"; two photos → "Compare"
- Clear labels: "Drop a photo here or click to upload"
- Privacy note: "Photos are saved to help grow the archive"

### Below Upload: Archive Search (Collapsible)
- "Or search by person" expander
- Compact person selector (search + thumbnails)
- Replaces overwhelming 46-face grid

### Results Section
- Clear similarity percentage with calibrated labels
- Tiered confidence based on AD-067 calibration:
  - 85%+ → "Very likely same person" (green)
  - 70-84% → "Strong match" (blue)
  - 50-69% → "Possible match" (yellow)
  - Below 50% → "Unlikely match" (gray)
- Action CTAs: Share Result, Name This Person, Try Another Photo
- Archive matches with context (collection, date, person name)

### Shareable Results
- /compare/result/{result_id} permalink for each comparison
- OG tags with face image for social sharing
- Response form: "Do you know either person?" (no login required)

## Acceptance Criteria

1. Upload section is above the fold on desktop and mobile
2. Face grid is collapsed by default, expandable
3. Match labels use calibrated thresholds (not "very likely" at 57%)
4. Share button on comparison results produces a working permalink
5. Uploaded photos are auto-saved for archive growth
6. All existing compare tests continue to pass
7. OG tags render correctly (absolute URLs)

## Out of Scope

- Feature-level similarity breakdown (eyes, nose, jawline)
- Two-photo side-by-side comparison mode (UC-2 deferred to future)
- Real-time face detection on upload in production (needs InsightFace on server)

## Data Model Changes

### data/comparison_results.json (NEW)
```json
{
  "results": {
    "<result_id>": {
      "result_id": "abc123def456",
      "created_at": "2026-02-17T...",
      "query_type": "upload|archive",
      "query_face_id": "...",
      "upload_id": "...",
      "matches": [
        {
          "face_id": "...",
          "identity_id": "...",
          "identity_name": "...",
          "distance": 0.85,
          "confidence_pct": 72,
          "tier": "STRONG MATCH"
        }
      ],
      "responses": []
    }
  }
}
```

## Priority Order

1. Upload-first layout (above the fold)
2. Calibrated match labels
3. Share button on results
4. Shareable result permalinks
5. Auto-save uploads
6. Response form on result pages
