# Session 52 Log
Started: 2026-02-19
Prompt: docs/prompts/session_52_prompt.md

## Phase Checklist
- [ ] Phase 0: Orient + deep audit
- [ ] Phase 1: Fix Session 51 regressions (face clicks + Name These Faces)
- [ ] Phase 2: Research — ML pipeline on Railway
- [ ] Phase 3: Enable ML dependencies in Docker
- [ ] Phase 4: Wire Compare upload to real processing
- [ ] Phase 5: Wire Estimate upload to real processing
- [ ] Phase 6: Cloud-ready photo processing pipeline
- [ ] Phase 7: FUNCTIONAL end-to-end verification
- [ ] Phase 8: Docs, ROADMAP, BACKLOG, changelog

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed

---

## Phase 0 Findings

### Face Overlays
- **Public photo page** (`/photo/{id}`): Uses `public_photo_page()` at line 15523
  - Face overlays are `<a>` tags with `href` to `/person/{id}` or `/identify/{id}` (lines 15676-15696)
  - Container has `position: relative` — overlays positioned correctly
  - CSS class `face-overlay-box` with `absolute` positioning, `cursor-pointer`
  - These are standard HTML links — should work without JavaScript
  - **No regression from Session 51** — Session 51 did NOT modify `public_photo_page`

- **Modal photo view** (via `/photo/{id}/partial`): Uses `photo_view_content()` at line 8868
  - Face overlays use _hyperscript for click handling (lines 9035-9053)
  - Confirmed faces: navigate to identity page
  - Other faces: toggle tag dropdown
  - Session 51 added sequential mode but did NOT change existing click logic

### "Name These Faces" Button
- Code EXISTS at line 9278 in `photo_view_content()` (MODAL only)
- Gate: `is_admin and len(unidentified_face_ids) >= 2 and not seq_mode`
- Button is NOT on the public `/photo/{id}` page — only in the MODAL
- The user may be looking at `/photo/{id}` and expecting modal features
- If the user is in the modal and button doesn't show, possible causes:
  - `is_admin` not being passed (check Session 51 partial route)
  - Photo has < 2 unidentified faces (faces may have been identified)

### ML Pipeline
- **Dockerfile explicitly says**: "Lightweight image - only web dependencies, no ML processing"
- `PROCESSING_ENABLED=false` in Dockerfile ENV
- `insightface` NOT in requirements.txt
- `onnxruntime` NOT in requirements.txt
- Compare handler has explicit fallback: "Photo received!" + email
- Estimate handler has explicit fallback: "check back soon"
- This is a DELIBERATE architecture choice, not an oversight

### PROCESSING_ENABLED
- Defined in `core/config.py` line 47: defaults to `true` from env
- Dockerfile overrides to `false` (line 59)
- Used in:
  - Upload handler (line 19647): gates subprocess processing
  - Health check (line 6550, 19599): reports status
  - Pending uploads tests: mocked as False

### Model Files
- Not in repo (no .onnx files found)
- buffalo_l is ~300MB, downloaded by insightface on first use
- Would need to be available on Railway for processing

### What Would It Take for ML on Railway
1. Add insightface + onnxruntime to requirements.txt
2. Add system deps to Dockerfile (libgomp needed for onnxruntime)
3. Download model at build time or startup (~300MB)
4. Set PROCESSING_ENABLED=true
5. Verify memory fits (Railway hobby = 512MB, insightface needs ~300MB)
6. Wire compare handler to process when InsightFace available
7. Wire estimate handler to call Gemini when key available
