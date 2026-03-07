# PRD-026: Universal Comparison Workspace

**Author:** Session 85c
**Date:** 2026-03-03
**Status:** SHIPPED (Session 85c, v0.88.0) — Two-slot design, all entity combos, multi-target, unified search, CSS animations
**Predecessor:** PRD-025 (Compare Functional Rebuild)

## Problem Statement

The comparison feature is fragmented across 3 separate pages (`/compare`, `/compare/pair`, `/facecompare`), only supports ~4/9 possible entity combinations, and the design is sparse and unfocused. Users expect to compare ANY entity against ANY other entity(ies) with fluid, polished UX.

### User Feedback (Nolan, 2026-03-03)
> "I explicitly said we need to be able to compare any given individual, existing picture, or newly uploaded picture with any other."
> "Currently it is NOT well designed."
> "This should be easier to use, more elegant, better designed and faster with more fluid animation."

## Entity Types

Three entity types flow through one comparison system:

| Type | Description | Identification |
|------|-------------|----------------|
| **Person** | Any identity (CONFIRMED, PROPOSED, INBOX) | identity_id |
| **Photo** | Any archive photo | photo_id |
| **Upload** | A newly uploaded photo (processed in real-time) | job_id |

## Entity Combination Matrix

| Source ↓ / Target → | Person | Photo | Upload | Archive (all) |
|---------------------|--------|-------|--------|---------------|
| **Person** | YES | YES | YES | YES |
| **Photo** | YES | YES | YES | YES |
| **Upload** | YES | YES | YES | YES |

All 12 combinations (3 source × 4 target types) must be supported.

## Workspace Model

```
┌─────────────── Source ──────────────┐ ┌──── Compare With ────┐
│ [Upload] [Person] [Photo]           │ │ Search people/photos  │
│                                     │ │                       │
│  Selected entity preview            │ │  [Target 1] [×]       │
│  + detected face thumbnails         │ │  [Target 2] [×]       │
│                                     │ │  [+ Add another]      │
│                                     │ │  [All Archive]        │
└─────────────────────────────────────┘ └───────────────────────┘

┌─────────────── Results ──────────────────────────────────────┐
│ Comparing N faces against M targets                          │
│ View: [Faces] [Photos]   Hide: [F3] [F4]                    │
│                                                              │
│ Face 1 ───────────────────────────────────────               │
│   vs Target A    85% ████████████████░  Strong match         │
│   vs Target B    42% ████████░░░░░░░░   Unlikely             │
│                                                              │
│ Face 2 ───────────────────────────────────────               │
│   vs Target A    22% ████░░░░░░░░░░░░   Unlikely             │
│   vs Target B    68% ██████████████░░   Possible match       │
└──────────────────────────────────────────────────────────────┘
```

## Acceptance Criteria

### Source Slot
1. Three tabs: Upload (default), Person, Photo
2. Upload: drag-drop zone, progress bar, face thumbnail display on completion
3. Person: search all identities (CONFIRMED, PROPOSED, INBOX) with state badges
4. Photo: search/browse with collection filter, photo gallery grid

### Target Slot
5. Unified search (people + photos) with type badges
6. Multi-select up to 5 targets as pills with remove button
7. "All Archive" option (top N matches per face)
8. "Find Similar" auto-populates targets from visual similarity search
9. Adding/removing targets triggers comparison instantly (no "Go" button)

### Results Area
10. Matrix layout: one section per source face × all targets
11. Confidence bars with calibrated scores and tier labels
12. Face/Photo toggle: crops vs full photos with bounding box overlays
13. Hide/collapse individual face sections with smooth animation
14. Best match highlight (gold border)
15. Context per match: target's best existing match %, rank among matches
16. Cross-target insights when face matches multiple targets strongly
17. Admin actions: Merge / Not Same buttons for person targets
18. Share comparison button + shareable result URL

### Backward Compatibility
19. `/compare/result/{id}` shareable links continue working
20. `/compare?photo_id=X&person_id=Y` auto-populates workspace
21. `/compare?face_id=X` pre-selects person as source
22. `/compare/pair` redirects to `/compare`

### Responsive
23. Desktop (>1024px): side-by-side slots
24. Tablet (768-1024px): stacked slots
25. Mobile (<768px): single column, no photo view

## Out of Scope
- `/facecompare` changes (different audience, standalone tool)
- GPU inference on Railway (AD-007, AD-110)
- ML model changes (use existing InsightFace + SimilarityCalibrator)
- Feature-level similarity breakdown (eyes, nose, jawline)
- Visual clue tagging (Civil War Photo Sleuth pattern)
- URL state/bookmarkable comparison setups

## Technical Constraints
- HTMX-first (no React/heavy JS frameworks)
- CSS transitions for animations (no JS animation libraries)
- AD-110: web requests never run heavy ML synchronously
- Lesson 88: all UI changes in app/main.py (monolith)
- Existing dark theme palette
