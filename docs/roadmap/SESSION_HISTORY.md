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

## Session 61C: GEDCOM-Enriched Analysis + Flash vs Pro (2026-02-23)
- Extended GEDCOM parser with RESI, OCCU, IMMI, EMIG, BURI life event extraction
- 5-variant GEDCOM context builder (rhodesli_ml/gedcom_context.py): none, full, curated, first_order, co_occurrence — 19 tests
- Supabase import script (scripts/import_gedcom_supabase.py) — tables not yet created
- Model comparison driver (scripts/compare_models.py) with cost/token/latency tracking
- 11 comparison runs: 3 models (gemini-2.0-flash, gemini-3-flash-preview, gemini-3.1-pro-preview) × 5 GEDCOM variants, $2.46 of $10 budget
- **Verdict**: Pro + curated GEDCOM optimal ($0.02/photo, 0% errors, city-level location)
- AD-147 (GEDCOM enrichment results), AD-148 (GEDCOM storage architecture)
- BACKLOG: 5 GEDCOM integration items added (GEDCOM-001 through GEDCOM-005)
- Outcomes: docs/session_context/session_61c_outcomes.md

## Session 64: Verify, Migrate, Harden (2026-02-23) — v0.67.0
- Harness hardening: 5 Claude Code skills, 3 path-scoped rules, 3 hooks
- CLAUDE.md trimmed from 4922 → 1952 chars (domain rules → .claude/rules/)
- Data layer audit: face alignment JSON-only, recalibration dead code, calibration not in UI
- Face alignment migrated to Supabase (`face_gemini_alignments` table, JSON fallback)
- `gemini_api_calls` tracking table — every Gemini call logged (model, tokens, cost, latency, status)
- Centralized model config: all `call_gemini_alignment()` uses `GEMINI_MODEL` from config
- Combined pipeline: `scripts/run_combined_pipeline.py` (alignment + GEDCOM + retry)
- Calibrated scores wired to UI: `neighbor_card()` shows "85% match" via isotonic regression
- Recalibration hooks wired into merge/reject/confirm endpoints
- 127/271 photos aligned, 144 rate-limited (retry ready)
- AD-152. ~50 new tests. ~3450 total (2906 app + 538 ML).
- Outstanding: 144 photo retry, Supabase table creation, migration script execution

## Session 81: Connected App — Tree, Map, Location, Face Labels (2026-03-01) — v0.83.0
- Photo→Tree smart navigation: BFS subtree logic, nuclear family detection, photo-person highlighting
- Face identity labels: confirmed names as clickable links to /person/{id}, unidentified show "Face N"
- Photo→Map + Person→Map navigation buttons
- Location estimate display: confidence badges, evidence cards, embedded Leaflet maps (OpenStreetMap)
- GEDCOM-enriched location prompts: residential history, children birth places, spouse events (AD-192)
- Location data model + UX research (AD-193)
- Relationship viz: thicker lines (shared photos), hover labels, generation bands
- Matilda GEDCOM face link fix (a2889099 xref corrected)
- Browser verification: 12/12 production pages PASS
- PRODUCT-006 chatbot concept added to BACKLOG
- 8 parallel subagents across 2 rounds, session recovered after interruption
- ~97 new tests (34 tree nav, 15 face/map, 22 location, 15 GEDCOM, 9 consistency, 10 tree API)
- Tests: ~3030 total

## Session 81B: Fix Real Issues Found in Browser Verification (2026-03-01) — v0.83.1
- Face label prefix fix: removed "Face N:" prefix from identified faces (commit `daa8c0d`)
- Leaflet map fix: moved script outside `<details>`, polling-based CDN check replaces DOMContentLoaded (Lessons 90/91)
- Tree subtree logic: removed `if pid in lookup` filter, include disconnected photo people (Lessons 92/93)
- 7 new lessons documented (90-96)
- 6 commits, all tests passing

## Session 81C: Data Consistency + WCAG (2026-03-01) — v0.83.2
- Fixed 21 truncated UUIDs in `data/gedcom_matches.json` (8-char → full UUIDs)
- Added xref fallback resolution in `_build_tree_adjacency()` and `_build_tree_person_lookup()`
- Synced 56 GEDCOM matches + 1240 relationships to Supabase
- Arrow touch targets: radius 14→22 (44px WCAG minimum), font 14→18px
- Tree rendering: 7 → 17 nodes for photo fb6a846971b30f4b
- Tests: 3917 total (3366 app + 551 ML)

## Session 82f: Completion Audit + Fix Everything (2026-03-02) — v0.85.1
- Exhaustive audit of all Session 82 work (82a-82e): 20 features shipped, 3 partially shipped, 4 dropped, 8 deferred
- Browser verification: 16 features confirmed WORKING in production, 0 BROKEN
- Fixed Similar button hit area (38x16px → 46x24px) for mobile usability
- Formally deferred 5 features to BACKLOG: UX-201 (Missing Info Table), UX-202 (Bulk Confirm), UX-203 (Relational Labels), UX-204 (Face Card Unification), ML-100 (82c Branch Merge)
- Gap analysis: 82b (Codex) never executed, 82c branch has 14 unmerged commits
- Feature #22 (Click-to-Target Bounding Boxes) confirmed already exists
- HTMX 2.x lesson: uses `htmx-internal-data` property (not `__htmx_internal` from 1.x)
- Tests: 3949 (3398 app + 551 ML). Browser verified 16/16 PASS.

## Session 82d: Inline Find Similar + Performance (2026-03-01) — v0.84.0
- Inline Find Similar expansion panel (AD-194): Admin clicks "Similar" → HTMX panel with hero face, similar tiles, Compare/Merge/Not Same
- Person gallery HTMX toggle (AD-195): Faces/Photos instant swap without page reload
- Visual modernization: card hover transitions, button active feedback, keyboard focus rings
- P0 lazy-load face counts fix, P1 admin button differentiation, P1 focus mode highlight fix
- Reject match endpoint: POST /api/identity/{id}/reject-match/{neighbor_id}
- 10 new tests in test_inline_find_similar.py

## Session 82e: UX Feature Sprint (2026-03-01) — v0.85.0
- Mobile hamburger fix: sm→md breakpoint (768px), slide-from-right, ESC key close
- Masonry photo grid: CSS columns layout on /photos, natural aspect ratios, 1-4 responsive columns
- Help Needed page (/help): Top 50 unidentified faces sorted by quality, CTAs to /identify pages
- Share for Help: OG meta tags on /identify pages with face crop images for social sharing
- Identify Mode focus state: Toggle button, dark overlay, amber pulse animation, "?" badges on unidentified faces
- Landing page: Help section with 6 mystery faces, "See All" counter linking to /help
- Browser verified: 7/7 PASS. Tests: 2942 (2391 app + 551 ML). 22 new tests.

## Session 81D: Final Verification Gate (2026-03-01)
- 13/13 feature verification PASS on production Chrome
- Verified: face labels, Leaflet maps, tree rendering, photo cycling, expand/collapse, time slider, hover labels, generation bands, line thickness, date estimate, location estimate, scene description, people cards
- Verification-only session (0 commits)

## Session 80 continuation: Parallel Track Improvements (2026-02-28) — v0.82.1
- 5 parallel worktree subagents merged cleanly to main
- Track A: Tree JS — per-person photo cycling (arrows + dot indicators), expand-from-any-node, multiple spouse support (children grouped by parent pair), text readability (17px names, text-shadow)
- Track B: app/main.py — Find Similar page fixed (color-coded tiers, breadcrumbs), share button restored on 3 surfaces (Web Share API + clipboard fallback), multi-face thumbnail gallery on cards
- Track C: 21 new GEDCOM matches (56 total, 4 not in tree: Arlene Kessler, Eleanore Cohen, Herman Benson, Molly Benson)
- Track D: DD-005 (photo-dominant cards), AD-190 (GEDCOM relationship import), AD-191 (best-face selection)
- Track E: Rounded-rect face crops replacing circles (~35% more face visible, squircle with 25% corner radius)
- Tests: 2933+ passing (2395 app + 538 ML)
- Deferred: Supabase GEDCOM face link fix for Matilda, relationship visualization enhancements

## Session 80: Fix Everything — Tree + Face Cards + UX (2026-02-28) — v0.82.0
- Family Tree complete overhaul: 3 API endpoints (data, expand, search), BFS lazy loading, type-ahead search, floating-face design (DD-004), gender rings, glassmorphism
- Graph unification: GEDCOM xrefs→UUIDs. Expand fix: source person in response
- GEDCOM relationship import: 1221 correct rels replacing 1000 wrong xref-based rels. Abraham's 7 children restored.
- Face cards: photo-dominant redesign (DD-005), collapsible admin, Find Similar full-page route
- Best-face selection: get_best_face_id() for tree nodes and identity cards
- Matilda Capouano + Hanula Mosafir added to GEDCOM matches (35 total)
- Compare feature deferred (AD-187). Lesson 89: /clear between acts is non-negotiable.
- Tests: ~3272

## Session 79: Fix Three Visible Failures (2026-02-28) — v0.81.0
- Tree fix: CardSvg replaces broken CardHtml (AD-184). 13-node family tree renders with names, lifespans, photos. 57 families in "Focus on" dropdown.
- Face card redesign: compact layout with face hero (60%+ area), icon-only action buttons, overflow menu. 5 cards/row desktop, 2/row mobile.
- Tier 2 threshold raised 1.10→1.30 (AD-183, Nolan approved). Backfill: 617 Tier 2 suggestions. 137 unique discoveries visible.
- Data loss investigation: No loss found. Big Leon (13 anchors) and Nace (3 candidates) both CONFIRMED and intact.
- Session 78 cleanup: Compare blocked (InsightFace not on Railway), 8 skipped tests documented, mobile viewport verified.
- Tests: 3246 app + 538 ML = 3784 passing. Pre-existing e2e failure documented.

## Session 78: Integration + Fix-Everything (2026-02-28) — v0.80.0
- Fixed stop hook (exit 1→2 blocking), test count audited (3254 app + 538 ML = 3792)
- Fixed 2 failing ML tests: photo dimensions cache fallback, relationship graph test assertion
- Per-face dedup in auto_cluster.py (full, partial, review categories). 11 new tests.
- Threshold analysis: 52% of clusters exceed Tier 2 ceiling of 1.10. Raise to 1.30 recommended.
- GEDCOM→Supabase sync: 1,019 relationships, pagination fix, batched inserts. 20 new tests.
- PRD-024 auto-clustering created. BACKLOG trimmed (292 lines). AD numbering verified.
- Visual audit: 9 pages verified via Chrome, all PASS.
- Deferred: Tier 2 threshold raise (needs admin decision), full compare upload E2E, mobile viewport.

## Session 77: Compare Rebuild Follow-up (2026-02-28) — v0.79.1
- Added pair compare archive context: selected faces in `/compare/pair` now show top archive matches beneath pair similarity output.
- Added all-face pair summaries (top A↔B matches and per-face archive best hits) in pair comparison output.
- Added automatic queueing for compare uploads to admin pending review.
- Added focused golden compare test suite in `tests/test_compare.py`.
- Added audit log: `docs/session_logs/session_77_audit.md`.
- AD-181 (pair-compare archive-context), AD-182 (compare uploads auto-queue).

## Session 76a: Auto-Clustering + Discoveries Redesign + Face Cards (2026-02-28) — v0.79.0
- **Track A — Auto-clustering pipeline (AD-179)**: `core/auto_cluster.py` with two-tier thresholds (Tier 1 < 0.85, Tier 2 0.85-1.10). Best-linkage distance to confirmed clusters. Discovery log (`data/discovery_log.json`) as ML audit trail. Wired into `process_uploads.py` step 5. Backfill results: 0 Tier 1 (all close matches already confirmed), 7 Tier 2 suggestions, 652 no match. `scripts/backfill_auto_cluster.py` CLI tool.
- **Track B — Discoveries UX redesign**: Two-tier layout on `/api/discoveries` — "Recently Auto-Added" (Tier 1) with Confirm/Undo + "Suggested Matches" (Tier 2) with Accept/Reject. Discovery log entries feed back as ML signals. Routes: `/api/discovery/confirm`, `/api/discovery/undo`. Reject route updated to log to discovery_log.
- **Track C — Browse card face sizing**: Face-dominant cards with min-h-[150px] sm:min-h-[200px]. Secondary actions behind hover overlay. Neighbor thumbnails 64→80px.
- **Data investigation**: Within-cluster distances mean=1.01, std=0.19, p5=0.70, p25=0.88. 57 duplicate face IDs across confirmed/inbox. Non-duplicate inbox-to-Big-Leon: 1.13+, inbox-to-Nace: 1.18+.
- 2 parallel worktree subagents (Tracks A, C). AD-179. 15 new tests + 4 regression fixes. ~3742 total (3205 app + 537 ML).

## Session 75: Post-Gemini Cleanup + Tree Upgrade (2026-02-28) — v0.78.0
- **Data integrity**: Reverted 9,000+ lines of key-reorder noise. Preserved 5 identity renames + 4 annotations. Restored 19 UUID relationships, merged with 1,000 GEDCOM-xref (1,019 total).
- **GEDCOM date parser**: Regex `parse_gedcom_year()` replaces broken `[:4]` slice. "21 SEP 1887" → "1887" (was "21 S"). Handles ABT/AFT/BEF/BET qualifiers. AD-175.
- **Tree rewrite**: `build_family_tree()` produces CardHtml-compatible format. Bidirectional relationships: 193 parents with 2+ children, siblings render. 718 people, 22 UUID identities with names.
- **Tree frontend**: family-tree.js uses CardHtml API. Light theme. Default to most-connected person. Loading state.
- **xdist fix**: Atomic `_reorder_routes_atomic()` replaces pop/insert race. Timeout 10s→30s. 0 failures across 2 consecutive runs. AD-178.
- **Junk cleanup**: Deleted fake test_tree_rendering.py, fixed rebuild_full_graph.py to load existing data.
- AD-175/176/177/178. 38 new tests. ~3153 tests.

## Session 74: Family Tree + UX Overhaul (2026-02-27) — Gemini 3.1 Pro
- **Agent**: Gemini 3.1 Pro (Antigravity), 5 missions. Evaluated by Claude Code (session-74-eval.md).
- **Mission 1**: Face card grid layouts (CSS grid, responsive). Grade: B.
- **Mission 2**: GEDCOM pagination with prev/next, page counter. Grade: A-.
- **Mission 3**: Family tree visualization with family-chart.js. Working tree, but wiped UUID relationships and broke date parsing. Grade: B-.
- **Mission 4**: Mobile responsive admin/compare layouts. Grade: B+.
- **Mission 5**: Nav grouping (Core Archive / Tools / Help Identify CTA). Grade: A-.
- **Issues**: Data integrity bugs (relationship wipe, date [:4] slice, key reordering noise). Fixed in Session 75.

## Session 73: Cleanup + Share-Readiness (2026-02-27) — v0.77.1
- **Phase 1 — File naming + harness cleanup**: Renamed 3 session logs to convention (lowercase hyphens). Removed 3 legacy scripts (enforce_worktree.sh, merge-worktree.sh, merge_tracks.sh). Fixed stop hook for merge sessions. Added naming conventions to CLAUDE.md (79 lines).
- **Phase 2 — Bug investigation + fix**: Track A revert mystery: no git hooks or formatters found (likely subagent interference, Lesson 88). Enter key fix: replaced 400ms setTimeout hack with htmx:afterSettle event-driven approach.
- **Phase 3 — Share-readiness assessment**: 10/10 smoke test checks PASS via Chrome browser. Status: READY to share with family.
- Single-threaded on main. ~2166 fast tests passing.

## Session 72: Harness Fix + ML Similarity Calibration (2026-02-27) — v0.77.0
- **Phase 1 — Permanent harness fixes**: Test tiering (`make test-fast` 28s, 2166 tests via pytest-xdist). Branch enforcement hooks in `.claude/settings.json`. `scripts/merge.sh` merge ceremony script. CLAUDE.md updated with testing section (77 lines).
- **Phase 2 — ML similarity calibration**: Extracted 3804 training pairs (951 pos, 2853 neg) from confirmed/rejected data. Trained MLP calibrator on frozen embeddings (AUC 0.84, F1 0.75, 111 epochs, early stopped). Regression gate: NO-SHIP on ECE (0.108 vs 0.095 baseline) despite AUC +0.013 and precision@90recall +0.037. Shadow scoring: 96.3% agreement with threshold system, 74 disagreements in MODERATE tier (calibrator more conservative).
- **AD-174**: Similarity calibration decision with full provenance.
- Single-threaded execution (no subagents). ~3180 tests (2166 fast / 1014 slow).

## Session 71D: Merge Ceremony — Discoveries Fix + Harness Enforcement (2026-02-27) — v0.76.1
- **Merge ceremony**: Merged 2 unmerged worktree branches from Session 71D into main.
- **Harness branch**: Worktree enforcement scripts (enforce_worktree.sh, merge_tracks.sh), AD-171, HD-021.
- **Discoveries branch**: Fix navigation dead-ends, replace misleading "54% match" with confidence labels ("Good match"/"Possible match"), widen threshold to 1.05 to surface Nace Capeluto, add photo context and co-occurring faces. AD-172, AD-173.
- **AD conflict resolution**: Both branches + Session 71 Track C all used AD-170. Renumbered: harness→AD-171, discoveries architecture→AD-172, confidence display→AD-173.
- **Browser verified**: Discoveries page shows 2 matches (Big Leon + Nace Capeluto) with correct labels, clickable navigation, photo context. Session 71 fixes intact.
- 3163 tests (up from 3146 baseline).

## Session 71: UX Dogfooding Fixes + GEDCOM Integration + Harness Enforcement (2026-02-26) — v0.76.0
- **Track A**: 6 UX fixes from dogfooding (quality labels, face card size, enter key, analysis sections, name truncation, loading indicator).
- **Track B**: GEDCOM search ranking with date/Rhodes bonuses, match strength labels, pagination, tree buttons on identity cards.
- **Track C**: Mechanical subagent commit enforcement (HD-021), AD-170 (banner vocabulary), parallel sessions doc.
- 3 parallel tracks. ~3146 tests.

## Session 70: UX Fix Pass + Multi-Tool Harness + Auto-Eval Loop (2026-02-25) — v0.75.0
- **UX fix pass**: 13 issues from session 69 audit addressed (2 HIGH, 5 MEDIUM, 6 LOW). UX-108 contrast fix, UX-109 color consistency, UX-110-113 discovery card improvements, UX-104/105 verified/fixed, MEDIUM #3-5 (ML banner vocab, tab styling, triage bar).
- **Multi-tool harness (HD-019)**: Canonical source + adapter pattern. AGENT_HARNESS.md (tool-agnostic rules), AGENTS.md (Codex), .cursorrules, .gemini/GEMINI.md, .antigravity/rules.md. sync-harness.sh + setup-worktree.sh.
- **Auto-evaluation loop (HD-020)**: run_session.sh rewritten as 6-stage orchestration (phases → evaluator → fix-prompt-writer → b-version). session-evaluator.md (20-item checklist), fix-prompt-writer.md (I/O contracts).
- **Parallelization skill validated**: Tested against session 70 prompt. Accuracy HIGH (8 correct, 6 minor gaps). Analysis in docs/analysis/.
- **Lessons 86-87**: Context overflow + subagent commit discipline added.
- 3 parallel worktree subagents. 28 new tests. ~3671 total (3133 app + 538 ML).

## Session 69: Bug Fixes + Design Audit + Discovery Notifications (2026-02-25) — v0.74.0
- **BUG-1 (P0, AD-168)**: Create Identity 500 error — `rename_identity()` missing `user_source` param. Also fixed hyperscript parse error (missing `end` keyword).
- **BUG-2 (P0, AD-169)**: Clustering pipeline confirmed BY DESIGN (Gatekeeper pattern). Upload → face detection → INBOX only. No auto-clustering intentional.
- **BUG-3 (P1)**: Collection dropdown UX — datalist hidden by pre-filled "Uncategorized". Fix: `onfocus="this.select()"`.
- **Editorial archival design (DD-001, DD-002)**: Playfair Display serif font for headings. Warm amber/parchment card styling. Face grid density +50% (3→6 cols). Sepia 0.3→0.15. "Heritage Archive" branding.
- **Discovery notification system (DD-003)**: High-confidence matches to CONFIRMED identities. Sidebar badge, /discoveries admin page, one-click confirm/reject. Proposals-first optimization with caching.
- **Parallelization skill (HD-018)**: `.claude/skills/prompt-parallelizer/SKILL.md`. Tiered regression (5-item smoke vs 15-item full). Content safety case study.
- **DESIGN_DECISIONS.md created** (DD-001 through DD-003).
- 3 parallel worktree subagents. 41 new tests. ~3595 total (3057 app + 538 ML).

## Session 68: Hook Hardening + LoRA Audit + UX-103 + Photo Retry (2026-02-25) — v0.73.1
- Python stop gate replaces bash grep (AD-167). PreCompact recovery strategy. UX-103: back nav + metadata overlay + mobile menu. LoRA audit: 221 positive pairs, MARGINAL. Photo retry: 142/144 done, 2 blocked by Gemini content safety. 3 parallel worktree subagents. ~3064 tests.

## Session 67: Hook Enforcement System (2026-02-25) — v0.73.0
- **Hook enforcement (AD-166)**: Replaced informational-only hooks with blocking enforcement. Stop hook blocks session end until assessment file exists, phase verdicts logged, screenshots reviewed, b-path written if failures. PreCompact (manual) blocks /compact via exit 2. UserPromptSubmit injects parallelization reminder. All hooks use python3 (jq not installed).
- **Deferred subagent invocations**: ux-reviewer reviewed 6 session-65b screenshots (8 new issues: 1 P1, 4 P2, 3 P3). session-evaluator independently evaluated session 66 (Phases 4/5/6 PARTIAL vs self-assessed PASS). Enrichment validation confirmed.
- **/clear investigation**: /clear is interactive-only, doesn't work in -p mode. Created scripts/run_session.sh for headless phase-splitting with true context isolation.
- **UX issues added**: UX-103 (P1, full-bleed photo dead end), UX-104-107 (P2, compare button, Help Identify CTA, phrasing, badge tooltip).
- No app code changed — harness/docs session. ~3588 tests (unchanged).

## Session 66b: Upload Silent Data Loss Fix (2026-02-25) — v0.72.1
- **CRITICAL FIX (AD-165)**: Upload showed "3 faces extracted, 3 added to Inbox" but data never appeared in UI. Root cause: TWO bugs — (1) background thread wrote to disk but never invalidated in-memory caches (_photo_cache, _face_data_cache, _face_to_photo_cache, _photo_registry_cache, _photo_id_aliases), (2) R2 upload ran in status polling endpoint after background thread deleted staging directory.
- **Fix**: Moved R2 upload inside background thread (before staging cleanup). Added cache invalidation (all 5 caches → None) after successful processing. Added embeddings.npy safety gate to init_railway_volume.py.
- **Production verified**: Uploaded leon_and_nace_capeluto_kiddyland.jpeg via Playwright. "2 faces extracted, 2 added to Inbox". Sidebar counts updated immediately (New Matches 407→409, Photos 271→272). This was the 5th session attempting this fix — finally verified end-to-end.
- 10 new tests (7 cache invalidation + 3 embeddings safety gate). ~3588 total (3050 app + 538 ML).

## Session 66: Parallel Worktrees + Enrichment Validation + GEDCOM Admin + Portfolio (2026-02-24) — v0.72.0
- **Harness overhaul**: 7 subagent definitions (.claude/agents/). Session log archival: renamed 21 files, recovered 4 from git, created INDEX.md with analytics. First successful parallel worktree execution with 3 simultaneous subagents.
- **GEDCOM admin UI (AD-164)**: Enhanced /admin/gedcom with Supabase-backed version management. Version info panel, upload/preview/apply/cancel flow, version history, re-enrichment queue counter. 25 new tests.
- **Enrichment validation**: Added --dry-run mode to run_combined_pipeline.py. Fixed _find_identity_for_face() to prefer CONFIRMED over INBOX identities. Validated enriched prompts reach 400-3700+ GEDCOM tokens (AD-159 confirmed). 5 real Gemini API calls ($0.06).
- **Portfolio**: docs/portfolio/ml_pipeline_writeup.md — 134-line technical writeup for interview use.
- **Infrastructure**: GEDCOM versioning migration on production Supabase. .claude/worktrees/ support.
- 25 new tests. ~3578 total (3040 app + 538 ML).

## Session 65d: Disk Space Fix + GEDCOM Versioning + Harness (2026-02-24) — v0.71.0
- **Disk space fix (AD-162)**: Root cause: Docker image bundled 393MB of unnecessary backup files, push endpoint created unbounded .bak files, no staging cleanup. Fix: .dockerignore excludes ~400MB, startup cleanup, backup pruning (keep 3), upload finally block, health endpoint reports disk space. All 3 uploads verified in Chrome browser (admin logged in).
- **GEDCOM temporal versioning (AD-163)**: gedcom_versions table with SHA256 dedup. version_id/superseded_by/is_current columns on existing tables. gedcom_change_log for field-level diffs. gedcom_enrichment_queue for Gatekeeper-pattern re-enrichment. current_gedcom_individuals view. Versioned import script with diff detection. Multi-community ready.
- **Harness**: Post-session eval Stop hook. Enhanced session_assessment.sh with 8 check categories. CLAUDE.md: /clear rule, /compact ban.
- 30 new tests (10 disk cleanup + 20 GEDCOM versioning). ~3553 total (3015 app + 538 ML).

## Session 65c: Upload Fix (MANDATORY) + Verification Sweep + Harness (2026-02-24) — v0.70.0
- **Upload fix (AD-161)**: Root cause: subprocess loaded full buffalo_l model (~300-500MB) in separate process, doubling memory with main app's hybrid models → OOM on Railway 512MB. Fix: replaced subprocess with background thread sharing main process's hybrid models via `prefer_hybrid=True`. R2 crop upload fix: was searching by identity UUID, now uses face_ids from status file.
- **Production verification**: All 3 upload surfaces tested with authenticated sessions. /upload: "1 face extracted, 1 added to Inbox" (no OOM). /compare/pair: face detected. /estimate: date estimate returned.
- **GEDCOM linking verification**: Search, link/unlink round-trip, auth guards, surname variants — 6/6 PASS.
- **Harness enforcement**: Mandatory Session Outputs section in CLAUDE.md. Browser Verification Rule. Session prompt template. Self-evaluation script.
- ~3475 tests (2937 app + 538 ML).

## Session 65b: GEDCOM Linking UX + Enrichment Pipeline Fix (2026-02-24) — v0.69.0
- **Production verification**: Compare pair PASS, face overlay toggle PASS, share links PASS, navigation PASS, health PASS. Upload skipped (admin auth required).
- **GEDCOM ↔ Identity linking (AD-160)**: Admin-only post-identification "Link to Family Tree" step. Fuzzy name search with Sephardic surname variants (Capeluto/Capuano/Capelluto etc.). In-memory cache of 21,809 GEDCOM individuals. Link saves to gedcom_face_links, auto-enriches birth/death. Unlink with soft delete. Person page shows link status.
- **Enrichment pipeline fix (AD-159 update)**: Root cause: `variant="curated"` only included person's own data (~106 tokens). Changed to `variant="first_order"` for parents/spouses/children/siblings (400-1000+ tokens). gemini_config and response_summary fields now populated in API call logging. Enrichment level tracking (full/partial/thin/none).
- 28 new tests. 3521 total (2983 app + 538 ML).

## Session 65a: Upload Fix + Compare Overhaul + UX Polish (2026-02-23) — v0.68.0
- **Upload fix (CRITICAL)**: Subprocess death detection via PID tracking + 5-min timeout for "processing" state. Error shows crash log excerpt, reassures user photo is saved. `write_status_file()` preserves started_at/pid.
- **Two-photo compare** (/compare/pair): New feature with face detection, face selection, cosine similarity with calibrated confidence tiers. Three new routes.
- **Prompt fidelity audit** (AD-159): 17/136 (12.5%) 64d Gemini calls received GEDCOM context (~106 tokens). Token variation primarily driven by face count. `gemini_config` field not populated — gap in logging.
- **Face overlay toggle**: Show/Hide Faces button on photo viewer + public page. Admin default ON, non-admin OFF.
- **Navigation audit**: All critical paths bidirectional (Photo ↔ Person ↔ Collection).
- 24 new tests. ~3493 total (2956 app + 537 ML).

## Session 64c: Concerns Resolution + Harness Validation (2026-02-23)
- Harness validation: 4 hooks, 6 skills, 39 rules audited. Pre-commit hook regex bug found (^git commit misses chained commands).
- Exception narrowing: 12 `except Exception` handlers replaced with specific `_SUPABASE_ERRORS` in GEDCOM loading, face alignment, and Gemini logging paths. Schema bugs (KeyError, AttributeError) now crash loudly.
- API cost tracking verified: 10 rows in gemini_api_calls table, cost_usd populated ($0.0004-$0.0012/call). Fixed missing total_tokens field.
- Calibrated scores verified end-to-end: neighbor cards (SimilarityCalibrator), compare upload (calibrated_similarity_batch), result cards (confidence_pct → tier labels).
- Roadmap updated: Sessions 65-67 planned (UX → Portfolio → LoRA). AD-158 documents sequencing rationale.
- +4 new tests. ~3472 total (2884 app + 538 ML).

## Session 64b: Execute What 64 Deferred (2026-02-23) — v0.67.1
- Supabase tables created: `face_gemini_alignments`, `gemini_api_calls` (SQL scripts from S64 executed)
- 127 face alignments migrated from JSON to Supabase (0 failures)
- GEDCOM context builder implemented: `_build_parsed_gedcom_from_supabase()` fully wired
  - Reconstructs ParsedGedcom from Supabase (21,809 individuals, 6,680 families, 40K events)
  - Fixed 3 bugs: column name (gedcom_xref→gedcom_id), pagination (1000→all), identities unwrapping
- Dry-run on 3 strategic photos: Vida Capeluto (6/6 faces), group (14/14), GEDCOM-linked (3/3 +GEDCOM)
- All API calls logged to gemini_api_calls (10 total from dry-runs)
- Production verified: all 7 routes return 200, face cards rendering
- AD-153 through AD-157. 8 new tests. ~3468 total (2930 app + 538 ML).

## Session 63: Close the Gaps, Calibrate, Re-Run (2026-02-23) — v0.66.0
- Deployed face alignment to Railway, verified on 3 real photos (100% success, $0.03)
- GEDCOM Supabase tables created: gedcom_individuals (21,809), gedcom_events (40,140), gedcom_relationships (145,574), gedcom_face_links (61)
- GEDCOM face linking with Sephardic surname variants (39 auto, 4 review, 12 no match)
- Ground truth calibration pairs: 348 pairs (221 match, 127 non-match) from confirmed identities
- Isotonic regression calibration: AUC=0.9577, threshold@90%=0.268, threshold@95%=0.269
- Recalibration hooks: on_face_merge, on_match_reject, on_identity_confirm (event-driven with safety rails)
- Batch face alignment pipeline (scripts/run_batch_alignment.py) — 5-photo validation passed, full run submitted
- AD-149 (isotonic regression), AD-150 (continuous recalibration), AD-151 (GEDCOM face linking)
- 29 new ML tests (12 calibration + 17 hooks). ~3402 total (2864 app + 538 ML).
- Outcomes: docs/session_context/session_63_outcomes.md

---

## Release Version History

| Version | Date | Session | Test Count |
|---------|------|---------|------------|
| v0.85.1 | 2026-03-02 | 82f | 3398+551 |
| v0.85.0 | 2026-03-01 | 82e | 2391+551 |
| v0.84.0 | 2026-03-01 | 82d | ~3398+551 |
| v0.83.2 | 2026-03-01 | 81C | 3366+551 |
| v0.83.1 | 2026-03-01 | 81B | ~3366+551 |
| v0.83.0 | 2026-03-01 | 81 | ~3030 |
| v0.82.1 | 2026-02-28 | 80-cont | 2395+538 |
| v0.82.0 | 2026-02-28 | 80 | ~3272 |
| v0.81.0 | 2026-02-28 | 79 | 3246+538 |
| v0.80.0 | 2026-02-28 | 78 | 3254+538 |
| v0.79.1 | 2026-02-28 | 77 | ~3163 |
| v0.79.0 | 2026-02-28 | 76a | 3205+537 |
| v0.78.0 | 2026-02-28 | 75 | 2176+977 |
| v0.77.1 | 2026-02-27 | 73 | 2166+1014 |
| v0.77.0 | 2026-02-27 | 72 | 2166+1014 |
| v0.76.1 | 2026-02-27 | 71D | 3163 |
| v0.76.0 | 2026-02-26 | 71 | 3146 |
| v0.75.0 | 2026-02-25 | 70 | 3133+538 |
| v0.74.0 | 2026-02-25 | 69 | 3057+538 |
| v0.73.1 | 2026-02-25 | 68 | 3064 |
| v0.72.0 | 2026-02-24 | 66 | 3040+538 |
| v0.71.0 | 2026-02-24 | 65d | 3015+538 |
| v0.70.0 | 2026-02-24 | 65c | 2937+538 |
| v0.69.0 | 2026-02-24 | 65b | 2983+538 |
| v0.68.0 | 2026-02-23 | 65a | ~2956+537 |
| v0.67.1 | 2026-02-23 | 64b | ~2930+538 |
| v0.67.0 | 2026-02-23 | 64 | ~2906+538 |
| v0.66.0 | 2026-02-23 | 63 | ~2864+538 |
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
