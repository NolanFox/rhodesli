# Session 57 Checkpoint: CORAL Date Estimation → Production

Started: 2026-02-21
Prompt: docs/prompts/session_57_prompt.md
Planning context: docs/session_context/session_57_planning_context.md

## Phase Checklist
- [x] Phase 0: Orient + Checkpoint
- [x] Phase 1: ONNX Export — date_estimation_v1.onnx (16.5 MB), validated 50/50 prediction match
- [x] Phase 2: Production Deployment — DateEstimationService, Dockerfile, health check
- [x] Phase 3: /estimate Endpoint — CORAL primary, Gemini supplementary, probability bars
- [x] Phase 4: Photo Viewer — decade probability bars on photo detail pages
- [x] Phase 5-6: Verification Gate + Docs — CHANGELOG, ROADMAP, BACKLOG, SESSION_HISTORY updated

## Key Decisions
- AD-129: ONNX export for CORAL date model (tolerance 0.05 for deep CNN, vs 1e-5 for MLP)
- Gatekeeper pattern: existing date correction UI already implements this for Gemini labels
- CORAL model is primary for /estimate uploads; Gemini shown as supplementary "Detailed AI Analysis"

## Test Counts
- ML tests: 399 (was 372, +27 new)
- App tests: 2649+ (was 2631, +18 new)

## Files Created
- rhodesli_ml/scripts/export_date_onnx.py — ONNX export script
- rhodesli_ml/artifacts/date_estimation_v1.onnx — 16.5 MB ONNX model
- rhodesli_ml/date_inference/__init__.py
- rhodesli_ml/date_inference/inference.py — fallback chain (ONNX→PyTorch→None)
- rhodesli_ml/date_inference/inference_onnx.py — ONNX Runtime inference
- rhodesli_ml/tests/test_date_export_onnx.py — 11 tests
- rhodesli_ml/tests/test_date_inference.py — 16 tests
- tests/test_session_57_coral_estimate.py — 14 tests
- docs/prds/PRD-025_date_estimation_production.md

## Files Modified
- app/main.py — /api/estimate/upload (CORAL integration), health check (date model status), date section (probability bars)
- Dockerfile — COPY rhodesli_ml/date_inference/
- tests/test_sync_api.py — Dockerfile coverage tests
- tests/test_session_52_fixes.py — health check field tests
- docs/ml/ALGORITHMIC_DECISIONS.md — AD-129
