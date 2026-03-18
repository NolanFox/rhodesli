# Session 115 Assessment — Community Routing Safety + ML Service Extraction Phase 1

## Shipped

- [x] **Phase 0: Orient + Baseline** — Session files set, baseline 3167 tests/35s recorded.
  Evidence: `.claude/current_session.txt` = 115, session log created.

- [x] **Phase 1: Community Routing Audit + Hardening (PRD-052)** — Comprehensive audit of all ~120 POST/PUT/DELETE routes. 95+ admin routes properly guarded. 5 intentionally public routes documented. Upload path verified: hidden form field + `is_community_explicit()` + moderation queue for non-admin. 27 new safety tests in `test_community_routing_safety.py`.
  Evidence: `pytest tests/test_community_routing_safety.py -v` → 27 passed. Commit d57db94.

- [x] **Phase 2: ML Service Skeleton (TOOLS-002 Phase 1)** — Standalone FastAPI service with health endpoint, face detection endpoint (`POST /api/v1/detect-and-embed`), bearer token auth, separate Dockerfile, ML-only requirements.txt. HTTP client stub in `core/ml_client.py`. 9 tests.
  Evidence: `pytest ml_service/tests/ -v` → 9 passed. `ls ml_service/` shows all files. Commit c37f005.

- [x] **Phase 3: ML Run Provenance (AD-228)** — Schema migration with 4 new columns (execution_environment, model_versions, community_id, scope_filter). `core/ml_run_logger.py` with `log_ml_run()`, `complete_ml_run()`, `fail_ml_run()`, and `MLRunContext` context manager. 18 tests.
  Evidence: `pytest tests/test_ml_run_logger.py -v` → 18 passed. Migration SQL at `scripts/migrations/alter_ml_runs_add_provenance.sql`. Commit eb0395d.

- [x] **Phase 4: Documentation** — AD-228 in ALGORITHMIC_DECISIONS.md. CHANGELOG v0.99.25. ROADMAP updated. Session log updated with audit results.
  Evidence: `grep "AD-228" docs/ml/ALGORITHMIC_DECISIONS.md` → found. Commit 3b8cb48.

- [x] **Phase 5: Deploy** — Pushed to main, `railway deploy` triggered with DOCKERFILE builder.
  Evidence: Railway deploy BUILDING (DOCKERFILE). `git log origin/main..HEAD` → empty.

## Deferred

- ~~**Supabase schema migration**~~: APPLIED. psycopg2 connected via explicit params (DATABASE_URL password contains `@` which broke urlparse). All 4 columns verified with real Supabase insert/read/delete test.

- **ML service Railway deployment**: The ML service exists locally but is NOT deployed to Railway. This is by design — Session 116 scope. BACKLOG: TOOLS-002 Phase 2.

- **Upload form community dropdown**: Upload works safely via hidden form field, but there's no visible dropdown for users to switch communities during upload. This is WORKSPACE-001 scope. Already in BACKLOG.

## Red Flags

- **LOW**: Pre-existing flaky test `test_front_label_on_photo_with_back` fails intermittently in parallel mode (passes alone). Not caused by this session. Known ordering issue.

- **LOW**: Pre-existing e2e test `test_landing_page_hero[chromium]` fails (Playwright setup). Not caused by this session.

- **LOW**: 5 public POST routes have no auth guard (annotations, compare upload, estimate upload). These are intentionally public for community contribution, but `/api/compare/upload` can auto-ingest photos for admin sessions. Documented in test suite as intentional. Rate limiting recommended for estimate endpoint (Gemini API cost).

- **MEDIUM**: The `railway deploy` CLI was needed because GitHub auto-deploy used RAILPACK instead of DOCKERFILE (OD-010). This is a recurring Railway issue that should be monitored.

## Next Session Should Verify

1. **Deploy the ML service to Railway** as a separate internal service (TOOLS-002 Phase 2)
2. **Wire web app to ML service** via `ML_SERVICE_URL` env var and `core/ml_client.py`
3. **Verify community routing** on production — upload path, Fox Family, tools all working
4. **Browser verify** the new deploy shows no regressions

## Metrics

| Metric | Before | After |
|--------|--------|-------|
| App tests | 3167 | 3214 (+47) |
| ML service tests | 0 | 9 |
| ML run logger tests | 0 | 18 |
| Test speed (make test-fast) | 35s | 28-30s |
| New files | 0 | 14 |
| PRDs | 51 | 52 |
| AD entries | 227 | 228 |
