# Session 85: Fix Compare — End-to-End Functional Validation

Started: 2026-03-03
Prompt: docs/prompts/session-85-prompt.md
PRD: docs/prds/025_compare_functional_rebuild.md
Context: docs/session_context/session-85-context.md

## Phase Checklist
- [x] Phase 0: Orient
- [ ] Phase 1: Diagnose + Architecture Plan
- [ ] Phase 2: Unify Compare Upload with Main Upload Pipeline
- [ ] Phase 3: Compare Against Specific Person (Search + Per-Face Scores)
- [ ] Phase 4: Fix Compare Result Page — Interactive Shareable View
- [ ] Phase 5: Tests + Regression Check
- [ ] Phase 6: Deploy + Browser Verification
- [ ] Phase 7: Session Docs

## Phase 0: Orient
- Session number set to 85
- Prompt, PRD, and context read
- Current compare page loads (200)
- Current compare result 28f18514d9d3: shows "22% Similar" flat list
- Confirmed: result page lacks uploaded photo, no per-face context

## Phase 1: Diagnosis + Architecture Plan

### Current Compare Upload Flow (BROKEN)
1. `POST /api/compare/upload` receives file
2. Probes `has_insightface` — FAILS on Railway (ImportError for cv2/insightface)
3. Falls back to `_save_compare_upload()` → saves to R2 `uploads/compare/` silo
4. Returns "Photo Received — analyzed within 24 hours" message
5. Photo NEVER enters archive: no photo_index, no identities, no embeddings

### Main Upload Page Flow (WORKS)
1. `POST /upload` receives file
2. Stages to `data/staging/{job_id}/`
3. Spawns `_background_ingest` thread (uses shared hybrid models, no OOM)
4. Thread calls `process_directory()` → full pipeline:
   - Face detection via `extract_faces_hybrid` (prefer_hybrid=True)
   - Embeddings appended to `embeddings.npy`
   - Photo registered in `photo_index.json`
   - INBOX identities created in `identities.json`
   - Crops generated in `app/static/crops/`
   - R2 upload of photos + crops
   - Cache invalidation
5. Client polls `/upload/status/{job_id}` every 2s

### Architecture Plan
**Phase 2 — Unified Upload:**
- Replace `_save_compare_upload()` with staging + `_background_ingest` pattern
- Compare upload handler: stage file → spawn background thread → poll status
- New `GET /api/compare/status/{job_id}` endpoint:
  - Polls same `data/inbox/{job_id}.status.json`
  - On completion: reads face_ids, runs `find_similar_faces` per face
  - Returns HTMX partial with photo preview, face overlays, top matches

**Phase 3 — vs-Person:**
- New `POST /api/compare/vs-person` endpoint
- Params: photo_id + identity_id (the archive person to compare against)
- Compute distance for each uploaded face vs. reference person's anchors
- Get reference person's existing Find Similar top matches for context
- Return HTMX partial with per-face scores + merge/reject/not-same actions

**Phase 4 — Result Page:**
- Embed neighbors_sidebar variant for reference person
- Uploaded faces shown as neighbor candidates with merge/reject actions
- Photo page links, person page links, face overlay toggle
- Shareable URL with full interactive view

### Nolan Feedback (in-session)
- Compare results = Find Similar variant (same merge/reject as neighbors_sidebar)
- Every face links to person page, every photo links to photo page
- Face overlay toggle on uploaded photo
- Find Similar context for compared faces
- Updated PRD-025 and context file to capture all requirements

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed
