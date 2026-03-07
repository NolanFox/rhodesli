# PRD-021: Multi-Photo Compare Upload

**Status**: SHIPPED (Sessions 61, 85c) — Multi-photo compare + universal workspace live (AD-141, PRD-026)
**Author**: Nolan Fox + Claude Code
**Priority**: P1

## Problem

Face Compare currently accepts only one photo at a time. Users comparing family
photos need to upload multiple photos to cross-match faces. This requires
multiple round trips through the entire upload flow.

## Solution

Extend the upload area to accept 2-5 photos simultaneously. Process each photo
for face detection, compare faces between uploaded photos (cross-match), and
compare all faces against the archive.

## User Flow

1. User visits /compare or /facecompare
2. Drags or selects 1-5 photos (existing single-photo flow still works)
3. Each photo shows face count after detection
4. Results page shows:
   - Per-photo: archive matches ranked by similarity
   - Cross-matches: faces matched between uploaded photos
5. All photos saved for pipeline processing

## Technical Approach

- Extend existing `/api/compare/upload` to accept multiple files via `photos[]`
- Client-side: `multiple` attribute on file input + thumbnail preview
- Cross-comparison: compare embeddings from all uploaded faces pairwise
- Each photo saved independently to R2 with shared `batch_id`

## Success Criteria

1. User can upload 2-5 photos via file picker (multiple select)
2. Each photo shows face count after upload
3. Archive matches shown for each photo
4. Cross-matches between photos shown
5. All photos persisted for pipeline processing
6. Progress via SSE during processing

## Out of Scope

- Drag-and-drop reordering
- Photo editing/cropping before upload
- Async background processing (all synchronous for now)
