# Session History

Complete log of all development sessions. For current priorities, see [ROADMAP.md](../../ROADMAP.md).

---

## Early Sessions (1-31) Summary

| Sessions | Date Range | Highlights |
|----------|-----------|------------|
| 1-3 | 2026-02-05 to 2026-02-06 | Railway deployment, Supabase auth, landing page, mobile CSS, ML decisions AD-001-012 |
| 4 | 2026-02-08 | Phase A stabilization: 4 P0 bugs fixed, keyboard shortcuts, search, 103 new tests (663-766) |
| 5-8 | 2026-02-08 to 2026-02-09 | Photo nav, mobile tabs, inline face actions, fuzzy search, progress dashboard, bug fixes |
| 9 | 2026-02-09 | ML validation: AD-013 threshold calibration, golden set evaluation, clustering validation |
| 10-13 | 2026-02-10 | Sync infrastructure, upload pipeline, skipped faces fix, annotation engine, contributor roles |
| 14-17 | 2026-02-10 | Upload flow overhaul, guest contributions, UX overhaul, quality hardening, EXIF, permission tests |
| 18-18c | 2026-02-11 to 2026-02-12 | Discovery UX audit, Focus Mode, reclustering, filter consistency, navigation hardening |
| 19-19f | 2026-02-12 | Discovery-first overhaul, core UX fixes, user journey, quality scoring, data safety, sharing, bug fixes |
| 20 | 2026-02-12 | Public photo viewer at /photo/{id}, OG tags, Web Share API, museum-like design |
| 21 | 2026-02-12 | Share buttons everywhere, photo flip animation, back image upload, orientation tools |
| 22 | 2026-02-13 | Person pages at /person/{id}, public /photos and /people browsing |
| 23 | 2026-02-13 | ML Phase 1: CORAL date estimation pipeline, Gemini labeling, heritage augmentations |
| 24 | 2026-02-11 | Community readiness: surname variants, face tag encoding, ML suggestions redesign |
| 25 | 2026-02-13 | Community contributions v2: suggestion lifecycle, admin approval UX, annotation dedup |
| 26 | 2026-02-14 | ML Phase 2: 250 Gemini labels, temporal auditor, search metadata, CORAL retrain |
| 27 | 2026-02-14 | Discovery layer: date badges, AI Analysis panel, decade filtering, date correction |
| 28 | 2026-02-11 | Navigation hardening, ML pipeline scaffold, rhodesli_ml/ package |
| 29 | 2026-02-15 | ML training fix: hash-based split, CORAL regression diagnosis, training_eligible field |
| 30 | 2026-02-15 | Timeline Story Engine at /timeline, decade markers, 15 Rhodes historical events |
| 31 | 2026-02-15 | Timeline polish, Face Comparison tool at /compare |

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

---

## Release Version History

| Version | Date | Session | Test Count |
|---------|------|---------|------------|
| v0.48.0 | 2026-02-18 | 46 | 2342 |
| v0.47.0 | 2026-02-18 | 45 | 2281 |
| v0.46.0 | 2026-02-17 | 44 | 2249 |
| v0.44.0 | 2026-02-17 | 42 | 2209 |
| v0.43.0 | 2026-02-17 | 41 | 2202 |
| v0.42.0 | 2026-02-17 | 40 | 2194 |
| v0.41.0 | 2026-02-17 | 39 | 2159 |
| v0.40.0 | 2026-02-16 | 36-38 | 2120 |
| v0.39.0 | 2026-02-15 | 35 | 2353 |
| v0.38.0 | 2026-02-15 | 34 | 2246 |
| v0.37.1 | 2026-02-15 | 33 | 2058 |
| v0.37.0 | 2026-02-15 | 32 | 2046 |
| v0.36.0 | 2026-02-15 | 31 | 2016 |
| v0.35.0 | 2026-02-15 | 30 | ~2000 |
| v0.34.1 | 2026-02-15 | 29 | ~1990 |
| v0.34.0 | 2026-02-14 | 27 | ~1900 |
| v0.33.0 | 2026-02-14 | 26 | ~1880 |
| v0.32.0 | 2026-02-13 | 25 | 1878 |
| v0.31.0 | 2026-02-13 | 23 | ~1850 |
| v0.30.0 | 2026-02-13 | 22 | 1848 |
| v0.29.1 | 2026-02-12 | 21 | 1769 |
| v0.29.0 | 2026-02-12 | 20 | 1733 |
| v0.28.x | 2026-02-12 | 19-19f | 1567-1672 |
| v0.26.0 | 2026-02-12 | 18c | 1557 |
| v0.25.0 | 2026-02-11 | 18/18b | 1527 |
| v0.24.0 | 2026-02-11 | — | 1473 |
| v0.23.0 | 2026-02-11 | — | 1438 |
| v0.22.x | 2026-02-11 | — | 1400-1415 |
| v0.21.0 | 2026-02-11 | — | 1355 |
| v0.20.0 | 2026-02-10 | — | 1282 |
| v0.19.0 | 2026-02-10 | — | 1235 |
| v0.18.0 | 2026-02-10 | — | 1221 |
| v0.17.x | 2026-02-10 | — | 1032-1152 |
| v0.16.0 | 2026-02-10 | — | 969 |
| v0.15.0 | 2026-02-10 | — | 943 |
| v0.14.x | 2026-02-10 | — | 891-900 |
| v0.13.0 | 2026-02-09 | — | 879 |
| v0.12.x | 2026-02-08 | 4-5 | 847-864 |
| v0.11.0 | 2026-02-08 | — | 766 |
| v0.10.0 | 2026-02-08 | — | 663 |
