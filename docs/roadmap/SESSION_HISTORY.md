# Session History

Complete log of all development sessions. For current priorities, see [ROADMAP.md](../../ROADMAP.md).

---

## Early Sessions (1-31) Summary

| Sessions | Date Range | Highlights |
|----------|-----------|------------|
| 1-9 | 2026-02-05 to 2026-02-09 | Railway deployment, Supabase auth, Phase A stabilization, ML validation, 766 tests |
| 10-21 | 2026-02-10 to 2026-02-12 | Upload pipeline, annotation engine, discovery UX, public pages, sharing, 1769 tests |
| 22-31 | 2026-02-13 to 2026-02-15 | Person pages, CORAL ML, community features, timeline, compare tool, ~2016 tests |

---

## Session 32: Compare Intelligence (2026-02-15)
- Kinship calibration from 46 confirmed identities (959 same-person, 385 same-family, 605 different-person pairs)
- Key finding: family resemblance (d=0.43) not reliably separable from different-person in embedding space
- Tiered compare results (strong/possible/similar/weak) with CDF-based confidence
- Upload persistence + multi-face detection + face selection UI
- 30 new tests (2046 total). AD-067-069

## Session 33: Production Polish + Upload Pipeline + Ideation (2026-02-15)
- Compare in admin sidebar, R2 upload persistence (survives Railway restarts)
- Production graceful degradation (save without InsightFace)
- Contribute-to-archive flow wired to admin queue
- VISION.md product direction doc, AD-070 future architecture
- 12 new tests (2058 total)

## Session 34: Birth Date Estimation ML Pipeline (2026-02-15)
- Birth year estimation with robust outlier filtering (median + MAD)
- Face-to-age matching via bbox x-coordinate sorting
- 32 estimates from 46 confirmed identities (3 HIGH, 6 MEDIUM, 23 LOW)
- Timeline age overlay + person page birth year display
- 48 new tests (2246 total). AD-071/072

## Session 35: GEDCOM Import + Relationship Graph (2026-02-15)
- GEDCOM 5.5.1 parser with messy date handling (ABT/BEF/AFT/BET...AND)
- Layered identity matcher (exact -> surname variants -> maiden name -> fuzzy + date proximity)
- Photo co-occurrence graph (21 edges from 20 photos)
- Admin GEDCOM UI at /admin/gedcom, person page family section
- 107 new tests (2365 total). AD-073-076

## Sessions 36-38: Social Graph + Collections + Map (2026-02-16)
- Six Degrees connection finder at /connect (BFS, D3.js, proximity scoring)
- Shareable collection pages at /collections and /collection/{slug}
- Geocoding pipeline: 267/271 photos matched (98.5%)
- Interactive map at /map with Leaflet.js, marker clustering, photo popups
- Consistent navigation across all 11 public pages via _public_nav_links()
- 86 new tests (2120 total). PRDs 010, 012, 013. AD-077-081

## Session 39: Family Tree + Relationship Editing (2026-02-17)
- Hierarchical D3.js family tree at /tree (Reingold-Tilford layout)
- Couple-based nodes with face crop avatars, person filter, theory toggle
- FAN relationship model (friends/associates/neighbors) with confidence levels
- Relationship editing API (admin only, non-destructive)
- 39 new tests (2159 total). AD-077-080

## Session 40: Production Cleanup + Sharing (2026-02-17)
- Fixed /map 500 error, /connect 500 error, collection data corruption (114 photos reassigned)
- Shareable identification pages at /identify/{id} and /identify/{a}/match/{b}
- Person page comments (no-login-required), action bar, clickable collection link
- Data integrity checker (18 checks) + critical route smoke tests (10 routes)
- 35 new tests (2194 total)

## Session 41: Production Fixes + Photo UX + Research (2026-02-17)
- Fixed /map 500 (PhotoRegistry.get_photo() doesn't exist), face overlay alignment, face click behavior
- Photo carousel with prev/next, keyboard arrows, position indicator
- Fixed search -> Focus mode (direct links to /person/{id} or /identify/{id})
- PRD-015: Gemini face alignment research + AD-090 (PROPOSED)
- 8 new tests (2202 total)

## Session 42: Systematic Verification + Fix Everything (2026-02-17)
- Systematic verification audit of all 16 routes + 20 features
- Fixed /identify/{id} 500, landing page nav, GEDCOM test data warning
- Compare page two-mode UX, "Add Photos" button on collection pages
- 7 new tests (2209 total). Audit at docs/verification/session_42_audit.md

## Session 44: Compare Faces Redesign + Sharing Design System (2026-02-17)
- Unified sharing: og_tags() + generalized share_button()
- Compare page upload-first redesign, calibrated confidence labels
- Shareable comparison result pages at /compare/result/{id} with OG tags + response form
- Site-wide OG tags + share buttons on /photos, /people, /collections
- 21 new tests (2249 total). AD-091, PRD-016, PRD-017

## Session 45: Overnight Polish -- Feature Audit Completion (2026-02-18)
- Completed all 12 remaining items from 36-item feature audit
- Photo + person inline editing (admin-only), life details, admin nav bar consistency
- Structured action logging, geographic autocomplete, comment rate limiting
- AD-081-089, 3 postmortems, lessons.md restructured (401->109 lines)
- 32 new tests (2281 total)

## Session 46: Match Page Polish + Year Estimation Tool V1 (2026-02-18)
- Help Identify sharing (Best Match links, dual photo context, share URL fix)
- Face carousel for multi-face identities, deep link CTAs on match/identify pages
- Lightbox face overlays with state colors, clickable navigation, metadata bar
- Year Estimation Tool V1 at /estimate with per-face reasoning, scene evidence, confidence
- core/year_estimation.py estimation engine, Compare/Estimate tab navigation
- 56 new tests (2342 total). AD-092-096, PRD-018

## Session 47: ML Gatekeeper + Feature Reality Contract (2026-02-18)
- ML birth year estimates gated behind admin review (AD-097)
- Bulk review page at /admin/review/birth-years with Accept/Edit/Reject/Accept All High
- Ground truth feedback loop — confirmed data → retraining samples (AD-099)
- Feature Reality Contract harness rule (AD-098), User Input Taxonomy (AD-100)
- Dynamic version display from CHANGELOG.md (was hardcoded "v0.6.0")
- ROADMAP + BACKLOG splits (394→90, 558→102 lines)
- 23 new tests (2365 total). AD-097-100

## Session 47B: Audit & Gap Fill (2026-02-18)
- Feature Reality Contract audit of Session 47 deliverables (9/11 REAL, 2 gaps found)
- birth_year_estimates.json deployed to data/ (was only in rhodesli_ml/data/)
- BACKLOG breadcrumbs updated to reference session_47_planning_context.md
- Deploy safety tests for production-origin files (ml_review_decisions.json, ground_truth_birth_years.json)
- 4 new tests (2369 total)
- Session log: docs/session_logs/session_47B_log.md

## Session 48: Harness Inflection (2026-02-18)
- Prompt decomposition, phase execution, verification gate rules
- HARNESS_DECISIONS.md (HD-001-007)
- Age on face overlays (Session 47 Phase 2F completion)
- Session log infrastructure, CLAUDE.md compressed (113→77 lines)
- 4 new tests (2373 total)

## Session 49: Production Polish (2026-02-18)
- Health check (10/10 routes), Session 47/48 deliverable verification (all PASS)
- Collection name truncation fix, triage bar tooltips
- Interactive session prep checklist
- 5 new tests (2378 total)

## Session 49C: Community Bug Fixes (2026-02-19)
- Photo 404 for inbox photos (alias resolution in _build_caches())
- Compare upload silent failure (onchange auto-submit on file input)
- Version v0.0.0 in admin footer (CHANGELOG.md now in Docker image)
- Collection name truncation (6 remaining locations)
- First real community sharing on Jews of Rhodes Facebook group
- 9 new tests (2387 total)

## Session 50: Estimate Overhaul + Gemini Upgrade (2026-02-19)
- Estimate page: face count fix (BUG-009), pagination (24/page), standalone /estimate nav, upload zone
- Compare upload hardening (client/server validation)
- PRD-020 (estimate overhaul), AD-101 (Gemini 3.1 Pro), AD-102 (progressive refinement), AD-103 (API logging)
- 16 new tests (2401 total)

## Session 51: Quick-Identify + "Name These Faces" (2026-02-19)
- "Name These Faces" sequential batch identification mode
- PRD-021: Quick-Identify from Photo View, AD-104
- 16 new tests (2417 total)

## Session 51B: Production Bug Fixes (2026-02-19)
- Compare upload honest messaging (was misleading "check back soon")
- Removed redundant Estimate/Compare tab switchers
- Supabase keepalive in /health endpoint
- HD-008 (functional verification)
- 16 new tests (2433 total)

## Session 52: ML Pipeline to Cloud (2026-02-19)
- InsightFace + ONNX Runtime in Docker with buffalo_l model pre-downloaded
- Gemini 3.1 Pro wired to Estimate upload with graceful degradation
- "Name These Faces" on public photo page, cloud-ready ingest pipeline
- Health check reports ML status
- 30 new tests (2465 total)

## Session 53: Comprehensive Production Audit (2026-02-20)
- 35 routes tested, all healthy. Compare upload fixes (loading indicator, uploaded photo display, resize)
- HTMX indicator CSS dual-selector fix (HD-009)
- UX audit framework (docs/ux_audit/)
- 4 new tests (2480 total)

## Session 54: Quick Fixes + Architecture (2026-02-20)
- Compare upload 640px ML resize (was 1024px), split display/ML paths
- AD-110 Serving Path Contract, AD-111-113
- UX Issue Tracker (35 issues, all with dispositions)
- HTTP 404 for non-existent person/photo pages
- 1 new test (2481 total)

## Session 54B: Hybrid Detection + Testing Infrastructure (2026-02-20)
- buffalo_sc detector + buffalo_l recognizer (AD-114, mean cosine sim 0.98)
- Real upload testing (4 tests, all pass, 0.3-1.3s)
- Production smoke test script (11 paths), production verification rule (HD-010)
- UX tracker coverage verified (35/35)
- 5 new tests (2486 total)

## Session 54c: ML Tooling & Product Strategy (2026-02-20)
- Memory infrastructure evaluation: rejected NotebookLM MCP, Mem0, Notion MCP, LangChain (AD-115)
- MLflow integration strategy: targeted, CORAL training first (AD-116)
- Face Compare three-tier product plan, Tier 1 prioritized (AD-117)
- NL Archive Query deferred (AD-118)
- 8 new BACKLOG entries, ROADMAP priority restructure
- Planning context: docs/session_context/session_54c_planning_context.md

## Session 54D: Production Verification + Hybrid Analysis (2026-02-20)
- Production verified: health OK (664 identities, 271 photos, ML ready)
- Smoke test: 11/11 passed (fixed SSL cert handling for macOS venv)
- Compare upload test: HTTP 200, 51.2s, 21 images, matches displayed
- Hybrid detection analysis doc: docs/ml/HYBRID_DETECTION_ANALYSIS.md (125 lines)
- 49B interactive prep updated (sections 10-11 added, 7 new fixed items, 7 noted items)
- CLAUDE.md updated for AD-114 hybrid detection

## Session 54E: Verification Sweep (2026-02-20)
- Deliverable existence audit: 22 checked, 21 present, 1 gap closed (54D in SESSION_HISTORY)
- Playwright browser smoke test: 8/8 production tests pass (scripts/browser_smoke_test.py)
- CLAUDE.md: added Session Operations Checklist, compressed to 76/80 lines
- All 2486 tests passing

## Session 54F: Compare Performance Fix (2026-02-20) — v0.54.3
- Compare pipeline latency 51.2s → 10.5s on production (4.9x improvement)
- Root cause: buffalo_sc not in Docker → silent fallback to full buffalo_l (det_10g, 10G FLOPs)
- Fixes: buffalo_sc in Dockerfile, hybrid-only startup, OOM fix, ONNX thread optimization, warmup
- AD-119: Compare performance optimization — model lifecycle
- 14-face group photo: 28.5s (first measurement)
- Production verified: 11/11 smoke tests pass

## Session 54G: Final Cleanup Before 49B Interactive (2026-02-20)
- Harness hardening, documentation, verification. Zero new features.
- AD-120: ML model loading observability — silent fallbacks are bugs (generalized from 54F)
- AD-121: Interactive upload UX — SSE progress streaming architecture (design only)
- HD-012: Silent ML fallback detection harness rule
- OD-006: Railway MCP Server for Claude Code integration (installed, verify next session)
- PERFORMANCE_CHRONICLE.md created (Chronicle 1: compare pipeline journey)
- Browser testing audit: 54F had NO Playwright tests (only curl). 8/8 pass now.
- SSE upload epic added to BACKLOG (2-3 session epic, AD-121)
- Railway MCP installed, npm cache issue noted, Tool Search auto-defers
- All 2486 tests passing

## Session 49B Section 2: GEDCOM Import (2026-02-21) — v0.56.0
- Real GEDCOM import: Fox_Capeluto_Fogel_Waldorf Family Tree.ged (21,809 individuals, 6,680 families)
- 33 identities matched to Ancestry tree (CSV review workflow: export → user corrects → re-import)
- User corrected 15 of 33 Ancestry IDs via spreadsheet review
- 19 relationships built (5 spouse, 14 parent-child) from GEDCOM family records
- 33 identities enriched with GEDCOM data (birth/death dates, places, gender, Ancestry URLs)
- ancestry_links.json created (33 identity-to-Ancestry mappings)
- Production data merge: synced from production → applied GEDCOM enrichment → preserved 31 Session 49B birth years → pushed
- Lesson 78: Production-local data divergence is the #1 recurring deployment failure (4th occurrence)
- All 2486 tests passing

## Session 49D: P0 + P1 Bug Fixes (2026-02-21) — v0.56.2
- 12 UX issues fixed: 6 P0 (Name These Faces, upload messaging, merge URL) + 6 P1 (birth year, 404, navbar, identify links, banners, pending count)
- 35 new tests in test_p0_fixes_49d.py and test_p1_fixes_49d.py
- All 2544 tests passing

## Session 49E: Stabilization & Verification (2026-02-21) — v0.56.3
- Fixed 130 state-pollution test failures (root cause: leaked patches in test_nav_consistency.py, fix: ExitStack)
- Verified all 49D fixes in production browser (10/10 PASS)
- Name These Faces confirmed fully functional end-to-end in production
- Compare/Estimate uploads confirmed saving to R2 (corrected inaccurate "not stored" messaging)
- Test count corrected: 2545 app + 306 ML = 2851 total (previous undercounts from missing venv)
- Compaction-resilient checkpoint system installed (PreCompact hook, HD-015)
- Lessons 79-80 added

## Session 55: Similarity Calibration (2026-02-21) — v0.57.0
- Siamese MLP calibration layer on frozen InsightFace embeddings (33K params)
- F1@0.5 improved 4.8x (0.13→0.60), precision@0.5=98%
- PyTorch + MLflow experiment tracking
- Integrated into compare pipeline with graceful degradation (ONNX→PyTorch→Euclidean)
- PRD-023, SDD-023, AD-123/124/125/126
- Backlog/roadmap audit — 8 new items, BACKLOG trimmed
- 2961 total tests (2604 app + 357 ML)

## Session 55b: ONNX Production Serving + ML Docs (2026-02-21) — v0.57.1
- ONNX export: calibration_v1.onnx (129KB, exact numerical match)
- Production serving via onnxruntime (15MB vs PyTorch 500MB+)
- Fallback chain: ONNX → PyTorch → Euclidean
- AD-127 (calibration results interpretation), AD-128 (ONNX serving decision)
- ML_ARCHITECTURE.md: comprehensive ML system docs (178 lines)
- Backlog audit verification: 20/20 planning context items tracked
- 2976 total tests (2604 app + 372 ML)

## Session 56: Landing Page Refresh + P1 UX Polish (2026-02-21) — v0.58.0
- **Phase 1**: 12 P1 UX fixes — merge direction indicator, merged ID redirect, admin controls on /person/, Enter key submit in Name These Faces, Create New at top, Skip button, photo preview before upload, auto-scroll to results, CTAs after estimate, loading indicators
- **Phase 2**: Landing page feature entry point cards (2x3 grid: Photos, People, Map, Timeline, Tree, Compare) with live stats. Removed dead code (duplicate landing_page() and _compute_landing_stats()). Added confirmed_count + SKIPPED to needs_help. PRD-024.
- **Phase 3**: Lazy loading for /photos (24 per page, HTMX infinite scroll) and /timeline (smart initial decades, lazy rest). New /api/photos/more and /api/timeline/more endpoints.
- **Phase 5**: Full production UX audit — all pages verified (photos, people, timeline, map, tree, person detail, landing, admin dashboard). Production smoke test 11/11 PASS.
- 3003 total tests (2631 app + 372 ML)

## Session 57: CORAL Date Estimation → Production (2026-02-21) — v0.59.0
- **Phase 1**: ONNX export of CORAL date classifier (16.5 MB). EfficientNet-B0 backbone, 11 decades (1900s-2000s). Validated 50/50 prediction match. AD-129 (tolerance 0.05 for deep CNN). PRD-025.
- **Phase 2**: Production deployment — DateEstimationService with fallback chain (ONNX→PyTorch→None). Dockerfile updated. Health check reports date_model status.
- **Phase 3**: /estimate endpoint wired to CORAL model as primary (instant, free). Gemini as supplementary "Detailed AI Analysis". Probability distribution bars, confidence tiers, expected year display.
- **Phase 4**: Decade probability bars on photo detail pages using existing Gemini decade_probabilities.
- **Phase 5-6**: Verification gate + documentation. All tests pass.
- 3048 total tests (2649 app + 399 ML)

## Session 58: MLflow Model Registry + Promotion Pipeline (2026-02-21) — v0.60.0
- Both ONNX models registered in MLflow with signatures, gate tags, and @champion aliases
- Automated promotion script (promote_model.py): regression gate → register → alias → export
- AD-130. Session 57 audit confirmed CORAL conversion correct.
- 3068 total tests (2649 app + 419 ML)

## Session 59: Face Compare Standalone Tier 1 (2026-02-21) — v0.61.0
- Museum-quality /facecompare page — upload → detect faces → find matches
- Three ML systems: InsightFace + Calibration + CORAL
- Shareable result URLs at /facecompare/result/{uuid}
- Bridge CTAs to full archive. AD-131/132/133.
- 3102 total tests (2683 app + 419 ML)

## Session 59B/59C: Recovery + Supabase Migration (2026-02-21/22) — v0.61.1/v0.62.0
- 59B: Emergency recovery + deploy safety gate (AD-134). 3123 tests.
- 59C: Supabase migration — 4 tables (identity_overrides, annotations, relationships, gedcom_matches). Dual-write pattern. Startup sync. DATA-001 resolved (AD-135). 3102 tests.

## Session 60: Gemini Progressive Refinement + SSE Upload (2026-02-22) — v0.63.0
- Centralized Gemini config (AD-136), API logging (AD-137), progressive refinement pipeline (AD-138)
- SSE streaming upload on /compare and /facecompare with stage indicators
- Admin bar + quick-identify inline flow
- 96 new tests. 3190 total.

## Session 60B: Production Verification + ML Deep Dive (2026-02-22) — v0.63.1
- Fixed P0 quick-identify CSS selector crash (legacy face IDs with colons/spaces)
- ML analysis: enriched prompt built but never sent to Gemini (gap found)
- UX review: 7 friction points, 12 new BACKLOG items
- 3192 total tests (2726 app + 466 ML)

## Session 61: Gemini Photo Detective + Multi-Photo Compare (2026-02-22) — v0.64.0
- Fixed enriched prompt gap (ML-090): call_gemini() now accepts custom prompt
- Upgraded to Gemini 3.1 Pro (AD-139) + MLflow tracking (AD-140)
- Multi-photo compare upload for 2-5 photos (PRD-021, AD-141)
- Photo Detective UX: evidence cards, model badges, refinement indicators (PRD-022, AD-142)
- Data integrity report script + verification
- ~50 new tests. ~3250 total.

## Session 61B: Verify, Optimize, Assess (2026-02-22)
- P0 ENOSPC deploy fix — auto_backup pruning reordered, max backups 10->5 (4 tests)
- Production smoke test: all 9 pages verified, Session 61 features confirmed live
- UX evaluation: 3 P2 issues (UX-130/131/132), 0 P1
- Gemini unified extraction architecture (AD-143): 3 presets, 10 extraction types, 16 tests
- PRD-015 v2: face alignment integrated with unified extraction (AD-144)
- PRD-023: LoRA/calibration research — Platt scaling first (AD-145)
- Self-assessment protocol installed (HD-016, .claude/rules/self-assessment.md)
- Flash vs Pro comparison deferred pending cost approval
- 20 new tests. ~3270 total.

## Session 62: PRD-015 Face Alignment Implementation (2026-02-22) — v0.65.0
- EXIF orientation handler (app/exif_handler.py): normalize_orientation(), get_image_dimensions(), has_exif_orientation() — 10 tests
- Coordinate bridging module (app/face_alignment.py): FaceDetection/AlignedFaceDescription/AlignmentResult dataclasses, format_faces_for_gemini(), build_alignment_prompt(), parse_alignment_response(), run_face_alignment(), JSON storage — 30 tests
- API endpoints: POST /api/face-alignment/{photo_id} (admin-only trigger), GET /api/face-alignment/{photo_id} (cached results) — 8 tests
- Photo page UI: per-face description cards (age, gender, clothing, features), mismatch warnings, admin trigger/re-run buttons — 6 tests
- AD-146: Face Alignment Implementation Results
- Real photo testing deferred to production (no GEMINI_API_KEY locally)
- 54 new tests. ~3373 total (2864 app + 509 ML).

---

## Release Version History

| Version | Date | Session | Test Count |
|---------|------|---------|------------|
| v0.65.0 | 2026-02-22 | 62 | ~2864+509 |
| v0.64.0 | 2026-02-22 | 61 | ~2776+474 |
| v0.63.1 | 2026-02-22 | 60B | 2726+466 |
| v0.63.0 | 2026-02-22 | 60 | 2724+466 |
| v0.62.0 | 2026-02-22 | 59C | 2683+419 |
| v0.61.1 | 2026-02-21 | 59B | 2704+419 |
| v0.61.0 | 2026-02-21 | 59 | 2683+419 |
| v0.60.0 | 2026-02-21 | 58 | 2649+419 |
| v0.59.0 | 2026-02-21 | 57 | 2649+399 |
| v0.58.0 | 2026-02-21 | 56 | 2631+372 |
| v0.57.1 | 2026-02-21 | 55b | 2604+372 |
| v0.57.0 | 2026-02-21 | 55 | 2604+357 |
| v0.56.3 | 2026-02-21 | 49E | 2545+306 |
| v0.56.2 | 2026-02-21 | 49D | 2544 |
| v0.56.0 | 2026-02-21 | 49B-S2 | 2486 |
| v0.48.0 | 2026-02-18 | 46 | 2342 |
| v0.47.0 | 2026-02-18 | 45 | 2281 |
| v0.46.0 | 2026-02-17 | 44 | 2249 |
| v0.44.0 | 2026-02-17 | 42 | 2209 |
| v0.43.0 | 2026-02-17 | 41 | 2202 |
| v0.42.0 | 2026-02-17 | 40 | 2194 |
| v0.41.0+ | 2026-02-17 and earlier | 1-39 | 663-2159 |
