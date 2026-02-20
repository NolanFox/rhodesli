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

## Phase 2: Local Timing (Instrumented)

### First request (cold — ONNX JIT compilation):
| Metric | Value |
|--------|-------|
| HTTP status | 200 |
| Total time | 3.78s |
| Response size | 27,753 bytes |

### Second request (warm):
| Metric | Value |
|--------|-------|
| HTTP status | 200 |
| Total time | 0.50s |
| Response size | 27,753 bytes |

### Startup model loading:
| Model | Time |
|-------|------|
| buffalo_l (all 5 models) | 6.0s |
| Hybrid (det_500m + w600k_r50) | 0.8s |
| Total ML startup | 6.8s |

### Key observation:
Local Mac with hybrid models → 0.5s warm. Production Railway without hybrid → 51.2s.
Root cause confirmed: **buffalo_sc not in Docker image → hybrid fallback → full buffalo_l**.

## Phase 3: Fixes Applied

### Fix A: buffalo_sc in Dockerfile (ROOT CAUSE)
- Dockerfile now downloads both buffalo_l and buffalo_sc at build time
- This ensures det_500m.onnx exists on Railway for hybrid detection

### Fix B: allowed_modules=['detection', 'recognition']
- get_face_analyzer() skips 3 unnecessary models (1k3d68, 2d106det, genderage)
- buffalo_l startup: 6.0s → 5.2s (0.8s faster)

### Fix C: OMP_NUM_THREADS=1
- ENV vars in Dockerfile for Railway shared CPU
- Prevents ONNX spin-wait thread contention

### Fix D: Model warmup at startup
- Dummy inference after model load triggers ONNX JIT compilation
- First real request: 3.78s → 0.34s

## Phase 4: Local Verification Post-Fix

| Test | Before (Phase 2) | After | Improvement |
|------|-------------------|-------|-------------|
| First request (Image 006) | 3.78s | 0.34s | 11x |
| Second request (Image 006) | 0.50s | 0.19s | 2.6x |
| Multi-face (596770938) | 0.82s | 0.76s | 1.1x |
| Test suite | 2486 pass | 2486 pass | No regressions |

## Phase Checklist
- [x] Phase 1: Add timing instrumentation to compare endpoint
- [x] Phase 2: Test locally with timing
- [x] Phase 3: Diagnose and fix root causes
- [x] Phase 4: Local verification post-fix
- [ ] Phase 3: Diagnose and fix root causes
- [ ] Phase 4: Local verification post-fix
- [ ] Phase 5: Deploy and test production
- [ ] Phase 6: Document and close (AD-119, ROADMAP, etc.)

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed
- [ ] Tests pass: `pytest tests/ -x -q`
