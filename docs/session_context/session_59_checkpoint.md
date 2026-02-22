# Session 59 Checkpoint — Face Compare Standalone

## Status: IN PROGRESS

## Phase Status
- [x] Phase 0: Orient + checkpoint
- [ ] Phase 1: Standalone landing page at /facecompare
- [ ] Phase 2: Upload flow + face detection + face selector
- [ ] Phase 3: Results page with 3 ML systems
- [ ] Phase 4: Shareable results + bridge CTAs
- [ ] Phase 5: Verification gate + docs

## Key Architecture
- New `/facecompare` route — standalone, no archive nav, museum-quality
- Reuse ML logic from core/neighbors.py (find_similar_faces)
- Reuse CalibrationService (ONNX), DateEstimationService (CORAL)
- Upload to uploads/facecompare/{uuid}.ext
- Shareable results at /facecompare/result/{uuid}
- Thresholds: strong <1.163, possible <1.3147, similar <1.3647

## Files Modified
- app/main.py — new /facecompare routes
- tests/test_facecompare.py — new test file

## Decisions
- AD-131: Standalone /facecompare separate from /compare
- AD-132: Community-agnostic language in compare UX
