# Session 54B Log

**Started:** 2026-02-20
**Prompt:** docs/session_context/session_54b_prompt.md
**Context:** docs/session_context/rhodesli-session-54b-context.md

## Phase Checklist
- [x] Phase 0: Setup
- [x] Phase 1: Hybrid Detection Fix (AD-114)
- [ ] Phase 2: Real Upload Testing
- [ ] Phase 3: Production Testing Infrastructure
- [ ] Phase 4: UX Issue Tracker Verification
- [ ] Phase 5: Harness Updates
- [ ] Phase 6: Verification Gate

## Phase 0 Results
- Session context files saved
- InsightFace available in venv (v0.7.3)
- buffalo_l models present locally
- No test photos in ~/Downloads — using raw_photos/ for testing
- 2481 tests passing

## Phase 1 Results — Hybrid Detection (AD-114: ACCEPTED)

### Empirical Test Results

| Config | Faces (40-face) | Faces (21-face) | Time (40-face) | Embedding Compat |
|--------|----------------|----------------|----------------|-----------------|
| buffalo_l full | 40 | 21 | 4.661s | baseline |
| buffalo_sc full | 38 | 19 | 0.042s | 0.0 (incompatible) |
| Hybrid (det_500m + w600k_r50) | 38 | 19 | 2.546s | 0.98 mean cosine |

Multi-photo validation (3 photos, 8 face pairs at 640px):
- Mean cosine similarity: 0.982
- Min: 0.972, Max: 0.993

### Detection Recall Tradeoff
- det_500m misses ~2 faces on large group photos (marginal, small faces)
- Acceptable for interactive compare (speed > marginal detection)
- Batch ingestion continues using buffalo_l for maximum recall

### Implementation
- `core/ingest_inbox.py`: Added `get_hybrid_models()` and `extract_faces_hybrid()`
- `app/main.py`: Compare and estimate upload endpoints use `extract_faces_hybrid()`
- Startup preloads hybrid models alongside buffalo_l
- Fallback: if buffalo_sc models unavailable, uses full buffalo_l
- 5 new tests (2486 total)

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed
