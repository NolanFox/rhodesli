# Rhodesli Development Roadmap

Heritage photo identification system. FastHTML + InsightFace + Supabase + Railway + R2.
Current: v0.99.28 · ~4600 tests · 965 photos · 3522 identities · 95 confirmed

## Progress Tracking Convention
- `[ ]` = Todo | `[-]` = In Progress (add date) | `[x]` = Completed (add date)
- When completing a task, move to "Recently Completed" with date

## Current State & Key Risks
- User data migrated to Supabase Postgres (Session 59C). Face alignment also in Supabase (Session 64).
- **ML architecture: AD-110 Serving Path Contract** — web requests NEVER run heavy ML.
- Community sharing live on Jews of Rhodes Facebook group (~2,000 members)
- Gemini 3.1 Pro wired to Estimate (AD-139) — progressive refinement designed (AD-102)
- **Similarity calibration live**: isotonic regression, AUC=0.9577, calibrated scores in UI (AD-149/152)
- **API call logging**: Every Gemini call tracked in gemini_api_calls table (AD-152). gemini_config + response_summary now populated (AD-159 fix).
- **GEDCOM linking**: Admin can link identities to GEDCOM records via in-app search (AD-160)
- **Auto-clustering pipeline**: Two-tier system — Tier 1 auto-adds (<0.85), Tier 2 surfaces as Discovery suggestions (0.85-1.10). AD-179.
- **Railway volume space** — auto_backups pruned to 5 (was 10), ENOSPC fixed in Session 61B

## Phase Summary

| Phase | Status | Details |
|-------|--------|---------|
| **A: Stabilization** | COMPLETE | All P0 bugs fixed, 103 tests added |
| **B: Share-Ready Polish** | ~98% complete | Email notifications wired (Resend). Remaining: custom domain sender |
| **C: Annotation Engine** | COMPLETE | Full submit/review/approve workflow |
| **D: ML Feedback** | ~95% complete | Multi-pass foundation built. Remaining: batch execution, FE-040-043 |
| **E: Collaboration** | ~80% complete | Help Identify verified, email notifications. Remaining: analytics dashboard, moderation |
| **F: Scale & Generalize** | ~65% complete | Sentry, PostHog, CI/CD, structlog shipped. Remaining: pgvector (DEFERRED), ML service extraction |

For full feature checklists, see [docs/roadmap/FEATURE_STATUS.md](docs/roadmap/FEATURE_STATUS.md).
For ML-specific roadmap, see [docs/roadmap/ML_ROADMAP.md](docs/roadmap/ML_ROADMAP.md).

## Open Work (Prioritized)

### Immediate — Post-Session 92
- [x] 2026-03-08: Deploy v0.95.0 to Railway + browser verify all features (Session 92)
- [x] 2026-03-08: Set SENTRY_DSN + POSTHOG_API_KEY + RESEND_API_KEY on Railway (Session 92)
- [x] 2026-03-08: Leon's Restaurant fix — business name → GEDCOM owner lookup (AD-210, Session 92)
- [x] 2026-03-08: Full API call logging — prompt_text, full_response, gedcom_context columns (Session 92)
- [x] 2026-03-08: 10 P1/P2 UX bugs fixed (Session 92)
- [x] 2026-03-08: Email notifications via Resend (Session 92)
- [x] 2026-03-08: CI/CD foundation — .github/workflows/test.yml (Session 92)
- [x] 2026-03-08: Multi-pass Gemini foundation (rhodesli_ml/multi_pass.py, Session 92)
- [x] 2026-03-08: Active learning foundation (rhodesli_ml/active_learning.py, Session 92)
- [x] 2026-03-08: DATA-007 — Postgres migration complete (Session 93)
- [x] 2026-03-08: Batch GEDCOM re-analyze — 67/72 photos, AD-211, report (Session 93)
- [x] 2026-03-08: Observability verified — Sentry, PostHog, Resend all confirmed (Session 93)
- [x] 2026-03-17: PERF-001: Test speed <30s — achieved 28s (Session 114, marked 3 slow integration tests)
- [x] 2026-03-10: DATA-008: Comprehensive data integrity audit + fixes (Session 96e-cont10)

### Near-Term — Standalone Tool Suite (PRD-034)
Community-agnostic versions of Rhodesli's ML tools. See `docs/prds/034_standalone_tool_suite.md`.

- [x] 2026-03-09: TOOLS-001: Date + Location Estimator Standalone — shipped as `/tools/estimate` (Session 95)
- [x] 2026-03-18: TOOLS-002: ML Service Extraction — Phase 1 (skeleton) Session 115, Phase 2 (deploy) Session 116, Phase 3 (wire pipeline) Session 117, Phase 4 (clustering automation — verified already wired, Session 118). ML service deployed on Railway, upload pipeline wired with fallback. Session 118: fixed critical port mismatch, ML service first healthy deploy. Remaining: Phase 5 (remove local ML deps — deferred per AD-229).
- [ ] TOOLS-003: Face Compare Real-Time — depends on TOOLS-002 (ML service), 1-2 sessions after
- [ ] TOOLS-004: NL Query + Chatbot — parser prototype exists, needs Supabase wiring, 3-5 sessions
- [ ] TOOLS-005: Estimate v2 — GEDCOM upload + text context + geography retry (Nolan feedback). See `docs/BACKLOG.md`
- [ ] TOOLS-006: Self-service archive creation — "Create Your Archive" flow for community upload onboarding (Nolan feedback). See `docs/BACKLOG.md`
- [x] 2026-03-09: ROUTE-001: /facecompare → 301 redirect to /tools/compare (shipped post-Session 95)
- [x] 2026-03-10: COMMUNITY-001: Community data scoping — photos section, sidebar counts, admin bar scoped (Session 96 hotfix + 96d). Remaining: about page, tools photo picker.
- [-] 2026-03-09: COMMUNITY-002: Workspace switcher UX — admin dropdown to switch between communities (Session 95b)
- [x] 2026-03-10: COMMUNITY-003: Cross-community identity tagging — photo-derived identity sets + auto-tag identity_communities (AD-213, AD-216, Session 96c + 96d)
- [ ] COMMUNITY-004: "Shared person" indicator on identity cards — show when a person appears in multiple archives
- [-] 2026-03-18: COMMUNITY-017: Community routing safety hardening — audit all write routes, add safety tests (PRD-052, Session 115)
- [x] 2026-03-10: COMMUNITY-005: Community-scoped sidebar counts — remove ML feature zeroing, enable Admin section for all communities (Session 96c + 96d proposals count)
- [x] 2026-03-10: COMMUNITY-006: Community-aware discoveries — filter by photo-derived identity set (Session 96c + 96d cross-community badges)

### Near-Term — Post-Upload Intelligence (PRD-037)
- [x] 2026-03-09: UPLOAD-001: Charlie Fox collection ingest — 636 photos via local pipeline (Session 96b)
- [x] 2026-03-09: PRD037-001: Auto-cluster after upload — wire clustering into `_background_ingest()` (Session 96b)
- [x] 2026-03-09: PRD037-002: GEDCOM triage page — surface top identities by face count for linking (Session 96b)
- [x] 2026-03-13: PRD037-004: Wire cluster review into community sidebar — speed-run mode with keyboard shortcuts (Session 100c)
- [x] 2026-03-14: PRD040-001: Batch cluster validation page — Google Photos-style select/confirm grid (Session 100f)
- [x] 2026-03-14: PRD039-002: Enriched speed-run — all faces, name input, merge search, recent actions, audit trail (Session 100f)
- [ ] PRD037-003: Batch Gemini with GEDCOM context — cost estimate UI, enriched prompts (future session)

### Near-Term — Longitudinal Face Modeling (PRD-038)
- [x] 2026-03-11: Session 97 foundation shipped — SDD, research pack, implementation bundle, prompt/state lineage spec, and merged-branch verification are wired into the harness
- [x] 2026-03-11: Phase 0: Eval repair + scorer-path unification
- [x] 2026-03-11: Phase 1: Local recalibration hygiene + label taxonomy
- [x] 2026-03-11: Phase 2: Prototype-bank longitudinal reranker in shadow mode
- [x] 2026-03-11: Phase 3: Active learning inside review UX
- [x] 2026-03-11: Phase 4: Adapter experiment track shipped with rollout gate still closed
- [ ] Phase 5: collect more Fox-family labels, rerun slice gates, and decide whether any matcher change graduates from shadow
- [ ] Scale path: keep PRD-038 local-first, but move offline scoring / retraining to queued cloud workers once local runtime, volume, or admin-concurrency thresholds are breached

### Near-Term — Infrastructure
- [ ] ENV-001: Dev/staging/prod environment separation — `SENTRY_ENVIRONMENT=development` in local `.env` (immediate), disable Sentry in local dev (medium-term), full env split (long-term). See OD-008, BACKLOG.md.
- [ ] OBS-001: Observability data retention — Sentry 90-day, PostHog 1-year. Export to Supabase if longer needed. See OD-009.
- [x] 2026-03-17: AUDIT-001: Audit logging foundation — 22 audit_log calls across route files, new app/audit.py. Remaining: entity timelines on `/person` + `/photo`, canonical actor fields. See `docs/BACKLOG.md`.

### Near-Term — Platform
- [ ] PRODUCT-002: Face Compare Tier 2 — consolidated into TOOLS-003 (depends on TOOLS-002 ML service)
- [ ] PRODUCT-003: NL Archive Query — consolidated into TOOLS-004 (PRD-032)
- [ ] Schema additions: previous_date_estimate, gedcom_token_count on gemini_api_calls (AD-211)
- [ ] Multi-GEDCOM support — merge/dedup architecture for community GEDCOM uploads

### Near-Term — Workspace & Onboarding (PRD-036)
Self-service workspace for users. See `docs/prds/036_workspace_onboarding.md`.

- [ ] WORKSPACE-001: Personal archive auto-creation on signup — 1 session. **Agent team candidate** — auth, upload, permissions, UI layers in parallel. See `docs/architecture/PARALLEL_AGENT_STRATEGY.md`.
- [ ] WORKSPACE-002: Sharing mode UX (Help Identify for members) — 1-2 sessions, depends on WORKSPACE-001
- [ ] WORKSPACE-003: Add photos to community flow — 1-2 sessions, depends on WORKSPACE-001
- [ ] WORKSPACE-004: Anonymous contributions with session tracking — 1 session
- [ ] WORKSPACE-005: Community discovery page (`/communities`) — 1 session
- [ ] WORKSPACE-006: Per-community permissions enforcement — 2 sessions

### Future Evaluation: Frontend Framework Migration
- **Trigger:** If 3+ JS embeds require shared state, or mobile UX audit scores below acceptable after Session 74
- **Options:** React SPA with FastAPI backend, or Next.js with Supabase direct
- **Queued by:** HD-022 (Session 74)
- **Status:** NOT YET TRIGGERED

### Future
- [ ] PRODUCT-004: Historical Photo Date Estimator Standalone — consolidated into TOOLS-001 (PRD-034)
- [ ] PRODUCT-005: Face Compare Tier 3 — product grade, consolidated into TOOLS-002 (PRD-034)
- [ ] PRODUCT-006: Interactive Photo Chatbot — consolidated into TOOLS-003 (PRD-034)
- [ ] ML service extraction — consolidated into TOOLS-002 (`docs/architecture/ML_SERVICE.md`)
- [ ] pgvector migration (evaluation doc written, DEFERRED until 5K+ embeddings)
- [ ] GEN-001+: Multi-tenant architecture

See [docs/BACKLOG.md](docs/BACKLOG.md) for full details on each item.
See [docs/prds/034_standalone_tool_suite.md](docs/prds/034_standalone_tool_suite.md) for standalone tools master plan.

## Planned Sessions

All planned sessions through 114 are COMPLETE. See Recently Completed below and [docs/roadmap/SESSION_HISTORY.md](docs/roadmap/SESSION_HISTORY.md) for details.

All planned sessions through 105b are COMPLETE. See Recently Completed above and [docs/roadmap/SESSION_HISTORY.md](docs/roadmap/SESSION_HISTORY.md) for details. Prompts in `docs/prompts/`.

## Recently Completed

- [x] 2026-03-18: **v0.99.28 — Session 118**: ML Service Fix + Codex Audit + Security Hardening. CRITICAL: Fixed ML service port mismatch (never deployed successfully before). Fixed image_size format mismatch. Codex CLI cross-AI audit (HD-028): mixed value, adopt for security scopes only. Upload community override security fix (Codex finding). ML health endpoint `/api/admin/ml-health`. AD-229: defer local ML removal. TOOLS-002 Phase 4 verified (already wired). 6 new tests. Deploy SUCCESS for both services.

- [x] 2026-03-18: **v0.99.27 — Session 117**: Upload Pipeline Wired to ML Service (TOOLS-002 Phase 3). detect_faces() wrapper with ML service + local fallback. One-line call site change. 10 tests. Feature flag via ML_SERVICE_URL.

- [x] 2026-03-18: **v0.99.26 — Session 116**: ML Service Railway Deployment (TOOLS-002 Phase 2). ML service deployed as separate Railway internal service. rootDirectory monorepo pattern. ML client completed with 10 tests.

- [x] 2026-03-18: **v0.99.25 — Session 115**: Community Routing Safety + ML Service Extraction Phase 1. PRD-052 community routing audit (120+ routes classified, 27 safety tests). TOOLS-002 Phase 1: standalone FastAPI ML service skeleton with detect endpoint + Dockerfile + 9 tests. ML client HTTP stub. AD-228: ml_runs provenance schema (execution_environment, model_versions, community_id, scope_filter) + run logger + 18 tests. 3214 app tests pass.

- [x] 2026-03-17: **v0.99.23 — Session 114**: Data Stability Completion (PRD-051 Phases 2+4). Proposals, annotations, relationships, GEDCOM matches all read from Supabase with TTL caches. Deploy pipeline cleaned (only embeddings.npy required). Supabase health check at startup. DATA-009 reconciliation script (dry-run mode). PERF-001 achieved: make test-fast 87s → 28s. SESSION_HISTORY backfilled. 30 new tests. 3166 app tests, 590 ML tests pass. Deploy SUCCESS.

- [x] 2026-03-17: **v0.99.22 — Session 113**: Audit Logging + Embeddings Sync. AUDIT-001 (P0): 22 audit_log calls across identity_routes, match_facecompare_routes, cluster_review_routes. New app/audit.py. Production embeddings synced (2957 entries, +85 from web uploads). Harry Fox cluster verification: 3/4 Dayton faces closer to Albert than naturalization form ground truth. CLUSTER-QUALITY-001 logged. 16 new tests. Deploy SUCCESS.

- [x] 2026-03-17: **v0.99.21 — Session 112**: Single Source of Truth (PRD-051 Phase 1). Supabase is the only read source for identities and photos — no JSON fallback. `_build_caches()` refactored to remove `json.load(photo_index.json)`. `_load_photo_dimensions_cache()` simplified. DATA_SOURCE default "json"→"postgres". JSON writes kept as backup only. 6 FB items verified (5 working, 1 deferred). Session 111f perf preserved. 14 new tests. 4584 app tests pass. Deploy SUCCESS.

- [x] 2026-03-17: **v0.99.20 — Session 111f**: Performance Overhaul. Vectorized confirmed identity distance via precomputed L2-normalized embedding matrix (`app/perf_cache.py`). Smart cache invalidation — surgical per-identity instead of full flush. `find_nearest_neighbors_fast()` added to `core/neighbors.py`. Focus mode 124ms (was 3-5s), Speed-run 171ms, Neighbors API 142ms. FB-036/037 tag persistence verified correct. FB-040 browse mode OOB delete verified present. 23 new tests. Deploy SUCCESS.

- [x] 2026-03-17: **v0.99.19 — Session 111e**: Performance + Fix Sprint. TTL caches for suggestions (30s) and speed-run clusters (30s) with invalidation on every identity mutation. FB-077 confirm button inline error for unidentified persons. FB-075 face overlay fix via Supabase photo registry. Focus URL preservation (`hx-push-url=false`). FB-072 approval history section. 8 new tests. Deploy SUCCESS.

- [x] 2026-03-17: **v0.99.18 — Session 111d**: Feedback Fix Sprint. FB-069 targeted Supabase writes (1 identity vs ~3400 per confirm). FB-065 merged identity search. FB-066 green checkmark error message. FB-036/037 tag save failure surfaced. FB-044 best match dedup. FB-048 Speed Loop view person link. FB-040 focus mode OOB fix. FB-070 CI fix. Face overlay cache invalidation for new uploads. FB-068 auto-merge attempted and REVERTED (needs PRD). 18 new tests. Deploy SUCCESS.

- [x] 2026-03-17: **v0.99.17 — Session 111c**: Proposals Page Rebuild + Triage Fixes. Proposals page rebuilt with face thumbnails, confidence tiers, action buttons. FB-039/055/067 fixed (bulk merge feedback, select-all, server-side search). Speed-run lazy-load enrichment (FB-025). Next Cluster button (FB-027). FB-068/069/070 documented. Deploy SUCCESS.

- [x] 2026-03-16: **v0.99.16 — Session 111 + 111b**: Community Prefix Sweep + UX Fix Sprint. 80+ community prefix gaps fixed across 11 route files (3 parallel worktree subagents). Regression test `test_community_prefix_audit.py` prevents future gaps. FB-026 suggestions sorted by embedding distance. FB-052 confirm button shows merge context. FB-059 discovery loading skeleton. COMMUNITY-015 substantially resolved. 4519 tests pass. Deploy SUCCESS.

- [x] 2026-03-16: **v0.99.15 — Session 109 + 109b**: Cross-Batch Clustering (PRD-049). `core/cross_batch_matching.py` compares new faces against ALL existing identities. Wired into upload pipeline, admin recluster, and post-confirm. 1355 cross-batch matches, 1130 proposals written to production. Recluster Supabase writes, community filter fix, CI green. James Fields Person 3474 validated at distance 0.87. AD-226. 20 tests. Deploy SUCCESS.

- [x] 2026-03-16: **v0.99.13 — Session 108b**: Bug Fix Sprint. FB-013 Compare button on person page fixed. FB-014 "View Photo" link made prominent. FB-015 sidebar photo search. Collage override NameError fix. 8 new tests. Deploy SUCCESS.

- [x] 2026-03-16: **v0.99.12 — Session 108**: Gap Closure, Data Integrity Fix, Deploy. 25 unpushed commits deployed (Sessions 106b-107b). 13 orphan faces repaired (9 James Fields + 4 pre-existing). Startup orphan detection auto-repair. Embeddings sync endpoint `/api/sync/embeddings`. Data health endpoint `/api/health/data`. Push verification in stop-gate.sh. COMPARE-002 backlog item (community-scoped compare). Lessons 146-148. 8 new tests. Deploy SUCCESS.

- [x] 2026-03-16: **v0.99.11 — Session 107b**: Community Middleware Audit + Approvals UX. Community explicit flag, upload community override, approval timestamps, auto-confirm, annotation provenance, person page name provenance, pending upload auto-expiry. Hook system redesign (3 modes). 23 new tests.

- [x] 2026-03-16: **v0.99.10 — Session 106b**: Triage Fix Sprint. 7 P1 feedback items fixed from Session 106 user triage. FB-007: photo filename search. FB-001: match view community prefix fix. FB-002: source photo thumbnails in match mode. FB-003: View Photo/Person links. FB-006: Same Person loading state. FB-008: reciprocal rank indicator in Find Similar. FB-011: prominent compare context with rank info. 5 P2 items logged to BACKLOG. 11 new tests, 2989 app tests pass. Deploy SUCCESS.

- [x] 2026-03-15: **v0.99.9 — Session 105/105b**: Write-Through Data Integrity. P0 split-brain fix: save_photo_registry() now writes photo_faces to Supabase (was missing), save_registry() Supabase path made synchronous (was background thread), upload pipeline errors use logging.error (was print). Health parity fix: compare total identities including merged. Production reconciliation: 1 stale photo pruned, 0 stale identities. Startup parity check in background thread. Reconciliation endpoint + CLI. DATA-015 fixed: wired dead sync_birth_year_estimate() and sync_person_comment() into app routes. AD-225. 15 structural prevention tests covering all write paths (core tables, secondary tables, community tables, date estimation) + 28 regression tests. Lessons 144-145. data_parity.synced=true on production. Deploy SUCCESS.

- [x] 2026-03-15: **v0.99.8 — Session 104b**: P0 Face Tagging Fix. Root cause: Supabase anchor_ids stored as JSON text strings instead of JSONB arrays — load_from_postgres() iterated characters instead of face IDs. Fix: _ensure_list() read guard, _ensure_list_for_supabase() write guard, 20 Supabase rows repaired. Hook enforcement audit: 4 broken hooks fixed (all now exit 2). test-gate.sh fast mode uses targeted core tests. Lessons 142-143. 3 new tests, 4380 app tests pass. Both Robert Mattatia photos browser-verified on production. Deploy SUCCESS.

- [x] 2026-03-15: **v0.99.7 — Session 104**: Fix Contributor UX + Claude Benatar Photos. P0 upload pipeline fixes: 404 after approval (compare_mode detection), anonymous attribution (auth gate removed), missing thumbnails (R2 path fix). Auto-approve for logged-in contributor uploads. Robert Mattatia photos ingested (2 photos, 20 faces, Congo group + family group). Gemini deep comparison: 2.5 Pro 9/10, 3.1 Pro 8.5/10 confidence — ML false negative from periocular occlusion. Both API calls logged. Lesson 140 (hooks exit 0). Pre-work hook threshold 2→1. 10 new tests, 4377 app tests pass. 2/2 photos browser verified. Deploy SUCCESS.

- [x] 2026-03-15: **v0.99.6 — Session 103**: ML Pipeline Execution + Triage Fixes. PRD-046 ml_runs + ml_proposals Supabase tables. Baseline clustering: 470 proposals (86 VERY HIGH, 384 HIGH). Reranker shadow comparison: Neutral (0 changes, not activated). compare_ml_runs.py diff tool. Community-scoped suggestions (find-similar + speed-run). P0 fixes: FB-168 tag search assignment, FB-150 clickable suggestion thumbnails. P1 fixes: FB-153 identify community lookup, FB-159/160 similar panel CONFIRMED ranking, FB-162 tag search prioritization. Session 102 test gaps closed (TEST-003, TEST-004, OBS-003). 14 P2 BACKLOG entries. 61 new tests, 4357 app tests pass. 5/5 browser verified. Deploy SUCCESS.

- [x] 2026-03-14: **v0.99.5 — Session 102**: Performance + Speed Loop fix + Navigation wiring. BUG-001 P0 fix (face lookup cache cleared in Postgres save path). DATA-019 community reassignment (Rhodes photos removed from Fox Family). DATA-020 Postgres name protection guard. Connected triage navigation (Identify Mode → Speed Loop, face click → per-face, back-to-queue). GEDCOM search optimization (trigram index, 3-char min). Similar panel community scoping. PRD-045 Active Learning Feedback Loop + PRD-046 ML Run Provenance. Unwired route detection test (TEST-002). 10/12 browser checks PASS. Health: 1922 identities, 941 photos. Session froze during Phase 5, recovered by second instance. Phase 8 (triage sprint) deferred to next session.

For sessions 59C–101 (v0.62.0–v0.99.4): see [docs/roadmap/SESSION_HISTORY.md](docs/roadmap/SESSION_HISTORY.md).

## Reference Documents
- Detailed backlog: `docs/BACKLOG.md`
- Feature status: `docs/roadmap/FEATURE_STATUS.md`
- ML roadmap: `docs/roadmap/ML_ROADMAP.md`
- Session history: `docs/roadmap/SESSION_HISTORY.md`
- ML decisions: `docs/ml/ALGORITHMIC_DECISIONS.md`
- Ops decisions: `docs/ops/OPS_DECISIONS.md`
- UX audit: `docs/ux_audit/UX_ISSUE_TRACKER.md`
- Lessons learned: `tasks/lessons.md`
