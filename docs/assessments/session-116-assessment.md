# Session 116 Assessment — ML Service Deployment (TOOLS-002 Phase 2)

## Shipped

- [x] **Phase 0: Orient** — Verified Session 115 artifacts, Railway project has 1 existing service.
  Evidence: `railway service` shows rhodesli. ML service tests pass (9/9).

- [x] **Phase 1: Deploy ML Service to Railway** — Created service, configured env vars, connected to GitHub repo, set rootDirectory=ml_service via Railway GraphQL API, fixed Dockerfile (added g++), deployed successfully.
  Evidence: Railway deploy status SUCCESS. `mcp__railway-mcp-server__get-logs` shows "Uvicorn running on http://0.0.0.0:5002". Build time: 131s.

- [x] **Phase 2: Complete ML Client** — MLServiceClient with singleton factory, 60s timeout, feature flag, availability checking. 10 tests.
  Evidence: `pytest tests/test_ml_client.py -v` → 10 passed.

- [x] **Phase 4: Documentation** — Session log, assessment, Railway deployment memory saved.
  Evidence: Files exist.

## Deferred

- **Phase 3: Wire Upload Pipeline** — The upload pipeline's `process_directory()` is monolithic (detection + identity creation + crops + R2). Wiring the ML service requires refactoring it to accept pre-computed face results. This is a focused refactoring task, not a simple wrapper. Deferred to Session 117.

## Red Flags

- **MEDIUM**: Railway `railway.toml` overrides API-set `dockerfilePath` via `propertyFileMapping`. Fixed by setting `railwayConfigFile: ""` and `rootDirectory: "ml_service"`. This Railway monorepo pattern should be documented (done — saved to memory).

- **LOW**: ML service healthcheck not yet verified from web service. Internal networking (`http://ml-service.railway.internal:5002`) needs end-to-end test once the upload pipeline is wired.

- **LOW**: ML service has no healthcheck configured in Railway dashboard initially. Set via API.

## Next Session Should Verify

1. **ML service health** — add a `/api/ml-health` endpoint to the web app that calls the ML service's `/health`
2. **Wire upload pipeline** — refactor `process_directory()` to use ML service for detection with local fallback
3. **End-to-end test** — upload a photo → ML service detects faces → results match local detection
4. **Cost monitoring** — check Railway billing for ml-service resource usage

## Metrics

| Metric | Before | After |
|--------|--------|-------|
| Railway services | 1 | 2 |
| ML client tests | 0 | 10 |
| ML service status | local only | deployed, running |
