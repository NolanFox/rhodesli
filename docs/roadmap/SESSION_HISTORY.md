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
