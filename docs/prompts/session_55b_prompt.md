# Session 55b Prompt: Calibration Audit + ONNX Production Export + ML Documentation

Saved from user prompt at session start. See docs/session_context/session_55b_checkpoint.md for progress.

## Session Goals (Priority Order)
1. Investigate and document the AUC drop and baseline precision characteristics
2. Verify backlog changes — diff what was removed, confirm nothing was lost
3. Export calibration model to ONNX, add onnxruntime to requirements, deploy to production
4. Create comprehensive ML architecture documentation
5. Document the local-vs-web serving decision and all deployment options

## Phases
- Phase 0: Orient (~3 min)
- Phase 1: Calibration Results Investigation (~15 min) — AD-127
- Phase 2: Backlog Audit Verification (~10 min)
- Phase 3: ONNX Export + Production Deployment (~25 min) — AD-128
- Phase 4: Comprehensive ML Documentation (~15 min)
- Phase 5: Verification Gate + Final Docs (~5 min)

## Key Deliverables
- AD-127: Calibration results interpretation
- AD-128: ONNX Runtime for production calibration serving
- ONNX export script + inference module
- Calibration serving in production (not local-only)
- docs/ML_ARCHITECTURE.md
- Backlog verification (20 items from planning context)
