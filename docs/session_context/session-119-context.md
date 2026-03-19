# Session 119 Context — ML Service End-to-End Verification

**Predecessor:** [Session 118 Context](session-118-context.md) (ML Service Fix + Codex Audit)
**Assessment:** [Session 118 Assessment](../assessments/session-118-assessment.md)
**Architecture:** [ML_SERVICE.md](../architecture/ML_SERVICE.md)

## Problem Statement

Session 118 fixed the ML service port mismatch and confirmed web-to-ML connectivity via `/api/admin/ml-health`. But **zero real detection requests** have gone through the ML service in production. The model hasn't even loaded yet (`models_loaded: false` — lazy-loads on first request). We need to verify the complete pipeline before we can consider removing local InsightFace (TOOLS-002 Phase 5, AD-229).

## Current State

### What's Working
| Component | Status | Evidence |
|-----------|--------|----------|
| ML service deployed | SUCCESS | Railway deploy `835962f7` + `7d10b28f` |
| ML service healthy | YES | `/api/admin/ml-health` → `{"status": "connected"}` |
| Web app → ML service connectivity | YES | Internal networking on port 5002 |
| Upload pipeline wired | YES | `detect_faces()` tries ML service first |
| Fallback to local | YES | Tested in unit tests only |
| Cross-batch matching wired | YES | Verified in Session 118 Phase 3 |

### What's NEVER Been Tested
| Component | Risk | How to Test |
|-----------|------|-------------|
| Real photo upload → ML service detection | HIGH | Upload a photo, check Railway ML service logs |
| Model lazy-load on first request | MEDIUM | First upload triggers 30-60s model load, 60s timeout |
| Embedding quality from ML service | HIGH | Compare cosine similarity with local detection |
| Crop generation after ML service detection | MEDIUM | Verify face crops appear correctly in UI |
| Cross-batch matching on ML-detected faces | MEDIUM | Verify proposals generated for new faces |

### AD-229 Stability Criteria (from Session 118)
1. ML service healthy for 24h+ continuous → **NOT MET** (deployed ~20 min ago)
2. At least 3 successful uploads through ML service path → **NOT MET** (0 uploads)
3. Embedding cosine similarity ≥0.999 between local and cloud → **NOT MET** (never compared)
4. Railway billing for ml-service ≤ $5/month → **UNKNOWN**

## Key Technical Details

### Upload Pipeline Flow
```
User uploads photo → app/upload_routes.py
  → _background_ingest()
    → process_directory() → process_single_image()
      → detect_faces()  ← THIS IS THE ML SERVICE CALL
        → ML service: POST /api/v1/detect-and-embed (60s timeout)
        → Response transformed to PFE format
        → On failure: fallback to local extract_faces()
      → save embeddings + create identities
    → group_inbox_identities() (within-batch clustering)
    → find_cross_batch_matches() (across-batch proposals)
```

### First Request Concern
The ML service lazy-loads the buffalo_l model (~300MB) on first detection request. This takes 30-60s on Railway. The HTTP client has a 60s timeout. If model load takes >60s, the first upload will fall back to local detection and we won't know if the ML service works.

**Mitigation options:**
1. Increase timeout to 120s for first request
2. Pre-warm the model by calling `/api/v1/detect-and-embed` with a tiny test image
3. Add a `/api/v1/warm` endpoint that loads the model without processing

### Embedding Comparison Approach
To verify embeddings match:
1. Pick a photo already processed locally (embeddings in embeddings.npy)
2. Send same photo to ML service via curl or test script
3. Compare: cosine similarity of each face's embedding should be ≥0.999
4. If not: investigate — could be model version difference, preprocessing, or normalization

### Railway Logs
ML service logs use `[ml-service]` prefix in `core/ingest_inbox.py`:
- `[ml-service] N face(s) in Xms from filename` — success
- `[ml-service] Failed for filename, falling back to local: error` — failure + fallback

Check via: Railway MCP `get-logs` with service=ml-service, logType=deploy

## Files to Watch

| File | Purpose |
|------|---------|
| `core/ingest_inbox.py:386-465` | `detect_faces()` wrapper |
| `core/ml_client.py` | HTTP client (60s timeout) |
| `ml_service/detect.py` | Detection endpoint |
| `ml_service/main.py` | Health endpoint |
| `app/upload_routes.py:850-1100` | Upload pipeline + cross-batch |

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| First request timeout (model load) | Pre-warm option, or increase timeout |
| Embedding mismatch | Same model (buffalo_l) → should match. Log diff if not |
| Upload breaks something | Use a test photo, not a real contribution |
| ML service crashes under load | Single photo test, monitor Railway logs |
| Browser verification breaks something | READ-ONLY on production (Lesson 149) |

## Breadcrumbs
- AD-229: ML service stability criteria
- HD-028: Codex audit strategy (security scopes only)
- TOOLS-002: ROADMAP.md (Phases 1-4 done, Phase 5 deferred)
- ML service Railway: memory/project_ml_service_railway.md
- Session 118 log: docs/session_logs/session-118-log.md
