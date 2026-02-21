# Changelog

All notable changes to this project will be documented in this file.

## [v0.56.0] — 2026-02-21

### Added
- **Real GEDCOM import**: Fox/Capeluto/Fogel/Waldorf Family Tree (21,809 individuals, 6,680 families) from Ancestry.com
- 33 archive identities linked to Ancestry records with direct URLs
- 19 family relationships (5 spouse, 14 parent-child) from real genealogical data
- `ancestry_links.json` — maps identity IDs to Ancestry person pages
- Human-reviewed CSV workflow for correcting automated GEDCOM matches

### Fixed
- **Birth year data preservation**: Synced from production before pushing to prevent overwriting 31 admin-reviewed birth years (Lesson 78)
- Merged GEDCOM enrichment (birth/death dates, places, gender) with Session 49B manual reviews

### Documentation
- Lesson 78: Production-local data divergence flagged as #1 recurring deployment failure

## [v0.55.3] — 2026-02-20

### Fixed
- **Compare/Estimate loading indicator**: CSS `display: block` for div-based htmx indicators (was `inline`), submit button disabled during processing, spinner enlarged (h-10 w-10), auto-scroll to spinner on file selection, accurate "10-30 seconds" timing text

### Documentation
- **Test triage**: 127 test failures classified — all state pollution, 0 real bugs. All pass in isolation.
- **Admin auth verification**: Auth mechanism documented (email-in-set, cookie sessions, 401/403). Playwright admin auth not configured (tests run with auth disabled).

### Testing
- 1 new test (submit button disable CSS assertion)

## [v0.55.2] — 2026-02-20

### Documentation
- **HD-014**: Every deploy must include production Playwright verification
- **AD-122**: Silent failures are bugs — general principle (subprocess.DEVNULL, ML fallbacks, swallowed exceptions)
- Post-deploy hook updated with Playwright reminder
- CLAUDE.md: post-deploy Playwright rule (Session Operations #3), DEVNULL ban (AD-122)
- Production verification: all 4 audit fixes confirmed live on production via MCP Playwright
- Admin routes: all 60 admin-protected routes correctly return 401 for unauthenticated access

## [v0.55.1] — 2026-02-20

### Fixed
- **Mobile navigation on public pages** — All 15+ public pages (/, /photos, /people, /map, etc.) had nav links hidden below 640px with no alternative. Added global JS that injects hamburger menu + slide-out overlay on mobile. (H1)
- **Styled 404 for unknown routes** — Arbitrary paths like `/nonexistent-page` returned bare "404 Not Found" text. Now returns styled page matching existing photo/person 404 design. (M1)
- **subprocess.DEVNULL in approve handler** — Same class of bug as v0.55.0 upload fix: approve-upload handler silenced all subprocess output, making debugging impossible. Now logs to file. (M3)
- **Missing favicon** — All pages returned console 404 for favicon.ico. Added inline SVG favicon (indigo "R") via site-wide headers. (M4)

### Testing
- 13 new tests (2509 total): public page mobile nav (7), styled 404 catch-all (4), favicon (2)

### Documentation
- Comprehensive Playwright-first site audit: 18 pages, 25+ user actions tested
- Audit findings: docs/ux_audit/session_findings/session_49b_audit.md

## [v0.55.0] — 2026-02-20

### Fixed
- **Sort routing in browse mode** — Sort controls (A-Z, Faces, Newest) on `/?section=to_review&view=browse` dropped the `view=browse` parameter, causing clicks to revert to focus mode where sorting is ignored. Sort links now preserve the current view mode.
- **Upload stuck at 0% forever** — When background upload processing failed (subprocess crash), `stderr` was piped to DEVNULL and no status file was created, causing infinite "Starting..." polling. Now writes initial status file before spawning, logs subprocess output to file, and shows error with log excerpt after 2-minute timeout.
- **Compare upload confirmed working** — Investigated "silent failure" report; compare endpoint processes uploads correctly on production (verified via curl and Playwright). Issue was likely transient or UX-related (no visible progress during 5-10s processing).

### Testing
- 10 new regression tests (2496 total): sort link view preservation (4), upload status timeout detection (4), compare form smoke (2)

### Documentation
- Session 49B triage log with root cause analysis for all 3 bugs
- HD-013: Smoke tests must test actual user flows (POST/upload), not just page loads

## [v0.54.4] — 2026-02-20

### Documentation
- **AD-120: Silent fallback observability principle** — Generalized from Session 54F: all ML model loading must log actual model (INFO) + WARNING on fallback. Silent fallbacks are invisible to functional tests.
- **AD-121: SSE upload architecture (design only)** — Server-Sent Events for compare/estimate upload progress streaming. 2-3 session epic added to BACKLOG.
- **PERFORMANCE_CHRONICLE.md** — New append-only document tracking optimization journeys. Chronicle 1: compare pipeline 51.2s → 10.5s.
- **HD-012**: Silent ML fallback detection harness rule.
- **OD-006**: Railway MCP Server installed for Claude Code integration.

### Infrastructure
- **Railway MCP Server** — Installed for mechanical enforcement of `railway logs` after deploy. Replaces instruction-following which failed across 4+ sessions.
- **Playwright browser testing audit** — Session 54F confirmed to have NO browser tests (only curl). 8/8 Playwright tests pass now. CLAUDE.md rule updated.

## [v0.54.3] — 2026-02-20

### Performance
- **Compare upload 51.2s → 10.5s on production (AD-119)** — Root cause: buffalo_sc model pack missing from Docker image, forcing fallback to full buffalo_l (det_10g, 10G FLOPs). Fixed by adding buffalo_sc to Dockerfile, loading only hybrid models at startup (not full FaceAnalysis — OOM on Railway 512MB), adding `allowed_modules=['detection', 'recognition']`, ONNX thread optimization, and model warmup. 4.9x improvement for typical photos.

### Fixed
- **OOM crash on Railway** — Startup was loading both buffalo_l FaceAnalysis (5 models) and hybrid models, exceeding 512MB. Now loads only hybrid (det_500m + w600k_r50) at startup; buffalo_l lazy-loaded as fallback.

## [v0.54.2] — 2026-02-20

### Added
- **AD-115 through AD-118** — Memory infrastructure evaluation (current harness sufficient), MLflow integration strategy (targeted, CORAL training first), Face Compare three-tier product plan (Tier 1 prioritized), NL Archive Query deferred.
- **8 new BACKLOG entries** — Face Compare Tiers 1-3, MLflow integration (3 entries), NL Archive Query, Historical Photo Date Estimator.
- **ROADMAP priority restructure** — Confirmed priority ordering from ML tooling and product strategy research session.
- **Planning context** — `docs/session_context/session_54c_planning_context.md` with competitive analysis of 7+ face comparison tools, evaluation of 5 memory/ML tools.

## [v0.54.1] — 2026-02-20

### Added
- **Hybrid detection (AD-114)** — Compare and estimate uploads now use det_500m from buffalo_sc (500M FLOPs, 20x lighter) for face detection + w600k_r50 from buffalo_l for archive-compatible embeddings. Session 54 incorrectly concluded buffalo_sc was fully incompatible — detection and recognition are separate ONNX files that can be mixed. Embedding compatibility: mean cosine sim 0.98. Detection recall: misses ~2 marginal faces on 40-face photos (acceptable for interactive use). Falls back to full buffalo_l if hybrid models unavailable.
- **Production smoke test script** — `scripts/production_smoke_test.py` tests 11 critical paths. Returns non-zero on critical failures. Outputs markdown table for session logs.
- **Production verification harness rule** — `.claude/rules/production-verification.md` (HD-010): mandatory verification after code changes affecting UI or uploads.
- **Playwright MCP config** — `.mcp.json` (gitignored) for future browser-based testing.
- **UX issue tracker coverage verified** — All 5 source files cross-referenced: 35/35 issues mapped. UX-004 updated from DEFERRED to FIXED.
- Real upload testing with timing data: 4 upload tests, all HTTP 200, 0.3-1.3s response times.
- 5 new tests, 1 updated test (2486 total)

## [v0.54.0] — 2026-02-20

### Fixed
- **Compare upload 640px ML resize** — Reduced from 1024px to 640px, matching InsightFace's internal `det_size=(640,640)`. Original image saved to R2 for display; separate 640px copy for ML processing only. Estimated 5-15x speedup vs original 1280px. (AD-110)
- **Estimate upload 640px ML resize** — Same 640px optimization applied to estimate upload face detection path.
- **HTTP 404 for non-existent resources** — `/person/{id}`, `/photo/{id}`, `/identify/{id}`, and `/identify/{a}/match/{b}` now return HTTP 404 (was 200) for non-existent resources. Friendly HTML preserved with same visual design.
- **Estimate loading indicator** — Enhanced with SVG spinner and duration warning ("This may take a moment for group photos"), matching compare page pattern.

### Added
- **AD-110: Serving Path Contract** — Named invariant: web request path MUST NEVER run heavy ML. Hybrid architecture documented: cloud lightweight (640px, compare) + local heavy (buffalo_l, batch). Future: MediaPipe client-side → remove InsightFace from Docker.
- **AD-111-113** — Face lifecycle states (future design), serverless GPU (rejected), ML removal from serving path (rejected as premature).
- **UX Issue Tracker** — `docs/ux_audit/UX_ISSUE_TRACKER.md` with 35 issues, all with dispositions (14 fixed, 7 planned, 10 backlog, 3 deferred, 1 rejected).
- **UX Audit README** — `docs/ux_audit/UX_AUDIT_README.md` explaining the audit framework.
- **buffalo_sc investigation** — Embeddings NOT compatible with buffalo_l (MobileFaceNet vs ResNet50 backbone). Cannot switch without re-embedding all ~550 faces.
- 1 new test, 6 updated tests (2481 total)

## [v0.53.0] — 2026-02-20

### Fixed
- **Compare upload loading indicator** — HTMX indicator CSS now handles both `.htmx-request .htmx-indicator` (descendant) and `.htmx-request.htmx-indicator` (combined) selectors. Spinners that use `hx-indicator="#id"` now display correctly.
- **Compare upload feedback** — Loading message updated from "a few seconds" to "up to a minute for group photos" with animated spinner. Scroll-to-results on file selection.
- **Uploaded photo visibility** — Compare upload results now show the uploaded photo with face count badge above the match results.
- **Compare resize optimization** — Reduced resize target from 1280px to 1024px for faster face detection on Railway's shared CPU.

### Added
- **Comprehensive production audit** — 35 routes tested (12 public, 10 admin, 13 detail/API). All routes healthy, all auth guards correct, all R2 images verified. Results in `docs/ux_audit/`.
- **UX assessment framework** — `docs/ux_audit/` directory with PRODUCTION_SMOKE_TEST.md, UX_FINDINGS.md, FIX_LOG.md, PROPOSALS.md for systematic UX tracking.
- **Harness decisions HD-008, HD-009** — Production smoke test as session prerequisite, HTMX indicator CSS dual-selector rule.
- 4 new tests (2480 total)

## [v0.52.1] — 2026-02-19

### Fixed
- **Docker build failure** — Added `g++` to Dockerfile apt-get for insightface Cython extension (`mesh_core_cython`) compilation. Previous deploy failed with "command 'g++' failed: No such file or directory."

### Added
- **Production smoke test** — `scripts/smoke_test.sh` verifies homepage, health/ML status, photo page with face overlays, compare, estimate, admin auth gate, people, and photos pages against the live site.

## [v0.52.0] — 2026-02-19

### Added
- **ML pipeline on Railway** — InsightFace buffalo_l face detection + ONNX Runtime now run in Docker. Pre-downloaded model at build time (~300MB). `PROCESSING_ENABLED=true` by default.
- **Gemini date estimation on upload** — Estimate upload now calls Gemini 3.1 Pro Vision API in real-time for date estimation. Graceful degradation: ML+Gemini (full), ML-only (faces), Gemini-only (date), neither (honest message).
- **"Name These Faces" on public photo page** — Admin users see the sequential identifier button on `/photo/{id}` (was modal-only). HTMX loads inline sequential mode.
- **Cloud-ready photo processing** — Admin uploads on Railway trigger full face detection pipeline. `ingest_inbox.py` respects `DATA_DIR`/`STORAGE_DIR` env vars. Photos and crops auto-uploaded to R2 on completion.
- **Health check ML status** — `/health` reports `ml_pipeline: ready|unavailable` and `processing_enabled: true|false`.
- 30 new tests (2465 total)

### Changed
- Dockerfile upgraded from lightweight web-only to full ML processing image
- `requirements.txt`: added `insightface==0.7.3`, `onnxruntime>=1.20`, `google-genai>=1.0`
- Upload handler passes `--data-dir` to ingest subprocess (Railway STORAGE_DIR support)

### Notes
- Face overlay clicks on public `/photo/{id}` page confirmed working — no Session 51 regression found (overlays are standard `<a>` tags with `href`)
- Compare upload handler already had InsightFace detection with graceful fallback — just needed dependencies installed

## [v0.51.1] — 2026-02-19

### Fixed
- **Compare upload honest messaging** — Production uploads now show "Photo received!" with honest messaging about offline processing and email fallback, instead of misleading "Check back soon for comparison results."
- **Removed Estimate/Compare tab duplication** — /compare and /estimate no longer show redundant tab switchers. Both are standalone routes accessible from the top nav.
- **Supabase keepalive in health check** — `/health` endpoint now pings Supabase auth API (`/auth/v1/health`) to prevent free-tier inactivity pause. Railway's 30-second health check interval generates the needed API traffic.

### Added
- `_ping_supabase()` function with error handling (returns ok/not_configured/error status)
- `_auth_disabled_warning()` helper — returns warning banner when auth env vars not configured
- 16 new tests (2433 total)

### Notes
- **BUG 2 (Name These Faces)**: Diagnosed as NOT A BUG — button is correctly admin-only per AD-104. Tester was not logged in as admin. Tests verify this.
- **BUG 5 (Email notifications)**: Audited — no misleading user-facing text. Backend email (Resend API) is gated behind env var. OPS-001 (custom SMTP) remains in backlog.

## [v0.51.0] — 2026-02-19

### Added
- **"Name These Faces" sequential mode** — Admin can click "Name These Faces (N unidentified)" button on any photo with 2+ unidentified faces. Activates sequential mode: first unidentified face auto-highlighted with tag dropdown open and auto-focused. After tagging, auto-advances to next face left-to-right. Progress banner shows "X of Y identified" with progress bar. "Done" button exits.
- **PRD-021: Quick-Identify from Photo View** — Documents existing tag dropdown infrastructure (P0) and new sequential mode (P1).
- **AD-104: Quick-Identify architecture** — Admin-only inline identification, same merge/create code paths as existing flow.
- 16 new tests (2417 total).

### Notes
- P0 Quick-Identify (inline tag dropdown on face click) was already implemented in earlier sessions. This session focused on the P1 sequential mode for batch identification — the Carey Franco 8-names-in-one-comment use case.

## [v0.50.0] — 2026-02-19

### Fixed
- **Estimate page "0 faces" bug (BUG-009)** — Grid used `face_ids` key but `_photo_cache` stores faces as `faces` list. Changed to `pm.get("faces", [])` so face counts display correctly.
- **Compare upload validation** — Added client-side file type (JPG/PNG only) and size (<10MB) validation with inline error messages. Added server-side validation as defense-in-depth. Accept attribute narrowed from `image/*` to `image/jpeg,image/png`.
- **Estimate "no evidence" text** — Changed unhelpful "No detailed evidence available" to actionable "Based on visual analysis. Identify more people to improve this estimate."

### Added
- **Standalone /estimate in navigation** — Added "Estimate" link to public nav bar and admin sidebar. No longer hidden behind Compare tab.
- **Estimate page pagination** — Photo grid shows 24 photos initially with "Load More Photos" HTMX button (was loading 60+ at once).
- **Estimate upload zone** — Drag-and-drop upload on /estimate with date label lookup. Shows existing AI estimate if available, or "check back soon" message.
- **PRD-020: Estimate Page Overhaul** — P0/P1/P2 requirements for transforming /estimate into a standalone "Photo Date Detective" tool.
- **AD-101: Gemini 3.1 Pro** — Use `gemini-3.1-pro-preview` for all vision work (77.1% ARC-AGI-2, improved bounding boxes, $2.00/$12.00 per 1M tokens).
- **AD-102: Progressive Refinement** — Fact-enriched re-analysis architecture. Re-run VLM when verified facts accumulate. Combined API call for date + faces + location. Gatekeeper review pattern.
- **AD-103: API Result Logging** — Comprehensive logging schema for every Gemini call. Build analytical dataset for model comparison and improvement tracking.
- **PRD-015 updated** for Gemini 3.1 Pro — combined API call, media_resolution, updated cost estimates.
- 16 new tests (2401 total)

## [v0.49.3] — 2026-02-19

### Fixed
- **Photo page 404 for community/inbox photos** — Added _photo_id_aliases map that resolves inbox_* IDs from photo_index.json to SHA256 cache IDs. All "View Photo" links from identify flow now work for community-submitted photos.
- **Compare upload silent failure** — File input now auto-submits form on file selection via onchange handler. Previously, selecting a file did nothing because the HTMX form never received a submit event.
- **Version v0.0.0 in admin footer** — Dockerfile now COPYs CHANGELOG.md so _read_app_version() works in production. Was falling back to v0.0.0 because the file didn't exist in the Docker image.
- **Collection name truncation on identify/person/compare pages** — Removed CSS truncate class from 6 additional locations. Session 49 only fixed stat cards; now all collection names wrap properly.

### Added
- Community feedback context from first Jews of Rhodes Facebook group sharing (docs/session_context/session_49C_community_feedback.md)
- 9 new regression tests (2387 total)

## [v0.49.2] — 2026-02-18

### Fixed
- **Collection name truncation** — stat cards on /photos now wrap text instead of truncating with ellipsis
- **Triage bar tooltips** — Ready/Rediscovered/Unmatched pills now show explanatory text on hover

### Added
- Production route health check baseline (10/10 routes verified)
- Session 47/48 deliverable verification (gatekeeper, harness rules, age overlays — all PASS)
- Interactive session prep checklist at `docs/session_context/session_49_interactive_prep.md`
- Next sessions plan (49B interactive, 50 UX unification, 51 landing page, 52 ML)
- 5 new tests: collection name, triage tooltips (2373 + 5 = 2378 total)

## [v0.49.1] — 2026-02-18

### Added
- **Age on face overlays** — photo viewer shows "Name, ~age" on confirmed faces when both birth year and photo date are known (Session 47 Phase 2F completion)
- **Harness rules** — prompt-decomposition.md, phase-execution.md, verification-gate.md, harness-decisions.md in `.claude/rules/`
- **HARNESS_DECISIONS.md** — HD-001 through HD-007 documenting workflow/harness engineering decisions with full provenance
- **Session log infrastructure** — `docs/session_logs/`, `docs/session_context/`, `docs/prompts/` directories; session 47B retrospective log
- 4 new tests for age overlay rendering (2365 + 4 = 2369 total)
- Lessons 72-76 added to tasks/lessons.md (harness & process)
- HARNESS-001/002/003 backlog items for future harness evaluation

### Changed
- **CLAUDE.md compressed** — 113 → 77 lines; added session management rule references and HARNESS_DECISIONS.md to key docs

## [v0.49.0] — 2026-02-18

### Added
- **ML Gatekeeper Pattern** — ML birth year estimates are now staged proposals requiring admin review before public display (AD-097). `_get_birth_year(include_unreviewed=False)` gates public views; admin sees suggestion cards with Accept/Edit/Reject buttons
- **Bulk Review Page** — `/admin/review/birth-years` with sortable table, inline editing, "Accept All High Confidence" batch action, and "Birth Years" admin nav link
- **Ground Truth Feedback Loop** — accepted/corrected birth years written to `data/ground_truth_birth_years.json` with face appearances for future ML retraining (AD-099)
- **Dynamic Version Display** — sidebar version reads from CHANGELOG.md instead of hardcoded "v0.6.0"
- **Feature Reality Contract** — `.claude/rules/feature-reality-contract.md` enforces data→load→route→render→test chain (AD-098)
- **Session Context Integration** — `.claude/rules/session-context-integration.md` for ingesting planning context files
- **AD-097 through AD-100** — Gatekeeper Pattern, Feature Reality Contract, Feedback Loop, User Input Taxonomy
- **ROADMAP.md split** — 394→90 lines; sub-files in `docs/roadmap/` (SESSION_HISTORY, FEATURE_STATUS, ML_ROADMAP)
- **BACKLOG.md split** — 558→102 lines; sub-files in `docs/backlog/` (COMPLETED_SESSIONS, FEATURE_MATRIX_*)
- 23 new tests (2342 → 2365 total)

### Fixed
- **Phantom feature: unreviewed ML data on public pages** — birth year estimates no longer shown to public without admin approval
- **Version display bug** — sidebar showed "v0.6.0" instead of actual version (v0.49.0)
- **Birth year estimates not deployed** — `birth_year_estimates.json` copied to `data/`, whitelisted in `.gitignore`, added to `OPTIONAL_SYNC_FILES` (session 47B gap fill)
- **BACKLOG breadcrumbs** — deferred session 47 ideas now reference `docs/session_context/session_47_planning_context.md`
- **Deploy safety tests** — added guards for `ml_review_decisions.json` and `ground_truth_birth_years.json` (production-origin data must not be overwritten by deploy)

## [v0.48.0] — 2026-02-18

### Added
- **Help Identify sharing** — Best Match face now has View Photo + View Profile/Help Identify links; Photo Context shows both source photos side by side; share URL fixed to share `/photo/{id}` (FB-46-01, FB-46-02, FB-46-03)
- **Face carousel** — multi-face identities on match page have prev/next arrows with face counter; source photo updates when face changes (FB-46-04, FB-46-05)
- **Deep link CTAs** — "View full profile" / "Help Identify" links under each face on match page; "Explore the Archive" section on /identify pages with Browse/People/Timeline links (FB-46-06, FB-46-07)
- **Lightbox improvements** — face bounding box overlays with state-based colors and clickable navigation; metadata bar (collection + date); "View Photo Page" link (FB-46-08, FB-46-09, FB-46-10)
- **Year Estimation Tool V1** — `/estimate` page with archive photo selector, per-face reasoning display (birth_year + apparent_age = estimated_year), scene evidence from Gemini labels, confidence badges, share/view CTAs (FB-46-11, FB-46-12, FB-46-13, PRD-018)
- **Compare/Estimate tab navigation** — tab links between /compare and /estimate pages
- **`core/year_estimation.py`** — estimation engine with weighted aggregation (confirmed=2x, ML=1x), bbox left-to-right face ordering, scene fallback, graceful degradation
- **AD-092 through AD-096** — year estimation algorithm decisions (weighted aggregation, face-age matching, scene fallback, confidence tiers, tab navigation)
- 56 new tests (2281 → 2342 total)

### Fixed
- **Lightbox "Unidentified" leak** — "Unidentified Person NNN" no longer appears in face bbox data attributes

## [v0.47.0] — 2026-02-18

### Added
- **Photo inline editing** — admin-only inline forms for collection, source, source URL on photo viewer pages, with autocomplete datalist (Block 3)
- **Person metadata editing** — admin-only form for birth/death year, birth/death place, maiden name on person pages (Block 4)
- **Person page life details** — birth/death/place display with "Unknown — Do you know?" contribution prompts for non-admin users (Block 9)
- **Admin nav bar consistency** — `_admin_nav_bar()` component on all admin sub-pages (approvals, audit, GEDCOM, ML dashboard) with active state highlighting (Block 2)
- **Structured action logging** — `log_user_action()` calls for upload approve/reject and annotation approve/reject (Block 7)
- **Geographic autocomplete** — location datalist on place input fields from curated Rhodes diaspora locations (Block 1)
- **Uploader attribution** — shows contributor name on admin upload review cards (Block 1)
- **Comment rate limiting** — IP-based 10 comments/hour limit on person page comments (Block 5)
- **AD-081 through AD-089** — 9 algorithmic decisions documented for sessions 40-41 (Block 6)
- **Postmortems** — /map+/connect 500 errors, collection data corruption, GEDCOM missing dependency (Block 8)
- **Integration smoke tests** — 6 new tests for /person, /person/404, /activity, /admin/approvals, /admin/audit (Block 10)
- **Lessons restructuring** — split 401-line monolith into 6 topic files + 109-line index (Block 11)
- 32 new tests (2249 → 2281)

### Fixed
- **Compare upload crash** — `has_insightface` check imported the function reference (always succeeds) instead of probing actual deferred dependencies (cv2, insightface). Graceful degradation path was never reached on production.
- **Missing opencv-python-headless** — added `opencv-python-headless<4.11` to requirements.txt (pinned for numpy 1.x compatibility)
- **HTML entity rendering** — `&harr;` on /connect page rendered as literal text instead of arrow; fixed with NotStr + numeric entity
- **Activity feed sort crash** — None timestamps caused TypeError in sort; fixed with `or ""` fallback
- **Dependency gate tests** — `tests/test_dependency_gate.py` scans all app/core imports and verifies each resolves

## [v0.46.0] — 2026-02-17

### Added
- **Unified sharing design system** — `og_tags()` helper + generalized `share_button()` with url=, prominent style, title/text params (FE-114)
- **Compare page upload-first redesign** — upload section above the fold, archive search collapsible below (FE-115)
- **Calibrated match confidence labels** — Very likely 85%+, Strong 70-84%, Possible 50-69%, Unlikely <50% (FE-116, AD-091)
- **Shareable comparison result pages** — `/compare/result/{id}` with OG tags, match list, response form (FE-117)
- **Site-wide OG tags + share buttons** — applied `og_tags()` to /photos, /people, /collections; share buttons on /photos and /people (FE-118)
- **Research docs** — compare_faces_competitive.md, sharing_design_system.md
- **PRD-016** (compare faces redesign) and **PRD-017** (sharing design system)
- **AD-091** — calibrated confidence labels for compare results
- 21 new tests (2209 → 2249)

### Fixed
- **uuid import bug** — missing import causing 4 test failures
- **Share JS duplication** — deduplicated share JavaScript across /person and /photo pages

## [v0.44.0] — 2026-02-17

### Fixed
- **`/identify/{id}` 500 error** — `get_photos_for_faces()` returns `set[str]`, but code tried to slice with `[:4]`; wrapped in `list()`
- **Landing page navigation** — was missing Map, Tree, Collections, Connect links; now shows all 8 public pages
- **Critical route test mock** — `get_photos_for_faces` mock returned `[]` instead of `set()`, masking the real type mismatch

### Added
- **GEDCOM test data warning** — admin GEDCOM page shows warning banner when source file contains "test"
- **Compare two-mode UX** — numbered sections "1. Search the Archive" and "2. Upload a Photo" with descriptions
- **"Add Photos" button** — admin-only button on collection detail pages
- **Session 42 verification audit** — systematic check of all 16 routes + 20 features
- **Postmortem: /identify 500** — root cause analysis at `docs/postmortems/identify_500.md`
- 7 new tests (GEDCOM warning, compare modes, landing nav)

### Changed
- Landing page nav uses proper routes (`/photos` instead of `/?section=photos`)
- Test count: 2202 → 2209 (7 new tests)

## [v0.43.0] — 2026-02-17

### Fixed
- **`/map` 500 error (again)** — `PhotoRegistry.get_photo()` method doesn't exist; replaced 5 call sites with `photo_reg._photos.get()`
- **Face overlay misalignment** — overlays positioned relative to padded container instead of image; added `position: relative` to inner image wrapper div
- **Circular face click behavior** — overlay click scrolled to thumbnail, thumbnail clicked scrolled to overlay; both now navigate to `/person/{id}` or `/identify/{id}`
- **Search → wrong Focus mode** — search results linked to `/?section=X#identity-Y` which dumped into Focus mode at position 0; now links directly to `/person/{id}` or `/identify/{id}`

### Added
- **Photo carousel** — prev/next navigation within same collection on `/photo/{id}` pages
  - SVG chevron arrows with bg-black/60 styling
  - "Photo X of Y" position indicator
  - Keyboard ArrowLeft/ArrowRight navigation
  - Collection name as clickable link
  - 4 tests
- **Face overlay alignment regression tests** — 2 tests verifying `position: relative` wrapper and no padding on overlay container
- **Face click behavior tests** — 3 tests verifying navigation to person/identify pages, no circular scroll
- **PRD-015: Gemini face alignment** — research doc for coordinate bridging approach (PROPOSED, no implementation)
- **AD-090** — algorithmic decision for Gemini-InsightFace coordinate bridging

### Changed
- Search results navigate to `/person/{id}` or `/identify/{id}` instead of Focus mode hash links
- Test count: 2194 → 2202 (8 new tests, 3 updated)

## [v0.42.0] — 2026-02-17

### Fixed
- **`/map` 500 error** — added missing `_build_caches()` call; `_photo_cache` was None
- **`/connect` 500 error** — `registry.get_identity()` raises KeyError, not returns None; created `_safe_get_identity()` helper for 6 call sites
- **Collection metadata corruption** — 114 community photos reassigned from "Community Submissions" to "Jews of Rhodes: Family Memories & Heritage" / "Facebook" (2 Benatar photos correctly kept)
- **test_map.py cache poisoning** — reset `_photo_locations_cache` between tests

### Added
- **Shareable identification pages** — crowdsourcing face identification without login
  - `GET /identify/{id}` — "Can you identify this person?" page with face crop, source photos, OG tags, share button
  - `POST /api/identify/{id}/respond` — saves name/relationship/email for admin review
  - `GET /identify/{a}/match/{b}` — side-by-side "Are these the same person?" page
  - `POST /api/identify/{a}/match/{b}/respond` — saves Yes/No/Not Sure confirmation
  - Confirmed identities auto-redirect to `/person/{id}`
  - 15 tests
- **Person page comments** — no-login-required community discussion
  - Comments section with visible/hidden status + admin moderation
  - `POST /api/person/{id}/comment` — submit comment (no auth required)
  - `POST /api/person/{id}/comment/{cid}/hide` — admin-only moderation
  - "No comments yet" empty state + comment form
  - 9 tests
- **Person page action bar** — Timeline, Map, Family Tree, Connections pill buttons
- **Clickable collection link** on photo page → `/collection/{slug}`
- **"Help Identify" CTA** on person page for unidentified persons → `/identify/{id}`
- **Data integrity checker** — `scripts/verify_data_integrity.py` with 18 checks
- **Critical route smoke tests** — `tests/test_critical_routes.py` with 10 route tests
- **Feedback tracker** — `docs/feedback/session_40_feedback.md` with 32 categorized items
- **Collection migration script** — `scripts/fix_collection_metadata.py` with --dry-run/--execute

### Changed
- `/connect` gracefully handles invalid person IDs (no 500)
- Test count: 2159 → 2194

## [v0.41.0] — 2026-02-17

### Added
- **Family Tree visualization** at /tree — hierarchical D3.js tree layout
  - Couple-based nodes: spouse pairs shown side-by-side with pink dashed connector
  - Face crop avatars in each card (letter-initial fallback)
  - Person filter dropdown to focus on specific person's subtree
  - Theory toggle to show/hide speculative connections
  - Zoom/pan with d3.zoom(), auto-zoom to focused person
  - Click node → navigate to /person/{id}
  - Share button, OG meta tags, empty state
  - 12 route tests, 10 data structure tests
- **FAN relationship model** — friends, associates, neighbors as first-class relationship types
  - New types: fan_friend, fan_associate, fan_neighbor
  - Confidence levels: confirmed/theory with filtering
  - Non-destructive removal (marks as removed, doesn't delete)
  - 15 tests for schema + API
- **Relationship editing API** (admin only)
  - POST /api/relationship/add — add relationships with dedup
  - POST /api/relationship/update — change confidence level
  - POST /api/relationship/remove — non-destructive removal
- **Person page tree links** — "View in Family Tree →" in Family and Connections sections
- **Connection photo counts** — shared photo count shown in connection badges
- **GEDCOM admin improvements** — import history section + enrichment status badges
- **Tree in navigation** — added to public nav bar and admin sidebar (between Timeline and Connect)

### Changed
- `get_relationships_for_person()` now returns `fan` key for FAN-type relationships
- `get_relationships_for_person()` accepts `include_theory` param and filters removed relationships
- Navigation link count: 7 → 8 (added Tree)
- Connect page shows "View in Family Tree →" link when family path found

### Decision Provenance
- AD-077: D3 Tree Layout — Hierarchical Reingold-Tilford
- AD-078: Couple-Based Hierarchy — Family Units as Nodes
- AD-079: FAN Relationship Model — Friends, Associates, Neighbors
- AD-080: Inline JSON for Tree Data — Same Pattern as /connect

## [v0.40.0] — 2026-02-16

### Added
- **Social graph + Six Degrees connection finder** at /connect — find how any two people are connected
  - Unified graph from GEDCOM relationships (20 edges) + photo co-occurrence (21 edges)
  - BFS pathfinding with path visualization (family=amber, photo=blue edge styling)
  - D3.js force-directed network visualization
  - Proximity scoring: `(1 / path_length) * avg_edge_weight`
  - Person page "Connections" section with top 5 closest connections
  - Auto-confirmed 14 GEDCOM matches, built 20 family relationships
  - 42 tests (34 ML + 8 app)
- **Shareable collection pages** at /collections and /collection/{slug}
  - Collection directory with preview thumbnails, face counts, OG tags
  - Collection detail with photo grid, people section, share button, timeline cross-link
  - Help-identify banner for unidentified faces, breadcrumb navigation
  - 15 tests
- **Geocoding pipeline + interactive map view** at /map
  - Curated location dictionary with 22 Rhodes diaspora places (lat/lng, aliases, regions)
  - Geocoding script matches Gemini `location_estimate` to dictionary — 267/271 photos (98.5%)
  - Leaflet.js map with CartoDB dark tiles, marker clustering (MarkerCluster)
  - Photo preview popups on marker click (up to 8 photos)
  - Filters: collection, person, decade
  - Share button with filter state preservation
  - 18 tests (10 route + 8 geocoding)
- **Consistent navigation across all public pages**
  - Centralized `_public_nav_links()` helper replaces 11 inline nav arrays
  - All pages show: Photos, Collections, People, Map, Timeline, Connect, Compare
  - Sidebar updated with Collections, Map, and Connect links
  - 11 nav consistency tests
- Decision provenance: AD-077 (social graph), AD-078 (collections), AD-079 (geocoding), AD-080 (map view), AD-081 (nav unification)
- PRDs: 010 (Geocoding & Map), 012 (Social Graph), 013 (Collections)
- 86 new tests — 2120 app tests total

## [v0.39.0] — 2026-02-15

### Added
- **GEDCOM import pipeline** — parse GEDCOM 5.5.1 files and match individuals to archive identities
  - Custom date parser handles ABT, BEF, AFT, BET...AND, partial dates, interpreted dates
  - Layered identity matching: exact name → surname variants → maiden name → fuzzy + date proximity
  - 14/14 test individuals matched correctly against archive (maiden name matching is key)
  - Library: python-gedcom v1.1.0
- **Identity matcher with maiden name support** — GEDCOM "Victoria Cukran" matches archive "Victoria Cukran Capeluto" via surname variant expansion across all name words
- **Photo co-occurrence graph** — built from existing photo data, no GEDCOM required
  - 21 edges from 20 photos with 2+ identified people
  - Top: Victoria Cukran Capeluto ↔ Moise Capeluto (10 shared photos)
  - Foundation for "six degrees" connection finder (Session 38)
- **Relationship graph builder** — creates parent-child and spouse relationships from GEDCOM data cross-referenced with confirmed identity matches
- **GEDCOM admin UI** at /admin/gedcom — upload .ged files, review match proposals, confirm/reject/skip with HTMX inline updates
- **Data enrichment** — confirming a GEDCOM match writes birth_year, death_year, places, gender to identity metadata
- **Person page family section** — shows Parents, Children, Spouse, Siblings from relationship graph with cross-links
- **New metadata keys** — birth_date_full, death_date_full, gender added to identity metadata allowlist
- **CLI import tool** — `python scripts/import_gedcom.py path/to/file.ged [--execute]`
- GEDCOM link in admin sidebar navigation
- Decision provenance: AD-073 (GEDCOM parsing), AD-074 (identity matching), AD-075 (graph schemas), AD-076 (source priority)
- 107 new tests (95 ML + 12 app) — 2081 app + 272 ML = 2353 total

## [v0.38.0] — 2026-02-15

### Added
- **Birth year estimation pipeline** — infers birth years for confirmed identities by cross-referencing photo dates with Gemini per-face age estimates
  - Matches faces to ages via bounding box left-to-right x-coordinate sorting
  - Robust outlier filtering: median + MAD to handle bbox mismatches in group photos
  - Single-person photos weighted 2x (unambiguous matching)
  - Results: 32 estimates from 46 confirmed identities (3 HIGH, 6 MEDIUM, 23 LOW confidence)
  - Script: `python -m rhodesli_ml.scripts.run_birth_estimation`
  - Output: `rhodesli_ml/data/birth_year_estimates.json`
- **Timeline age overlay from ML estimates** — person filter shows "Age ~32" on timeline photo cards using estimated birth years
  - Priority: human-confirmed metadata > ML estimate
  - Confidence-based styling: HIGH=solid, MEDIUM=dashed, LOW=faded
- **Person page birth year** — shows "Born ~1907 (estimated)" in stats line for identities with ML estimates
- **Identity metadata fallback** — `_identity_metadata_display()` shows ML birth years with ~ prefix when no confirmed birth year
- **Validation report** — `python -m rhodesli_ml.analysis.validate_birth_years` with temporal consistency checks, data improvement opportunities, Big Leon validation anchor
- Decision provenance: AD-071 (birth year estimation methodology), AD-072 (UI integration approach)
- PRD 008 updated with data audit findings and actual results
- 48 new tests (37 ML pipeline + 11 integration) — 2069 app + 177 ML = 2246 total

## [v0.37.1] — 2026-02-15

### Added
- **Compare in admin sidebar** — Browse section now includes Compare link between Timeline and About
- **R2 upload persistence** — compare uploads saved to Cloudflare R2 instead of ephemeral local filesystem
  - Uploads survive Railway restarts/deploys
  - Falls back to local storage when R2 write credentials unavailable
  - Metadata includes `status` and `image_key` fields for pipeline tracking
- **Production upload acceptance** — when InsightFace unavailable (Railway), uploads are accepted and saved to R2 with "awaiting analysis" status
- **Contribute to Archive** — compare uploads can be submitted to admin moderation queue via HTMX button
  - Creates entry in `pending_uploads.json` with source="compare_upload"
  - Shows inline confirmation after submission
- **VISION.md** — product direction document capturing the data flywheel, novel contributions, and multi-community vision
- **Roadmap sessions 34-39** — birth date estimation, GEDCOM import, geocoding, social graph, kinship v2, life events
- Decision provenance: AD-070 (future architecture directions), AD-069 updated (R2 storage)
- 12 new tests (2058 total): sidebar navigation, R2 storage, contribute endpoint, graceful degradation

## [v0.37.0] — 2026-02-15

### Added
- **Kinship calibration** — empirical distance thresholds from 46 confirmed identities (959 same-person pairs, 385 same-family pairs, 605 different-person pairs)
  - Key finding: family resemblance (Cohen's d=0.43) is NOT reliably separable from different-person distances — same-person identity matching (d=2.54) remains strong
  - Script: `python -m rhodesli_ml.analysis.kinship_calibration`
  - Output: `rhodesli_ml/data/model_comparisons/kinship_thresholds.json`
- **Tiered compare results** — results grouped into Identity Matches (green), Possible Matches (amber), Similar Faces (blue), and Other Faces
  - CDF-based confidence percentages replace linear similarity scores
  - Calibrated thresholds: strong match <1.16, possible match <1.31, similar features <1.36
  - Person page and timeline cross-links for confirmed identity matches
- **Upload persistence** — uploaded photos saved to `uploads/compare/` with metadata JSON
  - Multi-face detection: when >1 face found, shows face selector buttons
  - `/api/compare/upload/select` endpoint for switching between faces via HTMX
  - "Contribute to Archive" CTA for authenticated users, sign-in prompt for others
- 30 new tests (2046 total): kinship thresholds, tiered results, confidence percentages, upload persistence, cross-links
- Decision provenance: AD-067 (kinship calibration), AD-068 (tiered display), AD-069 (upload persistence)

## [v0.36.0] — 2026-02-15

### Added
- **Face Comparison Tool** — `/compare` route with face selector, similarity search, and upload support
  - Select any identified person from the archive to find similar faces ranked by confidence
  - Results grid with similarity percentage, confidence tiers (Very High/High/Moderate/Low), and photo links
  - Name search filter for quick face selection
  - Upload area for photo comparison (local dev only — requires InsightFace)
  - Graceful degradation on production (archive comparison works, upload shows helpful message)
  - `find_similar_faces()` in `core/neighbors.py` — face-level similarity search across all embeddings
  - 20 unit tests (algorithm, route, API, navigation)
- **Compare link** added to all navigation bars (landing, /photos, /people, /timeline, /photo, /person)
- **Timeline collection filter** — dropdown to filter timeline by collection (`?collection=`)
- **Timeline multi-person filter** — select multiple people (`?people=uuid1,uuid2`), merged chronological view with highlighted names
- **Timeline sticky controls** — person/collection filters and share button stick below nav on scroll
- **Timeline mobile nav** — navigation links visible on all screen sizes (not hidden on mobile)
- PRD stubs for future features: birth date estimation (008), GEDCOM import (009), geocoding/map view (010), life events (011)
- Decision provenance: AD-064 (context event era filtering), AD-065 (face comparison similarity engine)

### Fixed
- **Context events filtered to person's era** — when person filter active, only show events within ±30/+10 years of their photo dates (no more 1522 Ottoman Conquest on a 1920s timeline)
- Timeline `collection` variable name collision with filter parameter fixed

## [v0.35.0] — 2026-02-15

### Added
- **Timeline Story Engine** — `/timeline` route with vertical chronological view of the archive
- Decade markers with proportional grouping of photos by estimated year
- 15 historical context events for Rhodes Jewish community (1522–1997), source-verified from Yad Vashem, Rhodes Jewish Museum, Cambridge UP, and others
- Confidence interval bars on timeline photo cards showing probable date ranges
- Person filter dropdown (HTMX) — filter timeline to show only one person's photos
- Age overlay on photo cards when person filter active and birth_year available
- "Share This Story" button with clipboard copy for filtered timeline URLs
- Year range filtering via URL params (`?start=1920&end=1950`)
- Context events toggle (`?context=off` to hide historical events)
- Timeline link added to sidebar navigation, landing page, /photos, /people nav bars
- `data/rhodes_context_events.json` — curated historical events with categories and sources
- 28 unit tests + 11 e2e acceptance tests for timeline features
- Decision provenance: AD-062 (timeline data model), AD-063 (historical context events)

### Fixed
- Graceful handling of invalid person ID in timeline filter (was throwing KeyError)

## [v0.34.1] — 2026-02-15

### Fixed
- **CORAL training regression diagnosed and fixed** — 9 gemini-2.5-flash fallback labels caused −12.5 pp accuracy drop (67.9% → 55.4%). Added `training_eligible` field to date labels; 2.5-flash labels are display-only, excluded from training by default (AD-061).
- Hash-based train/val split for stable metrics across dataset changes (AD-060)

### Added
- `--exclude-models` flag for `train_date.py` to filter labels by model
- `--include-all` flag for `train_date.py` to override training_eligible filter
- `training_eligible` field in date labels schema — auto-set by `generate_date_labels.py` based on model

## [v0.34.0] — 2026-02-14

### Added
- Date badges on photo cards (/photos page) with confidence-based styling (solid/outlined/dashed)
- AI Analysis metadata panel on photo detail pages with collapsible subsections (date, scene, tags, evidence, ages)
- Decade filtering with pill navigation on /photos
- Keyword search on /photos with match reason labels
- Tag filtering with top-8 tag pills on /photos
- Date correction flow: inline pencil→form→submit with corrections_log.json
- Per-field provenance styling (indigo/AI vs emerald/verified)
- Admin review queue at /admin/review-queue with priority scoring
- Confirm AI endpoint for quick admin validation
- 12 e2e acceptance tests (Playwright) for all discovery features

### Fixed
- Photo ID mismatch: dual-keyed date labels cache maps both inbox_* and SHA256 IDs
- Search index also maps inbox IDs to SHA256 for proper filtering on /photos

### Technical
- AD-056: In-memory photo search (no external engine)
- AD-057: Dual-keyed date label cache
- AD-058: Per-field provenance tracking
- AD-059: Correction priority scoring

## [v0.33.0] - 2026-02-14

### Added
- **116 new community photos processed** — Downloaded from staging, face detection (InsightFace buffalo_l), embeddings generated, uploaded to R2, pushed to production. Archive now at 271 photos, 1061 embeddings, 775 identities, 100 match proposals.
- **250 Gemini 3 Flash date labels** — Labeled 93 new photos in 3 passes (multi-pass retry for 504 DEADLINE_EXCEEDED errors). 81.2% high confidence, 18.8% medium. Decade distribution: 1940s dominant (28.4%), followed by 1950s (17.6%), 1920s (14.0%).
- **Temporal consistency auditor** (AD-054): `audit_temporal_consistency.py` checks for impossible date combinations (photo before birth, after death), age mismatches, and people count discrepancies. Found 16 photos with potentially missed faces.
- **Search metadata export** (AD-055): `export_search_metadata.py` builds full-text search index from Gemini labels — scene descriptions, keywords, clothing notes, visible text, location estimates. Output: `data/photo_search_index.json` (250 documents, schema v1).
- **CORAL model retrained** with 250 labels (up from 157, +59% more training data). MLflow experiment tracking. Results: 73.2% exact accuracy, 96.0% adjacent accuracy, MAE 0.32 decades. Gate passes except 1980s recall (0/7 samples).
- 53 new tests (31 temporal audit + 22 search export). ML test count: 84 → 137.
- Decision provenance: AD-053 (scale-up labeling), AD-054 (temporal auditing), AD-055 (search metadata).

### Fixed
- Search state badge test updated to accept "Inbox" badge text alongside existing states.
- Evaluation script now loads photo_index for proper path resolution.

## [v0.32.0] - 2026-02-13

### Added
- **Suggestion state visibility** — After submitting a name suggestion, the face tag dropdown shows inline "You suggested: [name] — Pending review" confirmation instead of just a brief toast. Users can immediately see their suggestion was saved.
- **Admin approval face thumbnails** — Approval cards now show the actual face crop and source photo context thumbnail, not just raw UUIDs. Cards have `data-annotation-id` for targeting.
- **Admin skip + undo + audit log** — Skip button defers annotations for later review (shown at bottom of approvals page). Undo button on approved/rejected cards reverts to pending. Full audit log at `/admin/audit` with chronological entries.
- **Triage bar active state** — Active filter pill gets `ring-2` highlight with brighter background. Inactive pills are visually muted. Clear distinction of current view.
- **"+N more" clickable** — The "+N more" elements in Up Next carousels are now links that navigate to the full unidentified faces list.
- **Annotation dedup** — Duplicate suggestions for the same face/name add confirmations to the existing annotation instead of creating duplicates. Same user can't confirm twice or confirm their own submission. Admin cards show confirmation count.
- **Community confirmation** — Face tag dropdown shows existing pending suggestions with "I Agree" buttons. Other users can confirm suggestions without re-submitting, building community consensus.
- **Acceptance tests** — 11 Playwright e2e tests for the suggestion lifecycle (4 passing, 7 skipped pending auth wiring).
- 22 new unit tests covering all new features. Test count: 1856 → 1878.

## [v0.31.2] - 2026-02-13

### Fixed
- **Welcome modal wall removed** — First-time visitors no longer see a blocking modal. Replaced with a dismissible top banner that doesn't interrupt content viewing. Tests updated to match.
- **Frictionless guest tagging** — Anonymous annotation submissions now save directly (no guest-or-login modal loop). Users see a confirmation toast and can immediately continue tagging. Annotations saved as `pending_unverified` for admin review.
- **Navigation loss on Help Identify** — "I Can Help Identify" button on public photo viewer now links to the first unidentified face from the current photo. Landing page and nav "Help Identify" links go to the correct section (skipped, not inbox).
- **Modal Escape key dismissal** — All 6 modals now support Escape key to close (login-modal, guest-or-login-modal, and confirm-modal were missing it).
- **Guest modal copy** — Removed "credit" and "taking credit" language. Reframed as "Your suggestion will be reviewed by a family member."

### Changed
- 7 new tests (modal dismissibility, contextual CTA, anonymous submission). Test count: 1838 → 1845.

## [v0.31.1] - 2026-02-13

### Fixed
- **Share button copies to clipboard first** — On desktop, the share button now always copies the URL to clipboard with "Link copied!" toast. Previously opened the OS share sheet (confusing on desktop). Mobile still gets native share sheet after copy.
- **Face tag dropdown works for non-admin users** — The "click face → type name → select" flow was admin-only: clicking any result returned 401/403. Now non-admin users see "Suggest match" and "Suggest [name]" buttons that submit name_suggestion annotations for admin review. Anonymous users get the guest-or-login modal.

### Changed
- Tag dropdown placeholder: "Type name to tag..." (admin) vs "Who is this person?" (non-admin)
- 5 new tests (non-admin tag search, admin regression, anonymous flow, dropdown placeholders). Test count: 1846 → 1851.

## [v0.31.0] - 2026-02-13

### Added
- **Date estimation training pipeline** (ML-040): Complete CORAL ordinal regression model with EfficientNet-B0 backbone for predicting photo decades (1900s–2000s). Heritage-specific augmentations (sepia, film grain, scanning artifacts, resolution degradation, JPEG compression, geometric distortion, fading). Soft label training via KL divergence from Gemini decade probability distributions. PyTorch Lightning + MLflow experiment tracking.
- **Gemini evidence-first date labeling** (ML-041): Rewrote `generate_date_labels.py` with structured prompt architecture — 4 independent evidence categories (print format, fashion, environment, technology), per-cue strength ratings, cultural lag adjustment for Sephardic diaspora communities. Supports Gemini 3 Pro/Flash models with cost guardrails and dry-run mode.
- **Regression gate** (ML-042): Mandatory evaluation suite before production deployment — adjacent accuracy >= 0.70, MAE <= 1.5 decades, per-decade recall >= 0.20, calibration check. CLI: `python -m rhodesli_ml.scripts.run_evaluation`.
- **MLflow experiment tracking** (ML-043): Local file-based tracking at `rhodesli_ml/mlruns/`. First experiment `rhodesli_date_estimation` logged with synthetic data dry-run.
- **Signal harvester refresh**: 959 confirmed pairs (+12), 510 rejected pairs (+481 from 29), 500 hard negatives. Rejection signal 17x increase strengthens calibration training feasibility.
- **Decision provenance**: AD-039 through AD-045 in `ALGORITHMIC_DECISIONS.md`. `docs/ml/DATE_ESTIMATION_DECISIONS.md` with 7 detailed decisions including rejected alternatives.
- 53 new ML pipeline tests (CORAL loss, ordinal probabilities, dataset creation, augmentations, model forward/backward, regression gate, label generation). Synthetic test fixtures (30 labels + 30 images).

### Changed
- `rhodesli_ml/pyproject.toml`: Added torchvision, updated Pillow/scikit-learn versions, switched to `google-genai` SDK.
- Training dry-run skips pretrained weight download for faster pipeline validation.
- `.gitignore`: Added `rhodesli_ml/mlruns/` and `rhodesli_ml/checkpoints/`.

## [v0.30.0] - 2026-02-13

### Added
- **Public person page** (`/person/{id}`): Shareable page for each identified person with circular avatar, name, status badge, stats line, and share button. Face/photo gallery toggle. "Appears with" section showing co-appearing identified people with cross-links. OG meta tags for social sharing.
- **Public photos page** (`/photos`): Browse all archive photos with collection filter and sort (newest/oldest/most faces). No admin controls. Each photo links to `/photo/{id}`.
- **Public people page** (`/people`): Browse all identified people with sort (A-Z/most photos/newest). Each person links to `/person/{id}`.
- **Person links from photo viewer**: Person cards on `/photo/{id}` now link to `/person/{id}` instead of internal admin view. "See all photos" link for identified people.
- **"Public Page" link on identity cards**: Confirmed identity cards on the admin People page have a link to `/person/{id}` (opens in new tab).
- **Pipeline script verification tests**: 8 tests verifying all upload pipeline scripts have correct CLI interfaces.
- 59 new tests (person page, person links, public browsing, people page links, pipeline scripts). Test count: 1789 → 1848.

### Changed
- Navigation links on public pages (photo viewer, person page) now point to `/photos` and `/people` instead of `/?section=photos` and `/?section=confirmed`.
- "Explore More Photos" links updated to `/photos`.
- Cross-linked navigation structure: photo → person (cards), person → photo (gallery), person → person ("appears with").

## [v0.29.1] - 2026-02-12

### Added
- **Consistent share button**: Reusable `share_button()` helper with 3 styles (icon, button, link). Web Share API + clipboard fallback. Added to Photos grid, Photo Context modal, People page face cards, and Focus Mode (main card + photo context panel). Replaces inconsistent "Full Page"/"Open Full Page" text.
- **Admin back image upload**: `POST /api/photo/{id}/back-image` file upload endpoint (admin only). `POST /api/photo/{id}/back-transcription` for handwriting transcription. Admin upload form shown on public photo viewer when no back image exists.
- **Batch back association**: `scripts/associate_backs.py` scans for `{name}_back.{ext}` files and links them to front photos. `--dry-run` default.
- **Non-destructive image orientation**: `parse_transform_to_css()` and `parse_transform_to_filter()` convert stored transform strings to CSS. `image_transform_toolbar()` admin UI with rotate/flip/invert/reset. `POST /api/photo/{id}/transform` endpoint. `transform` and `back_transform` added to PhotoRegistry metadata allowlist.
- **Person card scroll-to-overlay**: Clicking a person card scrolls to the corresponding face overlay with a pulse highlight animation. Overlay IDs (`#overlay-{identity_id}`) for scroll targeting.
- 36 new tests (share buttons, flip animation, back upload, orientation tools, viewer polish). Test count: 1733 → 1769.

### Changed
- **Premium photo flip**: Perspective 1200px, dynamic box-shadow on flip, scale(1.02) lift, paper texture (#f5f0e8 + inner shadow), face overlay fade during flip. Button text "Flip Photo"→"Turn Over", "Flip Back"→"View Front".
- **Face overlay label positioning**: Name labels appear below face box when face is in top 15% of image (prevents clipping). Above box otherwise.
- **Quality scores admin-only**: `face_card()` now accepts `is_admin` parameter. Quality scores hidden for non-admin visitors. Hidden when score is 0.
- **Photo container padding**: `padding-top: 1.5rem` on photo hero container prevents overlay label clipping at top edge.

## [v0.29.0] - 2026-02-12

### Added
- **Public photo viewer** (`/photo/{id}`): Shareable, museum-like page with face overlays, person cards, and call-to-action. No auth required. Every photo in the archive is now linkable.
- **Front/back photo flip**: CSS 3D flip animation for photos with back images (handwriting, stamps). `back_image` and `back_transcription` fields in photo metadata model.
- **Open Graph meta tags**: Rich social sharing previews on `/photo/{id}` and landing page. Dynamic descriptions with identified/unidentified counts. Twitter Card support.
- **Web Share API**: Native mobile sharing (share sheet) with clipboard copy fallback on desktop. Toast notification for link copy.
- **Photo download**: `/photo/{id}/download` endpoint serves original file with Content-Disposition header (local) or redirects to R2 (production).
- **Internal UX links**: "Open Full Page" in photo modal, "Full Page" on face cards and photos grid. Every photo reachable via shareable URL.
- **SITE_URL constant**: Module-level canonical URL for OG tags and sharing.
- 61 new tests (public viewer, flip, OG tags, share/download, internal links). Test count: 1733.

## [v0.28.3] - 2026-02-12

### Fixed
- **Annotations sync**: `annotations.json` added to `OPTIONAL_SYNC_FILES` so clean data reaches Railway volume, clearing stale test entries from `/admin/approvals`.
- **Mobile horizontal overflow**: `overflow-x: hidden` on html/body, filter bar selects capped at 10rem on mobile, neighbor card buttons wrap on mobile, landing page nav hidden on mobile. Fixes 470px e2e overflow.
- **Pending upload thumbnails**: Graceful fallback shows filename when staging-preview images fail to load (onerror handler) instead of broken image icons.

### Added
- **Manual search Compare button**: Search results in Focus Mode now show Compare (primary) and Merge (secondary, outline) buttons. Users can view side-by-side comparison before merging.
- 12 new tests (annotations sync, search compare, mobile overflow, thumbnail fallback). Test count: 1653 + 19 e2e = 1672.

## [v0.28.2] - 2026-02-12

### Fixed
- **Test data pollution**: Removed 5 test annotations and 46 contaminated history entries from production data. Fixed Victoria Cukran Capeluto's version_id (76 -> 22, inflated by test renames).
- **Admin staging preview**: Photo thumbnails on pending uploads page now work using session-authenticated `/admin/staging-preview/` endpoint instead of token-only sync API.
- **Duplicate Focus Mode button**: Removed standalone "Focus Mode" button from admin dashboard banner. Focus/Browse toggle lives in each section's header.

### Changed
- **Help Identify ordering**: Quality scores (0-100) now influence ordering. Clear, high-quality faces surface before blurry ones within each confidence tier. Named match targets (e.g., "Rica Moussafer") sort before unidentified ones.

### Added
- **Data safety rules**: `.claude/rules/data-safety.md` with test isolation enforcement. 2 guard tests prevent future test data contamination.
- **Feedback tracking**: `docs/feedback/FEEDBACK_INDEX.md` centralizes all user feedback with status tracking and linked files. `.claude/rules/feedback-driven.md` enforces review at session boundaries.
- **Cleanup script**: `scripts/clean_test_data.py` for emergency test data removal with `--dry-run` default.
- 6 new tests (quality ordering, named match priority, staging preview, path traversal, 404, contamination guards). Test count: 1641.

## [v0.28.1] - 2026-02-12

### Added
- **Face quality scoring** (AD-038): Composite 0-100 score combining detection confidence, face area, and embedding norm. Best-quality crop automatically selected as identity thumbnail everywhere.
- **Discovery UX rules** (`.claude/rules/discovery-ux.md`): 10 principles for all future UI work.
- **Photo enhancement research doc**: Summarizes 3 papers confirming enhancement hurts face recognition.
- **Feedback tracker**: `docs/feedback/CLAUDE_BENATAR_FEEDBACK.md` tracking 11 items with status.

### Changed
- **Larger face crops globally**: Focus mode main crop 128→192px (mobile) / 192→288px (desktop). Neighbor thumbnails 48→64px. More matches strip 64→80px / 80→96px.
- **Quality-aware thumbnails**: `get_best_face_id()` replaces `all_face_ids[0]` in identity cards, neighbor cards, and focus mode.
- **Hover effects**: Face crop images have subtle scale-on-hover indicating clickability.
- 13 new tests (quality scoring), test count: 1622 → 1635.

## [v0.28.0] - 2026-02-12

### Added
- **Discovery UX research**: docs/design/DISCOVERY_UX_RESEARCH.md documenting patterns from MyHeritage, Google Photos, Ancestry and Rhodesli's unique dense community graph advantage.
- **Identity metadata fields**: `generation_qualifier` (e.g., "the Elder") and `death_place` added to identity metadata schema, form, and display.
- **Compact metadata display**: Life summary format "1890–1944 · Rhodes → Auschwitz · née Capeluto" replaces verbose field-by-field display.
- **Smart onboarding**: 3-step surname recognition flow replaces generic welcome modal. Step 1: surname grid from surname_variants.json. Step 2: matching confirmed identities via `/api/onboarding/discover`. Step 3: CTA buttons.
- **Personalized landing page**: When inbox is empty and user has selected interest surnames, shows a horizontal strip of matching confirmed identities above Help Identify section.
- **Admin approvals badge**: Sidebar shows pending annotation count next to Approvals link.
- **"I Know This Person" button**: Renamed from "Suggest Name" for clearer intent.

### Changed
- **Navigation renaming**: "Inbox" → "New Matches" and "Needs Help" → "Help Identify" across sidebar, mobile tabs, section headers, admin dashboard, and face overlay legend.
- **Section subtitles**: Updated to be more descriptive ("faces the AI matched — confirm or correct").
- 33 new tests, test count: 1589 → 1622.

## [v0.27.1] - 2026-02-12

### Fixed
- **Search AND-matching**: Multi-word queries now use AND logic — "Leon Capelluto" finds "Big Leon Capeluto" (both words must match) instead of returning all Capeluto variants. Full matches rank above partial matches.

### Added
- **300px face crops in Focus Mode**: Enlarged from 224px to 288px on desktop for confident identification.
- **More matches strip**: Horizontal scrollable strip shows 2nd-5th best ML matches below main comparison.
- **View Photo links**: Explicit text links below face crops for viewing full source photo.
- **Z-key undo**: Press Z to undo last merge, reject, or skip action in Focus Mode. Stores last 10 actions.
- **Admin photo previews**: Pending uploads page shows thumbnail previews of uploaded photos before approval.
- **Actionability unit tests**: 3 new tests verify VERY HIGH > HIGH ordering, no-match-last, and within-tier distance sorting.
- 22 new tests, test count: 1567 → 1589.

## [v0.27.0] - 2026-02-12

### Fixed
- **Best Match always empty**: All 16 proposals in proposals.json targeted INBOX identities, not SKIPPED. Added real-time neighbor computation fallback (`_compute_best_neighbor`, `_get_best_match_for_identity`) so Best Match works for all identities.
- **Source photo broken image**: Photo cache uses "filename" key (from embeddings.npy) but code used `photo.get("path")`. Added fallback: `photo.get("path") or photo.get("filename")`.
- **Ordering random**: All 211 SKIPPED identities had no proposals, so all landed in the same tier. Added `batch_best_neighbor_distances()` to `core/neighbors.py` for vectorized batch distance computation. Ordering now uses real embedding distances.
- **Welcome modal on every visit**: Session-based check meant modal reappeared every session. Switched to persistent cookie (`rhodesli_welcomed`, 1-year max-age) with JS-based show/hide.
- **Empty inbox dead end**: Logged-in users with empty inbox saw "All caught up!" instead of useful content. Smart landing now redirects to Needs Help section when inbox is empty.

### Added
- **Real-time neighbor computation**: `_compute_best_neighbor()` and `batch_best_neighbor_distances()` provide ML suggestions without pre-computed proposals.
- **Confidence rings on Best Match**: Face crops show colored ring borders (emerald=strong, blue=good, amber=possible, grey=weak).
- **Human-readable confidence labels**: "Strong match", "Good match", "Possible match", "Weak match" replace raw ML scores.
- **Larger face crops**: Focus mode crops enlarged from w-36/w-48 to w-40/w-56 for better detail.
- **Sticky action bar**: Action buttons stick to bottom of viewport for easy access on long cards.
- **Collapsible Similar Identities panel**: Changed from dismiss (Close) to toggle (Collapse/Expand) using Hyperscript.
- **Reject undo toast**: Reject suggestion action shows toast with Undo button linking to unreject endpoint.
- 10 new tests, test count: 1557 → 1567.

## [v0.26.0] - 2026-02-12

### Added
- **Focus Mode for Needs Help**: Guided single-identity review experience for skipped faces. Shows face + best ML suggestion side-by-side, photo context (collection, co-identified people), action buttons (Same Person/Not Same/I Know Them/Skip), keyboard shortcuts (Y/N/Enter/S), progress counter, Up Next carousel.
- **Actionability scoring**: Needs Help identities sorted by ML confidence — strong leads first in both Focus and Browse modes.
- **Visual badges**: "Strong lead" (emerald) and "Good lead" (amber) badges on browse cards indicating ML match quality.
- **Focus/Browse toggle**: Needs Help section now supports Focus and Browse views (matching Inbox pattern).
- **Three new action routes**: `/api/skipped/{id}/focus-skip`, `/api/skipped/{id}/reject-suggestion`, `/api/skipped/{id}/name-and-confirm` for focus mode workflow.
- **Merge route focus_section**: Merge and neighbors routes support `focus_section=skipped` for correct container targeting.
- **AD-030 to AD-037**: 8 rejected/under-investigation algorithmic approaches documented.
- **DECISION_LOG.md**: Chronological record of 18 major architectural decisions.
- **SUPABASE_AUDIT.md**: Auth-only usage audit — no critical path dependency.
- 30 new tests, test count: 1527 → 1557.

## [v0.25.0] - 2026-02-11

### Fixed
- **AI suggestions Compare button broken**: Compare button in skip-hints targeted `#neighbors-{id}` (sidebar) instead of `#compare-modal-content`. Modal never opened.
- **AI suggestion thumbnails not loading**: `find_nearest_neighbors()` returns raw results without face IDs. Skip-hints now enriches results with `anchor_face_ids`/`candidate_face_ids`, matching the `neighbor_card` pattern.
- **Search variant highlighting**: Searching "Capelluto" found "Capeluto" results but couldn't highlight the match. `_highlight_match()` now falls back to variant terms for highlighting.
- **Sidebar search breaks Needs Help layout**: Client-side card filter hid `.identity-card` but left skip-hint containers visible. Card+hint wrappers now carry `data-name` for unified filtering.
- **Staged uploads stuck**: Admin pending page had no action for staged uploads — only the CLI API could clear them. Added "Mark Processed" button with `POST /admin/pending/{id}/mark-processed`.
- **Detach button looked destructive**: Red styling and terse confirmation made non-destructive detach look scary. Changed to neutral slate + explains reversibility ("You can merge it back later").

### Added
- **UX audit (Session 18)**: 7 user story walkthroughs, 10 UX issues identified. `docs/UX_AUDIT_SESSION_18.md` + `docs/design/UX_PRINCIPLES.md` (10 principles).
- **Compare modal → Photo context (UX-001)**: "View Photo" buttons with `from_compare=1` for back navigation.
- **Back to Compare navigation**: Photo modal shows "Back to Compare" button when opened from compare modal.
- **Post-merge guidance banner (UX-002)**: Unnamed identities show "Grouped (N faces) — Add a name?" after merge.
- **Grouped badge**: Unnamed multi-face identities show purple "Grouped (N faces)" badge.
- **Compare modal sizing (UX-006)**: `max-w-[90vw] lg:max-w-7xl` for better photo comparison.
- **Compare modal filter preservation (UX-005)**: `?filter=` flows through compare endpoint, face nav, and neighbor_card.
- **Variable suggestion count**: Skip-hints adapts count based on confidence: 3 for strong, 2 for moderate, 1 for weak matches.
- **UX principles doc**: `docs/design/UX_PRINCIPLES.md` with 10 design principles.
- **UX context rule**: `.claude/rules/ux-context.md` — checklist for all UX changes.
- **Co-occurrence signals**: Neighbor cards show "N shared photos" badge when identities appear in the same photos.
- **Compare zoom**: Click-to-zoom on face crops in compare modal with cursor-zoom-in/out toggle.
- 54 new tests, test count: 1473 → 1527.

## [v0.24.0] - 2026-02-11

### Fixed
- **Search broken for non-confirmed identities**: `search_identities()` hard-filtered to CONFIRMED state only. Rewrote to search ALL non-merged states, with CONFIRMED ranked first. Tag-search and `/api/search` now find SKIPPED, INBOX, and PROPOSED identities.
- **Face tag URL encoding**: Face IDs containing colons/spaces (e.g., `Image 924_compress:face4`) broke HTMX URLs. All face IDs now URL-encoded in HTMX attributes.
- **Auto-confirm on tag**: Creating an identity from the tag dropdown now auto-confirms INBOX/PROPOSED/SKIPPED identities.

### Added
- **Surname variant search (BE-014)**: `data/surname_variants.json` with 13 Rhodes Jewish surname variant groups. Searching "Capeluto" also finds "Capelouto", "Capuano", etc. Bidirectional matching with 10 tests.
- **Identity metadata edit UI (BE-011)**: Inline HTMX edit form for admin metadata editing (maiden name, birth/death year, birth place, bio, relationship notes). Pre-fills existing values, returns updated display with OOB toast.
- **ML suggestions redesign**: Replaced raw "dist 0.82, +5% gap" with visual confidence tiers (Very High/High/Moderate/Low/Very Low), face crop thumbnails, and Compare/Merge action buttons.
- **Face overlay visual language**: Confirmed faces get always-visible name labels. Color-coded overlay legend (Identified=green, Needs Help=indigo, New=dashed).
- **Decision provenance rule**: `.claude/rules/decision-provenance.md` — behavior changes require documented decisions.
- **Feature completeness rule**: `.claude/rules/feature-completeness.md` — features must handle all states, entry points, and navigation context.
- **Upload safety checks**: File size limits (50 MB/file, 500 MB/batch), batch limit (50 files), server-side file type validation. Cleanup on failure.
- 35 new tests (10 surname variants, 10 all-states search, 6 metadata form, 3 ML suggestions, 6 upload safety), test count: 1438 → 1473.

## [v0.23.0] - 2026-02-11

### Added
- **Triage filter propagation**: Focus mode action buttons (confirm, reject, skip, merge) now preserve the active `?filter=` parameter through the full HTMX chain. Previously, clicking "Confirm" lost the filter and showed unfiltered next cards.
- **Focus mode sorting for filtered views**: `get_next_focus_card()` now accepts `triage_filter`, applies it to identity list, and sorts by `_focus_sort_key` priority. Up Next thumbnails also respect the filter.
- **Photo navigation boundaries**: First and last photos show dimmed arrow indicators instead of no arrows, signaling navigation limits.
- **Neighbor card filter preservation**: Merge buttons in the Similar Identities panel preserve the triage filter when returning to Focus mode.
- **Grammar pluralization**: `_pl()` helper replaces all `face(s)` and `photo(s)` patterns with proper singular/plural forms across the UI.
- **ML pipeline scaffold**: `rhodesli_ml/` package with 26 files — signal harvester, date label loader, model definitions, evaluation harness, training loops, and Gemini date labeling script.
- **ML audit reports**: `docs/ml/current_ml_audit.md` (signal inventory: 947 confirmed pairs, 29 rejections, calibration feasible) and `docs/ml/photo_date_audit.md` (92% of photos undated, silver-labeling feasible).
- 15 new tests (triage filter propagation, photo nav boundaries, pluralization), test count: 1423 → 1438.

## [v0.22.1] - 2026-02-11

### Fixed
- **Match mode filters**: `?filter=ready|rediscovered|unmatched` now works in Match mode. Previously match mode ignored the filter and showed all proposals regardless. Filter flows through the full HTMX chain: initial load → action buttons → Skip → decide → next pair.
- **Up Next filter preservation**: Clicking an Up Next thumbnail now preserves the active filter in the URL. Previously navigated to the unfiltered context, showing the wrong set of faces.
- **Promotion context banners**: Promotion banners now show specific context (e.g., "Groups with Person 033, Person 034") instead of generic text. `core/grouping.py` populates `promotion_context` for `new_face_match` and `group_discovery` promotions.

### Added
- Match mode filter behaviors: `ready` = proposals only, `rediscovered` = promoted faces only, `unmatched` = NN search only (no proposals).
- 15 new tests (6 match filters + 3 Up Next filter + 4 promotion context + 2 grouping context), test count: 1400 → 1415.
- Lesson 63: filter consistency across all navigation paths.
- `.claude/rules/ui-scalability.md` updated with filter consistency rules.

## [v0.22.0] - 2026-02-11

### Added
- **Global reclustering**: `group_all_unresolved()` in `core/grouping.py` clusters ALL unresolved faces (INBOX + SKIPPED), not just inbox. SKIPPED faces are no longer frozen — they participate in ML grouping like Apple Photos and Google Photos.
- **Promotion tracking**: When SKIPPED faces match INBOX or other SKIPPED faces, they are promoted back to INBOX with tracking fields (`promoted_from`, `promoted_at`, `promotion_reason`).
- **Inbox triage bar**: Top of inbox shows Ready to Confirm / Rediscovered / Unmatched counts with filter links. Admin starts with highest-value actions.
- **Triage filter**: `?filter=ready|rediscovered|unmatched` URL parameter narrows inbox views.
- **Promotion badges**: Browse view shows "Rediscovered" or "Suggested ID" badges on promoted identities.
- **Promotion banners**: Focus mode shows contextual banners above promoted faces ("New Context Available", "Identity Suggested", "Rediscovered").
- **Focus mode priority ordering**: confirmed_match > VERY HIGH proposals > promotions > HIGH proposals > other proposals > unmatched.
- **source_state tracking**: `proposals.json` now includes `source_state` field to identify proposals from SKIPPED faces.
- 31 new tests (13 global grouping + 18 triage UX), test count: 1355 → 1400.

### Data
- 4 groups formed (8 faces → 4 clusters), 4 identities merged
- 7 SKIPPED faces promoted: 1 new_face_match, 6 group_discovery
- 16 clustering proposals against confirmed identities
- INBOX: 65→68, SKIPPED: 196→187

## [v0.21.0] - 2026-02-11

### Fixed
- **Merge-aware push to production**: `push_to_production.py` now fetches production state and merges before git push. Production wins on conflicts (state, name, face set, merge, rejection changes). Prevents overwriting admin actions made on production.
- **Grammar pluralization**: Fixed "1 faces" → "1 face" and "1 photos" → "1 photo" in photo grid badges, collection stats cards, and filter bar subtitles
- **Test contamination**: 3 merge suggestion tests wrote to real `data/annotations.json` — now properly mock `_save_annotations`

### Added
- **Clustering proposals UI integration**: Focus mode prioritizes faces with ML proposals (sorted by distance), Match mode shows proposals before live search, Browse view shows "ML Match" badges
- **proposals.json pipeline**: `cluster_new_faces.py` now writes `data/proposals.json` with match proposals; loaded and cached in web app with full cache invalidation
- **Staging lifecycle**: `POST /api/sync/staged/mark-processed` endpoint marks staging jobs as processed after pipeline completion
- **Zeb Capuano identity restored**: Merged and confirmed as 24th confirmed identity
- **Collections carousel**: Horizontal scroll layout for 5+ collections, grid for fewer
- 4 new `.claude/rules/` files: data-sync, ui-scalability, ml-ui-integration, post-pipeline-verification
- 22 merge-aware push tests, 12 proposal tests, 6 staging lifecycle tests, 3 collection/grammar tests
- Test count: 1340 → 1355

## [v0.20.4] - 2026-02-10

### Fixed
- **Face overlay boxes missing on Nace Collection photos**: 12 photos uploaded via pipeline had no bounding box overlays because width/height was never stored during ingestion. Root cause: `extract_faces()` loaded the image but didn't return dimensions, and `process_single_image()` never stored them.
- **Ingestion pipeline now stores image dimensions**: `extract_faces()` returns `(faces, width, height)` tuple; `process_single_image()` calls `PhotoRegistry.set_dimensions()` to persist them in `photo_index.json`

### Added
- `PhotoRegistry.set_dimensions()` method for storing width/height on photo records
- `scripts/backfill_dimensions.py` — backfill script with `--dry-run`/`--execute` for photos missing dimensions
- 7 new tests: dimension storage in ingestion, PhotoRegistry.set_dimensions(), backfill script (happy path, skip, dry-run)
- Test count: 1299 → 1306

## [v0.20.3] - 2026-02-10

### Fixed
- **Keyboard shortcuts ignore modifier keys**: Cmd+R no longer triggers Reject; added metaKey/ctrlKey/altKey guard to global keydown handler
- **Upload feedback**: Admin uploads on production now show clear success panel with collection/source info and link to Pending Uploads
- **Pending uploads visibility**: Admin uploads on production now create "staged" entries in pending_uploads.json — appear on Pending Uploads page with badge count

### Added
- 12 new Nace Capeluto Tampa Collection photos processed (45 faces detected, 14 match proposals)
- Staged upload status type for admin uploads on production
- 2 new tests (modifier keys, staged admin upload, pending page staged items)
- Test count: 1297 → 1299 | Photos: 126 → 138 | Faces: 375 → 420

## [v0.20.2] - 2026-02-10

### Fixed
- **Production Display Bugs (5 fixes)**: Traced from rendered HTML back to root causes
  - **Photo count 124→126**: `embeddings.npy` was gitignored and never included in Docker bundles. Added to git tracking + `REQUIRED_DATA_FILES` for production sync.
  - **Inbox "?" placeholder**: Focus card showed "?" when `main_photo_id` was None (stale embeddings). Now shows crop image when URL is resolvable even without photo link.
  - **Quality 0.00**: Inbox crop filenames don't encode quality. Added `get_face_quality()` fallback to look up from embeddings cache.
  - **"No similar identities"**: Fixed by syncing embeddings.npy to production.
  - **Newspapers.com filter empty**: Fixed by syncing embeddings.npy (photos built from embeddings cache).
- **Photo dimensions**: Backfilled width/height for 2 new staged photos in photo_index.json

### Added
- `get_face_quality()` helper — looks up face quality from embeddings cache for inbox crops
- 9 regression tests for all 5 production display bugs
- Test count: 1288 → 1297

## [v0.20.1] - 2026-02-10

### Fixed
- **Data Integrity**: Restored 2 photos (Image 001, Image 054) from "Test Collection" to "Vida Capeluto NYC Collection" — test contamination from unpatched `save_photo_registry()` call
- **Test Isolation**: Fixed 3 tests that wrote to real data files without mocking save functions (`test_bulk_photos.py`, `test_regression.py`, `test_metadata.py`)

### Added
- **Data Integrity Checker** (`scripts/check_data_integrity.py`): Detects test contamination, invalid states, orphaned references. Fast (<1s), exit code 0/1.
- **Test Isolation Rule** (`.claude/rules/test-isolation.md`): Path-scoped rule enforcing mock-both-load-and-save pattern for all data-modifying test routes
- 6 new data integrity tests (checker validation + real data verification)
- CLAUDE.md Rule #14: test isolation requirement
- Test count: 1282 → 1288

## [v0.20.0] - 2026-02-10

### Added
- **Photo Provenance Model**: Separated `source` (origin/provenance), `collection` (archive classification), and `source_url` (citation link) as distinct fields on photos. Previously `source` served dual duty. Migration script (`scripts/migrate_photo_metadata.py`) copies existing source values to collection.
- **Upload UX Overhaul**: Upload form now has separate fields for collection, source, and source URL — each with autocomplete from existing values. Clear helper text distinguishes the concepts.
- **Photo Source & Source URL Routes**: `POST /api/photo/{id}/source` and `POST /api/photo/{id}/source-url` for admin editing. `POST /api/photo/{id}/collection` now uses `collection` param (breaking: previously used `source` param).
- **Dual Photo Filters**: Photos page has separate Collection and Source filter dropdowns that can be combined. Collection stats cards link to collection filter.
- **Bulk Metadata Editing**: Bulk action bar supports setting collection, source, and source URL simultaneously on selected photos.
- **PhotoRegistry Methods**: `set_collection()`/`get_collection()`, `set_source_url()`/`get_source_url()` on PhotoRegistry. Save/load roundtrip preserves all three fields. Backward compatible with data lacking new fields.
- 22 new provenance tests (registry, routes, migration, filters)

### Changed
- Collection stats on photos page now group by `collection` field (not `source`)
- Bulk update route `/api/photos/bulk-update-source` accepts `collection`, `source`, and `source_url` params (previously only `source`)
- Test count: 1260 → 1282 (22 new provenance tests)

## [v0.19.2] - 2026-02-10

### Added
- **Pipeline Orchestrator** (`scripts/process_uploads.py`): Single-command upload processing pipeline — backup, download, ML processing, clustering, R2 upload, push to production, clear staging. Three modes: interactive (default), `--auto` (no prompts except clustering), `--dry-run` (preview only). Clustering step always pauses for human review. 15 new tests.
- **Pipeline Documentation** (`docs/ops/PIPELINE.md`): Quick start, step-by-step guide, manual commands, common issues, backup restoration.

### Changed
- Updated `.claude/rules/photo-workflow.md` to reference orchestrator as canonical pipeline command.
- Test count: 1245 → 1260 (15 new pipeline orchestrator tests)

## [v0.19.1] - 2026-02-10

### Added
- **Sync Push API** (`POST /api/sync/push`): Token-authenticated endpoint for pushing locally-processed data (identities.json, photo_index.json) back to production. Creates timestamped backups before overwriting. Companion CLI: `scripts/push_to_production.py`. 9 new tests.
- **Upload Pipeline Stress Test**: End-to-end test of the full upload pipeline — download staged, ML processing, clustering, R2 upload, push to production, clear staging. Pipeline report: `docs/sessions/pipeline-test-report-20260210.md`.

### Fixed
- **Data corruption during test suite**: `/api/photo/{id}/collection` route called `photo_reg.save()` directly instead of `save_photo_registry()`, bypassing test mocks and overwriting real `data/photo_index.json` with fixture data on every test run.

### Changed
- Test count: 1235 → 1245 (9 new sync push tests, 1 data corruption fix)

## [v0.19.0] - 2026-02-10

### Added
- **Anonymous Guest Contributions**: Visitors can suggest names and annotations without creating an account. `POST /api/annotations/submit` now shows a guest-or-login modal (not 401) for anonymous users, preserving typed input. New `POST /api/annotations/guest-submit` saves annotations as `anonymous` with `pending_unverified` status. New `POST /api/annotations/stash-and-login` stores annotation in session, shows inline login form, and auto-submits after authentication. OAuth callback also submits stashed annotations. Admin approvals page shows guest annotations with amber "Guest" badge, sorted after authenticated submissions. 12 new tests.

### Changed
- Test count: 1221 → 1235 (14 new/updated tests)

## [v0.18.0] - 2026-02-10

### Added
- **Contributor Merge Suggestions** (Phase 3): Role-aware merge buttons — admins see "Merge", contributors see "Suggest Merge". New `POST /api/identity/{target}/suggest-merge/{source}` endpoint creates `merge_suggestion` annotations. Admin approvals page shows merge suggestions with face thumbnails and "Execute Merge" button. Match mode shows "Suggest Same" for contributors. 18 new tests.
- **Bulk Photo Select Mode** (Phase 7): Select toggle in photo grid filter bar, checkboxes on photo cards, floating action bar with Select All/Clear/Move to Collection. `POST /api/photos/bulk-update-source` endpoint for admin bulk collection reassignment. Event delegation for all interactions. 13 new tests.
- **Login Prompt Modal** (Phase 1): HTMX 401 interceptor extracts `data-auth-action` from trigger element for contextual login messages. Signup link in login modal. `?next=` redirect parameter on login page.
- **Compare Faces UX Overhaul** (Phase 4): Face/photo toggle view, clickable identity names, "1 of N" navigation counter, max-w-5xl modal sizing. 7 new tests.
- **Button Prominence** (Phase 6): View All Photos and Find Similar promoted from underline links to styled buttons with icons. 3 new tests.

### Changed
- **UI Clarity** (Phase 8): "Confirmed" → "People" in sidebar, mobile tabs, stat bar. "Skipped" → "Needs Help" in sidebar and stat bar. Section descriptions added to Inbox, People, Needs Help headers. Empty states rewritten with friendly guidance messages. 9 new tests.
- **Landing Page** (Phase 5): Fixed unidentified stat to include SKIPPED faces. Rewrote About section with historical Rhodes community content (La Juderia, 1492, diaspora). Dynamic `/about` page with community/diaspora/project/FAQ sections. 11 new tests.
- Test count: 1152 → 1221 (69 new tests across 6 new test files)

## [v0.17.2] - 2026-02-10

### Added
- **EXIF Ingestion Integration** (BE-013): `extract_exif()` now runs during `process_single_image()`, storing date_taken, camera, and GPS location on photo records. Camera added to PhotoRegistry metadata allowlist. Best-effort — EXIF failures never break ingestion. 9 new tests.
- **Route Permission Boundary Tests**: 61 tests covering 14 admin data-modification routes (confirm, reject, merge, undo-merge, detach, rename, skip, reset, bulk-merge, bulk-reject, collection, identity/photo metadata). Each route tested for anonymous(401), non-admin(403), admin(success), auth-disabled(pass). Cross-cutting tests for 401 empty body, 403 toast, no 303 redirects.

### Fixed
- **Graceful Error Handling**: `IdentityRegistry.load()` and `PhotoRegistry.load()` now catch `JSONDecodeError` and `KeyError` with descriptive messages. `load_registry()`, `load_photo_registry()`, and `_load_annotations()` degrade to empty defaults instead of crashing the server. 23 new tests.

### Changed
- Test count: 1059 → 1152 (93 new tests across 3 new test files)

## [v0.17.1] - 2026-02-10

### Added
- **Golden Set Analysis Improvements** (ML-011): Refactored `analyze_golden_set.py` into testable `analyze_golden_set()` function, auto-generates from confirmed identities when golden set is missing, graceful empty-set handling. 15 new tests.
- **Contributor Permission Boundary Tests**: 7 safety tests confirming contributors cannot merge, confirm, reject, skip, or approve annotations. Verified `is_trusted_contributor()` is not wired into any route guard.
- **Role Permissions Documentation**: `docs/ROLES.md` with complete permission matrix for viewer/contributor/trusted/admin roles.
- **Undo Merge Route Tests**: 5 route-level HTTP tests covering undo button in toast, contributor rejection, identity restoration, and error paths (no history, nonexistent identity).
- Test count: 1032 → 1059

## [v0.17.0] - 2026-02-10

### Added
- **Merge Audit Snapshots** (BE-005): `source_snapshot` and `target_snapshot_before` saved in every merge_history entry for full reversibility
- **Annotation Merging** (BE-006): `_merge_annotations()` retargets identity annotations when identities are merged
- **Photo-Level Annotations** (AN-002–AN-006): `_photo_annotations_section()` displays approved annotations and provides submission form for captions, dates, locations, stories, and source attributions
- **Photo Metadata** (BE-012): `set_metadata()`/`get_metadata()` on PhotoRegistry with allowlisted fields (date_taken, location, caption, occasion, donor, camera). Admin endpoint `POST /api/photo/{id}/metadata`. Display integrated into photo viewer.
- **EXIF Extraction** (BE-013): `core/exif.py` extracts date, camera, GPS from uploaded photos with deferred PIL imports for testability
- **Golden Set Diversity Analysis** (ML-011): `scripts/analyze_golden_set.py` examines identity distribution, pairwise potential, collection coverage. Dashboard section shows key metrics.
- **Identity Metadata Display** (AN-012): `_identity_metadata_display()` shows bio, birth/death years, birthplace, maiden name, relationships on identity cards
- **Identity Annotations Section** (AN-013/AN-014): `_identity_annotations_section()` with approved annotation display and contributor submission form for bio, relationship, story types
- **Contributor Role** (ROLE-002): `User.role` field (admin/contributor/viewer), `CONTRIBUTOR_EMAILS` env var, `_check_contributor()` permission helper
- **Trusted Contributor** (ROLE-003): `is_trusted_contributor()` auto-promotes users with 5+ approved annotations
- **63 new tests** across 5 new test files (test_merge_enhancements, test_photo_annotations, test_photo_metadata, test_identity_annotations, test_contributor_roles)
- Test count: 969 → 1032

## [v0.16.0] - 2026-02-10

### Added
- **ML Pipeline Improvements**:
  - Post-merge re-evaluation: after merging identities, nearby HIGH+ confidence faces are shown inline for immediate review
  - Rejection memory in clustering: `cluster_new_faces.py` now checks `negative_ids` before matching, preventing re-suggestion of explicitly rejected pairs
  - Ambiguity detection: margin-based flagging when top two matches are within 15% distance of each other
- **ML Evaluation Dashboard** (ML-013): Admin page at `/admin/ml-dashboard` showing identity stats, golden set results, calibrated thresholds, and recent actions
- **Annotation System** (AN-001–AN-005): Full submit/review/approve/reject workflow
  - `POST /api/annotations/submit` — logged-in users submit name suggestions with confidence levels
  - `GET /my-contributions` — user's annotation history with status tracking
  - `GET /admin/approvals` — admin review queue for pending annotations
  - `POST /admin/approvals/{id}/approve` and `/reject` — annotation moderation
- **Structured Names** (BE-010): `rename_identity()` auto-parses first_name/last_name from display name
- **Identity Metadata** (BE-011): `set_metadata()` on IdentityRegistry with allowlisted keys (birth_year, death_year, birth_place, maiden_name, bio, etc.)
  - `POST /api/identity/{id}/metadata` — admin endpoint for editing metadata fields
- **Suggest Name UX**: Non-admin users see "Suggest Name" button on identity focus cards, submitting via annotation system
- **Activity Feed** (ROLE-005): `/activity` route showing recent identifications and approved annotations
- **Welcome Modal** (FE-052): First-time visitor welcome with archive overview, dismissed via session flag
- **43 new tests** across 5 new test files (test_post_merge, test_cluster_new_faces additions, test_ml_dashboard, test_annotations, test_metadata, test_activity_feed)
- Test count: 926 → 969

## [v0.15.0] - 2026-02-10

### Added
- **Staged File Sync API**: Three new endpoints for downloading uploaded photos from production to local machine for ML processing:
  - `GET /api/sync/staged` — list all staged upload files with metadata
  - `GET /api/sync/staged/download/{path}` — download individual staged files (path traversal protected)
  - `POST /api/sync/staged/clear` — remove staged files after processing
- **Download Script** (`scripts/download_staged.py`): Pull staged uploads from production with `--dry-run`, `--clear-after`, and `--dest` flags.
- **Upload Processing Orchestrator** (`scripts/process_uploads.sh`): End-to-end pipeline — download → ingest → cluster → R2 upload → deploy → clear staging. Supports `--dry-run`.
- **18 new tests** for staged sync endpoints (auth, listing, download, path traversal, clearing).
- Test count: 925 → 943

### Changed
- Updated `docs/PHOTO_WORKFLOW.md` with complete upload processing pipeline documentation.

## [v0.14.1] - 2026-02-10

### Fixed
- **Clustering ignores skipped faces**: `cluster_new_faces.py` now includes SKIPPED identities (192 faces) as candidates alongside INBOX and PROPOSED. Previously reported "0 new proposals" for the largest pool of unresolved work.
- **Lightbox face overlays not clickable**: Face overlays in the identity-card lightbox now have click handlers — clicking navigates to the identity's face card in the correct section.
- **Identity links route to wrong section**: `neighbor_card`, `identity_card_mini`, and lightbox face overlays now route to the correct section based on identity state (confirmed/skipped/to_review/rejected) instead of hardcoding `section=to_review`.
- **Footer stats exclude skipped**: Sidebar footer "X of Y identified" now includes skipped faces in denominator (was "23 of 23" → "23 of 215 identified").

### Added
- `_section_for_state()` helper in `app/main.py` — canonical mapping from identity state to sidebar section.
- 9 new tests in `tests/test_skipped_faces.py` covering all 4 bugs.
- Test count: 891 → 900

## [v0.14.0] - 2026-02-10

### Added
- **Token-Authenticated Sync API**: Three new endpoints — `/api/sync/status` (public stats), `/api/sync/identities` and `/api/sync/photo-index` (Bearer token auth). Replaces cookie-based export that never worked for scripts.
- **Sync Script** (`scripts/sync_from_production.py`): Python script with `--dry-run`, `--from-zip` fallback, auto-backup before overwrite, diff summary. Uses `RHODESLI_SYNC_TOKEN` env var.
- **Token Generator** (`scripts/generate_sync_token.py`): Generates secure token with Railway + local setup instructions.
- **Backup Script** (`scripts/backup_production.sh`): Timestamped backups of data files, auto-cleans to keep last 10.
- **ML Refresh Pipeline** (`scripts/full_ml_refresh.sh`): One-command sync -> backup -> golden set -> evaluate -> validate -> dry-run apply.
- **12 new tests** for sync API permission matrix (token validation, 503 on unconfigured, public status endpoint).

### Changed
- `SYNC_API_TOKEN` added to `core/config.py` (from `RHODESLI_SYNC_TOKEN` env var)
- Test count: 879 → 891

## [v0.13.0] - 2026-02-09

### Added
- **AD-013: Evidence-Based Threshold Calibration**: Four-tier confidence system (VERY_HIGH/HIGH/MODERATE/LOW) based on golden set evaluation (90 faces, 23 identities, 4005 pairwise comparisons). Zero false positives up to distance 1.05.
- **Clustering Validation Script** (`scripts/validate_clustering.py`): Compares clustering proposals against admin tagging decisions. Reports agreed/disagreed/skipped/rejected with per-distance-band analysis.
- **Threshold Calibration Script** (`scripts/calibrate_thresholds.py`): Combines golden set evaluation + clustering validation to recommend evidence-based thresholds.
- **Cluster Match Application** (`scripts/apply_cluster_matches.py`): Tiered application of clustering matches with --tier very_high|high|moderate and mandatory dry-run default. 33 matches ready at HIGH tier.
- **15 new tests**: confidence_label boundaries (7), apply_suggestions safety (4), threshold config ordering (4).

### Changed
- `MATCH_THRESHOLD_HIGH` raised from 1.00 to 1.05 (zero false positives, +10pp recall)
- New thresholds: `MATCH_THRESHOLD_VERY_HIGH=0.80`, `MATCH_THRESHOLD_MODERATE=1.15`, `MATCH_THRESHOLD_LOW=1.25`
- UI confidence labels now show 5 tiers: Very High, High, Moderate, Medium, Low
- `cluster_new_faces.py` uses calibrated `confidence_label()` function
- Test count: 864 → 879

## [v0.12.1] - 2026-02-09

### Fixed
- **BUG-005: Face count badges wildly wrong**: Badge denominator used raw embedding detection count (e.g., 63 for a 3-person newspaper photo). Now filters to only registered faces from photo_index.json. Also fixes lightbox "N faces detected" and removes noise face overlays. 5 tests.
- **BUG-006: Photo navigation dies after few clicks**: Duplicate keydown listeners (one in photo_nav_script, one in global delegation) caused double navigation per key press. Removed the per-section handler. 6 tests.
- **BUG-007: Rhodesli logo doesn't link home**: Sidebar header "Rhodesli / Identity System" wrapped in `<a href="/">`. 2 tests.
- **BUG-008: Client-side fuzzy search not working**: Sidebar filter used `indexOf` (exact substring). Now includes JS Levenshtein distance with threshold-based fuzzy matching per word. "Capeluto" matches "Capelluto". 4 tests.

### Changed
- Test count: 847 → 864 (17 new tests across 4 test files)
- `_build_caches()` restructured: loads photo_index.json first, filters faces, then builds reverse mapping

## [v0.12.0] - 2026-02-08

### Added
- **Identity-Context Photo Navigation**: Face card and search result clicks now compute prev/next arrows from the identity's photo list. No more "no arrows" dead ends. 11 tests.
- **Mobile Bottom Tabs** (FE-011): Fixed bottom tab bar with Photos, Confirmed, Inbox, Search tabs. Hidden on desktop (lg:hidden). Active section highlighting. 6 tests.
- **Progress Dashboard** (FE-053): Landing page identification progress bar showing "X of Y faces identified" with percentage and help CTA. 5 tests.
- **Fuzzy Name Search** (FE-033): Levenshtein edit distance fallback when exact substring match returns no results. "Capeluto" finds "Capelouto" (distance 1). 6 tests.
- **Search Match Highlighting**: Matched portion of names highlighted in amber in search results. 5 tests.
- **Inline Face Actions**: Admin users see hover-visible confirm/skip/reject icon buttons on face overlays in photo view. New `/api/face/quick-action` endpoint. 17 tests.
- **Confirmed Face Click**: Clicking a confirmed face overlay in photo view navigates to the identity card instead of opening the tag dialog.

### Fixed
- **Search Navigation**: Search results now navigate to the correct identity via hash fragment scrolling + 2s highlight ring animation (was silently ignoring `?current=` param)
- **Merge History Backfill**: Added `scripts/backfill_merge_history.py` to populate stub merge_history entries for 24 pre-existing merges. Undo UI no longer shows empty state unexpectedly.

### Changed
- Test count: 799 → 847 (48 new tests across 5 test files)
- Photo view routes now pass admin status for conditional inline actions
- All `photo_view_content()` callers updated with `is_admin` parameter

## [v0.11.0] - 2026-02-08

### Added
- **Merge Direction Tests**: 18 tests covering auto-correction (named identity always survives), undo safety, state promotion, name conflict resolution, and tiebreakers
- **Event Delegation Lightbox** (BUG-001 permanent fix): All photo navigation uses data-action attributes with ONE global click/keydown listener. No more HTMX swap breakage. 16 regression tests.
- **Universal Keyboard Shortcuts** (FE-002/FE-003): Match mode (Y/N/S), Focus mode (C/S/R/F), and photo navigation all consolidated in one global keydown handler with input field suppression. 10 tests.
- **Client-side Instant Search** (FE-030/FE-031): Sidebar identity list has data-name attributes and 150ms debounced client-side filter. Server-side search preserved as fallback. 13 tests.
- **Skip Hints**: Skipped section lazy-loads ML suggestions showing top 3 similar confirmed identities ("Might be: Leon Capeluto (dist 0.82, +15% gap)"). 6 tests.
- **Confidence Gap**: Neighbor results now show relative ranking — how much closer the best match is vs next-best, as a percentage margin. Helps humans adjudicate comparative evidence.
- **Smoke Tests**: 21 tests verifying all major routes return 200, required scripts are loaded, interactive elements have correct attributes.
- **Canonical Collection Stats** (BUG-004 fix): `_compute_sidebar_counts()` replaces 4 inline stats computations. 11 regression tests.
- **About Page** (`/about`): Heritage context, how-to-help guide, FAQ (Skip, Merge, Undo), live archive stats. 10 tests.
- **Unified Lightbox** (FE-004): Consolidated two separate modal systems (#photo-modal and #photo-lightbox) into one. "View All Photos" and face-click photo viewing now share the same modal component. 11 tests.

### Fixed
- **BUG-001**: Lightbox arrows disappear after HTMX swap — permanent fix with event delegation (4th and final attempt)
- **BUG-002**: Face count label now shows displayed face boxes, not raw detection count
- **BUG-003**: Merge direction already fixed in v0.10.0 code; now has 18 direction-specific tests confirming correctness
- **BUG-004**: Collection stats inconsistency — single canonical function

### Changed
- Test count: 663 → 787 (124 new tests)
- CLAUDE.md rule #12: event delegation mandatory for HTMX apps
- Neighbor cards show confidence gap instead of raw percentile
- Focus mode keyboard handler removed (consolidated into global handler)

## [v0.10.0] - 2026-02-08

### Added
- **Face Overlay Status Colors**: Overlays now use status-based colors instead of all-green
  - CONFIRMED: green border + ✓ badge
  - PROPOSED: indigo border (ML suggestion)
  - SKIPPED: amber border + ⏭ badge
  - REJECTED: red border + ✗ badge
  - INBOX/unassigned: dashed gray border (needs attention)
- **Photo Completion Badges**: Grid cards show progress (green=all done, indigo=partial N/M, dark=none)
- **Single Tag Dropdown**: Clicking a face overlay now closes other open dropdowns first
- **Create Identity from Tag**: "+ Create New Identity" button in tag search autocomplete
- **Keyboard Shortcuts**: Focus mode actions via C=Confirm, S=Skip, R=Reject, F=Find Similar
- **Proposals Admin Page**: `/admin/proposals` page with sidebar nav link for reviewing proposed matches
- **Mobile Touch Swipe**: Swipe left/right to navigate photos in the photo modal
- **AD-013**: Documented cluster_new_faces.py fix from centroid to multi-anchor matching

### Fixed
- **Multi-merge bug (3rd attempt)**: FastHTML bare `list` annotation splits strings into character lists; fixed to `list[str]`
- **Lightbox arrows disappearing**: Arrows after photo 2+ broke because prev_id/next_id weren't passed; switched to client-side `photoNavTo()`
- **Collection stats wrong when filtered**: Subtitle showed global stats instead of filtered collection count
- **AD-001 violation in cluster_new_faces.py**: Replaced centroid averaging with multi-anchor best-linkage using `scipy.cdist`
- **Mobile responsive**: Match mode stacks vertically, modals fill screen, 44px touch targets, responsive autocomplete

### Changed
- Mobile responsive improvements across all workstation pages
- Focus mode action buttons now have id attributes for keyboard targeting
- Photo grid face count badge redesigned with completion semantics
- Golden set rebuilt: 90 faces, 23 identities, threshold analysis saved

## [v0.9.0] - 2026-02-07

### Added
- **Photo Navigation**: Keyboard arrow keys (Left/Right) and prev/next buttons for browsing photos in lightbox; Escape to close
- **Match Mode Redesign**: Larger face display, confidence percentage bar, clickable faces to view source photo, decision logging to JSONL
- **Face Tagging**: Instagram-style tag dropdown on face overlays with autocomplete search and one-click merge
- **Identity Notes**: Add/view notes on identities with author tracking and timestamps
- **Proposed Matches**: Propose, list, accept/reject match suggestions between identities without immediate merge
- **Collection Stats Cards**: Per-collection photo/face/identified counts displayed above photo grid, clickable to filter
- **Collection Reassignment**: Admin endpoint to change a photo's collection (`POST /api/photo/{id}/collection`)
- **Clustering Report**: Dry-run clustering report for Betty Capeluto collection (35 high-confidence matches found)

### Fixed
- **Multi-merge form bug**: HTMX ignored `formaction` on buttons; moved `hx_post` to individual buttons with `hx_include`
- **Checkbox toggle bug**: `toggle @checked` modified HTML attribute, not JS `.checked` property; switched to property assignment
- **Carousel "+N More" count static**: `get_next_focus_card()` now returns both card and carousel in `#focus-container`
- **Main face image not clickable**: Wrapped main face in Focus mode with photo modal trigger
- **Registry shallow-copy bug**: `add_note()` and `resolve_proposed_match()` modified copies from `get_identity()` instead of originals

## [v0.8.0] - 2026-02-06

### Added
- **UX Overhaul**: Merge system, redesigned landing page, sidebar navigation, face cards, inbox workflow
- **Pending Upload Queue**: Admin moderation queue for user-submitted photos
- **ML Clustering Pipeline**: Golden set evaluation harness and face matching
- **Landing Page**: Public-facing landing page with project intro
- **Admin Export**: Data export functionality for admin users
- **Mobile CSS**: Responsive layout improvements for mobile devices
- **Design Docs**: `docs/design/MERGE_DESIGN.md`, `docs/design/FUTURE_COMMUNITY.md`

### Fixed
- **9 pre-existing test failures**: Stale assertions from UI changes (landing page, colors, URL prefixes)
- **Uploaded photos not rendering in R2 mode**: Photos served from R2 instead of local filesystem
- **Photo source lookup for inbox IDs**: Added filename-based fallback in `_build_caches()` for inbox-style photo IDs

### Changed
- Consolidated photo storage to single `raw_photos/` path (removed separate uploads directory)
- Split `docs/SYSTEM_DESIGN_WEB.md` (1,373 lines) into 4 focused docs under `docs/architecture/`
- Restructured `CLAUDE.md` to stay under 80 lines with `@` references to docs

## [v0.7.0] - 2026-02-05

### Added
- **Password Recovery**: Full forgot-password flow with Supabase `/auth/v1/recover`
- **Google OAuth Social Login**: One-click Google Sign-In via Supabase OAuth
- **Email Templates**: Branded confirmation and recovery email templates via Supabase Management API
- **Login Modal**: HTMX-powered login modal for protected actions (no page redirect)
- **Styled Confirmation Dialog**: Custom confirmation dialog replacing browser `confirm()`
- **Regression Test Suite**: Comprehensive test harness with permission matrix tests
- **Testing Requirements**: Mandatory testing rules added to `CLAUDE.md`

### Fixed
- **Facebook login button removed**: OAuth deferred — Meta requires Business Verification
- **Email button legibility**: Inline styles instead of `<style>` blocks (stripped by email clients)
- **Password recovery redirect**: Added `redirect_to` parameter for correct landing page
- **PKCE code exchange**: Fixed auth hash fragment handling for Supabase PKCE flow
- **Auth hash fragment errors**: Friendly error messages for malformed auth callbacks
- **Upload permissions**: Restricted to admin-only until moderation queue exists

### Changed
- Google Sign-In button uses official branding guidelines
- All HTMX auth failures return 401 (not 303) with `beforeSwap` handler for login modal

## [v0.6.0] - 2026-02-05

### Added
- **Supabase Authentication (Phase B)**: Invite-only auth with login/signup/logout
  - `app/auth.py` — Supabase client with graceful degradation (disabled when env vars unset)
  - Login, signup, and logout routes in `app/main.py`
  - Beforeware-based route protection (conditional on auth being configured)
  - Invite code validation for signup access control
  - Session management via FastHTML's built-in session support

### Fixed
- **Find Similar 500 error**: Added `scipy` to `requirements.txt` (was missing — only in requirements-local.txt). Added error handling around the neighbors endpoint.

### Changed
- `requirements.txt` — Added scipy, supabase>=2.0.0
- `.env.example` — Updated auth configuration section with Supabase env vars
- `CLAUDE.md` — Added Boris Cherny autonomous workflow protocol

## [v0.5.1] - 2026-02-05

### Fixed
- **Single Railway Volume**: Railway only supports one volume per service
  - Added `STORAGE_DIR` environment variable for single-volume mode
  - When set, `DATA_DIR` and `PHOTOS_DIR` are derived automatically
  - Init script creates subdirectories: `data/`, `raw_photos/`, `staging/`
  - Local development unchanged (uses `DATA_DIR` and `PHOTOS_DIR` directly)

### Changed
- `core/config.py`: Added `STORAGE_DIR` logic with fallback to individual paths
- `scripts/init_railway_volume.py`: Supports single-volume mode
- `app/main.py`: Uses config paths instead of hardcoded project-relative paths
- `Dockerfile`: Creates `/app/storage` directory, updated comments
- `docs/DEPLOYMENT_GUIDE.md`: Updated for single volume setup
- `.env.example`: Added `STORAGE_DIR` documentation

### Documentation
- Added "Deployment Impact Rule" to CLAUDE.md

## [v0.5.0] - 2026-02-05

### Added
- **Railway Deployment**: Full Docker-based deployment configuration
- `Dockerfile` using python:3.11-slim with lightweight web dependencies only
- `.dockerignore` excluding dev files, tests, and ML dependencies
- `railway.toml` with health check configuration
- `.env.example` documenting all environment variables
- `scripts/init_railway_volume.py` for first-run data seeding
- `/health` endpoint returning status, identity/photo counts, processing mode
- `PROCESSING_ENABLED` environment variable to control ML processing
- `docs/DEPLOYMENT_GUIDE.md` with step-by-step Railway + Cloudflare setup

### Changed
- `core/config.py` now includes server configuration (HOST, PORT, DEBUG, etc.)
- `app/main.py` uses environment variables for host/port/debug settings
- Upload handler checks `PROCESSING_ENABLED`:
  - When `false`: stores files in `data/staging/` for admin review (no ML)
  - When `true`: spawns subprocess for ML processing (local dev)
- Added Pillow to `requirements.txt` (needed for image dimensions)
- Updated `.gitignore`: added `.env`, `data/staging/`
- Comprehensive startup logging showing config and data stats

### Architecture
- **Clean Vercel Constraint Maintained**: Docker image uses only `requirements.txt`
- ML dependencies (`requirements-local.txt`) are NOT installed in production
- Production workflow: web users upload → staging → admin processes locally → sync back

## [v0.4.0] - 2026-02-04

### Added
- **Source Attribution**: Photos now track provenance/collection metadata
- `source` field in PhotoRegistry schema (backward compatible)
- Source input field on upload form with autocomplete suggestions
- Source display in Photo Context modal
- **Photo Viewer**: New photo-centric browsing section
- "Browse > Photos" sidebar navigation
- Photo grid showing thumbnails, face counts, identified faces
- Filter by collection dropdown
- Sort options: newest, oldest, most faces, by collection
- `scripts/migrate_photo_sources.py` for classifying existing photos
- `--source` CLI argument for ingestion pipeline

### Changed
- PhotoRegistry now stores `source` alongside `path` and `face_ids`
- Upload endpoint accepts and passes source to subprocess
- Index route accepts `filter_source` and `sort_by` query params

### Fixed
- N/A

## [v0.3.9] - 2026-02-04

### Added
- **Darkroom Theme**: Professional dark mode for forensic workstation aesthetic
- `.font-data` CSS class for monospace data elements (filenames, IDs, quality scores)
- Photo filename display in Photo Context modal

### Changed
- Body background from light gray (#f9fafb) to slate-900 (#0f172a)
- Sidebar to slate-800 with slate-700 borders
- All UI components (cards, modals, inputs, buttons) themed for dark mode
- Text colors updated: gray/stone-* to slate-* equivalents
- Accent colors maintained for state indicators (green=confirmed, yellow=skipped, red=rejected, blue=inbox)

### Fixed
- **Photo filename not showing**: Filename now displays in Photo Context modal with monospace styling
- **Face click navigation broken**: Clicking a face bounding box in Photo Context now properly navigates to that identity's section based on state (Confirmed/Inbox/Skipped/Rejected)

## [v0.3.8] - 2026-02-04

### Added
- **Command Center UI**: Complete redesign with fixed sidebar navigation
- `sidebar()` component with section navigation and live counts
- Focus Mode: Review one identity at a time with prominent actions
- Browse Mode: Traditional grid view for scanning
- `identity_card_expanded()` for focus mode display
- `identity_card_mini()` for queue preview
- `get_next_focus_card()` helper for focus mode flow
- `section_header()` component with Focus/Browse toggle
- Section-specific rendering functions
- URL parameters: `section` (to_review/confirmed/skipped/rejected) and `view` (focus/browse)

### Changed
- Main route now uses sidebar + main content layout
- Action endpoints support `from_focus=true` to return next focus card
- Default view is Focus mode showing one item prominently
- Removed old header with "Rhodesli Forensic Workstation" title

### Fixed
- Actions in focus mode now advance to next item instead of showing completed card
- **Upload button 405**: Added GET handler for `/upload` route
- **View Full Photo stuck loading**: Fixed endpoint from non-existent `/api/photo/{id}/context` to `/photo/{id}/partial`
- **Face thumbnails not clickable**: Wrapped faces in buttons with photo modal handler
- **Find Similar anchor navigation fails**: Added fallback navigation when target element doesn't exist in Focus mode
- **Up Next thumbnails not clickable**: Made thumbnails links with `current` parameter to load specific identity
- **Skip ordering mismatch**: Aligned sorting in `get_next_focus_card()` with visual queue (sort by date then face count)

### Documentation
- Added `docs/POST_MORTEM_UI_BUGS.md` - Root cause analysis of 6 interaction bugs
- Added `docs/INTERACTION_TESTING_PROTOCOL.md` - Testing protocol to prevent render-but-don't-work bugs

## [v0.3.7] - 2026-02-04

### Added
- `SKIPPED` state to `IdentityState` enum for deferred reviews
- `skip_identity()` and `reset_identity()` functions in registry
- `SKIP` and `RESET` action types for event logging
- `/identity/{id}/skip` endpoint to defer items for later
- `/identity/{id}/reset` endpoint to return any state to Inbox
- Unified `review_action_buttons()` showing state-appropriate buttons
- stone/rose colors for Skipped/Rejected sections

### Fixed
- **Vanishing reject bug**: Rejected items now fetched and rendered in Rejected section
- `confirm_identity()` and `reject_identity()` now accept SKIPPED state

### Changed
- Main page shows 4 sections: Inbox, Confirmed, Skipped, Rejected
- Inbox section combines INBOX + PROPOSED states
- Rejected combines REJECTED + CONTESTED states
- All identity cards now show appropriate action buttons for their state

### Removed
- Old `action_buttons()` with UI-only hyperscript skip
- Old `skipped_section()` collapsible (replaced with proper lane_section)

## [v0.3.6] - 2026-02-04

### Added
- Ingestion-time face grouping: similar faces are automatically grouped into one inbox identity
- `core/grouping.py`: `group_faces()` using Union-Find for transitive grouping
- `GROUPING_THRESHOLD = 0.95` in `core/config.py` (stricter than Find Similar)
- `grouped_faces` count in identity provenance for transparency
- 15 new tests for grouping functionality (`tests/test_grouping.py`)

### Changed
- `create_inbox_identities()` now groups faces before creating identities
- Uploading 10 photos of same person → 1 inbox identity (was 10)

## [v0.3.5] - 2026-02-04

### Fixed
- Manual search showing blank grey thumbnails instead of face photos
- Manual search results not clickable (missing navigation links)
- `search_identities()` now falls back to `candidate_ids` when `anchor_ids` is empty
- `search_result_card()` now wraps thumbnail and name in clickable `<a>` tags

### Changed
- `test_rename_identity` now restores original name after test (prevents data corruption)

### Data
- Restored "Victoria Cukran Capeluto" identity name (corrupted by test to "Test Person Name")

## [v0.3.4] - 2026-02-04

### Fixed
- View Photo returning 404 for inbox uploads stored in `data/uploads/`
- `/photos/` endpoint now serves from both `raw_photos/` and `data/uploads/`

### Added
- `_photo_path_cache` for O(1) photo path resolution from photo_index.json
- `serve_photo()` dynamic route replacing StaticFiles mount
- Startup validation warns about missing photo files
- Integration tests for photo serving (`tests/test_photo_serving_integration.py`)

## [v0.3.3] - 2026-02-04

### Fixed
- Identities displaying as "Identity <UUID>..." instead of "Unidentified Person XXX"
- View Photo showing wrong photo or "Could not load" for inbox uploads
- `generate_photo_id()` now uses full path for absolute paths to avoid collisions

### Changed
- Backfilled 88 historical identities with proper sequential names

## [v0.3.2] - 2026-02-03

### Fixed
- Find Similar returning no results for inbox faces
- `load_face_embeddings()` now preserves stored `face_id` instead of regenerating
- `load_embeddings_for_photos()` applies same fix for photo context views

### Added
- Contract tests for face_id preservation (`tests/test_face_record_contract.py`)

## [v0.3.1] - 2026-02-03

### Fixed
- Inbox lane showing 0 items despite identities existing with `state=INBOX`
- `resolve_face_image_url()` now handles inbox face_id format (`inbox_{hash}`)

### Added
- Contract tests for inbox visibility invariant (`tests/test_inbox_contract.py`)

## [v0.3.0] - 2026-02-03

### Added
- `list_identities_by_job(job_id)` method to IdentityRegistry for querying artifacts by job
- `core/file_hash_registry.py` module for SHA256 content hashing and deduplication
- File-level idempotency checking in ingestion pipeline (skip already-processed files)
- `scripts/cleanup_job.py` script for surgical cleanup of failed uploads
- `--dry-run` and `--execute` modes for cleanup with automatic backup
- `data/orphaned_face_ids.json` for soft-delete tracking (embeddings remain immutable)

### Changed
- Ingestion pipeline now checks file hashes before processing to prevent duplicates
- All process_single_image calls now pass file_hash_path for idempotency tracking

### Fixed
- Duplicate identities created when retrying failed uploads

## [v0.2.3] - 2026-02-03

### Fixed
- UnicodeEncodeError crash when rendering strings with surrogate escapes
- Malformed emoji literals using invalid surrogate pair notation

### Added
- `core/ui_safety.py` module with `ensure_utf8_display()` for UI boundary sanitization
- `has_surrogate_escapes()` detection function for logging without mutation
- Ingestion warning for filenames containing surrogate escapes
- Comprehensive regression tests for Unicode boundary handling

### Changed
- All UI rendering paths now sanitize text through `ensure_utf8_display()`
- Emoji escapes updated from `\ud83d\udce5` to `\U0001F4E5`

## [v0.2.2] - 2026-02-03

### Fixed
- Frontend/backend contract mismatch preventing multi-file uploads
- Upload input now uses `name="files"` with `multiple=True`
- Subprocess execution context causing `ModuleNotFoundError: No module named 'core'`
- Worker subprocess now invoked with `-m core.ingest_inbox` and explicit `cwd=PROJECT_ROOT`

### Added
- `--directory` CLI option for batch ingestion of multiple files
- Support for mixed uploads (images + ZIPs in same selection)
- Job-specific upload directories for batch isolation
- `core/__init__.py` package marker (was missing)
- Regression test for worker subprocess entrypoint invocation

### Changed
- Upload handler accepts `files: list[UploadFile]` instead of single file
- Ingestion spawned with `--directory` instead of `--file` for batches
- Status message shows file count for multi-file uploads

## [v0.2.1] - 2026-02-03

### Fixed
- Test suite aligned with current API contracts (mls_score -> distance)
- Removed tests for compute_identity_centroid (intentionally omitted per design)

### Added
- ZIP ingestion with per-file error isolation
- Per-file error tracking in job metadata
- Partial success status for batch uploads with mixed results
- Real-time progress reporting driven by backend job state

### Changed
- Upload progress bar now reflects actual completion percentage
- Error reporting shows per-file failure details

## [v0.2.0] - 2026-02-03

### Added
- Inbox Review workflow with confirm/reject actions
- Manual Search & Merge for human-authorized identity merges
- Bulk ZIP-based ingestion pipeline
- Evaluation harness with Golden Set regression testing

### Changed
- Calibration updated to Leon Standard (High < 1.0, Medium < 1.20)

### Fixed
- Scalar sigma computation in uncertainty estimation (ADR-006)
