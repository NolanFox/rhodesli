# ML Service Extraction — Architecture

**Date:** 2026-03-07
**Session:** 92
**Status:** Draft
**References:** AD-110 (Serving Path Contract), ROADMAP.md Phase F

---

## Problem Statement

The Rhodesli Docker image is bloated because ML dependencies (InsightFace,
PyTorch, ONNX, NumPy) are bundled with the web application. This causes:

1. **Large image size** — ~2.5GB Docker image, slow deploys (~3-5 min)
2. **Memory pressure** — ML models consume ~500MB RAM even when idle
3. **Coupling** — Web app restart reloads ML models unnecessarily
4. **Scaling mismatch** — Web requests scale differently from ML inference
5. **AD-110 violation risk** — Heavy ML in web process risks timeout

## Current Architecture

```
┌─────────────────────────────────────────┐
│          Railway Container              │
│                                         │
│  ┌───────────┐  ┌───────────────────┐   │
│  │  FastHTML  │  │  InsightFace +    │   │
│  │  Web App   │  │  PyTorch +        │   │
│  │  (Uvicorn) │  │  ONNX Runtime     │   │
│  │            │  │  (loaded at start) │   │
│  └───────────┘  └───────────────────┘   │
│       │              │                   │
│       ▼              ▼                   │
│  ┌──────────────────────┐               │
│  │  Railway Volume      │               │
│  │  (data + models)     │               │
│  └──────────────────────┘               │
└─────────────────────────────────────────┘
```

## Proposed Architecture

```
┌──────────────────────┐    ┌──────────────────────┐
│   Web Service        │    │   ML Service          │
│   (Railway)          │    │   (Railway or other)  │
│                      │    │                       │
│   FastHTML + HTMX    │───▶│   FastAPI             │
│   Auth, UI, CRUD     │◀───│   InsightFace         │
│   ~200MB image       │    │   PyTorch/ONNX        │
│   ~100MB RAM         │    │   ~1.5GB image        │
│                      │    │   ~500MB RAM          │
└──────────────────────┘    └──────────────────────┘
         │                           │
         ▼                           ▼
┌──────────────────────┐    ┌──────────────────────┐
│   Supabase           │    │   Model Storage      │
│   (Postgres + Auth)  │    │   (R2 or volume)     │
└──────────────────────┘    └──────────────────────┘
```

## ML Service API

### Endpoints

| Method | Path | Description | Input | Output |
|--------|------|-------------|-------|--------|
| `GET` | `/health` | Health check + model status | — | `{"status": "ok", "models_loaded": true}` |
| `POST` | `/api/v1/detect` | Detect faces in image | Image file | Face bounding boxes + scores |
| `POST` | `/api/v1/embed` | Extract face embeddings | Image file | 512-dim embedding vectors |
| `POST` | `/api/v1/detect-and-embed` | Combined detection + embedding | Image file | Faces with bboxes + embeddings |
| `POST` | `/api/v1/compare` | Compare two face sets | Two image files | Similarity matrix |
| `POST` | `/api/v1/align` | Face alignment coordinates | Image file + face index | Alignment landmarks |

### Request/Response Format

```python
# POST /api/v1/detect-and-embed
# Request: multipart/form-data with image file

# Response:
{
  "faces": [
    {
      "bbox": [x1, y1, x2, y2],
      "det_score": 0.95,
      "quality": 0.82,
      "embedding": [0.123, -0.456, ...],  # 512-dim
      "landmarks": [[x, y], ...]  # 5-point
    }
  ],
  "image_size": [width, height],
  "processing_time_ms": 1234
}
```

### Authentication

Service-to-service auth via shared secret:
```
Authorization: Bearer {ML_SERVICE_TOKEN}
```

No user-level auth — the web service handles all user authentication.

## Deployment Options

### Option A: Railway Internal Service (Recommended)

Two Railway services in the same project. Internal networking (no public URL).

| Pro | Con |
|-----|-----|
| Simple deployment | Railway hobby plan limits |
| Internal networking | Shared resource pool |
| Same deploy workflow | Two services to manage |

**Cost:** ~$10-20/month additional (Railway Pro plan)

### Option B: Separate Cloud (GPU)

ML service on a GPU provider (RunPod, Lambda, Modal).

| Pro | Con |
|-----|-----|
| GPU available | Network latency |
| Independent scaling | More complex deployment |
| Cost-efficient for batches | Cold start issues |

**Cost:** ~$0.20-0.50/hour GPU, or ~$30-50/month reserved

### Option C: Serverless (Modal/Banana)

ML inference as serverless functions.

| Pro | Con |
|-----|-----|
| Scale to zero | Cold start (10-30s) |
| Pay per use | Complex deployment |
| No server management | Vendor lock-in |

**Cost:** ~$0.01-0.05 per inference call

### Recommendation

**Start with Option A** (Railway internal service). It is the simplest to
deploy and manage, uses the same workflow, and avoids network latency issues.
Migrate to Option B if GPU is needed for real-time inference.

## Migration Plan

### Phase 1: Extract (1 session)
- Create `ml_service/` directory with FastAPI app
- Extract face detection from `core/ingest_inbox.py`
- Extract embedding from `core/processing.py`
- Health check endpoint
- Docker separate image

### Phase 2: Wire (1 session)
- Web app calls ML service instead of local InsightFace
- Fallback to local if ML service unavailable
- Feature flag: `ML_SERVICE_URL` env var

### Phase 3: Deploy (1 session)
- Railway internal service setup
- Service-to-service auth
- Monitoring and logging

### Phase 4: Optimize
- Remove ML dependencies from web Docker image
- Benchmark latency and throughput
- ONNX optimization if needed

## Web App Changes

### Before (current)
```python
# app/upload_routes.py
from core.processing import process_directory
result = process_directory(photo_path)  # Local InsightFace
```

### After (with ML service)
```python
# app/upload_routes.py
from core.ml_client import MLServiceClient
client = MLServiceClient(os.environ.get("ML_SERVICE_URL"))
result = await client.detect_and_embed(photo_path)
```

### Fallback
```python
# core/ml_client.py
class MLServiceClient:
    async def detect_and_embed(self, image_path):
        if self.service_url:
            return await self._call_service(image_path)
        else:
            # Fallback to local (development)
            from core.processing import process_directory
            return process_directory(image_path)
```

## Size Impact

| Component | Current (combined) | After (web only) | After (ML only) |
|-----------|-------------------|-------------------|------------------|
| Docker image | ~2.5 GB | ~500 MB | ~2.0 GB |
| RAM usage | ~600 MB | ~150 MB | ~500 MB |
| Startup time | ~15s | ~3s | ~12s |
| Deploy time | ~4 min | ~1 min | ~3 min |

## Risks

1. **Network latency** — Inter-service calls add ~10-50ms. Acceptable for
   upload processing, may be noticeable for real-time compare.
2. **Service availability** — ML service downtime blocks uploads. Mitigate
   with health checks and fallback to local.
3. **Data transfer** — Images sent over network. Use internal networking
   (Railway) to avoid egress costs and latency.
4. **Complexity** — Two services to deploy, monitor, and debug. Mitigate
   with structured logging (structlog already in place).
