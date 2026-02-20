# Rhodesli: Project Backlog

**Version**: 26.0 — February 20, 2026
**Status**: 2486 tests passing, v0.54.1, 271 photos, 46 confirmed identities, 181 faces, 267 geocoded
**Live**: https://rhodesli.nolanandrewfox.com

---

## Current State Summary

Rhodesli is an ML-powered family photo archive for the Rhodes/Capeluto Jewish heritage community. It uses InsightFace/AdaFace PFE with MLS distance metrics, FastHTML for the web layer, Supabase for auth, Railway for hosting, and Cloudflare R2 for photo storage. Admin: NolanFox@gmail.com (sole admin). 50 sessions have delivered deployment, auth, core UX, ML pipeline, stabilization, share-ready polish, ML validation, sync infrastructure, family tree, social graph, map, timeline, compare tool, sharing design system, feature audit polish, match page polish, year estimation tool, community bug fixes, estimate page overhaul, and 2401 tests. Community sharing live on Jews of Rhodes Facebook group with 3 active identifiers.

---

## Active Bugs

**All P0 bugs resolved.** BUG-001 through BUG-009 fixed as of v0.50.0.
Details: [docs/backlog/FEATURE_MATRIX_FRONTEND.md](backlog/FEATURE_MATRIX_FRONTEND.md#1-bugs)

### Deferred from Session 49B Audit (Medium/Low)
- **M2**: Compare file input lacks preview feedback — dropzone shows "Drop a photo here" after file selection, no filename or thumbnail. See: `docs/ux_audit/session_findings/session_49b_audit.md`
- **L1**: Login inputs missing `autocomplete` attribute (browser warning)
- **L2**: Tailwind CDN development warning in console (move to production build)
- **L3**: Landing stats counter visible at 0 before scroll triggers IntersectionObserver animation
- **Pre-existing test ordering bug**: `test_nav_consistency` `/map` test fails in full suite (state pollution), passes in isolation. Not caused by audit session.

---

## Latest: Session 49B-Audit (v0.55.1 — 2026-02-20)

- Comprehensive Playwright-first site audit: 18 pages, 25+ user actions tested
- **H1 FIXED**: Mobile navigation on all public pages (global JS hamburger + overlay)
- **M1 FIXED**: Styled 404 catch-all handler for unknown routes
- **M3 FIXED**: subprocess.DEVNULL in approve-upload handler → file logging
- **M4 FIXED**: Missing favicon (inline SVG)
- Triage fixes verified: upload (Bug 1), compare (Bug 2), sort routing (Bug 3)
- 13 new tests (2509 total)
- Audit findings: docs/ux_audit/session_findings/session_49b_audit.md

---

- Hybrid detection: det_500m + w600k_r50 for compare/estimate uploads (AD-114)
- Real upload testing: 4 tests, all pass, 0.3-1.3s response times
- Production smoke test script: scripts/production_smoke_test.py (11 paths)
- Production verification harness rule: .claude/rules/production-verification.md (HD-010)
- UX tracker coverage verified: 35/35 issues mapped
- 5 new tests (2486 total)

## Session 54 (v0.54.0 — 2026-02-20)

- Compare upload: 640px ML resize (was 1024px), split display/ML paths (AD-110)
- buffalo_sc investigated: incompatible embeddings (different backbone)
- AD-110 Serving Path Contract, AD-111-113 (face lifecycle, Modal rejected, ML removal rejected)
- UX Issue Tracker: 35 issues with dispositions (docs/ux_audit/UX_ISSUE_TRACKER.md)
- HTTP 404 for non-existent person/photo pages (was 200)
- Estimate loading indicator enhanced with spinner
- 1 new test (2481 total)

## Session 53 (v0.53.0 — 2026-02-20)

- Comprehensive production audit: 35 routes tested, all healthy
- Compare upload fixes: loading indicator, uploaded photo display, resize optimization
- HTMX indicator CSS dual-selector fix (HD-009)
- UX audit framework in docs/ux_audit/
- 4 new tests (2480 total)

## Session 52 (v0.52.0 — 2026-02-19)

- ML pipeline on Railway: InsightFace + ONNX Runtime in Docker
- Gemini 3.1 Pro real-time date estimation on Estimate upload
- "Name These Faces" on public photo page (was modal-only)
- Cloud-ready ingest pipeline (DATA_DIR support, R2 auto-upload)
- Health check reports ML status
- 30 new tests (2465 total)

## Session 51 (v0.51.0 — 2026-02-19)

- "Name These Faces" sequential batch identification mode
- PRD-021: Quick-Identify from Photo View
- AD-104: Quick-Identify architecture decision
- 16 new tests (2417 total)

## Session 50 (v0.50.0 — 2026-02-19)

- Estimate page overhaul: face count fix (BUG-009), pagination (24/page), standalone /estimate nav, upload zone
- Compare upload hardening: client/server file type + size validation
- PRD-020: Estimate page overhaul plan (P0/P1/P2 tiers)
- AD-101 (Gemini 3.1 Pro), AD-102 (progressive refinement), AD-103 (API logging)
- PRD-015 updated for Gemini 3.1 Pro + combined API call
- 16 new tests (2401 total)

## Session 49C (v0.49.3 — 2026-02-19)

- Photo page 404 for community/inbox photos — alias resolution in _build_caches()
- Compare upload silent failure — onchange auto-submit on file input
- Version v0.0.0 in admin footer — CHANGELOG.md now in Docker image
- Collection name truncation — 6 remaining locations fixed
- 9 new tests (2387 total)

---

## From Community Sharing Feedback (Session 49C)

### Quick-Identify from Photo View — DONE (Session 51, v0.51.0)
P0 tag dropdown was already implemented. Session 51 added P1 sequential
"Name These Faces" mode: admin clicks button → auto-advances through
unidentified faces left-to-right with progress tracking. See PRD-021.

### Batch Identity Entry from External Source — PARTIALLY DONE (Session 51)
"Name These Faces" sequential mode covers the left-to-right naming
use case. Remaining: bulk text paste ("Albert Cohen, Morris Franco,
Ray Franco") auto-assigned to faces. Deferred to future session.
See: docs/session_context/session_49C_community_feedback.md

### Facebook Integration Research (LOW priority)
The sharing -> comment -> identification loop works manually but is
friction-heavy. Research: can we create a bot or integration that
monitors tagged posts and pulls identifications back into the system?
Alternatively: shareable photo pages with inline commenting that
feeds back to the admin review queue.
See: docs/session_context/session_49C_community_feedback.md

---

## Progressive Refinement Architecture (Session 50)

### Fact-Enriched Re-Analysis (AD-102)
When verified facts accumulate (identities, dates, locations, GEDCOM data),
re-run Gemini analysis with enriched context. Compare old vs new estimates.
Stage for admin review. Build analytical dataset of which facts improve
estimates most. Architecture documented — implementation in Session 52+.

### Comprehensive API Result Logging (AD-103)
Every Gemini API call logged with full prompt/response, cost, comparison
to previous estimates. Enables model comparison and improvement analysis.
Schema defined — implementation with first API calls in Session 52+.

### Estimate Page Remaining (PRD-020 P1/P2)
- [ ] Search/filter by collection, date range
- [ ] Date correction flow — "Know the date?" → Gatekeeper pattern
- [ ] Deep CTAs: "View in archive", "Help identify", "Explore era"
- [ ] Auto-run Gemini on uploaded photos when API key configured

---

## Session 47 (v0.49.0 — 2026-02-18)

- ML Gatekeeper Pattern — ML birth year estimates gated behind admin review (AD-097)
- Bulk review page at /admin/review/birth-years with Accept/Edit/Reject/Accept All High
- Ground truth feedback loop — confirmed data → retraining samples (AD-099)
- Feature Reality Contract harness rule — anti-phantom-feature check (AD-098)
- User Input Taxonomy documentation (AD-100)
- Dynamic version display from CHANGELOG.md (was hardcoded "v0.6.0")
- ROADMAP.md split (394→90 lines) + BACKLOG.md split (558→102 lines)
- AD-097–100. 23 new tests (2365 total)

---

## Immediate Priority (Next 1-2 Sessions)

- [x] **Quick-Identify**: Inline face naming on photo page — DONE (Session 51)
- [x] **Batch Identity Entry**: "Name These Faces" sequential mode — DONE (Session 51)
- [ ] **OPS-001**: Custom SMTP for branded "Rhodesli" email sender
- [ ] **FE-040-043**: Skipped faces workflow for non-admin users
- [ ] **PRODUCT-001: Face Compare Standalone — Tier 1**: New FastHTML app at subdomain. Same InsightFace backend + kinship calibration from Session 32. Stripped-down UI: upload two photos → tiered results → no persistence. Mobile-responsive, privacy-first. Differentiation: "Calibrated against real genealogical data." Estimated 1-2 sessions. See AD-117, docs/session_context/session_54c_planning_context.md Part 2C.

## Near-Term (3-5 Sessions)

- [x] **Gemini 3.1 Pro integration**: Wired to Estimate upload (Session 52). Batch run on 271 photos deferred.
- [ ] **PRD-015**: Face alignment via coordinate bridging (Session 53)
- [ ] **Progressive refinement**: First test with verified facts (AD-102)
- [ ] **FE-041**: "Help Identify" mode for non-admin users
- [ ] **BE-031-033**: Upload moderation queue with rate limiting
- [ ] **ROLE-006**: Email notifications for contributors
- [ ] **ML-053**: Multi-pass Gemini for low-confidence re-labeling
- [ ] **BE-015-016**: Geographic data model + temporal date handling
- [ ] **FE-061-063**: Quick Compare, batch confirmation, browser performance audit
- [ ] **Overnight ML pipeline** — `scripts/ml_pipeline.py` with modes: overnight (full pipeline), interactive (quick), validate (re-check compare results). See session 54B context.
- [ ] **Playwright MCP integration** — Browser-based production testing. `.mcp.json` configured, needs first test run.
- [ ] **Production smoke test in CI** — Auto-run `scripts/production_smoke_test.py` on deploy
- [ ] **ML-070: MLflow Integration — CORAL Training**: Add `mlflow.pytorch.autolog()` to CORAL date estimation training script. Run locally with `mlflow ui`. ~10 lines of code. Portfolio value: demonstrate MLflow proficiency. See AD-116, docs/session_context/session_54c_planning_context.md Part 1B.
- [ ] **PRODUCT-002: Face Compare Tier 2 — Shared Backend**: Shared comparison engine between standalone and Rhodesli. Rhodesli path adds: archive identity matching, upload persistence, date context, contribute-to-archive flow. Public path: compare and discard. See AD-117, docs/session_context/session_54c_planning_context.md Part 2C.

## Medium-Term

- [ ] **OPS-002**: CI/CD pipeline (automated tests, staging, deploy previews)
- [ ] **OPS-004**: Error tracking (Sentry)
- [ ] **QA-005-007**: Mobile viewport tests, UX walkthroughs, performance benchmarking
- [ ] **AN-022**: Cross-reference genealogy databases (Ancestry, FamilySearch, JewishGen)
- [ ] **DOC-010-013**: In-app help, about page, admin guide, contributor onboarding
- [ ] **FE-080-083**: Client-side analytics and admin dashboard
- [ ] **ROLE-004**: Family member self-identification ("That's me!" button)
- [ ] **Admin/Public UX Unification**: Progressive admin enhancement + admin toolbar (deferred from Session 50)
- [ ] **Confidence scores per identification**: Show which results are ground truth vs provisional. Genealogy-specific differentiation. (Source: Expert review, Session 54)
- [ ] **Identity voting / community verification**: Let users confirm/reject ML matches. Improves embeddings over time. (Source: Expert review, Session 54)
- [ ] **Processing Timeline UI**: Per-photo status display for trust restoration. (Source: Expert review, Session 54. See AD-111)
- [ ] **Observability over unit tests**: Prioritize integration tests, per-photo processing timelines, job status visibility. (Source: Expert review, Session 54. See AD-110)

## Medium-Term — New Products & ML (Session 54c)

- [ ] **ML-071: MLflow — Gemini Prompt Tracking**: Track how different Gemini API prompts yield better/worse photo context extraction over time. Log prompt text, model version, output quality metrics per run. See AD-116, docs/session_context/session_54c_planning_context.md Part 1B.
- [ ] **ML-072: MLflow — Local vs Web ML Benchmarking**: Compare InsightFace local inference vs API-based face comparison. Track latency, accuracy, cost per comparison. See AD-116, docs/session_context/session_54c_planning_context.md Part 1B.
- [ ] **PRODUCT-003: NL Archive Query MVP (LangChain)**: Natural language interface: "Show me photos from the 1930s with people who look like [uploaded face]." Chain: face detection → embedding search → date filtering → NL response. Prerequisites: similarity calibration + CORAL + stable identity matching. Estimated 2-3 sessions once prerequisites met. See AD-118, docs/session_context/session_54c_planning_context.md Part 1B.
- [ ] **PRODUCT-004: Historical Photo Date Estimator Standalone**: Upload historical photo → estimate when taken using CORAL model. Genuinely novel — no existing tool offers this. Prerequisite: CORAL model trained and validated. Could combine with face comparison in shared "faces" tool site. See docs/session_context/session_54c_planning_context.md Part 2D.

## EPIC: Interactive Upload UX with SSE Progress (2-3 sessions)

### Why
Compare/estimate uploads take 10-28s with zero feedback. Users think it's broken.
The current UX is: click upload → stare at nothing → maybe results appear.

### What
- Photo preview immediately on upload
- SSE-powered progress bar showing pipeline stage + face count
- Faces populate one-by-one below the photo as detection completes
- Face overlays on photo change colors through pipeline stages
- Fully interactive result when complete (same as other photo views)
- Transition between compare/estimate views with same photo
- Every uploaded photo saved through gatekeeper pipeline
- Support 2-3 concurrent uploads via asyncio.Queue
- Multi-photo upload for compare; single for estimate

### Technical Stack
- SSE (Server-Sent Events) for progress streaming
- HTMX SSE extension (`hx-ext="sse"`) for progressive face rendering
- asyncio.Queue for upload serialization on Railway single-worker
- Gatekeeper pattern for photo persistence

### Sessions Estimate
- Session A: SSE infrastructure + queue + basic progress bar
- Session B: Face-by-face progressive rendering + overlay animations
- Session C: Multi-photo upload + compare/estimate view switching

### Breadcrumbs
- AD-121: Architecture decision
- Session 54G planning context: Full UX specification from Nolan
- PERFORMANCE_CHRONICLE.md: Latency context (10-28s baseline)

## Performance Chronicle Maintenance
- Keep `docs/PERFORMANCE_CHRONICLE.md` updated with future optimizations
- Planned future entries: SSE upload progress, ML pipeline scaling, GPU migration
- Breadcrumbs: docs/PERFORMANCE_CHRONICLE.md, AD-119, AD-120

## Long-Term

- [ ] **BE-040-042**: PostgreSQL migration (JSON won't scale past ~500 photos)
- [ ] **ML-030-032**: Model evaluation (ArcFace, ensemble, fine-tuning)
- [ ] **GEN-001+**: Multi-tenant architecture (if traction)
- [ ] **AI-001/003-005**: Auto-caption, photo restoration, handwriting OCR, story generation
- [ ] **GEO-003**: Community-specific context events (diaspora cities)
- [ ] **KIN-001**: Kinship recalibration post-GEDCOM
- [ ] **Session 43**: Life Events & Context Graph (event tagging, richer timeline)
- [ ] **PRODUCT-005: Face Compare Tier 3 — Product Grade**: User accounts, saved comparisons, API access, batch comparison. Post-employment priority. See AD-117, docs/session_context/session_54c_planning_context.md Part 2C.

---

## Next Sessions (Prioritized)

### Session 49B (Interactive — requires Nolan)
- Birth year bulk review (generate ground truth anchors)
- Real GEDCOM upload + match review
- Visual walkthrough of all features
- Bug list from manual testing
- See: [docs/session_context/session_49_interactive_prep.md](../session_context/session_49_interactive_prep.md)

### Session 55: Landing Page Refresh + Lazy Loading
- Landing page: live-data entry points, mobile-first
- Timeline/Photos lazy loading (271 images, needed before 500)
- Activity feed enrichment (more event types)

### Session 56: ML Architecture Evolution
- MediaPipe client-side face detection
- Docker image slimming (target <500MB)
- Upload pipeline wiring (AD-110)

---

## Execution Phases

### Phase A: Stabilization — COMPLETE (2026-02-08)
All 9 bugs fixed. 103+ new tests. Event delegation pattern established.

### Phase B: Share-Ready Polish — MOSTLY COMPLETE (2026-02-06 to 2026-02-19)
Landing page, search, mobile, sync, photo viewer, timeline, compare, sharing, year estimation, estimate overhaul.
Remaining: OPS-001 (branded email).

### Phase C: Annotation Engine — COMPLETE (2026-02-10 to 2026-02-13)
Photo/identity annotations, merge safety, GEDCOM, suggestion lifecycle.

### Phase D: ML Feedback & Intelligence — MOSTLY COMPLETE (2026-02-09 to 2026-02-19)
Threshold calibration, golden set, date estimation pipeline, Gemini 3.1 Pro wired to Estimate upload, ML on Railway.
Remaining: ML-053 (multi-pass Gemini), FE-040-043, progressive refinement, batch Gemini run on 271 photos.

### Phase E: Collaboration & Growth — IN PROGRESS
Contributor roles done. Community sharing live. Quick-Identify + "Name These Faces" done (Session 51). Remaining: Help Identify mode, upload moderation, notifications.

### Phase F: Scale & Generalize — FUTURE
PostgreSQL migration, CI/CD, model evaluation, multi-tenant.

### Harness Engineering — BACKLOG
- [ ] HARNESS-001: Evaluate Ralph Wiggum for overnight runs after 3+ sessions with verification gate (see HD-001)
- [ ] HARNESS-002: Consider native Tasks system for sessions with independent phases (see HD-001)
- [ ] HARNESS-003: Build session log analyzer script for docs/session_logs/*.md patterns (see HD-005)

---

## Sub-Files

| File | Content |
|------|---------|
| [docs/backlog/COMPLETED_SESSIONS.md](backlog/COMPLETED_SESSIONS.md) | All completed session history (Sessions 1-46) |
| [docs/backlog/FEATURE_MATRIX_FRONTEND.md](backlog/FEATURE_MATRIX_FRONTEND.md) | Bugs + Front-End/UX items (Sections 1-2) |
| [docs/backlog/FEATURE_MATRIX_BACKEND.md](backlog/FEATURE_MATRIX_BACKEND.md) | Backend + ML + Annotations + Infra (Sections 3-6) |
| [docs/backlog/FEATURE_MATRIX_OPS.md](backlog/FEATURE_MATRIX_OPS.md) | Testing + Docs + Roles + Vision (Sections 7-10) |
