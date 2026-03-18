# Session 116 Context — ML Service Deployment + Web App Wiring (TOOLS-002 Phase 2)

**Predecessor:** [Session 115 Context](session-115-context.md) (Community Routing Safety + ML Service Phase 1)
**Assessment:** [Session 115 Assessment](../assessments/session-115-assessment.md)
**Architecture:** [ML_SERVICE.md](../architecture/ML_SERVICE.md)

## Problem Statement

Session 115 created the ML service skeleton (`ml_service/`) with face detection endpoint, Dockerfile, and HTTP client stub. The service works locally but is not deployed. The web app still runs InsightFace directly via `core/ingest_inbox.py`. This session deploys the ML service to Railway and wires the web app to call it, with fallback to local InsightFace if the service is unavailable.

## What Exists (Session 115 Deliverables)

| Component | Location | Status |
|-----------|----------|--------|
| FastAPI ML service | `ml_service/main.py` | Working locally |
| Detect endpoint | `ml_service/detect.py` | Working locally (mocked tests) |
| ML service Dockerfile | `ml_service/Dockerfile` | Written, not built on Railway |
| ML service requirements | `ml_service/requirements.txt` | InsightFace + FastAPI deps |
| HTTP client | `core/ml_client.py` | Stub — async methods defined |
| ML run logger | `core/ml_run_logger.py` | Working, Supabase-verified |
| ml_runs provenance | 4 new columns | Migration applied, verified |

## Session 116 Scope

### Phase 1: Deploy ML Service to Railway (internal service)
- Create a new Railway service in the existing project
- Point it at `ml_service/Dockerfile`
- Set env vars: `ML_SERVICE_TOKEN`, `EXECUTION_ENVIRONMENT=railway_ml_service`
- Verify health endpoint accessible via internal networking
- **Key**: Internal service = no public URL, only accessible within Railway project

### Phase 2: Wire Web App to ML Service
- Set `ML_SERVICE_URL` env var on web service (Railway internal URL)
- In `app/upload_routes.py`: replace local `core.ingest_inbox.extract_faces()` with `core.ml_client.MLServiceClient.detect_and_embed()`
- Feature flag: if `ML_SERVICE_URL` not set, fall back to local InsightFace
- If ML service returns error or times out, fall back to local InsightFace

### Phase 3: Integration Tests + Verification
- Test: ML service health reachable from web service
- Test: Upload photo → ML service detects faces → results match local detection
- Test: ML service down → fallback to local works seamlessly
- Browser verify: upload a test photo, confirm faces detected

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| ML service crashes | Fallback to local InsightFace (existing code path) |
| Railway networking issue | Health check + retry logic in ml_client.py |
| Model loading OOM on Railway | Same model (buffalo_l) already runs on Railway web service |
| Upload latency increase | HTTP overhead ~10-50ms, acceptable for upload flow |
| Existing uploads break | Feature flag — ML_SERVICE_URL empty = use local |

## Key Files to Modify

| File | Change |
|------|--------|
| `app/upload_routes.py` | Add ML service call with fallback |
| `core/ml_client.py` | Complete the stub with real HTTP calls |
| `core/ingest_inbox.py` | NO CHANGES — keep as fallback |
| Railway config | New service + env vars |

## Breadcrumbs
- TOOLS-002: ROADMAP.md (Phase 1 done, Phase 2 this session)
- ML_SERVICE.md: Full architecture doc
- ml_service/API.md: Endpoint specification
- ml_service/DEPLOYMENT.md: Railway deployment options
- AD-228: ML run provenance (Session 115)
- AD-110: Serving path contract (web never runs heavy ML)
