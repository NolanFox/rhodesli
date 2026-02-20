# Session 54F Log — Compare Timing Investigation

**Started:** 2026-02-20
**Goal:** Reduce compare upload from 51.2s → target <10s on production

## Pre-Investigation Diagnosis (Code Reading)

**Root cause identified before any instrumentation:**
The Dockerfile only downloads `buffalo_l` models. On Railway:
- `~/.insightface/models/buffalo_sc/det_500m.onnx` does NOT exist
- `get_hybrid_models()` returns `(None, None)`
- `extract_faces_hybrid()` falls back to `extract_faces()` → full buffalo_l
- Full buffalo_l loads ALL 5 ONNX models (det_10g, w600k_r50, 1k3d68, 2d106det, genderage)
- det_10g on Railway shared CPU ≈ 30-50s detection alone

**Additional issues found:**
1. `get_face_analyzer()` has no `allowed_modules` filter — loads all 5 models
2. No ONNX thread count optimization for shared CPU
3. No warmup inference at startup (first real request pays JIT cost)

## Phase Checklist
- [ ] Phase 1: Add timing instrumentation to compare endpoint
- [ ] Phase 2: Test locally with timing
- [ ] Phase 3: Diagnose and fix root causes
- [ ] Phase 4: Local verification post-fix
- [ ] Phase 5: Deploy and test production
- [ ] Phase 6: Document and close (AD-119, ROADMAP, etc.)

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed
- [ ] Tests pass: `pytest tests/ -x -q`
