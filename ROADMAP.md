# Rhodesli Development Roadmap

Heritage photo identification system. FastHTML + InsightFace + Supabase + Railway + R2.
Current: v0.54.2 · 2486 tests · 271 photos · 181 faces · 46 confirmed

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
- JSON data files won't scale past ~500 photos — Postgres migration is on the horizon
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
- [ ] Similarity calibration on frozen embeddings — Very High portfolio value
- [ ] Fix production UX issues — phantom features, broken loading, missing nav
- [ ] **PRODUCT-001: Face Compare Standalone Tier 1** — quick win, shippable demo (AD-117)

### Next (After Immediate)
- [ ] CORAL date estimation training — PyTorch portfolio centerpiece
- [ ] ML-070: MLflow integration — add to CORAL training script (AD-116)
- [ ] OPS-001: Custom SMTP for branded email sender

### Medium-Term
- [ ] PRODUCT-002: Face Compare Tier 2 — shared backend architecture (AD-117)
- [ ] ML-053: Multi-pass Gemini — low-confidence re-labeling
- [ ] FE-041: "Help Identify" mode for non-admin users
- [ ] Active learning pipeline

### Future
- [ ] PRODUCT-003: NL Archive Query MVP — LangChain (AD-118)
- [ ] PRODUCT-004: Historical Photo Date Estimator Standalone
- [ ] BE-040–042: PostgreSQL migration
- [ ] OPS-002: CI/CD pipeline
- [ ] PRODUCT-005: Face Compare Tier 3 — product grade (post-employment)
- [ ] GEN-001+: Multi-tenant architecture

See [docs/BACKLOG.md](docs/BACKLOG.md) for full details on each item.

## Planned Sessions

### Session 49B: Interactive Review (requires Nolan) — OVERDUE
- Birth year bulk review — generate ground truth anchors
- Real GEDCOM upload + match review
- Visual walkthrough of all features
- **This is overdue — schedule this weekend**
- See: docs/session_context/session_49_interactive_prep.md

### Session 55: Landing Page Refresh + Lazy Loading
- Landing page: live-data entry points, mobile-first
- Timeline/Photos lazy loading (271 images, needed before 500)
- Activity feed enrichment (more event types)
- Processing Timeline UI (trust restoration, AD-111)

### Session 56: ML Architecture Evolution
- MediaPipe client-side face detection (replace InsightFace in browser)
- Docker image slimming (target <500MB from current 3-4GB)
- Bounding boxes on uploaded photo for multi-face selection
- Upload pipeline wiring (AD-110)

### Session 43: Life Events & Context Graph (deferred)
- Event tagging: "Moise's wedding in Havana"
- Events connect photos, people, places, dates
- PRD: docs/prds/011_life_events_context_graph.md

## Recently Completed

- [x] 2026-02-20: **Session 54c**: ML Tooling & Product Strategy. Memory infra evaluation (AD-115), MLflow strategy (AD-116), Face Compare 3-tier plan (AD-117), NL Query deferred (AD-118). 8 new BACKLOG entries.
- [x] 2026-02-20: **v0.54.1 — Session 54B**: Hybrid Detection + Testing Infrastructure. buffalo_sc detector + buffalo_l recognizer (AD-114). Real upload testing. Production smoke test script. 5 new tests (2486 total).
- [x] 2026-02-20: **v0.54.0 — Session 54**: Quick Fixes + Architecture. AD-110 Serving Path Contract, AD-111-113. UX Issue Tracker (35 issues). HTTP 404 for non-existent pages. 1 new test (2481 total).
- [x] 2026-02-20: **v0.53.0 — Session 53**: Comprehensive Production Audit. 35 routes tested. Compare upload fixes. UX audit framework. HD-008-009. 4 new tests (2480 total).
- [x] 2026-02-19: **v0.52.0 — Session 52**: ML Pipeline to Cloud. InsightFace + ONNX in Docker. Gemini 3.1 Pro on Estimate upload. 30 new tests (2465 total).

For sessions 1-51: see [docs/roadmap/SESSION_HISTORY.md](docs/roadmap/SESSION_HISTORY.md).

## Reference Documents
- Detailed backlog: `docs/BACKLOG.md`
- Feature status: `docs/roadmap/FEATURE_STATUS.md`
- ML roadmap: `docs/roadmap/ML_ROADMAP.md`
- Session history: `docs/roadmap/SESSION_HISTORY.md`
- ML decisions: `docs/ml/ALGORITHMIC_DECISIONS.md`
- Ops decisions: `docs/ops/OPS_DECISIONS.md`
- UX audit: `docs/ux_audit/UX_ISSUE_TRACKER.md`
- Lessons learned: `tasks/lessons.md`
