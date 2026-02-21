# Rhodesli: Project Backlog

**Version**: 28.0 — February 21, 2026
**Status**: 2909 tests passing, v0.56.3, 271 photos, 54 confirmed identities, 662 total identities, 267 geocoded
**Live**: https://rhodesli.nolanandrewfox.com

---

## Current State Summary

Rhodesli is an ML-powered family photo archive for the Rhodes/Capeluto Jewish heritage community. It uses InsightFace/AdaFace PFE with MLS distance metrics, FastHTML for the web layer, Supabase for auth, Railway for hosting, and Cloudflare R2 for photo storage. Admin: NolanFox@gmail.com (sole admin). 50 sessions have delivered deployment, auth, core UX, ML pipeline, stabilization, share-ready polish, ML validation, sync infrastructure, family tree, social graph, map, timeline, compare tool, sharing design system, feature audit polish, match page polish, year estimation tool, community bug fixes, estimate page overhaul, and 2401 tests. Community sharing live on Jews of Rhodes Facebook group with 3 active identifiers.

---

## Active Bugs

### P0 — Blocks Core Workflow
- ~~**UX-036**: Merge button 404~~ FIXED (Session 49D)
- ~~**UX-070-072**: Name These Faces broken on /photo/ pages~~ FIXED (Session 49D)
- ~~**UX-044/052**: Compare/Estimate upload messaging~~ FIXED (Session 49D/49E)

### P1 — Significant Friction
- **UX-037-038**: Merge direction unintuitive + operations on merged-away IDs return 200 silently
- **UX-039**: No admin controls on /person/ page (no rename/confirm/merge)
- **UX-042**: /identify/{id} shareable page has no link to source photo (critical for community onboarding)
- **UX-045-046**: No loading indicator + no auto-scroll on compare upload results
- **UX-053-057**: Estimate upload: no photo preview, no loading, no CTAs, dead end
- **UX-080**: 404 page unstyled — Tailwind not loading
- **UX-081**: About page missing navbar
- **UX-092**: Birth year Save Edit race condition (click interference)

### Deferred from Earlier Audits (Medium/Low)
- **M2**: Compare file input lacks preview feedback
- **L1**: Login inputs missing `autocomplete` attribute
- **L2**: Tailwind CDN development warning
- **L3**: Landing stats counter shows 0 before scroll
- **Pre-existing**: `test_nav_consistency` `/map` state pollution (passes in isolation)

Full tracker: [docs/ux_audit/UX_ISSUE_TRACKER.md](../docs/ux_audit/UX_ISSUE_TRACKER.md) — 100 issues total

---

## Recent Sessions (v0.56.3 — 2026-02-21)

- **Session 49E** (v0.56.3): Stabilization. 130 test state-pollution failures fixed (ExitStack). All 49D fixes verified in production (10/10 PASS). 2909 total tests.
- **Session 49D** (v0.56.2): 12 UX bugs fixed (6 P0 + 6 P1). Name These Faces, upload messaging, merge URL, birth year race condition. 35 new tests.
- **Session 49B** (v0.56.1): Interactive review. 28 birth years accepted, GEDCOM import (33 matches), 67 UX issues compiled. 54 confirmed identities.
- **Sessions 50-54** (v0.50-0.54): ML on Railway, Gemini integration, hybrid detection (AD-114), compare 4.9x perf fix, Name These Faces, Estimate overhaul, UX tracker, 428 tests added. See docs/roadmap/SESSION_HISTORY.md.
- **Session 49C** (v0.49.3): Community bug fixes, alias resolution, compare auto-submit.

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

- [x] **Gemini 3.1 Pro integration**: Wired to Estimate upload (Session 52).
- [ ] **ML-075: Batch Gemini Run on 271 Photos**: Run date estimation on all existing photos. Deferred from Session 52.
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
- [ ] **COMMUNITY-001: Nancy Gormezano Beta Test**: Engage Nancy as first non-family beta tester. Source: Session 49C community thread.
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
- [ ] **GEO-004: Geographic Migration Analysis**: Combine Gemini-extracted locations with GEDCOM data to trace family migration patterns (Rhodes → diaspora cities). Source: Session 54c planning.
- [ ] **KIN-001**: Kinship recalibration post-GEDCOM (19 relationships now available)
- [ ] **Session 43**: Life Events & Context Graph (event tagging, richer timeline)
- [ ] **PRODUCT-005: Face Compare Tier 3 — Product Grade**: User accounts, saved comparisons, API access, batch comparison. Post-employment priority. See AD-117.
- [ ] **GRAPH-001: "Six Degrees" Connection Finder**: Graph traversal showing shortest path between any two people in the archive via photos, family, events. Novel feature. Source: Session 54c planning.
- [ ] **ML-080: DNA Matching Integration**: Explore DNA-based family matching as complement to face comparison. Community interest from Leo Di Leyo (Facebook). Source: Session 49C community feedback.
- [ ] **PARTNER-001: Institutional Partnership**: Museum/archive collaboration for expanded photo access and academic credibility. Source: Session 49C community feedback.
- [ ] **UX-110: Three-Mode Cognitive Framing**: Explore/Investigate/Curate modes with progressive complexity. Adopted conceptually, not yet built. Source: Session 50 planning.

---

## Next Sessions (Prioritized)

### Session 55: Similarity Calibration + Backlog Audit (CURRENT)
- Learned calibration layer on frozen InsightFace embeddings
- PyTorch Lightning + MLflow experiment tracking
- PRD-023, SDD-023, full training pipeline + evaluation

### Session 56: Landing Page Refresh + P1 UX Polish
- Landing page: live-data entry points, mobile-first
- Timeline/Photos lazy loading (271 images, needed before 500)
- P1 UX fixes from UX tracker

### Session 57: CORAL Date Estimation Model
- PyTorch portfolio centerpiece

### Session 58: MLflow Integration + Experiment Dashboard

### Session 59: Face Compare Standalone Tier 1 (PRODUCT-001)

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
