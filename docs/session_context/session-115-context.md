# Session 115 Context — Community Routing Safety + ML Service Extraction Phase 1

**Predecessor:** [Session 114 Context](session-114-context.md) (Data Stability Completion)
**Assessment:** [Session 114 Assessment](../assessments/session-114-assessment.md)
**PRDs:** [PRD-052](../prds/052_community_routing_safety.md), [PRD-034](../prds/034_standalone_tool_suite.md)
**Architecture:** [ML_SERVICE.md](../architecture/ML_SERVICE.md)

## Problem Statement

Two blockers prevent wider external sharing of Rhodesli:

1. **Community Routing Risk (COMMUNITY-017)**: The community middleware defaults non-prefixed URLs to Rhodes. While Session 100 added a neutral root landing and `is_community_explicit()` guards exist on upload, there's no comprehensive audit confirming ALL data-modifying routes are protected. Community routing bugs have been the #1 recurring regression (Sessions 96c, 96d, 100, 111, 111b — 80+ fixes). Before sharing externally, every write path must be verified.

2. **Local Laptop Dependency (TOOLS-002)**: The ML pipeline (clustering, batch analysis, production sync) runs exclusively on Nolan's laptop. It's been executed only 6 times in 4 months. Face detection runs on Railway, but everything downstream is manual. This session begins extraction into a standalone ML service.

3. **ML Run Provenance Gap**: The `ml_runs` table tracks pipeline executions but doesn't record what system/environment ran them, what models were used, or what scope was targeted. As we move from laptop to cloud service, comparing outputs across environments is critical for quality assurance. The schema also needs to support community-scoped and subset runs as we scale to dozens of communities.

## Research Findings

### Community Routing — Current State

| Component | Status | Location |
|-----------|--------|----------|
| Neutral root landing (`/`) | DONE (Session 100) | `app/page_routes.py` `_platform_root_page()` |
| `/c/{slug}` prefix routing | DONE (Session 96d+) | `app/main.py:477-520` `CommunityMiddleware` |
| `is_community_explicit()` guard | DONE (Session 100) | `app/main.py:529-536` |
| Regression test for prefix gaps | DONE (Session 111b) | `tests/test_community_prefix_audit.py` |
| Upload form community selector | MISSING | No dropdown/picker |
| Test: upload on non-explicit route | MISSING | No test for this edge case |
| Test: platform root renders for anon | MISSING | No test |
| Audit of all POST routes | MISSING | Unknown gaps |

**Middleware behavior** (app/main.py:477-520):
- Static/API routes: skip middleware, default to `community_slug="rhodes"`, `community_explicit=False`
- `/c/{slug}/...` routes: extract slug, set `community_explicit=True`, rewrite path
- All other routes: default to `community_slug="rhodes"`, `community_explicit=False`
- The `is_community_explicit()` function (main.py:529) is the canonical guard

**Remaining risk**: Any data-modifying POST route that doesn't check `is_community_explicit()` could silently assign data to Rhodes. Upload routes already check, but annotation submission, and any HTMX POST endpoints need verification.

### ML Service — Current Architecture

| Step | Location | Automated | Frequency |
|------|----------|-----------|-----------|
| Face detection | Railway (PROCESSING_ENABLED=true) | YES | Every upload |
| Embedding extraction | Railway (bundled) | YES | Every upload |
| Clustering | Nolan's laptop | NO | 6x in 4 months |
| Cross-batch matching | Railway (on upload) | YES | Every upload |
| Batch reanalysis | Nolan's laptop | NO | Rare |
| Production sync | Nolan's laptop | NO | 6x in 4 months |

**Key insight**: Face detection already runs on Railway. The extraction goal is to:
1. Put it behind a clean HTTP API (FastAPI)
2. Create a separate Docker image for the ML service
3. Add clustering + batch operations to the service
4. Eventually move ALL ML to the service and shrink the web image

**Existing architecture docs**: `docs/architecture/ML_SERVICE.md` + 4 sub-files (API, DEPLOYMENT, PIPELINE, MIGRATION) provide the full design. This session implements Phase 1 (Extract skeleton).

### ML Run Provenance — Current Schema

```sql
-- scripts/migrations/create_ml_run_tables.sql (PRD-046)
CREATE TABLE ml_runs (
  run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ DEFAULT now(),
  pipeline_type TEXT NOT NULL,        -- 'clustering', 'cross_batch', 'calibration', etc.
  config_json JSONB,                  -- pipeline-specific config
  status TEXT DEFAULT 'running',      -- 'running', 'completed', 'failed'
  result_summary JSONB,               -- output metrics
  duration_ms INT,
  triggered_by TEXT DEFAULT 'manual', -- 'manual', 'upload_webhook', 'scheduled'
  parent_run_id UUID REFERENCES ml_runs(run_id)
  -- MISSING: execution_environment, model_versions, scope
);
```

**What's needed:**
- `execution_environment` TEXT — 'local_laptop', 'railway_web', 'railway_ml_service', 'ci'
- `model_versions` JSONB — `{"insightface": "0.7.3", "buffalo": "buffalo_l", "calibration": "isotonic_v3"}`
- `community_id` UUID — scope to specific community (NULL = all)
- `scope_filter` JSONB — `{"photo_ids": [...]}` or `{"identity_ids": [...]}` for subset runs

**Scale considerations**: With dozens/hundreds of communities, ML runs should be community-scoped by default. A run on "Fox Family" shouldn't reprocess Rhodes embeddings. The `community_id` column enables this. `scope_filter` enables even finer targeting (specific photos, specific batch).

## Scope for Session 115

### In Scope

| Deliverable | Effort | Track |
|-------------|--------|-------|
| Community routing audit (all POST routes) | 15 min | A |
| Community routing test coverage (5+ tests) | 20 min | A |
| Upload path hardening verification | 10 min | A |
| ML service FastAPI skeleton | 30 min | B |
| Face detection endpoint (extracted) | 25 min | B |
| ML service Dockerfile | 10 min | B |
| ML service local tests | 15 min | B |
| ml_runs schema migration (4 new columns) | 15 min | B |
| ML client HTTP wrapper | 10 min | B |
| Deploy + production verification | 15 min | — |
| Harness outputs | 15 min | — |

**Total: ~3 hours**

### Out of Scope (Explicit Non-Goals)

| Item | Reason | When |
|------|--------|------|
| ML service Railway deployment | Needs separate service config | Session 116 |
| Web app wiring to ML service | Depends on deployed ML service | Session 116 |
| Clustering automation | Depends on deployed ML service | Session 117 |
| Upload form community dropdown | WORKSPACE-001 scope | Future |
| Community discovery page | WORKSPACE-005 scope | Future |
| Removing ML deps from web Dockerfile | Needs ML service deployed + stable first | Session 117+ |

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Community routing regression | P0 — wrong community assignment | Regression test + new test suite |
| ML service skeleton breaks ingest_inbox | P0 — no face detection | Don't modify ingest_inbox yet — copy/extract, keep original intact |
| Schema migration breaks existing ml_runs | P1 — lost provenance | ALTER TABLE ADD COLUMN with defaults (non-breaking) |
| Docker build too large for ML service | P2 — slow builds | Same model pre-download strategy as current Dockerfile |
| Tests slow down further | P2 — dev velocity | New ML service tests are standalone (fast), don't add to app suite |

## Parallelization Analysis

**Track A** (Community Routing) touches:
- `app/main.py` (middleware, read-only audit)
- `app/upload_routes.py` (verification, possible guard additions)
- `app/engagement_routes.py` (annotation submission audit)
- `tests/test_community_routing_safety.py` (NEW)

**Track B** (ML Service Extraction) touches:
- `ml_service/` (NEW directory — no conflicts)
- `scripts/migrations/` (schema migration — no conflicts)
- `core/ml_client.py` (NEW — no conflicts)

**Overlap**: NONE. Tracks are fully independent.
**Recommendation**: Can parallelize via worktrees. Merge order: Track A first (safety), then Track B.
**Caveat**: Only parallelize if both tracks are well-defined enough to delegate. Given the user's emphasis on data safety, community routing (Track A) should be done in the main context for careful verification.

## Key Files

| File | Purpose |
|------|---------|
| `app/main.py:477-536` | CommunityMiddleware + is_community_explicit() |
| `app/upload_routes.py` | Upload community assignment |
| `app/engagement_routes.py` | Annotation submission |
| `core/ingest_inbox.py:1-50` | Face detection entry points to extract |
| `core/ingest_inbox.py` `extract_faces()` | Main detection function |
| `scripts/migrations/create_ml_run_tables.sql` | Current ml_runs schema |
| `docs/architecture/ML_SERVICE.md` | ML service architecture doc |
| `docs/architecture/ml_service/API.md` | API spec |
| `Dockerfile` | Current combined web+ML image |

## Breadcrumbs

- BACKLOG: COMMUNITY-017 (P1), TOOLS-002 (near-term)
- PRD: [052](../prds/052_community_routing_safety.md), [034](../prds/034_standalone_tool_suite.md)
- Architecture: [ML_SERVICE.md](../architecture/ML_SERVICE.md)
- AD: AD-110 (serving path contract), AD-226 (cross-batch threshold)
- OD: OD-011 (Supabase egress), OD-010 (Railway deploy)
- Lessons: 109, 112, 113 (community middleware), 78 (production-local divergence), 133 (DATA_SOURCE fallback)
- PRD-046: ML run provenance (Session 103)

## Post-Session Planning

### Session 116 Candidates
1. **TOOLS-002 Phase 2 (Wire)**: Deploy ML service to Railway, wire web app via ML_SERVICE_URL
2. **TOOLS-002 Phase 3 (Automate)**: Upload webhook trigger, clustering automation
3. **Community routing e2e**: Playwright tests for community flows

### Deferred to Future Sessions
- WORKSPACE-001: Personal archive auto-creation
- WORKSPACE-005: Community discovery page
- Upload form community selector (needs WORKSPACE-001)
