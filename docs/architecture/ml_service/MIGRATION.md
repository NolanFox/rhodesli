# ML Service Migration Plan

**Parent:** [ML_SERVICE.md](../ML_SERVICE.md)

## Phase 1: Extract (1 session)
- Create `ml_service/` directory with FastAPI app
- Extract face detection from `core/ingest_inbox.py`
- Extract embedding from `core/processing.py`
- Health check endpoint
- Docker separate image

## Phase 2: Wire (1 session)
- Web app calls ML service instead of local InsightFace
- Fallback to local if ML service unavailable
- Feature flag: `ML_SERVICE_URL` env var

## Phase 3: Deploy (1 session)
- Railway internal service setup
- Service-to-service auth
- Monitoring and logging

## Phase 4: Automate (1 session)
- Upload webhook trigger
- Clustering automation
- Scheduled batch pipeline (nightly/weekly)
- Pipeline health dashboard

## Phase 5: Optimize
- Remove ML dependencies from web Docker image
- Benchmark latency and throughput
- ONNX optimization if needed

## Risks

1. **Network latency** — Inter-service calls add ~10-50ms. Acceptable for
   upload processing, may be noticeable for real-time compare.
2. **Service availability** — ML service downtime blocks uploads. Mitigate
   with health checks and fallback to local.
3. **Data transfer** — Images sent over network. Use internal networking
   (Railway) to avoid egress costs and latency.
4. **Complexity** — Two services to deploy, monitor, and debug. Mitigate
   with structured logging (structlog already in place).
5. **Embeddings migration** — Moving from .npy file to Supabase table is a
   data migration. Mitigate by running both in parallel during transition.
