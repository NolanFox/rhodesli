# PRD: Face Comparison Tool

**Author:** Nolan Fox
**Date:** 2026-02-15
**Status:** Implemented
**Session:** 31 (initial), 32 (intelligence upgrade)

---

## Problem Statement

Users want to identify unknown faces in the archive. Currently they must manually browse 775+ identities or rely on admin-run ML clustering. A comparison tool lets them select a face from the archive and instantly see the most similar faces ranked by confidence, or upload a new photo to search across the entire archive.

## Research Summary

- **FamilySearch Compare-a-Face**: Upload photo, get percentage match scores. Simple single-upload flow.
- **MyHeritage Photo Tagger**: Auto-groups faces across photos, batch tagging with face crop + full photo context.
- **Civil War Photo Sleuth** (IUI 2019 Best Paper): Crowdsourced metadata + face recognition. Visual clues (clothing, insignia) narrow search space before face matching. 85%+ accuracy with community voting.

Key UX patterns across all three:
1. Side-by-side face crops with full photo context
2. Similarity scores as a starting point, not definitive proof
3. Batch confirm/reject workflows for efficiency
4. Contextual metadata (date, location, collection) supplements face matching

## Who This Is For

- **Family members** (primary): "Is my relative in the archive?" Upload a photo or select a face to find matches.
- **Admin**: Quickly find all potential matches for an unidentified face.
- **Contributors**: Help identify unknown people by comparing faces.

## User Flows

### Flow A: "Who is this person?" (from archive)
1. User is viewing a photo with an unidentified face
2. Clicks "Find Similar Faces" on that face (already exists)
3. System shows top matches from the archive with confidence tiers
4. User can confirm a match to link the face to that identity

### Flow B: "Is my relative in the archive?" (upload)
1. User navigates to /compare (new top-level route)
2. Uploads a photo of their relative (drag & drop or file picker)
3. If InsightFace available (local dev): faces detected, embeddings computed, matches shown
4. If InsightFace unavailable (production): graceful message "Face comparison from uploads is available in the local development environment. Browse the archive to find similar faces."
5. Results grid: face crops with similarity scores, person name if identified, source photo

### Flow C: "Browse from archive" (select existing face)
1. User navigates to /compare
2. Uses search/browse to select an existing face from the archive
3. System uses that face's embedding to find top matches
4. Results displayed with confidence tiers and photo context

## Acceptance Criteria

```
TEST 1: Compare page loads
  GET /compare returns 200
  Page contains upload area OR face selector

TEST 2: Compare page has navigation
  /compare has Photos, People, Timeline, Compare links
  Navigation is consistent with other pages

TEST 3: Select existing face shows matches
  GET /api/compare?face_id=<known_face_id> returns results
  Results contain similarity scores and identity info

TEST 4: Results are sorted by similarity
  Top result has highest similarity (lowest distance)

TEST 5: Results link to source photos
  Each result card links to /photo/<photo_id>

TEST 6: Compare link in top navigation
  All main pages include "Compare" in nav links

TEST 7: Upload area exists on compare page
  Page contains file upload form element

TEST 8: Graceful degradation without InsightFace
  When InsightFace unavailable, upload shows helpful message
  Archive face comparison still works (uses precomputed embeddings)
```

## Data Model Changes

No changes to existing data files. The comparison tool reads from:
- `data/embeddings.npy` (precomputed face embeddings)
- `data/identities.json` (identity names, face assignments)
- `data/photo_index.json` (face-to-photo mapping)

## Technical Approach

### Core Engine
- Reuse `find_nearest_neighbors()` from `core/neighbors.py` for identity-level comparison
- Add new `find_similar_faces()` function that works at the face level (not identity level) for raw embedding comparison
- For uploads: use InsightFace `buffalo_l` model (same as ingest pipeline) — only available locally

### API Endpoint
- `GET /api/compare?face_id=<face_id>&limit=20` — compare an existing face against all others
- `POST /api/compare/upload` — upload a photo, detect faces, compare (local dev only)
- Returns JSON or HTML partial depending on Accept header

### Performance
- 775 identities x 512-dim embeddings = trivial computation (<10ms in numpy)
- No external API needed — all local computation using precomputed embeddings
- For uploaded photos: InsightFace extraction takes ~1-2 seconds (local only)

## Technical Constraints

- InsightFace NOT available on production (Railway) — upload comparison is local-dev only
- Archive face comparison (precomputed embeddings) works everywhere
- Pure server-side rendering (FastHTML + HTMX), no JS frameworks
- Must use event delegation pattern for all JS handlers

## Out of Scope

- Real-time face detection on production server (needs GPU/more RAM)
- Cross-archive comparison (multi-tenant)
- Video frame extraction
- Age progression/regression

## Priority Order

1. /compare route with face selector (browse archive faces)
2. API endpoint for face-level similarity search
3. Results grid with confidence tiers and photo context
4. Navigation integration (top nav link on all pages)
5. Upload area with graceful degradation
6. Integration with existing "Find Similar" buttons
