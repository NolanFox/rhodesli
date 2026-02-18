# Rhodesli — Completed Sessions History

Compact record of all completed sessions. For active backlog items see [docs/BACKLOG.md](../BACKLOG.md).

---

## Session 46 (2026-02-18): v0.48.0 — Match Page Polish + Year Estimation Tool V1
- Help Identify sharing — Best Match links, dual photo context, share URL fix
- Face carousel for multi-face identities with source photo updates
- Deep link CTAs on match and identify pages
- Lightbox face overlays with state colors, metadata bar, View Photo Page link
- Year Estimation Tool V1 at /estimate with per-face reasoning, scene evidence, confidence
- core/year_estimation.py engine (weighted aggregation, bbox ordering, scene fallback)
- Compare/Estimate tab navigation
- AD-092-096, PRD-018. 56 new tests (2342 total)

## Session 45 (2026-02-18): v0.47.0 — Overnight Polish: Feature Audit Completion
- Photo + person inline editing (admin-only HTMX)
- Admin nav bar consistency, geographic autocomplete, comment rate limiting
- Structured upload/approval logging, 3 postmortems
- Person page life details with contribution prompts
- Lessons.md restructured (401 -> 6 topic files + 109-line index)
- AD-081-089. 32 new tests (2281 total)

## Session 44 (2026-02-17): v0.46.0 — Compare Faces Redesign + Sharing Design System
- Unified sharing components (og_tags() + generalized share_button())
- Compare page upload-first redesign, calibrated confidence labels
- Shareable comparison result pages at /compare/result/{id}
- Site-wide OG tags + share buttons on /photos, /people, /collections
- AD-091, PRD-016, PRD-017. 21 new tests (2249 total)

## Session 42 (2026-02-17): v0.44.0 — Systematic Verification + Fix Everything
- Audit of all 16 routes + 20 features
- Fixed /identify/{id} 500, landing page nav, GEDCOM warning, Compare two-mode UX
- Collection "Add Photos" button (admin-only). 7 new tests (2209 total)

## Session 41 (2026-02-17): v0.43.0 — Production Fixes + Photo UX + Research
- Fixed /map 500, face overlay alignment, face click behavior, search -> Focus mode
- Photo carousel with prev/next, keyboard arrows, position indicator
- PRD-015 + AD-090 (Gemini face alignment research). 8 new tests (2202 total)

## Session 40 (2026-02-17): v0.42.0 — Production Cleanup + Sharing
- Fixed /map and /connect 500 errors, reassigned 114 community photos
- Shareable identification pages (/identify/{id}, /identify/{a}/match/{b})
- Person page comments, action bar, collection links
- Data integrity checker (18 checks), critical route smoke tests. 35 new tests (2194 total)

## Session 39 (2026-02-17): v0.41.0 — Family Tree + Relationship Editing
- D3.js family tree at /tree (Reingold-Tilford layout, couple nodes, avatars)
- FAN relationship model + relationship editing API (admin only)
- Person page tree links, GEDCOM admin improvements
- AD-077-080. 39 new tests (2159 total)

## Sessions 36-38 (2026-02-16): v0.40.0 — Social Graph + Collections + Map
- Six Degrees connection finder at /connect (BFS, D3.js, proximity scoring)
- Shareable collection pages at /collections and /collection/{slug}
- Geocoding pipeline: 267/271 photos (98.5%), Leaflet.js map at /map
- Consistent navigation via _public_nav_links(). 86 new tests (2120 total)

## Session 35 (2026-02-15): v0.39.0 — GEDCOM Import + Relationship Graph
- GEDCOM 5.5.1 parser with custom date handling
- Layered identity matcher (14/14 matched), photo co-occurrence graph (21 edges)
- Family relationship graph, admin GEDCOM UI, person page family section
- AD-073-076. 107 new tests (2365 total)

## Session 34 (2026-02-15): v0.38.0 — Birth Date Estimation
- Birth year estimation pipeline (median + MAD outlier filtering)
- 32 estimates from 46 confirmed identities (3 HIGH, 6 MEDIUM, 23 LOW)
- Timeline age overlay, person page birth year display
- AD-071-072. 48 new tests (2246 total)

## Session 33 (2026-02-15): v0.37.1 — Production Polish + Ideation
- Compare in admin sidebar, R2 upload persistence, production graceful degradation
- Contribute-to-archive flow, VISION.md, AD-070. 12 new tests (2058 total)

## Session 32 (2026-02-15): v0.37.0 — Compare Intelligence
- Kinship calibration (959 same-person, 385 family, 605 different pairs)
- Tiered compare results with CDF confidence, upload persistence + multi-face
- AD-067-069. 30 new tests (2046 total)

## Session 31 (2026-02-15): v0.36.0 — Timeline Polish + Face Comparison
- Timeline era filtering, sticky controls, multi-person/collection filters, mobile nav
- Face Comparison tool at /compare. PRD stubs 008-011. 14 new tests (2016 total)

## Session 30 (2026-02-15): v0.35.0 — Timeline Story Engine
- Vertical chronological timeline at /timeline with decade markers
- 15 verified Rhodes historical events, person filter + age overlay
- AD-062-063. 28 unit + 11 e2e tests

## Session 29 (2026-02-15): v0.34.1 — ML Training Fix
- Hash-based train/val split (AD-060), CORAL regression diagnosis
- training_eligible field + --exclude-models flag (AD-061). 3 new ML tests

## Session 27 (2026-02-14): v0.34.0 — Discovery Layer
- Date badges, AI Analysis panel, decade/search/tag filtering
- Date correction flow, admin review queue, dual-keyed label cache
- AD-056-059. 12 e2e + unit tests

## Session 26 (2026-02-14): v0.33.0 — ML Phase 2: Scale-Up Labeling
- 250 Gemini Flash date labels (+59% data), CORAL model retrained
- Temporal consistency auditor (AD-054), search metadata export (AD-055)
- 53 new ML tests (137 total)

## Session 25 (2026-02-13): v0.32.0 — Community Contributions v2
- Suggestion state visibility, admin approval UX, annotation dedup
- Triage bar active state, "I Agree" buttons. 22 new unit tests (1878 total)

## Session 23 (2026-02-13): v0.31.0 — ML Phase 1: Date Estimation Pipeline
- CORAL ordinal regression + EfficientNet-B0, Gemini evidence-first labeling
- Heritage augmentations, regression gate, MLflow, signal harvester refresh
- AD-039-045. 53 ML tests

## Session 22 (2026-02-13): v0.30.0 — Person Pages + Public Browsing
- Public /person/{id}, /photos, /people (no auth required)
- Person links from photo viewer, upload pipeline verification. 60 new tests (1848 total)

## Session 21 (2026-02-12): v0.29.1 — Sharing Everywhere + Photo Flip
- Consistent share buttons, premium photo flip animation
- Admin back image upload, non-destructive orientation, photo viewer polish
- 36 new tests (1769 total)

## Session 20 (2026-02-12): v0.29.0 — The Shareable Moment
- Public /photo/{id} with face overlays, CSS 3D flip, OG meta tags
- Web Share API + download buttons. 61 new tests (1733 total)

## Sessions 19b-19f (2026-02-12): v0.27.1-v0.28.3 — Iterative Polish
- v0.28.3: Annotations sync, mobile overflow fix, upload thumbnails (12 tests)
- v0.28.2: Production data cleanup, quality score ordering (6 tests)
- v0.28.1: Face quality scoring (AD-038), quality-aware thumbnails (13 tests)
- v0.28.0: Structured metadata, surname onboarding, nav renaming (33 tests)
- v0.27.1: Search AND-matching, 300px crops, Z-key undo (22 tests)

## Session 19 (2026-02-12): v0.27.0 — Discovery-First Overhaul
- Fixed Best Match, source photo rendering, batch vectorized distances
- Welcome modal persistence, confidence rings, sticky action bar. 1567 tests

## Session 18/18b/18c (2026-02-11-12): v0.25.0-v0.26.0
- v0.26.0: Focus Mode (guided review, actionability scoring, visual badges). 1557 tests
- v0.25.0: UX audit (7 user stories, 10 issues), compare modal fixes. 1527 tests
- v0.24.0: Community Readiness (surname variants, face tag encoding, ML redesign). 1473 tests
- v0.23.0: Navigation Hardening + rhodesli_ml/ package (26 files). 1438 tests
- v0.22.1: Filter Consistency + Promotion Context. 1415 tests
- v0.22.0: Global Reclustering + Inbox Triage. 1400 tests
- v0.21.0: Data Integrity + Proposals UI + Scalability. 1355 tests

## Earlier Sessions (2026-02-05 to 2026-02-10)
- v0.20.0: Upload Flow + Photo Metadata Model Overhaul (1282 tests)
- v0.19.0: Anonymous Guest Contributions (1235 tests)
- v0.18.0: UX Overhaul + Contributor Flow (1221 tests)
- v0.17.2: Quality & hardening + 93 permission tests (1152 tests)
- v0.17.1: Verification pass + golden set analysis (1059 tests)
- v0.17.0: Annotation engine + merge safety + contributor roles (1032 tests)
- v0.16.0: ML pipeline + annotation engine + collaboration (969 tests)
- v0.15.0: Upload processing pipeline (943 tests)
- v0.14.1: Skipped faces fix (900 tests)
- v0.14.0: Sync infrastructure (891 tests)
- v0.13.0: ML validation session (879 tests)
- v0.12.1: 4 live-site bug fixes (864 tests)
- v0.12.0: Photo nav, mobile tabs, search polish, inline actions (847 tests)
- v0.11.0: Phase A stabilization, all P0 bugs fixed (766 tests)
- v0.10.0: Face overlay colors, completion badges, tag dropdown, keyboard shortcuts
- Sessions 1-3: Railway deployment, Supabase auth, permission model (663 tests)
