# Session 77 Audit — Compare Feature

## Compare-Related Route Map
- `GET /compare`: primary upload + archive face selection UI, confidence tier legend, progress stage UI.
- `GET /api/compare`: archive face-to-archive comparison partial.
- `POST /api/compare/upload`: single-photo upload detection + archive matching + persistence metadata.
- `POST /api/compare/upload-multiple`: multi-photo upload with cross-matches + archive matches.
- `POST /api/upload/stream`: progressive upload status/events endpoint for stage-based loading feedback.
- `POST /api/compare/upload/select`: face selector follow-up for multi-face uploads.
- `GET /compare/result/{result_id}`: shareable result view.
- `POST /api/compare/result/{result_id}/respond`: response capture on shared results.
- `GET /compare/pair`: two-photo compare UX shell.
- `POST /api/compare/pair/upload`: upload handler for each side of pair compare.
- `POST /api/compare/pair/match`: selected-face pair similarity compute (now includes archive context sections).

## Upload Flow (Single Photo)
1. Upload widget submits to compare upload endpoint.
2. Backend validates mime/size and decodes image.
3. InsightFace detection runs on normalized image path.
4. For each detected face, embedding (`mu`) is compared against precomputed `face_index` vectors.
5. Results are confidence-tiered and rendered by `_compare_results_grid`.
6. Upload metadata is saved via `_save_compare_upload` (R2 when available, local fallback otherwise).
7. Upload can be queued into contribution flow (`/api/compare/contribute`).

## Upload Flow (Two Photo Pair)
1. Photo A and B are uploaded separately to `/api/compare/pair/upload`.
2. Faces and embeddings are persisted to `uploads/compare/*_faces.pkl`.
3. User selects one face from each panel.
4. `/api/compare/pair/match` computes pair score and confidence label.
5. Pair results now include top archive matches for each selected face.

## Where Things Were Weak
- Pair comparison previously stopped at pair-only score and did not bridge users into archive context.
- Golden tests were fragmented across larger test modules; explicit compare smoke tests were missing as a single guardrail file.

## Competitive Research (UX Patterns)
- MyHeritage: clear single-zone upload and immediate “you’re processing” state.
- FamilySearch: simple confidence output and minimal friction.
- Betaface: rich diagnostics but poor consumer readability.

### Recommended Patterns Applied
- Keep upload-first hero and visible loading indicator states.
- Add archive bridge from pair mode so user can act on discoveries.
- Keep calibrated confidence language instead of raw-distance-only language.

## Improvement Plan
### Critical Fixes
- Add archive match context to pair comparison results (implemented).
- Add explicit golden compare test module to guard upload/pair/share flows (implemented).

### UX Improvements
- Preserve HTMX/SSE loading affordances and clear action CTAs.
- Keep “Compare another” loop and archive bridge links.

### New Features
- Pair mode now shows archive context sections for Photo A and Photo B selected faces.

### Test Improvements
- New `tests/test_compare.py` with focused compare acceptance tests.


## Incremental review-follow-up work
- Extended pair result endpoint to include **all-face cross-photo ranking** (not only selected face pair).
- Added **archive best-hit summaries for every detected face** in photo A and photo B.
- Added **automatic moderation queue creation** for compare uploads at persistence time to satisfy upload→review pipeline without user extra clicks.
- Expanded golden tests with queueing and cross-match summary checks.
