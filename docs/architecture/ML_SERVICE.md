# ML Service Extraction — Architecture

**Date:** 2026-03-07 (created), 2026-03-09 (reframed)
**Session:** 92 (created), 94 (reframed)
**Status:** Draft — Prioritized
**References:** AD-110 (Serving Path Contract), PRD-034 (Standalone Tool Suite), ROADMAP.md Phase F

---

## Problem Statement (Reframed — Session 94)

The original framing of ML service extraction was about Docker image size and
memory pressure. **That undersells the actual problem.** The real issue is:

### The Admin's Laptop is a Single Point of Failure

Today, the ML pipeline has a critical dependency on Nolan's local machine.
While Railway runs face detection on upload (PROCESSING_ENABLED=true), the
**clustering, batch analysis, and production sync** steps are 100% manual:

```
Step 1: sync_from_production.py          ← Manual, never scheduled
Step 2: download_staged.py               ← Manual, never scheduled
Step 3: Move files to raw_photos/        ← Manual filesystem operation
Step 4: core.ingest_inbox                ← ONLY step that runs on Railway
Step 5: cluster_new_faces.py --dry-run   ← Manual, never scheduled
Step 6: Upload crops to R2               ← Manual boto3
Step 7: push_to_production.py            ← Manual, never scheduled
Step 8-10: Verify + clear staging        ← Manual
```

**Only step 4 runs automatically.** Everything else requires Nolan's laptop,
Nolan's time, and Nolan's attention.

### Evidence: The Pipeline Has Barely Run

Git history of `embeddings.npy` changes (the canonical evidence of pipeline runs):

| Date | Commit | What Happened |
|------|--------|---------------|
| Feb 10, 2026 | `cd5b4be` | Initial Docker tracking |
| Feb 10, 2026 | `96524a4` | 12 Nace Collection photos (manual) |
| Feb 10, 2026 | `e62f934` | 30 faces from 3 batches (manual) |
| Feb 13, 2026 | `bc0fba0` | Benatar upload (manual) |
| Feb 13, 2026 | `210b46d` | 1 community photo (manual) |
| Feb 14, 2026 | `4dc9758` | 116 community photos — largest batch (manual) |

**6 total manual pipeline runs across 4 months of production operation.**
That's roughly once every 2-3 weeks, despite 7 fully-implemented pipeline
scripts sitting ready to run.

### What This Means

1. **Clustering doesn't happen** — faces get detected on upload but are never
   matched to existing identities until Nolan manually runs clustering locally
2. **New community members wait** — uploads sit as "INBOX" state indefinitely
3. **Vacation = downtime** — if Nolan is unavailable, no photos get fully processed
4. **Production-local divergence** — Lesson 78 documents this as the #1 recurring
   deployment failure. Every manual sync risks data loss.

### Why It Hasn't Been a Crisis (Yet)

- Tiny community (~3 active identifiers uploading ~1 photo/day)
- Nolan is the sole admin — no queue builds up
- Face detection works automatically (step 4) — photos appear immediately
- Clustering is "nice to have" — users can browse without pre-computed matches

**But:** Once community grows, or a second collection is onboarded (Fox family),
or standalone tools drive external traffic, this becomes a critical bottleneck.

---

## What Cloud ML Actually Unlocks

### Value That Is NOT Already Captured Elsewhere

| Capability | Value | Current State |
|-----------|-------|---------------|
| **Remove laptop dependency** | HIGH | No automation exists |
| **Automated clustering on upload** | HIGH | Manual-only today |
| **Automated batch reanalysis** | MEDIUM | Scripts exist but manual |
| **Smaller web Docker image** (2.5GB → 500MB) | MEDIUM | Not addressed |
| **Faster deploys** (4min → 1min) | MEDIUM | Not addressed |
| **Unblock TOOLS-002** (real-time face compare) | HIGH | Blocked by ONNX |
| **Independent ML scaling** | LOW (at current scale) | Not needed yet |

### Value That IS Already Captured

| Capability | Already Handled By |
|-----------|-------------------|
| Date/location estimation | Gemini API (already cloud) |
| Batch GEDCOM reanalysis | Scripts work (just manual trigger) |
| Observability | Sentry + PostHog (deployed) |

---

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
        │
        │  Manual laptop pipeline (6 runs in 4 months)
        │
┌───────▼─────────┐
│  Nolan's Laptop  │
│  (InsightFace    │
│   clustering     │
│   push scripts)  │
└─────────────────┘
```

**Note:** InsightFace IS installed on Railway (Dockerfile lines 27-43).
`PROCESSING_ENABLED=true` by default. Face detection runs on upload.
But clustering, batch analysis, and sync do NOT run on Railway.

## Proposed Architecture

```
┌──────────────────────┐    ┌──────────────────────┐
│   Web Service        │    │   ML Service          │
│   (Railway)          │    │   (Railway or other)  │
│                      │    │                       │
│   FastHTML + HTMX    │───▶│   FastAPI             │
│   Auth, UI, CRUD     │◀───│   InsightFace         │
│   ~200MB image       │    │   PyTorch/ONNX        │
│   ~100MB RAM         │    │   Clustering          │
│                      │    │   Batch pipeline       │
│                      │    │   ~1.5GB image        │
│                      │    │   ~500MB RAM          │
└──────────────────────┘    └──────────────────────┘
         │                           │
         ▼                           ▼
┌──────────────────────┐    ┌──────────────────────┐
│   Supabase           │    │   Model Storage      │
│   (Postgres + Auth)  │    │   (R2 or volume)     │
└──────────────────────┘    └──────────────────────┘
```

**Key difference from original:** The ML service doesn't just serve inference —
it also runs the **automated pipeline** (clustering, batch analysis, sync).
Nolan's laptop is no longer in the architecture diagram.

---

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
| `POST` | `/api/v1/cluster` | Run clustering on new faces | — | Cluster assignments |
| `GET` | `/api/v1/pipeline/status` | Pipeline run status | — | Last run, next scheduled, queue depth |

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

---

## Deployment Options

### Option A: Railway Internal Service (Recommended Start)

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
Migrate to Option B if GPU is needed for real-time inference or standalone
tool traffic exceeds Railway CPU capacity.

---

## Automated Pipeline (NEW — Session 94)

The ML service should run the full pipeline automatically, not just serve
inference requests. This eliminates the laptop dependency entirely.

### Trigger: Upload Webhook

```
User uploads photo → Web app saves to R2 staging
                   → Web app POSTs to ML service /api/v1/pipeline/trigger
                   → ML service:
                       1. Downloads photo from R2
                       2. Runs face detection + embedding
                       3. Writes embeddings to Supabase (not .npy file)
                       4. Runs clustering against existing embeddings
                       5. Creates proposals (Tier 1 auto-add, Tier 2 suggestions)
                       6. Uploads crops to R2
                       7. Notifies web app via callback
```

### Trigger: Scheduled Batch

```
Cron (nightly or weekly) → ML service:
    1. Recalibrate isotonic model (if new confirmed pairs exist)
    2. Re-cluster INBOX faces against updated embeddings
    3. Run Gemini batch reanalysis on flagged photos
    4. Generate pipeline health report
```

### Data Flow Change

**Before:** Embeddings in `data/embeddings.npy` (file on Railway volume, synced via git)
**After:** Embeddings in Supabase `face_embeddings` table (already partially migrated
per DATA-007). The ML service reads/writes Supabase directly.

This eliminates the entire `sync_from_production.py` → local processing →
`push_to_production.py` cycle that has caused Lesson 78 (production-local
divergence, the #1 recurring deployment failure).

---

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

### Phase 4: Automate (1 session)
- Upload webhook trigger
- Clustering automation
- Scheduled batch pipeline (nightly/weekly)
- Pipeline health dashboard

### Phase 5: Optimize
- Remove ML dependencies from web Docker image
- Benchmark latency and throughput
- ONNX optimization if needed

---

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

---

## Size Impact

| Component | Current (combined) | After (web only) | After (ML only) |
|-----------|-------------------|-------------------|------------------|
| Docker image | ~2.5 GB | ~500 MB | ~2.0 GB |
| RAM usage | ~600 MB | ~150 MB | ~500 MB |
| Startup time | ~15s | ~3s | ~12s |
| Deploy time | ~4 min | ~1 min | ~3 min |

---

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

---

## Relationship to Other Work

| Item | How ML Service Extraction Helps |
|------|-------------------------------|
| **TOOLS-002** (Face Compare Standalone) | Unblocks real-time compare without ONNX workaround |
| **PRD-034** (Standalone Tool Suite) | Shared ML backend for all standalone tools |
| **Lesson 78** (Production-local divergence) | Eliminates the sync cycle entirely |
| **PERF-001** (Test speed) | Smaller web image = faster CI |
| **AD-110** (Serving Path Contract) | Clean separation of web and ML |
| **DATA-007** (Postgres migration) | ML service writes directly to Supabase |
| **PRD-030** (Multi-collection) | ML service handles per-community embeddings |

---

## Breadcrumbs

- Master standalone tools PRD: `docs/prds/034_standalone_tool_suite.md`
- Face Compare Tier 2 PRD: `docs/prds/031_face_compare_tier2.md`
- Serving Path Contract: AD-110 in `docs/ml/ALGORITHMIC_DECISIONS.md`
- Local-only ML decision: AD-007 in `docs/ml/ALGORITHMIC_DECISIONS.md`
- Production-local divergence: Lesson 78 in `tasks/lessons/deployment-lessons.md`
- Pipeline scripts: `scripts/download_staged.py`, `scripts/push_to_production.py`, etc.
- Upload pipeline documentation: MEMORY.md "Upload Pipeline" section
