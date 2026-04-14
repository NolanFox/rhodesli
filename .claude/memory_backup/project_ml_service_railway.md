---
name: ML Service Railway Deployment
description: Configuration details for the standalone ML service on Railway (TOOLS-002)
type: project
---

ML service deployed as separate Railway service in the rhodesli project.

**Service details:**
- Service name: `ml-service`
- Service ID: `22d072b4-4012-4ffe-bb08-5dcb8c351fb2`
- Environment ID: `4f3223cf-ea80-411b-84af-7353872035cf`
- Root directory: `ml_service` (set via Railway GraphQL API, monorepo pattern)
- Dockerfile: `ml_service/Dockerfile` (relative to rootDirectory)
- Port: 5002
- Internal URL: `http://ml-service.railway.internal:5002`
- Config file: disconnected from railway.toml (set `railwayConfigFile: ""` via API)

**Why:** Railway's multi-service monorepo requires `rootDirectory` per service via API. The `railway.toml` at project root only configures the web service. Setting `railwayConfigFile: ""` prevents the ml-service from reading the web service's config.

**How to apply:** When Railway settings need updating, use the GraphQL API at `https://backboard.railway.com/graphql/v2` with the user token from `~/.railway/config.json["user"]["token"]`.

**Environment variables on ml-service:**
- `ML_SERVICE_TOKEN` — bearer auth token (shared with web service)
- `EXECUTION_ENVIRONMENT=railway_ml_service`
- `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`

**Environment variables on web service (rhodesli):**
- `ML_SERVICE_URL=http://ml-service.railway.internal:5002`
- `ML_SERVICE_TOKEN` — same token as ml-service

**Dockerfile requirements:**
- Must include `g++` for InsightFace Cython build
- Pre-downloads buffalo_l model at build time (~300MB)
- Build context is `ml_service/` directory (not project root)

**How to apply:** Session 115-116. TOOLS-002 Phase 1-2.

**Troubleshooting:**
- `railway.toml` overrides API settings via `propertyFileMapping`. Set `railwayConfigFile: ""` to prevent.
- `railway up` always uses project root Dockerfile. Use GitHub auto-deploy instead.
- DATABASE_URL password contains `@` — use explicit psycopg2 params, not URL parsing.
