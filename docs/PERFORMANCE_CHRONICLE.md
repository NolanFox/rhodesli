# Performance Chronicle

Tracks optimization journeys across Rhodesli. Each section chronicles a performance improvement from initial measurement through resolution, with breadcrumbs to decisions, sessions, and code changes.

**Claude Code: Update this file whenever a performance optimization is completed. Include before/after metrics, root cause, and breadcrumbs.**

---

## Chronicle 1: Compare Pipeline Latency

### Timeline

| Date | Session | Metric | Value | Change |
|------|---------|--------|-------|--------|
| 2026-02-19 | 54A | Compare upload (2-face) | 51.2s | Baseline (first production measurement) |
| 2026-02-20 | 54F | Compare upload (2-face) | 10.5s | -79.5% (4.9x improvement) |
| 2026-02-20 | 54F | Compare upload (14-face) | 28.5s | First group photo measurement |
| 2026-02-20 | 54F | Embedding comparison | 0.39s | Fast — not the bottleneck |
| 2026-02-20 | 54F | Local cold start | 3.78s → 0.34s | 11x with warmup |
| 2026-02-20 | 54F | Local warm | 0.50s → 0.19s | 2.6x |

### Root Causes

1. **Initial hypothesis (WRONG):** Per-request model loading (Hypothesis 1 from 54A planning)
2. **Actual root cause:** buffalo_sc model not in Docker image → hybrid detection silently fell back to buffalo_l with all 5 ONNX models (det_10g at 10G FLOPs). Singleton model loading was working correctly but loading the wrong (heavier) model.
3. **Contributing factors:** No ONNX thread optimization (spin-waiting on shared vCPU), no model warmup (JIT cost on first inference), OOM from dual FaceAnalysis loading.
4. **Why smoke tests didn't catch it:** Output format identical between buffalo_sc and buffalo_l — both produce 512-dim embeddings. No WARNING logged on fallback. Only latency differed.

### Fixes Applied (AD-119)

1. Added buffalo_sc to Dockerfile (separate RUN step to avoid build OOM)
2. `allowed_modules=['detection', 'recognition']` for buffalo_l fallback
3. `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1` in Dockerfile
4. Dummy warmup inference at startup
5. Startup loads ONLY hybrid models; buffalo_l FaceAnalysis lazy-loaded as fallback

### Architecture Constraints

- **Platform:** Railway Hobby plan ($5/mo), shared CPU, no GPU, 512MB RAM
- **Floor:** ~10s for 2-face photo is the approximate floor for shared CPU with correct model
- **GPU projection:** Under 1 second with dedicated GPU inference
- **Future options:** Pre-computed embeddings served without runtime detection; Modal/serverless GPU for burst compute; client-side detection via MediaPipe (Session 56)

### Lessons

- Silent ML model fallbacks are invisible to functional tests (AD-120)
- Instrumentation (Phase 1 logging) in optimization work caught the real cause
- Always verify WHICH model is loaded, not just that A model loaded
- Model warmup eliminates JIT cost (11x local improvement)
- ONNX thread optimization prevents spin-waiting contention on shared vCPU

### Breadcrumbs

- AD-119: buffalo_sc Docker fix (specific)
- AD-120: Silent fallback observability principle (general)
- HD-012: Silent ML fallback detection harness rule
- Sessions 54A-54F: Full optimization journey
- CHANGELOG: v0.54.3 (performance fix entry)
