# Session 116 Log — ML Service Deployment + Web App Wiring (TOOLS-002 Phase 2)

**Started:** 2026-03-18
**Predecessor:** Session 115 (Community Routing Safety + ML Service Phase 1)
**Prompt:** docs/prompts/session-116-prompt.md
**Context:** docs/session_context/session-116-context.md

## Baseline Metrics
- App tests: 3211 passed, 28s
- ML service tests: 9 passed

## Phase Checklist
- [x] Phase 0: Orient — verified Session 115 artifacts, Railway project structure
- [x] Phase 1: Deploy ML Service to Railway — service created, env vars set, Dockerfile fixed, deployed SUCCESS
- [x] Phase 2: Complete ML Client — singleton factory, 60s timeout, 10 tests
- [ ] Phase 3: Wire Upload Pipeline — deferred (requires refactoring process_directory)
- [x] Phase 4: Documentation — session log, assessment, memory
- [x] Phase 5: Deploy verification — web app healthy, ML service running

## Railway Deployment Details

### Service Creation
- `railway add --service ml-service` → service ID: 22d072b4-4012-4ffe-bb08-5dcb8c351fb2
- Env vars set: ML_SERVICE_TOKEN, EXECUTION_ENVIRONMENT, OMP/OPENBLAS threads
- Connected to GitHub repo: `railway serviceConnect` via GraphQL API

### Dockerfile Iterations
1. First attempt: `railway up` from project root → used root Dockerfile (wrong)
2. Set `dockerfilePath=ml_service/Dockerfile` via API → still overridden by railway.toml
3. Set `railwayConfigFile=""` to disconnect from railway.toml → still used cached config
4. Set `rootDirectory=ml_service` via API (monorepo pattern) → correct Dockerfile used!
5. Build failed: missing `g++` for InsightFace Cython build
6. Added `g++` to Dockerfile → **BUILD SUCCESS (131s)**
7. Deploy → **SUCCESS** — Uvicorn running on port 5002

### Key Railway API Calls
```graphql
# Disconnect from railway.toml
serviceInstanceUpdate(input: { railwayConfigFile: "" })

# Set monorepo root directory
serviceInstanceUpdate(input: { rootDirectory: "ml_service", dockerfilePath: "Dockerfile" })

# Set healthcheck
serviceInstanceUpdate(input: { healthcheckPath: "/health", healthcheckTimeout: 300 })
```

### Web Service Env Vars Set
- `ML_SERVICE_URL=http://ml-service.railway.internal:5002`
- `ML_SERVICE_TOKEN=VaIETBk1b_1BmzUs7U4ARF0zBx5q-k-XuiaIR4F4LOc`

## Phase 3 Deferral — Upload Pipeline Wiring

The upload pipeline calls `process_directory()` from `core/ingest_inbox.py` which is a monolithic function handling:
1. Face detection (InsightFace)
2. Embedding extraction
3. Identity creation
4. Crop generation
5. R2 upload

Wiring the ML service requires splitting step 1-2 (call ML service) from steps 3-5 (local processing). This is a refactor of `process_directory()` — not a simple wrapper. Deferred to a focused session.

**What's ready for wiring:**
- ML service deployed and running ✓
- ML client complete and tested ✓
- ML_SERVICE_URL configured on web service ✓
- Feature flag: `client.is_configured` returns True when URL is set ✓

**What's needed to wire:**
- Refactor `process_directory()` to accept pre-computed face detection results
- Or: add ML service call inside `process_directory()` with fallback
- Tests for the integration path

## Test Counts
- Session 115 end: 3214 app tests
- After Phase 2: +10 ML client tests
