# Rhodesli Development Roadmap

Heritage photo identification system. FastHTML + InsightFace + Supabase + Railway + R2.
Current: v0.64.0 · ~3240 tests · 271 photos · 775 identities · 55 confirmed

## Progress Tracking Convention
- `[ ]` = Todo
- `[-]` = In Progress (add date when started)
- `[x]` = Completed (add date when done)
- When completing a task, move it to "Recently Completed" with date
- When starting a task, update checkbox and add start date

## Current State & Key Risks
- ~~Merge direction bug (BUG-003)~~ FIXED — auto-correction + 18 direction tests
- ~~Lightbox arrows~~ FIXED (4th attempt) — event delegation pattern with 16 regression tests
- ~~Face count / collection stats~~ FIXED — canonical functions, 19 regression tests
- ~~JSON data files won't scale past ~500 photos~~ User data migrated to Supabase Postgres (Session 59C). ML data (photo_index, embeddings) still in JSON/NumPy.
- Contributor roles implemented (ROLE-002/003) — needs first real contributor to test
- **ML architecture: AD-110 Serving Path Contract** — web requests NEVER run heavy ML. Compare: 640px + buffalo_l. Batch: local.
- Community sharing live on Jews of Rhodes Facebook group (~2,000 members) — first 3 active identifiers
- Gemini 3.1 Pro wired to Estimate upload (AD-101) — progressive refinement architecture designed (AD-102)

## Active Bugs (P0)
- [x] BUG-001: Lightbox arrows disappear after first photo — fixed with event delegation (2026-02-08)
- [x] BUG-002: Face count label shows detection count, not displayed/tagged count (2026-02-08)
- [x] BUG-003: Merge direction — already fixed in code, 18 direction-specific tests added (2026-02-08)
- [x] BUG-004: Collection stats inconsistency — canonical _compute_sidebar_counts() (2026-02-08)
- [x] BUG-005: Face count badges wildly wrong (63 for 3-person photo) — filter to registered faces (2026-02-09)
- [x] BUG-006: Photo nav dies after few clicks — duplicate keydown handler removed (2026-02-09)
- [x] BUG-007: Logo doesn't link home — wrapped in `<a href="/">` (2026-02-09)
- [x] BUG-008: Client-side fuzzy search not working — JS Levenshtein added (2026-02-09)
- [x] BUG-009: Estimate page shows "0 faces" for all photos — used 'faces' not 'face_ids' (2026-02-19)

## Phase Summary

| Phase | Status | Details |
|-------|--------|---------|
| **A: Stabilization** | COMPLETE | All P0 bugs fixed, 103 tests added |
| **B: Share-Ready Polish** | ~95% complete | 53/54 items done. Remaining: OPS-001 (custom SMTP) |
| **C: Annotation Engine** | COMPLETE | 16/16 items done. Full submit/review/approve workflow |
| **D: ML Feedback** | ~90% complete | Date pipeline + golden set + cloud ML done. Remaining: ML-053 (multi-pass Gemini), FE-040-043 |
| **E: Collaboration** | ~70% complete | Contributor roles + activity feed + Quick-Identify + "Name These Faces" done. Remaining: Help Identify mode, analytics, moderation queue |
| **F: Scale & Generalize** | ~10% complete | Playwright tests done. Remaining: Postgres, CI/CD, Sentry, model eval |

For full feature checklists, see [docs/roadmap/FEATURE_STATUS.md](docs/roadmap/FEATURE_STATUS.md).
For ML-specific roadmap, see [docs/roadmap/ML_ROADMAP.md](docs/roadmap/ML_ROADMAP.md).

## Open Work (Prioritized — confirmed Session 54c)

### Immediate (Current Sprint)
- [x] **ML-076: Similarity Calibration on Frozen Embeddings** — Session 55. F1@0.5 improved 4.8x (0.13→0.60). 33K param Siamese MLP + MLflow. (2026-02-21)
- [x] Fix production UX issues — 12 bugs fixed (49D): 6 P0 + 6 P1, 35 new tests (2026-02-21)
- [x] **ML-070: MLflow Model Registry + Promotion Pipeline** — Session 58, v0.60.0, both ONNX models registered with @champion aliases, automated gate → register → alias → export pipeline (2026-02-21)
- [x] **PRODUCT-001: Face Compare Standalone Tier 1** — Session 59, v0.61.0 (2026-02-21)

### Next
- [x] CORAL date estimation → ONNX production serving (Session 57, v0.59.0, 2026-02-21)
- [ ] OPS-001: Custom SMTP for branded email sender (code ready, needs RESEND_API_KEY in Railway)

### Medium-Term
- [x] **EPIC: Interactive Upload UX with SSE Progress** — Session 60 (AD-121, SSE endpoint + progressive UI) (2026-02-22)
- [ ] PRODUCT-002: Face Compare Tier 2 — shared backend architecture (AD-117)
- [ ] ML-053: Multi-pass Gemini — low-confidence re-labeling
- [ ] FE-041: "Help Identify" mode for non-admin users
- [ ] Active learning pipeline

### Future
- [ ] PRODUCT-003: NL Archive Query MVP — LangChain (AD-118)
- [ ] PRODUCT-004: Historical Photo Date Estimator Standalone
- [ ] OPS-002: CI/CD pipeline
- [ ] PRODUCT-005: Face Compare Tier 3 — product grade (post-employment)
- [ ] GEN-001+: Multi-tenant architecture

See [docs/BACKLOG.md](docs/BACKLOG.md) for full details on each item.

## Planned Sessions

### Session 61: Gemini Photo Detective + Multi-Photo Compare + ML Iteration — COMPLETE
- [x] ML-090: Fix enriched prompt gap — call_gemini() now accepts custom prompt, run_refinement() passes it (2026-02-22)
- [x] ML-094: Write ADs — AD-139 (Gemini 3.1 Pro), AD-140 (MLflow), AD-141 (Multi-Photo), AD-142 (Photo Detective) (2026-02-22)
- [x] Gemini 3.1 Pro upgrade + MLflow tracking module (2026-02-22)
- [x] Multi-photo compare upload (PRD-021, 2-5 photos, cross-match + archive) (2026-02-22)
- [x] Photo Detective UX (PRD-022, evidence cards, model badge, refinement badge) (2026-02-22)
- [x] Data integrity report script + verification (2026-02-22)
- Deferred to future: ML-091 (real validation), UX-120 (Help Identify), UX-121 (/contribute)

### Session 49B: Interactive Review (requires Nolan) — COMPLETE
- [x] Birth year bulk review — 31 estimates reviewed, 28 accepted (2026-02-20)
- [x] Real GEDCOM upload + match review — 33 matches, 19 relationships (2026-02-21)
- [x] Enter Carey Franco's 8 IDs (1970s photo, corrected from Thanksgiving 1946) (2026-02-21)
- [x] Isaac Franco + Morris Franco merged and confirmed (2026-02-21)
- [x] Visual walkthrough of all features — 15 pages, 12 issues (2026-02-21)
- [x] Compare/Estimate/Quick-Identify UX audit — 36 issues (2026-02-21)
- [x] Bug compilation — 67 new entries, UX tracker at 100 total (2026-02-21)
- [x] Smoke test 11/11 PASS (2026-02-21)
- See: docs/session_context/session_49b_interactive_log.md

### Session 55: Similarity Calibration + Backlog Audit — COMPLETE
- [x] Learned calibration layer on frozen InsightFace embeddings (2026-02-21)
- [x] PyTorch + MLflow experiment tracking (33K param Siamese MLP)
- [x] PRD-023 + SDD-023 + AD-123/124/125/126
- [x] Backlog/roadmap audit — 8 new items, BACKLOG trimmed
- [x] Integrated into compare pipeline with graceful degradation
- [x] 2961 total tests (2604 app + 357 ML)

### Session 55b: ONNX Production Serving + ML Docs — COMPLETE
- [x] AD-127: Calibration results interpretation (AUC drop = noise, F1 = signal) (2026-02-21)
- [x] Backlog audit verification: 20/20 planning context items tracked (2026-02-21)
- [x] ONNX export: calibration_v1.onnx (129KB, exact numerical match) (2026-02-21)
- [x] Production serving via onnxruntime (ONNX → PyTorch → Euclidean fallback) (2026-02-21)
- [x] AD-128: ONNX Runtime production serving decision (2026-02-21)
- [x] ML_ARCHITECTURE.md: comprehensive ML system docs (178 lines) (2026-02-21)
- [x] 2976 total tests (2604 app + 372 ML)

### Session 56: Landing Page Refresh + P1 UX Polish — COMPLETE
- [x] Phase 1: 12 P1 UX quick wins (merge direction, admin controls, photo preview, loading indicators) (2026-02-21)
- [x] Phase 2: Landing page feature entry point cards (2x3 grid, live stats, PRD-024) (2026-02-21)
- [x] Phase 3: Lazy loading for /photos (24/page) and /timeline (smart decades) (2026-02-21)
- [x] Phase 5: Full production UX audit — all pages verified, smoke test 11/11 (2026-02-21)
- [x] 3003 total tests (2631 app + 372 ML)

### Session 57: CORAL Date Estimation → Production — COMPLETE
- [x] Phase 1: ONNX export — date_estimation_v1.onnx (16.5 MB), validated 50/50 prediction match (2026-02-21)
- [x] Phase 2: Production deployment — DateEstimationService, Dockerfile, health check (2026-02-21)
- [x] Phase 3: /estimate endpoint — CORAL primary, Gemini supplementary, probability bars (2026-02-21)
- [x] Phase 4: Photo viewer — decade probability bars on photo detail pages (2026-02-21)
- [x] Phase 5-6: Verification gate + docs (2026-02-21)
- [x] 3048 total tests (2649 app + 399 ML)

### Session 58: MLflow Model Registry + Promotion Pipeline — COMPLETE
- [x] Phase 0.5: Session 57 deliverables audit (CORAL correct, Gatekeeper minimal) (2026-02-21)
- [x] Phase 1: Model Registry setup — both ONNX models registered with signatures + @champion (2026-02-21)
- [x] Phase 2: promote_model.py — automated gate → register → alias → export pipeline (2026-02-21)
- [x] Phase 3: AD-130, README, CHANGELOG, verification gate (2026-02-21)
- [x] 3068 total tests (2649 app + 419 ML)

### Session 59: Face Compare Standalone Tier 1 (PRODUCT-001) — COMPLETE
- [x] Phase 0: Orient + checkpoint (2026-02-21)
- [x] Phase 1: Museum-quality landing page at /facecompare — serif font, warm palette, no archive nav (2026-02-21)
- [x] Phase 2: Upload flow + InsightFace face detection + CORAL date estimation + multi-face selector (2026-02-21)
- [x] Phase 3: Results page with 3 ML systems — tiered matches, confidence, date bars, archive links (2026-02-21)
- [x] Phase 4: Shareable results at /facecompare/result/{uuid} + bridge CTAs (2026-02-21)
- [x] Phase 5: Verification gate + docs — AD-131/132/133, CHANGELOG, ROADMAP (2026-02-21)
- [x] 3102 total tests (2683 app + 419 ML)

### Session 59B Follow-up: Verify Recovery, Commit, Sync, Cross-Check — COMPLETE
- [x] Committed recovery + deploy safety gate (AD-134) + 21 tests (2026-02-21)
- [x] Pushed to production, verified all 49B identities live (55 confirmed)
- [x] Synced from production — 8 annotations pulled (5 new from production)
- [x] Cross-checked all 8 identities + 3 birth years against session notes: 100% match
- [x] GEDCOM data verified: 19 relationships, 33 ancestry links, CSV now tracked
- [x] ML work verified: ONNX models intact, 419 ML tests pass
- [x] AD-135 Supabase migration plan + DATA-001 recurring incident tracker
- [x] Forward links on Lessons 69/78/85, backward link on AD-134
- [x] Session 59C planning context created
- [x] Email diagnosis: code ready but RESEND_API_KEY not set (no code fix needed)
- [x] 3123 total tests (2704 app + 419 ML)

### Session 59C: Supabase Migration — User Data Safety — COMPLETE
- [x] Migrated user-entered data to Supabase Postgres (AD-135) (2026-02-22)
- [x] 4 Supabase tables: identity_overrides (372), annotations (8), relationships (19), gedcom_matches (33) (2026-02-22)
- [x] Dual-write: save_registry() and _save_annotations() sync to Supabase after JSON save (2026-02-22)
- [x] Startup sync rebuilds JSON cache from Supabase on every deploy (2026-02-22)
- [x] DATA-001 resolved — deploys can never lose user data (2026-02-22)
- [x] 27 new tests for Supabase persistence + deploy safety regression (2026-02-22)
- [x] 3102 total tests (2683 app + 419 ML)

### Session 43: Life Events & Context Graph (deferred)
- Event tagging: "Moise's wedding in Havana"
- Events connect photos, people, places, dates
- PRD: docs/prds/011_life_events_context_graph.md

## Recently Completed

- [x] 2026-02-22: **v0.64.0 — Session 61**: Gemini Photo Detective + Multi-Photo Compare + ML Iteration Loop. Fixed critical enriched prompt gap (ML-090). Upgraded to Gemini 3.1 Pro (AD-139). MLflow experiment tracking (AD-140). Multi-photo compare upload for 2-5 photos with cross-matching (AD-141, PRD-021). Photo Detective UX: evidence cards, model badges, progressive refinement indicators (AD-142, PRD-022). Data integrity report script. ~50 new tests. Test count: ~2776 app + ~474 ML = ~3250 total.
- [x] 2026-02-22: **v0.63.1 — Session 60B**: Production Verification + ML Deep Dive + UX Review. Found+fixed P0 quick-identify CSS selector crash (legacy face IDs with colons/spaces break CSS selectors). ML analysis: progressive refinement pipeline 60% complete — enriched prompt built but never sent to Gemini in real mode. UX review: 7 friction points logged, top 5 improvements prioritized. 2 regression tests added. See `docs/session_logs/session_60b_*.md`. Test count: 2726 app + 466 ML = 3192 total.
- [x] 2026-02-22: **v0.63.0 — Session 60**: Gemini Progressive Refinement + SSE Upload UX + Admin Unification. Three-act session: (1) ML — centralized Gemini config, API logging, progressive refinement pipeline (41 eligible photos with verified facts). (2) UX — SSE streaming upload with progressive stage indicators on /compare and /facecompare, client-side validation, timeout handling. (3) Admin — admin bar component on photo/person pages, quick-identify inline flow with autocomplete. AD-136/137/138. 96 new tests. Test count: 2724 app + 466 ML = 3190 total.
- [x] 2026-02-22: **v0.62.0 — Session 59C**: Supabase Migration for User Data Safety. All user-entered data (confirmations, merges, annotations, birth years, relationships, GEDCOM matches) migrated to Supabase Postgres. 4 tables: identity_overrides (372), annotations (8), relationships (19), gedcom_matches (33). Dual-write pattern ensures every user action persists to both Supabase and JSON cache. Startup sync rebuilds JSON from Supabase on every deploy. DATA-001 (deploy data loss, 5 incidents) structurally resolved. AD-135. Test count: 2683 app + 419 ML = 3102 total.
- [x] 2026-02-21: **v0.61.1 — Session 59B**: Emergency Recovery + Deploy Safety Gate. Recovered 9 identity confirmations, 3 birth years, 2 merges from Railway volume backup. Triple safety gate (AD-134). 21 deploy safety tests. Session 59B follow-up: full cross-check, AD-135 Supabase migration plan, DATA-001 recurring incident tracker, GEDCOM CSV tracked, email system diagnosed. Test count: 2704 app + 419 ML = 3123 total.
- [x] 2026-02-21: **v0.61.0 — Session 59**: Face Compare Standalone. Museum-quality /facecompare page — upload a photo, detect faces, find matches with calibrated confidence, estimate decade. Three ML systems in one flow (InsightFace + Calibration + CORAL). Shareable result URLs. Bridge CTAs to full archive. No login required. Community-agnostic language for future expansion. AD-131/132/133. Test count: 2683 app + 419 ML = 3102 total.
- [x] 2026-02-21: **v0.60.0 — Session 58**: MLflow Model Registry + Promotion Pipeline. Both ONNX models registered in MLflow with signatures, gate tags, and @champion aliases. Automated promotion script (promote_model.py): regression gate → register version → tag results → assign @champion if passed → copy ONNX to artifacts. AD-130. Session 57 audit confirmed CORAL conversion correct. Test count: 2649 app + 419 ML = 3068 total.
- [x] 2026-02-21: **v0.59.0 — Session 57**: CORAL Date Estimation → Production. ONNX export of CORAL date model (16.5 MB, EfficientNet-B0, 11 decades). Production inference module with fallback chain (ONNX→PyTorch→None). /estimate endpoint uses local ML model as primary (instant, free). Gemini as supplementary. Decade probability bars on photo detail pages. Gatekeeper via existing correction UI. AD-129, PRD-025. Test count: 2649 app + 399 ML = 3048 total.
- [x] 2026-02-21: **v0.58.0 — Session 56**: Landing Page Refresh + P1 UX Polish. 12 P1 UX fixes (merge direction, admin controls, photo preview, loading indicators). Feature entry point cards (2x3 grid with live stats). Lazy loading for /photos (24/page infinite scroll) and /timeline (smart initial decades). Full production UX audit (all pages verified). PRD-024. Test count: 2631 app + 372 ML = 3003 total.
- [x] 2026-02-21: **v0.57.1 — Session 55b**: ONNX Production Serving + ML Docs. Calibration model exported to ONNX (129KB). Production now uses onnxruntime (15MB) vs PyTorch (500MB+). Fallback chain: ONNX→PyTorch→Euclidean. AD-127 (results interpretation), AD-128 (ONNX serving). ML_ARCHITECTURE.md (178 lines). Backlog audit: 20/20 items verified. Test count: 2604 app + 372 ML = 2976 total.
- [x] 2026-02-21: **v0.57.0 — Session 55**: Similarity Calibration. Siamese MLP (33K params) on frozen InsightFace embeddings. F1@0.5 improved 4.8x (0.13→0.60), precision@0.5=98%. MLflow tracked. PRD-023, SDD-023, AD-123-126. Integrated into compare pipeline. Backlog audit (8 new items). Test count: 2604 app + 357 ML = 2961 total.
- [x] 2026-02-21: **v0.56.3 — Session 49E**: Stabilization & Verification. Fixed 130 state-pollution test failures (ExitStack). Verified all 49D fixes in production (10/10 PASS). Name These Faces confirmed working end-to-end. Compare/Estimate uploads confirmed saving to R2 (messaging corrected). Test count: 2545 app + 306 ML = 2851 total.
- [x] 2026-02-21: **v0.56.2 — Session 49D**: P0 + P1 Bug Fixes. 12 UX issues fixed (6 P0 + 6 P1). Name These Faces targeting (UX-070-072), upload messaging (UX-044/052), merge URL (UX-036), birth year race condition (UX-092), 404 styling (UX-080), about navbar (UX-081), identify links (UX-042), review polish (UX-100/101). 35 new tests (2544 total).
- [x] 2026-02-21: **v0.56.1 — Session 49B Complete**: Items 5-11 autonomous. Compare/Estimate/Quick-Identify UX audit (36 issues). Visual walkthrough 15 pages (12 issues). Bug compilation: 67 new UX issues (100 total). Smoke test 11/11. 8 people tagged in 1970s photo (Section 3). 54 confirmed identities.
- [x] 2026-02-21: **v0.56.0 — Session 49B Section 2**: Real GEDCOM import (21,809 individuals). 33 identities matched to Ancestry tree via CSV review workflow. 19 relationships (5 spouse, 14 parent-child). ancestry_links.json. Production data merge preserved 31 birth years. Lesson 78 (data sync).
- [x] 2026-02-20: **v0.55.3 — Session 49B-Final**: Compare/estimate loading indicator (block display, button disable, auto-scroll, accurate timing). Test triage: 127 failures all state pollution, 0 real bugs. Admin auth verification documented.
- [x] 2026-02-20: **v0.55.1 — Session 49B-Audit**: Comprehensive Playwright site audit. 18 pages, 25+ user actions. Fixed: mobile nav (H1), styled 404 (M1), subprocess.DEVNULL (M3), favicon (M4). 13 new tests (2509 total).
- [x] 2026-02-20: **Session 54G**: Final Cleanup. AD-120 (silent fallback principle), AD-121 (SSE upload architecture), HD-012, OD-006 (Railway MCP), PERFORMANCE_CHRONICLE.md, browser testing audit, SSE epic documented.
- [x] 2026-02-20: **v0.54.3 — Session 54F**: Compare Performance Fix. 51.2s → 10.5s (4.9x). AD-119. buffalo_sc in Docker, hybrid-only startup, OOM fix.
- [x] 2026-02-20: **Session 54E**: Verification Sweep. 22 deliverables audited, 1 gap closed. Playwright browser tests (8/8). CLAUDE.md Session Operations Checklist.
- [x] 2026-02-20: **Session 54D**: Production Verification + Hybrid Analysis. 11/11 smoke test. Compare upload 51.2s. Hybrid detection analysis doc.
- [x] 2026-02-20: **Session 54c**: ML Tooling & Product Strategy. AD-115-118. Face Compare 3-tier plan. 8 new BACKLOG entries.
- [x] 2026-02-20: **v0.54.1 — Session 54B**: Hybrid Detection + Testing. AD-114. Production smoke test script. 5 new tests (2486 total).
- [x] 2026-02-20: **v0.54.0 — Session 54**: Quick Fixes + Architecture. AD-110-113. UX Issue Tracker (35 issues). 1 new test (2481 total).

For all sessions: see [docs/roadmap/SESSION_HISTORY.md](docs/roadmap/SESSION_HISTORY.md).

## Reference Documents
- Detailed backlog: `docs/BACKLOG.md`
- Feature status: `docs/roadmap/FEATURE_STATUS.md`
- ML roadmap: `docs/roadmap/ML_ROADMAP.md`
- Session history: `docs/roadmap/SESSION_HISTORY.md`
- ML decisions: `docs/ml/ALGORITHMIC_DECISIONS.md`
- Ops decisions: `docs/ops/OPS_DECISIONS.md`
- UX audit: `docs/ux_audit/UX_ISSUE_TRACKER.md`
- Lessons learned: `tasks/lessons.md`
