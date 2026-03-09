# ML Service Extraction — Architecture

**Date:** 2026-03-07 (created), 2026-03-09 (reframed)
**Session:** 92 (created), 94 (reframed)
**Status:** Draft — Prioritized
**References:** AD-110 (Serving Path Contract), PRD-034 (Standalone Tool Suite), ROADMAP.md Phase F

**Sub-documents:**
- [API Specification](ml_service/API.md)
- [Deployment Options](ml_service/DEPLOYMENT.md)
- [Automated Pipeline](ml_service/PIPELINE.md)
- [Migration Plan](ml_service/MIGRATION.md)

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

### What This Means

1. **Clustering doesn't happen** — faces get detected but never matched
2. **New community members wait** — uploads sit as "INBOX" indefinitely
3. **Vacation = downtime** — if Nolan is unavailable, no photos get processed
4. **Production-local divergence** — Lesson 78, #1 recurring deployment failure

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

## Detailed Sections

- **[API Specification](ml_service/API.md)** — Endpoints, request/response formats, auth
- **[Deployment Options](ml_service/DEPLOYMENT.md)** — Railway vs GPU vs serverless, size impact
- **[Automated Pipeline](ml_service/PIPELINE.md)** — Upload webhook, scheduled batch, data flow, web app integration
- **[Migration Plan](ml_service/MIGRATION.md)** — 5-phase plan, risks

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
