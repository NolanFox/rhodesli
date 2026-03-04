# Session 87 Log — Compare & Discoveries UX Overhaul
## Mission: Unify scoring, improve Compare/Discoveries/Identity cards UX
## Started: 2026-03-04
## Version: v0.90.0 → v0.91.0
## Predecessor: Session 86b (v0.90.0)

### Act 1: Orient & Setup
- [x] Session artifacts created
- [x] Lesson 100 added

### Act 2: Unify Confidence Scoring (AD-200)
- [x] core/confidence.py with unified compute_face_confidence()
- [x] Wired into neighbors.py, compare_routes.py, main.py
- [x] 35 new tests

### Act 3: Compare Best Matches Summary
- [x] _compare_summary_section() — top matches across all faces
- [x] 8 new tests

### Act 4: Shareable Result Page Overhaul
- [x] 200px hero, "Could this be [Name]?" framing, OG tags
- [x] 5 new tests

### Act 5: Discoveries Improvements
- [x] Sort by confidence, filter by tier + photo, inline Compare link
- [x] 15 new tests

### Act 6: Identity Card Fixes
- [x] "Faces (N)" button, visible detach for admin

### Act 7: Verification & Close
- [x] make test-fast: 1412 pass
- [x] Distance 1.13 → 43% everywhere
- [x] Browser verified: Discoveries, Compare, People cards
- [x] Assessment written

### Red Flags
- Chrome extension unavailable — used Playwright for verification
- 1 pre-existing xdist test ordering flake
