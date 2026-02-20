# Session 54B Log

**Started:** 2026-02-20
**Prompt:** docs/session_context/session_54b_prompt.md
**Context:** docs/session_context/rhodesli-session-54b-context.md

## Phase Checklist
- [x] Phase 0: Setup
- [x] Phase 1: Hybrid Detection Fix (AD-114)
- [x] Phase 2: Real Upload Testing
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

## Phase 2 Results — Real Upload Testing

### Upload Test Results (Local, hybrid detection)

| Test | Photo | Size | HTTP | Time | Faces | Matches | Upload Visible | Issues |
|------|-------|------|------|------|-------|---------|---------------|--------|
| Compare 2-face | Image 006 | 1.2M | 200 | 1.34s | 2 | 16 | Yes | None |
| Compare 14-face | 596770938 | 828K | 200 | 0.82s | 12 | Yes | Yes | None |
| Compare 3-face | lucia_cap | 8K | 200 | 0.33s | 3 | Yes | Yes | None |
| Estimate 2-face | Image 006 | 1.2M | 200 | 0.36s | 2 | N/A | N/A | None |

### Observations
- All uploads return HTTP 200 with correct face detection
- Hybrid detection active (startup logs confirm det_500m + w600k_r50)
- 14-face photo detected 12 faces (vs 14 in index) — expected det_500m recall tradeoff
- Response times excellent on local Mac (0.3-1.3s)
- Upload preview image present in compare results
- Multi-face selector present when >1 face detected
- No errors or crashes

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed
