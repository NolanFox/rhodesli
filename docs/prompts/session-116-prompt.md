# Session 116 — ML Service Deployment + Web App Wiring (TOOLS-002 Phase 2)

@docs/session_context/session-116-context.md
@docs/architecture/ML_SERVICE.md
@tasks/lessons.md

## Goal

Deploy the ML service skeleton (from Session 115) to Railway as an internal service and wire the web app to call it for face detection, with fallback to local InsightFace. After this session: uploads use the ML service for face detection when available, fall back gracefully when not.

## CRITICAL CONSTRAINTS

1. **ZERO REGRESSIONS** — run `make test-fast` before every commit.
2. **DO NOT modify `core/ingest_inbox.py`** — it is the fallback. Keep it intact.
3. **Feature flag**: `ML_SERVICE_URL` env var. Empty/unset = use local InsightFace (current behavior).
4. **Browser automation is READ-ONLY on production** (Lesson 149).
5. **/clear between phases** — commit first, then /clear immediately.
6. **TTL cache every new Supabase read** — minimum 120s (OD-011).
7. **DO NOT touch**: `app/perf_cache.py`, `core/neighbors.py` (frozen), embeddings.npy handling.

## Pre-Requisites

```bash
echo "116" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline
```

Read these files:
- `docs/session_context/session-116-context.md`
- `docs/assessments/session-115-assessment.md`
- `ml_service/main.py` and `ml_service/detect.py`
- `core/ml_client.py`
- `app/upload_routes.py` (find where `extract_faces` is called)

---

## Phase 0: Orient (10 min)

### 0A: Verify Session 115 Artifacts
```bash
ls ml_service/main.py ml_service/detect.py ml_service/Dockerfile core/ml_client.py core/ml_run_logger.py
pytest ml_service/tests/ -q
```

### 0B: Check Railway Project Structure
Use `mcp__railway-mcp-server__list-services` to see existing services.
We need to create a NEW service for the ML backend.

### 0C: Set Up Session Log
Create `docs/session_logs/session-116-log.md` with phase checklist.

**Commit:** `docs: session 116 phase 0 — orient`
**/clear**

---

## Phase 1: Deploy ML Service to Railway (30 min)

### 1A: Create Railway Service

Use Railway MCP tools or CLI to create a new service in the existing project:
```bash
# Option 1: Railway CLI
railway service create ml-service

# Option 2: Railway MCP
# mcp__railway-mcp-server__create-project-and-link (if separate project)
```

The service needs:
- Name: `ml-service` (or `rhodesli-ml`)
- Dockerfile: `ml_service/Dockerfile`
- Root directory: `ml_service/` (or project root with dockerfilePath)
- Port: 5002
- Internal networking: enabled (no public domain)

### 1B: Set Environment Variables

```bash
# On the ML service:
ML_SERVICE_TOKEN=<generate-secure-token>
EXECUTION_ENVIRONMENT=railway_ml_service
OMP_NUM_THREADS=1
OPENBLAS_NUM_THREADS=1

# On the web service:
ML_SERVICE_URL=http://ml-service.railway.internal:5002
ML_SERVICE_TOKEN=<same-token-as-above>
```

Use `mcp__railway-mcp-server__set-variables` to set these.

### 1C: Deploy ML Service

Trigger deployment of the ML service. Monitor build logs.
The Dockerfile pre-downloads buffalo_l model (~300MB) so first build takes ~5-10 min.

### 1D: Verify Health

Once deployed, verify from the web service:
```bash
curl http://ml-service.railway.internal:5002/health
```

Or add a temporary health check endpoint to the web app that calls the ML service.

### 1E: Tests

No new tests needed — ML service tests already exist from Session 115.
Verify they still pass: `pytest ml_service/tests/ -q`

**Commit:** `feat(ml-service): session 116 phase 1 — deploy ML service to Railway`
**/clear**

---

## Phase 2: Complete ML Client (25 min)

### 2A: Implement HTTP Client

The `core/ml_client.py` stub from Session 115 has the interface defined.
Complete the implementation:

1. `health()` — GET /health, return response JSON
2. `detect_and_embed(image_path)` — POST /api/v1/detect-and-embed with multipart image
3. `is_available()` — try health(), return bool
4. `close()` — cleanup async client

Use `httpx.AsyncClient` with:
- Timeout: 60s (face detection can take 10-30s for large images)
- Retry: 1 retry on connection error
- Bearer token auth header

### 2B: Add ML Client Tests

Create `tests/test_ml_client.py`:
- Test health() calls correct URL
- Test detect_and_embed() sends multipart file
- Test is_available() returns False on connection error
- Test is_available() returns False when not configured
- Test auth header is set correctly

### 2C: Verify

```bash
pytest tests/test_ml_client.py -v
make test-fast  # No regressions
```

**Commit:** `feat(ml-client): session 116 phase 2 — complete ML client HTTP implementation`
**/clear**

---

## Phase 3: Wire Upload Pipeline (30 min)

### 3A: Find Current Detection Call

In `app/upload_routes.py`, find where face detection is triggered:
- Search for `extract_faces`, `ingest_inbox`, `process_photo`, `PROCESSING_ENABLED`
- Understand the current flow: upload → staging → subprocess → detect → embed → save

### 3B: Add ML Service Integration

At the point where face detection is called:
1. Check if `ML_SERVICE_URL` is configured
2. If yes: call `MLServiceClient.detect_and_embed()`
3. If no, or if ML service returns error: fall back to local `extract_faces()`
4. Log which path was taken (for ML run provenance)

```python
# Pseudocode for the integration point:
ml_client = MLServiceClient()  # reads ML_SERVICE_URL from env

if ml_client.is_configured:
    try:
        result = await ml_client.detect_and_embed(image_path)
        faces = result["faces"]
        detection_source = "ml_service"
    except Exception as e:
        logger.warning("ML service failed, falling back to local: %s", e)
        faces = extract_faces(image_path)
        detection_source = "local_fallback"
else:
    faces = extract_faces(image_path)
    detection_source = "local"
```

### 3C: Log Detection Source

Use `core/ml_run_logger.py` to log each detection with the source:
```python
from core.ml_run_logger import MLRunContext

with MLRunContext(supabase_client, "detection",
                  triggered_by="upload",
                  community_id=upload_community_id) as run:
    # detection happens here
    run.set_result({"faces": len(faces), "source": detection_source})
```

### 3D: Tests

Add tests to `tests/test_upload_ml_service.py`:
- Test: ML_SERVICE_URL set → client called
- Test: ML_SERVICE_URL not set → local detection used
- Test: ML service error → fallback to local
- Test: ML service timeout → fallback to local
- Test: Detection source logged correctly

### 3E: 2nd/3rd Order Effects

- **Latency**: HTTP call adds ~50ms overhead. Acceptable for upload flow (already async).
- **Double detection**: Don't detect twice on fallback — try ML service first, if fails, then local.
- **Embedding format**: ML service returns same 512-dim PFE format as local. Verify shapes match.
- **Subprocess isolation**: If detection currently runs as subprocess, the ML service call replaces the subprocess (no process spawning needed).

**Commit:** `feat(upload): session 116 phase 3 — wire upload pipeline to ML service with fallback`
**/clear**

---

## Phase 4: Deploy + Production Verification (15 min)

### 4A: Final Test Gate
```bash
make test-fast    # App tests
make test-ml      # ML tests
pytest ml_service/tests/ -q  # ML service tests
```

### 4B: Deploy Web App
```bash
git push origin main
# If RAILPACK issue: railway deploy
```

### 4C: Set ML_SERVICE_URL on Railway
After both services are deployed, set the env var on the web service to point to the ML service's internal URL.

### 4D: Production Verification (READ-ONLY)
1. Health endpoint returns 200
2. Upload page loads
3. If possible: check Railway logs for ML service health check calls
4. Verify no console errors

**Commit:** `docs: session 116 deploy verification`
**/clear**

---

## Phase 5: Harness Outputs (15 min)

### 5A: Assessment
`docs/assessments/session-116-assessment.md`

### 5B: Documentation Updates
1. CHANGELOG.md: v0.99.26
2. ROADMAP.md: TOOLS-002 Phase 2 complete
3. BACKLOG.md: update TOOLS-002 status
4. SESSION_HISTORY.md: Session 116 entry
5. tasks/todo.md: update

**Commit:** `docs: session 116 harness outputs`

---

## Verification Gate

| Check | Method | Expected |
|-------|--------|----------|
| ML service deployed? | Railway dashboard / MCP | Service running, health OK |
| ML client complete? | `pytest tests/test_ml_client.py -v` | All pass |
| Upload wired? | grep for ml_client in upload_routes.py | Present |
| Fallback works? | Test with ML_SERVICE_URL unset | Local detection used |
| All tests pass? | `make test-fast` | PASS |
| Deploy successful? | Railway status | SUCCESS |
| Assessment exists? | `ls docs/assessments/session-116-assessment.md` | Exists |
| CHANGELOG updated? | `grep "v0.99.26" CHANGELOG.md` | Found |
| `git log origin/main..HEAD` empty? | git log | Empty |

## Parallelization

Phase 2 (ML client) and Phase 3 (upload wiring) are sequential — Phase 3 depends on Phase 2.
No parallelization opportunities in this session.
