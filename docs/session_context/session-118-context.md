# Session 118 Context — ML Service Verification + TOOLS-002 Phase 4-5 + Harness Audit

**Predecessor:** [Session 117 Context](session-117-context.md) (Upload Pipeline Wiring)
**Assessment:** [Session 117 Assessment](../assessments/session-117-assessment.md)
**Architecture:** [ML_SERVICE.md](../architecture/ML_SERVICE.md)
**Memory:** `~/.claude/projects/-Users-nolanfox-rhodesli/memory/project_ml_service_railway.md`

## Problem Statement

Sessions 115-117 built the ML service end-to-end (skeleton → deploy → wire), but **nothing has been tested in production**. The ML service is deployed on Railway and the upload pipeline is wired with fallback, but no actual upload has gone through the service path. Additionally, TOOLS-002 Phase 4 (clustering automation) and Phase 5 (remove local ML deps) remain.

There are also harness gaps from Sessions 115-117 that need cleanup: Session 117 log was missing (fixed), tasks/todo.md was stale (fixed), but the BACKLOG breadcrumbs and context file completeness need verification.

## Current State

### ML Service Architecture
```
┌─────────────────────────────┐
│ Railway: rhodesli (web)     │
│ ML_SERVICE_URL configured   │──────► ┌──────────────────────────┐
│ detect_faces() wrapper      │        │ Railway: ml-service      │
│ Fallback to local if error  │◄──────│ buffalo_l model loaded   │
└─────────────────────────────┘        │ POST /api/v1/detect      │
                                       │ GET /health               │
                                       └──────────────────────────┘
```

### What's Deployed
| Component | Status | Verified in Production? |
|-----------|--------|------------------------|
| ML service on Railway | Running (SUCCESS) | Health only — no real detection test |
| Web app calls ML service | Code deployed | **NEVER TESTED** — no real upload through this path |
| Fallback to local | Code deployed | Tested locally only |
| ML run provenance (AD-228) | Schema migrated | Verified with test insert/delete |
| Community routing safety (PRD-052) | Tests passing | Browser verified (neutral root, Fox Family prefixes) |

### Known Issues From Session 116 Deployment
1. **Railway build configuration was complex**: Required 6 iterations to get the correct Dockerfile used:
   - `railway up` always uses root Dockerfile (wrong)
   - `dockerfilePath` set via API overridden by `railway.toml` `propertyFileMapping`
   - Fixed by: `railwayConfigFile: ""` + `rootDirectory: "ml_service"` via GraphQL API
   - **Risk**: If Railway resets service settings, the ml-service will revert to wrong Dockerfile
2. **g++ missing**: InsightFace Cython build requires g++ — first build failed
3. **No healthcheck verification**: Web app doesn't check ML service on startup

### Harness Gaps Found (Audit of Sessions 115-117)

| Gap | Severity | Status |
|-----|----------|--------|
| Session 117 log missing | CRITICAL | FIXED |
| tasks/todo.md stale (dated March 9) | HIGH | FIXED |
| Session 117 context file incomplete | MEDIUM | Fix in this session |
| BACKLOG not breadcrumbed to PRD-052 | LOW | Fix in this session |
| BACKLOG version header stale (March 15) | LOW | Fix in this session |

## Scope for Session 118

### Phase 1: ML Service Health Verification
- Check ML service deploy status on Railway
- Add `/api/ml-health` endpoint to web app that calls ML service `/health`
- Web app startup: log ML service status (WARN if unavailable)
- Fix any deploy issues discovered

### Phase 2: End-to-End Production Verification
- Run local detection on a test image → capture face count + embeddings
- Run ML service detection on same image (via curl or client) → capture face count + embeddings
- Compare results: face count, bbox overlap, embedding cosine similarity
- Must be identical (same buffalo_l model, same PFE transform)
- If not identical: investigate and fix

### Phase 3: TOOLS-002 Phase 4 — Clustering Automation (if time)
- After upload + detection, auto-trigger cross-batch matching
- Wire `find_cross_batch_matches()` into the post-detection flow
- Auto-generate proposals for new faces
- **Only if Phase 1-2 pass cleanly**

### Phase 4: TOOLS-002 Phase 5 — Remove Local ML Deps (if time)
- Remove InsightFace model downloads from web Dockerfile
- Keep `extract_faces()` as fallback code (don't delete)
- Add ML service health gate: uploads blocked if ML service unavailable and local models not present
- **Only if Phase 3 works**

### Phase 5: Harness Cleanup + Documentation
- Fix remaining harness gaps from audit
- Update BACKLOG with PRD-052 breadcrumb
- Comprehensive browser verification
- Final assessment with evidence

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| ML service down during verification | Check health first, document status |
| Detection results differ | Same model → should be identical. If not, log the diff for investigation |
| Removing local ML breaks uploads | Don't remove yet — verify ML service is stable first |
| Breaking existing functionality | `make test-fast` before every commit, browser verify after deploy |

## Key Files

| File | Purpose |
|------|---------|
| `core/ingest_inbox.py:386-465` | `detect_faces()` wrapper |
| `core/ml_client.py` | HTTP client for ML service |
| `ml_service/main.py` | FastAPI health endpoint |
| `ml_service/detect.py` | Detection endpoint |
| `app/upload_routes.py:850-980` | `_background_ingest()` upload pipeline |
| `core/cross_batch_matching.py` | Cross-batch match (Phase 4 wiring) |
| `Dockerfile` | Web app Docker image (Phase 5 target) |

## Breadcrumbs
- TOOLS-002: ROADMAP.md (Phases 1-3 done)
- COMMUNITY-017: BACKLOG.md (HARDENED)
- AD-228: ML run provenance
- AD-110: Serving path contract
- PRD-052: Community routing safety
- Session 116 memory: `~/.claude/projects/.../memory/project_ml_service_railway.md`
- Railway service ID: `22d072b4-4012-4ffe-bb08-5dcb8c351fb2`
- Railway GraphQL API: `https://backboard.railway.com/graphql/v2`
- Railway token: `~/.railway/config.json["user"]["token"]`

## Post-Session Planning

### Session 119 Candidates (if Phase 4-5 complete)
1. **TOOLS-005**: Estimate v2 — GEDCOM upload + text context + geography retry
2. **COMMUNITY-017 remaining**: Upload form community dropdown (WORKSPACE-001)
3. **UX-130**: Cluster splitting UI (PRD needed)

### If Phase 4-5 deferred
1. Session 119: TOOLS-002 Phase 4 (clustering automation)
2. Session 120: TOOLS-002 Phase 5 (remove local ML deps)
