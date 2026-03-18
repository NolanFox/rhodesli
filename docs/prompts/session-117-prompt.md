# Session 117 — Wire Upload Pipeline to ML Service (TOOLS-002 Phase 3)

@docs/session_context/session-117-context.md
@tasks/lessons.md

## Goal

Wire the upload pipeline to use the deployed ML service for face detection, with automatic fallback to local InsightFace. After this session: photo uploads use the ML service when available, fall back seamlessly when not, and log which detection source was used.

## CRITICAL CONSTRAINTS

1. **ZERO REGRESSIONS** — `make test-fast` before every commit.
2. **DO NOT modify `extract_faces()` or `extract_faces_hybrid()`** — they are the fallback. Keep intact.
3. **Feature flag**: If `ML_SERVICE_URL` env var is empty/unset, use local detection (current behavior). No behavior change for users without the ML service.
4. **/clear between phases**.
5. **DO NOT touch**: `app/perf_cache.py`, `core/neighbors.py` (frozen), `core/pfe.py`.
6. **Browser automation is READ-ONLY on production** (Lesson 149).

## Pre-Requisites

```bash
echo "117" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline
```

Read:
- `docs/session_context/session-117-context.md`
- `core/ingest_inbox.py` lines 386-470 (extract_faces) and 630-830 (process_single_image)
- `core/ml_client.py`
- `ml_service/detect.py`

---

## Phase 1: Add ML Service Detection Wrapper (30 min)

### 1A: Create `detect_faces()` Wrapper

In `core/ingest_inbox.py`, add a new function `detect_faces()` that:

1. Checks if ML service is configured (`MLServiceClient.is_configured`)
2. If yes: calls ML service, transforms response to PFE format
3. If no, or on any error: falls back to local `extract_faces()`
4. Logs which path was taken

```python
def detect_faces(filepath: Path, prefer_hybrid: bool = False) -> tuple:
    """Detect faces using ML service with local fallback.

    Returns same tuple as extract_faces(): (faces_list, width, height)
    """
    from core.ml_client import get_ml_client
    client = get_ml_client()

    if client.is_configured:
        try:
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                client.detect_and_embed(str(filepath))
            )
            faces = _transform_ml_response(result, filepath)
            w, h = result["image_size"]
            logger.info("Face detection via ML service: %d faces in %dms",
                       len(faces), result.get("processing_time_ms", 0))
            return faces, w, h
        except Exception as e:
            logger.warning("ML service failed, falling back to local: %s", e)

    return extract_faces(filepath, prefer_hybrid=prefer_hybrid)
```

### 1B: Create `_transform_ml_response()` Helper

Transform ML service response to match `extract_faces()` output format:

```python
def _transform_ml_response(result: dict, filepath: Path) -> list[dict]:
    """Convert ML service response to PFE face format."""
    faces = []
    for face_data in result.get("faces", []):
        embedding = np.array(face_data["embedding"], dtype=np.float32)
        raw_norm = float(np.linalg.norm(embedding))
        normed = embedding / raw_norm if raw_norm > 0 else embedding

        face = {
            "mu": normed,
            "sigma_sq": 1.0 / max(raw_norm, 1e-6),  # PFE uncertainty
            "det_score": face_data["det_score"],
            "bbox": face_data["bbox"],
            "filename": filepath.name,
            "filepath": str(filepath),
            "quality": raw_norm,
        }
        faces.append(face)
    return faces
```

**CRITICAL**: The embedding normalization and sigma_sq calculation must match `create_pfe()` in `core/pfe.py`. Read that function first and replicate the exact math.

### 1C: Replace Call in `process_single_image()`

At line 698, change:
```python
# OLD:
result = extract_faces(filepath, prefer_hybrid=prefer_hybrid)
# NEW:
result = detect_faces(filepath, prefer_hybrid=prefer_hybrid)
```

This is a ONE LINE change. Everything downstream stays the same.

### 1D: Tests

Create `tests/test_ml_service_detection.py`:
- Test: ML service configured → detect_faces uses ML service
- Test: ML service not configured → detect_faces uses local
- Test: ML service error → detect_faces falls back to local
- Test: _transform_ml_response produces correct PFE format
- Test: Transformed face has all required keys (mu, sigma_sq, det_score, bbox, etc.)
- Test: Embedding normalization matches PFE format

**Commit:** `feat(upload): session 117 phase 1 — ML service detection wrapper with fallback`
**/clear**

---

## Phase 2: ML Run Logging Integration (15 min)

### 2A: Log Detection Source

In the `detect_faces()` wrapper, log each detection to ml_runs:

```python
from core.ml_run_logger import log_ml_run, complete_ml_run

run_id = log_ml_run(supabase_client, "detection",
                     config={"filepath": filepath.name},
                     triggered_by="upload")
# ... detection happens ...
complete_ml_run(supabase_client, run_id,
                result_summary={"faces": len(faces), "source": source},
                duration_ms=elapsed)
```

### 2B: Get Supabase Client in Detection Context

The detection runs in a background thread. Need to get a Supabase client there.
Check how other parts of the codebase get the client in background threads.

### 2C: Tests

- Test: ml_run is created when ML service is used
- Test: ml_run records correct source ("ml_service" vs "local_fallback" vs "local")

**Commit:** `feat(upload): session 117 phase 2 — detection source logging`
**/clear**

---

## Phase 3: Deploy + Verify (15 min)

### 3A: Test Gate
```bash
make test-fast
pytest ml_service/tests/ -q
```

### 3B: Deploy
```bash
git push origin main
```

### 3C: Verify
1. Health endpoint returns 200
2. Check Railway logs for ml-service — should show health checks from web app
3. Upload a test photo if safe (or verify via logs)

**Commit:** `docs: session 117 deploy verification`
**/clear**

---

## Phase 4: Harness Outputs (10 min)

1. Assessment: `docs/assessments/session-117-assessment.md`
2. CHANGELOG: v0.99.27
3. ROADMAP: TOOLS-002 Phase 3 complete
4. SESSION_HISTORY: Session 117 entry
5. Session log archive

**Commit:** `docs: session 117 harness outputs`

---

## Verification Gate

| Check | Method | Expected |
|-------|--------|----------|
| detect_faces() exists? | `grep "def detect_faces" core/ingest_inbox.py` | Found |
| process_single_image uses detect_faces? | `grep "detect_faces" core/ingest_inbox.py` | Called at detection point |
| Fallback works? | Test with ML_SERVICE_URL unset | Local detection used |
| Transform produces PFE format? | `pytest tests/test_ml_service_detection.py` | All pass |
| All tests pass? | `make test-fast` | PASS |
| Assessment exists? | `ls docs/assessments/session-117-assessment.md` | Exists |
