# Rhodesli: Project Backlog

**Version**: 35.0 — February 23, 2026
**Status**: ~3450 tests passing, v0.67.0, 271 photos, 55 confirmed identities, 775 total identities, 267 geocoded
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

## Recent Sessions (v0.67.0 — 2026-02-23)

- **Session 64** (v0.67.0): Verify, Migrate, Harden. Harness hardening (5 skills, 3 rules, 3 hooks). Face alignment → Supabase. gemini_api_calls tracking. Centralized model config. Combined pipeline. Calibrated scores in UI. Recalibration hooks wired. AD-152. ~50 new tests. ~3450 total.
- **Session 63** (v0.66.0): Close the Gaps, Calibrate, Re-Run. Real photo face alignment (3/3 pass). GEDCOM Supabase import (21,809 individuals, 145,574 relationships). Similarity calibration (AUC=0.9577, 348 pairs). Recalibration hooks. AD-149/150/151. 29 new ML tests. ~3402 total.
- **Session 62** (v0.65.0): PRD-015 Face Alignment via Coordinate Bridging. EXIF handler, coordinate bridging module (app/face_alignment.py), API endpoints (POST/GET /api/face-alignment/{photo_id}), photo page UI with per-face description cards. AD-146. 54 new tests. ~3373 total.
- **Session 61** (v0.64.0): Gemini Photo Detective + Multi-Photo Compare + ML Iteration Loop. Fixed enriched prompt gap (ML-090), upgraded to Gemini 3.1 Pro (AD-139), MLflow tracking (AD-140), multi-photo compare upload 2-5 photos (AD-141, PRD-021), Photo Detective UX with evidence cards (AD-142, PRD-022), data integrity report script. ~50 new tests.
- **Session 60B** (v0.63.1): Production Verification + ML Deep Dive + UX Review. Found+fixed P0 quick-identify CSS selector crash (legacy face IDs with colons/spaces). ML analysis: progressive refinement pipeline 60% complete (enriched prompt built but never sent to Gemini). UX review: 7 friction points, 5 improvement recommendations. See `docs/session_logs/session_60b_*.md`. 3192 total tests.
- **Session 60** (v0.63.0): Gemini Progressive Refinement + SSE Upload UX + Admin Unification. Three-act session: centralized Gemini config (AD-136), API logging (AD-137), progressive refinement pipeline (AD-138), SSE streaming upload on /compare + /facecompare, admin bar, quick-identify inline flow. 96 new tests. 3190 total.
- **Session 59C** (v0.62.0): Supabase Migration for User Data Safety. All user-entered data migrated to Postgres. DATA-001 structurally resolved (AD-135). 3102 total tests.
- **Session 59/59B** (v0.61.0/v0.61.1): Face Compare Standalone Tier 1 + Emergency Recovery. Museum-quality /facecompare page (AD-131/132/133). Deploy safety gate (AD-134). 3123 total tests.
- **Session 58** (v0.60.0): MLflow Model Registry + Promotion Pipeline (AD-130). 3068 total tests.
- **Session 57** (v0.59.0): CORAL Date Estimation → Production. ONNX export (16.5 MB), /estimate uses local ML model (instant, free), decade probability bars on photo detail. 3048 total tests.
- **Sessions 49B-56** (v0.55-0.58): Similarity calibration, ONNX serving, landing page refresh, UX fixes, GEDCOM import. See docs/roadmap/SESSION_HISTORY.md.

---

## Session 60B Findings (2026-02-22)

### ML — Progressive Refinement Completion (P1)
- [x] **ML-090: Fix enriched prompt gap** — DONE (Session 61). `call_gemini()` now accepts `prompt` parameter, `run_refinement()` passes enriched prompt. AD-139.
- [ ] **ML-091: Real 3-photo validation** — Run refinement on top photo (inbox_b5e8a89e_9, 19 facts, existing label 1950s, birth year math says 1940s). ~$0.10.
- [ ] **ML-092: Results-to-web bridge** — Script/endpoint to merge refinement_results.json into date_labels.json for admin review. Currently no connection to web app.
- [ ] **ML-093: Full 41-photo batch run** — After prompt gap fixed and validated. ~$1.31.
- [x] **ML-094: Write AD-136/137/138** — DONE (Session 61). AD-139-142 also added. See ALGORITHMIC_DECISIONS.md.
- [ ] **ML-095: CORAL retroactive run** — Run local model on all 271 photos, compare to Gemini labels. Free independent validation.

### UX Improvements (from Production Review)
- [ ] **UX-120: Help Identify mode for non-admin users (P1)** — Primary community use case requires admin intervention. Let logged-in users suggest names for unidentified faces → admin approval queue. See `docs/session_logs/session_60b_ux_review.md`.
- [ ] **UX-121: Contribution instructions page (P2)** — /contribute page explaining: how to identify faces, submit photos, report errors. Community members arrive from Facebook links.
- [ ] **UX-122: Person page family context (P2)** — 19 relationships exist in data but aren't visible. Show family connections, timeline of appearances.
- [ ] **UX-123: Mobile photo overlay readability (P2)** — Photos with 12+ faces have overlapping labels. CSS media query for reduced label size or tap-to-show.
- [ ] **UX-124: People page search/filter (P2)** — No search input on /people page.

### Face Alignment (Session 62)
- [-] **FA-001: Batch face alignment for all 271 photos** — 127/271 aligned (Session 63/64). 144 rate-limited, retry ready: `python scripts/run_combined_pipeline.py --retry-failed results/batch_alignment_20260223_023456.json`
- [x] **FA-002: Face alignment + GEDCOM context integration** — DONE (Session 64). Combined pipeline includes GEDCOM curated context. `scripts/run_combined_pipeline.py` with `--no-gedcom` flag to disable.
- [ ] **FA-003: Mobile UI refinement for face description cards** — Cards may overlap on small screens with many faces. Needs CSS media queries. Source: Session 62 prompt 6B.
- [ ] **FA-004: Auto-trigger face alignment on new photo upload** — After upload + face detection, auto-run alignment if GEMINI_API_KEY available. Source: Session 62 prompt 6B.
- [x] **FA-005: Production test face alignment** — DONE (Session 63). 3 photos tested, 100% success, $0.03. Source: Session 62 Phase 5 deferred.

### GEDCOM Integration (Session 61C, AD-147/148)
- [x] **GEDCOM-001: Supabase GEDCOM tables** — DONE (Session 63). 4 tables created via psycopg2: gedcom_individuals (21,809), gedcom_events (40,140), gedcom_relationships (145,574), gedcom_face_links (61). Source: Session 61C, AD-147/148.
- [ ] **GEDCOM-002: Admin GEDCOM link review UI** — Interface for linking identities to GEDCOM individuals. Admin can browse/search GEDCOM individuals and associate them with existing Rhodesli identity records. Status: OPEN. Source: Session 61C, AD-147/148.
- [ ] **GEDCOM-003: GEDCOM enrichment in upload flow** — When a face is identified and has a GEDCOM link, show enriched analysis popup with genealogical context (birth year, relationships, life events). Status: OPEN. Source: Session 61C, AD-147/148.
- [ ] **GEDCOM-004: "Analysis improved because..." UX feature** — Show users what GEDCOM context added vs visual-only analysis. Side-by-side or inline comparison of results with and without genealogical enrichment. Status: OPEN. Source: Session 61C, AD-147/148.
- [ ] **GEDCOM-005: Batch re-analysis with GEDCOM enrichment** — Re-run all 271 photos with curated GEDCOM variant. Leverage linked GEDCOM data to improve date estimation and identity confidence across the full archive. Status: OPEN. Source: Session 61C, AD-147/148.

### Similarity Calibration (Session 63, AD-149/150)
- [ ] **CAL-001: Community "reject" UX** — Enable explicit non-match pair collection from admin/user rejections. Feeds recalibration hooks (AD-150). Critical for calibration model improvement. Source: Session 63 Phase 9.
- [ ] **CAL-002: Active learning — surface uncertain pairs** — Find face pairs near the decision boundary (P(match) 0.4-0.6) and surface them for admin labeling. Maximizes information gain per label. Source: Session 63 Phase 9.
- [ ] **CAL-003: Calibration drift monitoring dashboard** — Admin page showing calibration model version, AUC trend, threshold history, pair count growth. Alert on drift >0.1. Source: Session 63 Phase 9.
- [ ] **CAL-004: Wire calibrated probabilities to compare UI** — Replace raw cosine similarity display with calibrated P(match) + confidence label (High/Medium/Low/Unlikely). Source: Session 63 AD-149.

### Data Layer (Session 64, AD-152)
- [ ] **DATA-002: Create Supabase tables** — Run `scripts/sql/create_face_gemini_alignments.sql` and `scripts/sql/create_gemini_api_calls.sql` in Supabase. Required for Supabase-first data layer to function. Source: Session 64.
- [ ] **DATA-003: Run alignment migration** — Execute `python scripts/migrate_alignments_to_supabase.py --execute` after tables created. Migrates 127 alignment records from JSON to Supabase. Source: Session 64.
- [ ] **DATA-004: Retry 144 rate-limited photos** — Run `python scripts/run_combined_pipeline.py --retry-failed results/batch_alignment_20260223_023456.json`. Requires GEMINI_API_KEY. Estimated cost: ~$4 at $0.028/photo. Source: Session 64.

### Architecture
- [ ] **ARCH-001: Rhodesli-specific hardcoding** — 171 references to "Rhodes/Jewish/Ladino/Sephardic" in app/main.py. Heavy refactoring needed for multi-community. See `docs/session_logs/session_60b_ux_review.md` Broader Scope section.

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

### Fact-Enriched Re-Analysis (AD-102) — DONE (Session 60)
Progressive refinement pipeline implemented: `rhodesli_ml/scripts/progressive_refinement.py`.
Gathers verified facts (confirmed identities, birth years, GEDCOM relationships),
builds enriched prompts, compares old vs new estimates. 41 eligible photos identified.
AD-138. See Session 60 log.

### Comprehensive API Result Logging (AD-103) — DONE (Session 60)
API logging infrastructure: `rhodesli_ml/utils/api_logger.py`. Per-call JSON logs
with full prompt, response, token counts, cost tracking, comparison to previous analysis.
AD-137. See Session 60 log.

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
- [x] **PRODUCT-001: Face Compare Standalone — Tier 1**: Museum-quality /facecompare page. Session 59, v0.61.0. AD-131/132/133.

## Near-Term (3-5 Sessions)

- [x] **Gemini 3.1 Pro integration**: Wired to Estimate upload (Session 52). Updated to 3.1 Pro (Session 61, AD-139).
- [ ] **ML-075: Batch Gemini Run on 271 Photos**: Run date estimation on all existing photos. Deferred from Session 52.
- [ ] **ML-096: Run compare_models.py with --photos 20**: Flash vs Pro A/B comparison on 20 photos (~$0.62). Needs Nolan approval. (Session 61)
- [ ] **ML-097: Run full 271-photo re-analysis with 3.1 Pro**: After ML-096 validates quality. Needs cost approval. (Session 61)
- [-] **PRD-015 v2**: Face alignment via coordinate bridging — design complete (AD-144), integrated with unified extraction (AD-143). Implementation TODO. Session 53 design → Session 61B update.
- [x] **Gemini unified extraction architecture**: AD-143, rhodesli_ml/gemini_extraction.py, 16 tests. Session 61B.
- [x] **PRD-023 Stage 1**: Similarity calibration — isotonic regression (better than Platt). AUC=0.9577, 348 pairs. Session 63, AD-149. Stage 2 (LoRA) deferred.
- [x] **Progressive refinement**: Pipeline fully wired — enriched prompt now sent to Gemini. Session 60 (AD-138) + Session 61 (ML-090 fixed).
- [ ] **UX-130**: Homepage visitor experience — non-admin landing page with CTAs (P2). Source: Session 61B UX evaluation.
- [ ] **UX-131**: Photo page admin tools below evidence — collapse behind toggle (P2). Source: Session 61B UX evaluation.
- [ ] **UX-132**: Homepage "Compare a Face" CTA for non-admin visitors (P2). Source: Session 61B UX evaluation.
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
- [x] **ML-070: MLflow Integration — CORAL Training**: MLflow Model Registry + Promotion Pipeline. Session 58, v0.60.0. AD-130.
- [ ] **PRODUCT-002: Face Compare Tier 2 — Shared Backend**: Shared comparison engine between standalone and Rhodesli. Rhodesli path adds: archive identity matching, upload persistence, date context, contribute-to-archive flow. Public path: compare and discard. See AD-117, docs/session_context/session_54c_planning_context.md Part 2C.

## Medium-Term

- [ ] **OPS-002**: CI/CD pipeline (automated tests, staging, deploy previews)
- [ ] **OPS-004**: Error tracking (Sentry)
- [ ] **QA-005-007**: Mobile viewport tests, UX walkthroughs, performance benchmarking
- [ ] **AN-022**: Cross-reference genealogy databases (Ancestry, FamilySearch, JewishGen)
- [ ] **DOC-010-013**: In-app help, about page, admin guide, contributor onboarding
- [ ] **FE-080-083**: Client-side analytics and admin dashboard
- [ ] **ROLE-004**: Family member self-identification ("That's me!" button)
- [x] **Admin/Public UX Unification**: Admin bar + quick-identify inline flow — Session 60, v0.63.0
- [ ] **Confidence scores per identification**: Show which results are ground truth vs provisional. Genealogy-specific differentiation. (Source: Expert review, Session 54)
- [ ] **Identity voting / community verification**: Let users confirm/reject ML matches. Improves embeddings over time. (Source: Expert review, Session 54)
- [ ] **Processing Timeline UI**: Per-photo status display for trust restoration. (Source: Expert review, Session 54. See AD-111)
- [ ] **Observability over unit tests**: Prioritize integration tests, per-photo processing timelines, job status visibility. (Source: Expert review, Session 54. See AD-110)

## Medium-Term — New Products & ML (Session 54c)

- [ ] **ML-071: MLflow — Gemini Prompt Tracking**: Track how different Gemini API prompts yield better/worse photo context extraction over time. Log prompt text, model version, output quality metrics per run. See AD-116, docs/session_context/session_54c_planning_context.md Part 1B.
- [ ] **ML-072: MLflow — Local vs Web ML Benchmarking**: Compare InsightFace local inference vs API-based face comparison. Track latency, accuracy, cost per comparison. See AD-116, docs/session_context/session_54c_planning_context.md Part 1B.
- [ ] **PRODUCT-003: NL Archive Query MVP (LangChain)**: Natural language interface: "Show me photos from the 1930s with people who look like [uploaded face]." Chain: face detection → embedding search → date filtering → NL response. Prerequisites: similarity calibration + CORAL + stable identity matching. Estimated 2-3 sessions once prerequisites met. See AD-118, docs/session_context/session_54c_planning_context.md Part 1B.
- [ ] **PRODUCT-004: Historical Photo Date Estimator Standalone**: Upload historical photo → estimate when taken using CORAL model. Genuinely novel — no existing tool offers this. Prerequisite: CORAL model trained and validated. Could combine with face comparison in shared "faces" tool site. See docs/session_context/session_54c_planning_context.md Part 2D.

## EPIC: Interactive Upload UX with SSE Progress — DONE (Session 60)

SSE streaming endpoint (`/api/upload/stream`) with progressive stage indicators
on both `/compare` and `/facecompare`. Client-side validation, timeout warning,
connection drop recovery. 24 tests. AD-121. See Session 60 log.

Remaining from original epic (deferred):
- [ ] Face-by-face progressive rendering + overlay animations
- [x] Multi-photo upload + compare/estimate view switching — DONE (Session 61, PRD-021)
- [ ] asyncio.Queue for concurrent upload serialization

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
