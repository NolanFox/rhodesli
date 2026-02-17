# Rhodesli Development Roadmap

Heritage photo identification system. FastHTML + InsightFace + Supabase + Railway + R2.
Current: v0.37.0 · 2046 tests · 271 photos · 181 faces · 46 confirmed

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
- ML date estimation pipeline ready (CORAL + EfficientNet-B0 + Gemini labeling) — needs UX integration

## Active Bugs (P0)
- [x] BUG-001: Lightbox arrows disappear after first photo — fixed with event delegation (2026-02-08)
- [x] BUG-002: Face count label shows detection count, not displayed/tagged count (2026-02-08)
- [x] BUG-003: Merge direction — already fixed in code, 18 direction-specific tests added (2026-02-08)
- [x] BUG-004: Collection stats inconsistency — canonical _compute_sidebar_counts() (2026-02-08)
- [x] BUG-005: Face count badges wildly wrong (63 for 3-person photo) — filter to registered faces (2026-02-09)
- [x] BUG-006: Photo nav dies after few clicks — duplicate keydown handler removed (2026-02-09)
- [x] BUG-007: Logo doesn't link home — wrapped in `<a href="/">` (2026-02-09)
- [x] BUG-008: Client-side fuzzy search not working — JS Levenshtein added (2026-02-09)

## Phase A: Stabilization — COMPLETE
Goal: Fix all active bugs, get site stable enough to share.

- [x] BUG-003: Direction-aware merge — already implemented with 18 tests (2026-02-08)
- [x] BUG-001: Lightbox arrow fix with 16 regression tests, event delegation (2026-02-08)
- [x] BUG-002: Face count label matches visible boxes (FE-025, QA-003) (2026-02-08)
- [x] BUG-004: Collection stats denominator fix — canonical _compute_sidebar_counts() (2026-02-08)
- [x] FE-002: Keyboard shortcuts in Match Mode — Y/N/S for same/different/skip (2026-02-08)
- [x] FE-003: Universal keyboard shortcuts — consolidated global handler for all views (2026-02-08)
- [x] Smoke tests: 21 tests covering all routes, scripts, interactive elements (2026-02-08)
- [x] FE-004: Consistent lightbox component — consolidated #photo-lightbox into #photo-modal (2026-02-08)
- [x] FE-032: Fix search result navigation — hash fragment scroll + highlight (2026-02-08)
- [x] DATA-001: Backfill merge_history for 24 pre-existing merges (2026-02-08)
- [ ] Smoke test all fixes on live site

## Phase B: Share-Ready Polish
Goal: Landing page, search, mobile — ready for family members.

- [x] FE-050: Welcome/about landing page with heritage photos (2026-02-06)
- [x] FE-051: Interactive hero with real archive photos (2026-02-06)
- [x] FE-052: First-time user welcome modal (2026-02-10)
- [x] FE-053: Progress dashboard ("23 of 181 faces identified") (2026-02-08)
- [x] FE-030: Global search improvements (2026-02-08)
- [x] FE-031: Fast name lookup with typeahead (2026-02-08)
- [x] FE-033: Fuzzy name search with Levenshtein distance (2026-02-08)
- [x] FE-010: Mobile sidebar — hamburger menu or slide-over (2026-02-06)
- [x] FE-011: Bottom tab navigation on mobile (2026-02-08)
- [x] FE-014: Responsive photo grid (2-col mobile, 4-col desktop) (2026-02-06)
- [x] FE-015: Mobile match mode — vertical stacking with swipe (2026-02-06)
- [x] FE-054: Landing page stats fix + historical Rhodes content rewrite (2026-02-10)
- [x] FE-055: UI clarity — section descriptions, Skipped→Needs Help, Confirmed→People, empty states (2026-02-10)
- [x] FE-056: Button prominence — View All Photos + Find Similar as styled buttons (2026-02-10)
- [x] FE-057: Compare faces UX overhaul — face/photo toggle, clickable names, sizing (2026-02-10)
- [x] FE-058: Login prompt modal with action context for unauthenticated users (2026-02-10)
- [x] FE-059: Bulk photo select mode with collection reassignment (2026-02-10)
- [ ] OPS-001: Custom SMTP for branded "Rhodesli" email sender
- [x] BE-020: Admin data export endpoint (2026-02-06)
- [x] BE-021: Production-to-local sync script (2026-02-10)
- [x] BE-022: Staged upload download API + processing pipeline (2026-02-10)
- [x] FE-070: Public shareable photo viewer at /photo/{id} (2026-02-12)
- [x] FE-071: Front/back photo flip with CSS 3D animation (2026-02-12)
- [x] FE-072: Open Graph meta tags for social sharing (2026-02-12)
- [x] FE-073: Web Share API + download buttons (2026-02-12)
- [x] FE-074: Internal UX links to public photo viewer (2026-02-12)
- [x] FE-075: Consistent share button across all surfaces — Web Share API + clipboard fallback on Photos grid, Photo Context modal, People page, Focus Mode (2026-02-12)
- [x] FE-076: Premium photo flip animation — perspective, dynamic shadow, scale lift, paper texture, face overlay fade (2026-02-12)
- [x] BE-024: Admin back image upload — file upload endpoint + transcription editor + batch association script (2026-02-12)
- [x] BE-025: Non-destructive image orientation — rotate/flip/invert via CSS transforms stored as metadata (2026-02-12)
- [x] FE-077: Photo viewer polish — overlay label clipping fix, quality scores admin-only, person card scroll-to-overlay (2026-02-12)
- [x] FE-078: Public person page at /person/{id} — hero avatar, face/photo toggle, appears with section, OG tags (2026-02-13)
- [x] FE-079: Public /photos and /people browsing pages — no auth required, collection filter, sort (2026-02-13)
- [x] FE-090: Person page links from photo viewer — cards link to /person/{id}, "See all photos" link (2026-02-13)
- [x] FE-091: "Public Page" link on identity cards — opens /person/{id} in new tab (2026-02-13)
- [x] FE-100: Timeline Story Engine — /timeline with vertical chronological view, decade markers, context events (2026-02-15)
- [x] FE-101: Person filter + age overlay on timeline (2026-02-15)
- [x] FE-102: Share button + year range filter on timeline (2026-02-15)
- [x] DATA-010: Rhodes historical context events — 15 curated events (1522-1997), source-verified (2026-02-15)
- [x] FE-103: Timeline collection filter — dropdown to filter by collection (2026-02-15)
- [x] FE-104: Timeline multi-person filter — ?people= param, merged view, highlighted names (2026-02-15)
- [x] FE-105: Timeline sticky controls — filters and share button stick on scroll (2026-02-15)
- [x] FE-106: Timeline context events era filtering — person-specific event range (2026-02-15)
- [x] FE-107: Timeline mobile nav — links visible on all screen sizes (2026-02-15)
- [x] FE-110: Face Comparison Tool — /compare with face selector, similarity search, upload (2026-02-15)
- [x] FE-111: Compare navigation — link added to all nav bars across the site (2026-02-15)
- [x] ML-065: Kinship calibration — empirical thresholds from 959 same-person, 385 same-family, 605 different-person pairs (2026-02-15)
- [x] FE-112: Tiered compare results — Identity Matches / Possible / Similar / Other with CDF confidence (2026-02-15)
- [x] FE-113: Compare upload persistence — saved to uploads/compare/ with metadata + multi-face selection (2026-02-15)

## Phase C: Annotation Engine
Goal: Make the archive meaningful beyond face matching.

- [x] BE-010: Structured identity names — auto-parse first/last from display name (2026-02-10)
- [x] BE-011: Identity metadata — set_metadata() with allowlisted keys + API endpoint (2026-02-10)
- [x] BE-012: Photo metadata — set_metadata/get_metadata + display + admin endpoint (2026-02-10)
- [x] BE-013: EXIF extraction — core/exif.py with date, camera, GPS (2026-02-10)
- [x] BE-023: Photo provenance model — separate source/collection/source_url, migration, dual filters (2026-02-10)
- [x] FE-064: Upload UX overhaul — separate collection/source/URL fields, autocomplete, bulk metadata (2026-02-10)
- [x] BE-014: Canonical name registry — surname_variants.json with 13 variant groups, wired into search (2026-02-11)
- [x] AN-001: Annotation system core — submit/review/approve/reject workflow (2026-02-10)
- [x] AN-002–AN-006: Photo-level annotations display + submission form (2026-02-10)
- [x] AN-010–AN-014: Identity metadata display + annotations section (2026-02-10)
- [x] BE-001–BE-006: Non-destructive merge with audit snapshots + annotation merging (2026-02-10)
- [x] FE-033: Fuzzy name search with Levenshtein distance (2026-02-08)
- [x] AN-030: Suggestion state visibility — inline "You suggested" confirmation in tag dropdown (2026-02-13)
- [x] AN-031: Admin approval UX — face thumbnails, skip, undo, audit log at /admin/audit (2026-02-13)
- [x] AN-032: Annotation dedup — duplicate suggestions add confirmations, community "I Agree" buttons (2026-02-13)
- [x] FE-092: Triage bar active state + clickable "+N more" in Up Next carousels (2026-02-13)

## Phase D: ML Feedback & Intelligence
Goal: Make the system learn from user actions.

- [ ] ML-001: User actions feed back to ML predictions
- [x] ML-004: Dynamic threshold calibration from confirmed/rejected pairs (2026-02-09, AD-013)
- [x] ML-005: Post-merge re-evaluation — inline suggestions for nearby faces after merge (2026-02-10)
- [x] ML-006: Ambiguity detection — margin-based flagging when top matches are within 15% (2026-02-10)
- [x] ML-010: Golden set rebuild (90 mappings, 23 identities) (2026-02-09)
- [x] ML-012: Golden set evaluation (4005 pairs, sweep 0.50-2.00) (2026-02-09)
- [x] ML-011: Golden set diversity analysis — script + dashboard section (2026-02-10)
- [x] ML-013: Evaluation dashboard — /admin/ml-dashboard with stats, thresholds, golden set (2026-02-10)
- [x] ML-021: Calibrated confidence labels (VERY HIGH/HIGH/MODERATE/LOW) (2026-02-09)
- [x] ML-040: Date estimation training pipeline — CORAL ordinal regression, EfficientNet-B0, heritage augmentations (2026-02-13, AD-039–AD-045)
- [x] ML-041: Gemini evidence-first date labeling — structured prompt with cultural lag (2026-02-13, AD-041–AD-042)
- [x] ML-042: Regression gate for date model — adjacent accuracy ≥0.70, MAE ≤1.5 (2026-02-13)
- [x] ML-043: MLflow experiment tracking initialized (2026-02-13)
- [x] ML-044: Scale-up Gemini labeling — 250 photos labeled with multi-pass retry (2026-02-14, AD-053)
- [x] ML-045: Temporal consistency auditor — birth/death/age cross-checks + missed face detection (2026-02-14, AD-054)
- [x] ML-046: Search metadata export — full-text search index from Gemini labels (2026-02-14, AD-055)
- [x] ML-047: CORAL model retrain — 250 labels (+59% data), MLflow tracked (2026-02-14)
- [x] ML-050: Date UX integration — display estimated decade + confidence on photo viewer, admin override (2026-02-14)
- [ ] ML-051: Date label pipeline — integrate generate_date_labels.py into upload orchestrator
- [ ] ML-052: New upload auto-dating — run date estimation on newly uploaded photos
- [ ] ML-053: Multi-pass Gemini — low-confidence re-labeling with Flash model
- [ ] FE-040–FE-043: Skipped faces workflow for non-admin users

## Phase E: Collaboration & Growth
Goal: Enable family members to contribute, not just browse.

- [x] ROLE-002: Contributor role — User.role field, CONTRIBUTOR_EMAILS, _check_contributor() (2026-02-10)
- [x] ROLE-003: Trusted contributor — is_trusted_contributor() auto-promotes after 5+ approvals (2026-02-10)
- [ ] FE-041: "Help Identify" mode for non-admin users
- [ ] FE-070–FE-073: Client-side analytics and admin dashboard
- [ ] BE-031–BE-033: Upload moderation queue with rate limiting
- [x] ROLE-007: Contributor merge suggestions — role-aware buttons, suggest-merge endpoint, admin approval with merge execution (2026-02-10)
- [x] ROLE-005: Activity feed — /activity route with action log + approved annotations (2026-02-10)
- [x] FE-060: Anonymous guest contributions — guest-or-login modal, guest-submit endpoint, stash-and-login, admin Guest badge (2026-02-10)
- [ ] ROLE-006: Email notifications for contributors

## Phase F: Scale & Generalize
Goal: Production-grade infrastructure and multi-tenant potential.

- [ ] BE-040–BE-042: PostgreSQL migration (Supabase Postgres)
- [ ] AN-020–AN-023: Family tree integration (GEDCOM, timeline view)
- [ ] OPS-002: CI/CD pipeline (automated tests, staging, deploy previews)
- [ ] OPS-004: Error tracking (Sentry)
- [ ] ML-030–ML-032: Model evaluation (ArcFace, ensemble, fine-tuning)
- [x] QA-004: End-to-end browser tests (Playwright) (2026-02-08)
- [ ] GEN-001+: Multi-tenant architecture (if traction)

## Planned Sessions

### Session 32: Compare Intelligence (COMPLETED 2026-02-15)
- [x] Kinship calibration from confirmed identity data (AD-067)
- [x] Tiered compare results — strong match, possible, similar (AD-068)
- [x] Upload persistence + multi-face support (AD-069)
- [x] 30 new tests (2046 total)

### Session 33: Production Polish + Upload Pipeline + Ideation (COMPLETED 2026-02-15)
- [x] Compare link in admin sidebar navigation
- [x] R2 upload persistence for compare uploads (survives Railway restarts)
- [x] Production graceful degradation (save photo, async analysis)
- [x] "Contribute to Archive" → admin moderation queue
- [x] VISION.md — product direction document
- [x] AD-070 — future architecture directions

### Session 34: Birth Date Estimation ML Pipeline (COMPLETED 2026-02-15)
- [x] Data audit: Gemini subject_ages exist for 100% of 271 photos (no new data needed)
- [x] Birth year estimation pipeline with robust outlier filtering (median + MAD)
- [x] Face-to-age matching via bbox left-to-right x-coordinate sorting
- [x] 32 estimates from 46 confirmed identities (3 HIGH, 6 MEDIUM, 23 LOW)
- [x] Timeline age overlay using ML-estimated birth years
- [x] Person page birth year display with confidence styling
- [x] Validation report + data improvement opportunities
- [x] AD-071/072, PRD 008 updated with actual results
- [x] 48 new tests (2069 app + 177 ML = 2246 total)

### Session 35: GEDCOM Import + Relationship Graph (COMPLETED 2026-02-15)
- [x] GEDCOM parser with custom date handling (ABT, BEF, AFT, BET...AND)
- [x] Identity matcher — layered name + maiden name + surname variant matching (14/14 test)
- [x] Photo co-occurrence graph — 21 edges from 20 photos (free data, no GEDCOM needed)
- [x] Relationship graph builder (parent-child, spouse from GEDCOM + confirmed matches)
- [x] Admin UI at /admin/gedcom — upload, review, confirm/reject matches
- [x] Data enrichment + person page family section with cross-links
- [x] CLI: `python scripts/import_gedcom.py` with --execute/--dry-run
- [x] 107 new tests (2365 total)

### Sessions 36-38: Social Graph + Collections + Map (COMPLETED 2026-02-16)
- [x] Social graph + Six Degrees connection finder at /connect (BFS, D3.js, proximity scoring)
- [x] Auto-confirmed 14 GEDCOM matches, built 20 relationships into data/relationships.json
- [x] Shareable collection pages at /collections and /collection/{slug}
- [x] Curated location dictionary with 22 Rhodes diaspora places
- [x] Geocoding pipeline: 267/271 photos matched (98.5%)
- [x] Interactive map view at /map with Leaflet.js, marker clustering, photo popups
- [x] Consistent navigation across all 11 public pages via _public_nav_links()
- [x] 86 new tests (2120 total)

### Session 39: Kinship Calibration v2
- Revisit kinship thresholds after GEDCOM import
- With actual family relationships encoded, compute true same-family distributions
- More photos + more data = better calibration
- Update AD-067 with improved results

### Session 40: Life Events & Context Graph
- Event tagging: "Moise's wedding in Havana"
- Events connect photos, people, places, dates
- Richer timeline with life events interspersed
- PRD: docs/prds/011_life_events_context_graph.md

## Recently Completed
- [x] 2026-02-16: v0.40.0 — Social Graph + Collections + Map (Sessions 36-38): Six Degrees connection finder at /connect with D3.js force-directed visualization, BFS pathfinding, proximity scoring. Shareable collection pages at /collections and /collection/{slug}. Curated location dictionary (22 places), geocoding pipeline (267/271 = 98.5%), interactive Leaflet.js map at /map with marker clustering and photo popups. Consistent navigation across all public pages via centralized _public_nav_links() helper. 86 new tests (2120 total). PRDs 010, 012, 013. Decision provenance AD-077–AD-081.
- [x] 2026-02-15: v0.39.0 — GEDCOM Import (Session 35): GEDCOM 5.5.1 parser with messy date handling (ABT/BEF/AFT/BET...AND). Layered identity matcher (exact → surname variants → maiden name → fuzzy + date proximity). 14/14 test individuals matched. Photo co-occurrence graph (21 edges from 20 photos). Family relationship graph from GEDCOM cross-referenced with confirmed matches. Admin GEDCOM UI at /admin/gedcom. Person page family section. CLI import tool. 107 new tests (2081 app + 272 ML = 2353 total). Decision provenance AD-073–AD-076.
- [x] 2026-02-15: v0.38.0 — Birth Date Estimation (Session 34): Birth year estimation pipeline with robust outlier filtering (median + MAD). Face-to-age matching via bbox x-coordinate sorting. 32 estimates from 46 confirmed identities (3 HIGH, 6 MEDIUM, 23 LOW). Timeline age overlay with confidence styling. Person page birth year display. Validation report with data improvement opportunities. 48 new tests (2246 total). Decision provenance AD-071–AD-072.
- [x] 2026-02-15: v0.37.1 — Production Polish + Ideation (Session 33): Compare in admin sidebar. R2 upload persistence (compare uploads survive Railway restarts). Production graceful degradation (save without InsightFace). Contribute-to-archive flow wired to admin queue. VISION.md product direction doc. Roadmap sessions 34-39. AD-070 future architecture. 12 new tests (2058 total).
- [x] 2026-02-15: v0.37.0 — Compare Intelligence (Session 32): Kinship calibration from 46 confirmed identities (959 same-person, 385 same-family, 605 different-person pairs). Key finding: family resemblance (d=0.43) not reliably separable from different-person in embedding space. Tiered compare results (strong/possible/similar/weak) with CDF-based confidence percentages. Upload persistence + multi-face detection + face selection UI. 30 new tests (2046 total). Decision provenance AD-067–AD-069.
- [x] 2026-02-15: v0.36.0 — Timeline Polish + Face Comparison (Session 31): Context event era filtering, sticky controls, multi-person filter, collection filter, mobile nav for timeline. Face Comparison tool at /compare with archive face selector, similarity search, upload support, navigation integration. PRD stubs 008-011. 14 new tests (2016 total). Decision provenance AD-064–AD-065.
- [x] 2026-02-15: v0.35.0 — Timeline Story Engine (Session 30): Vertical chronological timeline at /timeline with decade markers, 15 verified Rhodes historical events inline, person filter with age overlay, confidence interval bars, share button, year range filtering. Navigation links across all pages. 28 unit + 11 e2e tests. Decision provenance AD-062–AD-063.
- [x] 2026-02-15: v0.34.1 — ML Training Fix (Session 29): Hash-based train/val split (AD-060), diagnosed CORAL regression from gemini-2.5-flash labels (−12.5 pp accuracy). Added training_eligible field + --exclude-models flag (AD-061). 3 new ML tests (140 total).
- [x] 2026-02-14: v0.34.0 — Discovery Layer (Session 27): Date badges on photo cards, AI Analysis metadata panel, decade/search/tag filtering, date correction flow with provenance tracking, admin review queue with priority scoring. Dual-keyed label cache for photo ID mismatch. 12 e2e + XX unit tests. Decision provenance AD-056–AD-059.
- [x] 2026-02-14: v0.33.0 — ML Phase 2: Scale-Up Labeling + Tooling (Session 26): Processed 116 community photos (271 total). 250 Gemini 3 Flash date labels (+59% data). Temporal consistency auditor (AD-054). Search metadata export (AD-055). CORAL model retrained with MLflow. 53 new ML tests (137 total). Decision provenance AD-053–AD-055.
- [x] 2026-02-13: v0.32.0 — Community Contributions v2: Suggestion Lifecycle (Session 25): Suggestion state visibility (inline "You suggested" confirmation), admin approval face thumbnails + skip + undo + audit log, triage bar active state, clickable "+N more", annotation dedup with confirmation counting, community "I Agree" buttons. 11 e2e acceptance tests (4 passing, 7 skipped). 22 new unit tests. 1878 tests.
- [x] 2026-02-13: v0.31.0 — ML Phase 1: Date Estimation Pipeline (Session 23): Complete training pipeline with CORAL ordinal regression on EfficientNet-B0 backbone. Gemini 3 Pro evidence-first date labeling script with cultural lag adjustment. Heritage-specific augmentations (sepia, film grain, scanning artifacts, fading). Regression gate evaluation suite. MLflow experiment tracking. Signal harvester refresh (959 confirmed, 510 rejected, 500 hard negatives). 53 ML tests. Decision provenance AD-039 through AD-045.
- [x] 2026-02-13: v0.30.0 — Person Pages + Public Browsing (Session 22): Public person page at /person/{id} with hero avatar, face/photo toggle, "appears with" section, OG tags. Public /photos and /people browsing pages (no auth required). Person page links from photo viewer. "Public Page" link on identity cards. Upload pipeline verification tests. Cross-linked navigation (photo→person, person→photo, person→person). 60 new tests. 1848 tests
- [x] 2026-02-12: v0.29.1 — Sharing Everywhere + The Photo Flip (Session 21): Consistent share buttons across all surfaces (Photos grid, Photo Context, People page, Focus Mode). Premium photo flip animation (perspective, dynamic shadow, lift, paper texture). Admin back image upload + transcription + batch association script. Non-destructive image orientation tools (rotate/flip/invert via CSS transforms). Photo viewer polish (overlay label clipping, admin-only quality scores, person card scroll-to-overlay). 36 new tests. 1769 tests
- [x] 2026-02-12: v0.29.0 — The Shareable Moment (Session 20): Public photo viewer at /photo/{id} with face overlays and person cards, front/back photo flip with CSS 3D animation, Open Graph meta tags for rich social sharing, Web Share API + download buttons, internal UX links to public viewer. Museum-like warm design. 61 new tests. 1733 tests
- [x] 2026-02-12: v0.28.3 — Recurring Bug Fixes (Session 19f): Annotations sync to Railway volume, mobile horizontal overflow fix (overflow-x:hidden + responsive wrapping), manual search Compare button, pending upload thumbnail fallback. 12 new tests. 1672 tests
- [x] 2026-02-12: v0.28.2 — Data Safety & Admin Fixes (Session 19e): Removed test data from production (5 annotations, 46 history entries), quality scores influence Help Identify ordering, admin staging preview endpoint, duplicate Focus Mode button removal, feedback tracking architecture. 6 new tests. 1641 tests
- [x] 2026-02-12: v0.28.1 — Quality & Documentation (Session 19d): Face quality scoring (AD-038, composite 0-100), quality-aware thumbnail selection, larger face crops globally, hover effects. Photo enhancement research doc, discovery UX rules, feedback tracker. 13 new tests. 1635 tests
- [x] 2026-02-12: v0.28.0 — User Journey & Data Model (Session 19c): Discovery UX research doc, structured identity metadata (generation_qualifier, death_place, compact display), 3-step surname onboarding, personalized landing banner, nav renaming (Inbox→New Matches, Needs Help→Help Identify), admin approvals badge, "I Know This Person" button. 33 new tests. 1622 tests
- [x] 2026-02-12: v0.27.1 — Core UX Fixes (Session 19b): Search AND-matching for multi-word queries, 300px face crops, more matches strip, Z-key undo, admin photo previews, View Photo links. 22 new tests. 1589 tests
- [x] 2026-02-12: v0.27.0 — Discovery-First Overhaul (Session 19): Fixed Best Match (real-time neighbor fallback), source photo rendering, ordering (batch vectorized distances), welcome modal persistence (cookie), empty inbox redirect. Larger face crops, confidence rings, sticky action bar, collapsible neighbors panel, reject undo toast. `batch_best_neighbor_distances()` in core/neighbors.py. 1567 tests
- [x] 2026-02-12: v0.26.0 — Focus Mode + Docs (Session 18c): Needs Help Focus Mode (guided single-identity review, photo context, Same Person/Not Same/I Know Them/Skip actions, Y/N/Enter/S keyboard shortcuts, progress counter, Up Next carousel). Actionability scoring (best ML leads first), visual badges (Strong lead/Good lead). AD-030–037 rejected approaches, DECISION_LOG.md, SUPABASE_AUDIT.md. 1557 tests
- [x] 2026-02-11: v0.25.0 — Discovery UX + Bug Fixes (Session 18/18b): UX audit (7 user stories, 10 issues), compare modal View Photo + Back to Compare, post-merge guidance banners, grouped badge, compare modal 90vw + filter preservation. Bug fixes: AI suggestion thumbnails, search variant highlighting, sidebar filter layout, staged upload actions, detach UX. Variable suggestion count, co-occurrence signals, compare zoom. 1527 tests
- [x] 2026-02-11: v0.24.0 — Community Readiness: search finds all identity states, surname variant matching (13 groups), face tag URL encoding + auto-confirm, metadata edit UI, ML suggestions visual redesign, face overlay name labels + legend, upload safety checks, decision-provenance + feature-completeness harness rules (1473 tests)
- [x] 2026-02-11: v0.23.0 — Navigation Hardening + ML Pipeline Scaffold: triage filter propagation through action chain, photo nav boundaries, grammar pluralization, rhodesli_ml/ package with 26 files (signal harvester, date labeler, audit reports), 1438 tests
- [x] 2026-02-11: v0.22.1 — Filter Consistency + Promotion Context: match mode respects triage filters, Up Next preserves filter in navigation, promotion banners show specific group context, 15 new tests (1415 tests)
- [x] 2026-02-11: v0.22.0 — Global Reclustering + Inbox Triage: SKIPPED faces participate in clustering, promotion tracking (new_face_match/group_discovery/confirmed_match), triage bar with filter links, promotion badges/banners in Focus/Browse, priority-sorted Focus mode, 31 new tests (1400 tests)
- [x] 2026-02-11: v0.21.0 — Data Integrity + Proposals UI + Scalability: merge-aware push, Zeb Capuano restored, clustering proposals wired to Focus/Match/Browse, staging lifecycle, grammar pluralization, collections carousel, 4 rules files (1355 tests)
- [x] 2026-02-10: v0.20.0 — Upload Flow + Photo Metadata Model Overhaul: separate source/collection/source_url fields, upload UX with autocomplete, dual photo filters, bulk metadata editing, migration script, 22 new tests (1282 tests)
- [x] 2026-02-10: v0.19.0 — Anonymous Guest Contributions: guest-or-login modal, guest-submit endpoint, stash-and-login flow, admin Guest badge, pending_unverified status (1235 tests)
- [x] 2026-02-10: v0.18.0 — UX Overhaul + Contributor Flow: landing page rewrite, login prompt modals, section rename (Confirmed→People, Skipped→Needs Help), button prominence, compare faces UX, contributor merge suggestions, bulk photo select mode (1221 tests)
- [x] 2026-02-10: v0.17.2 — Quality & hardening: EXIF ingestion integration, graceful error handling for corrupted data, 93 route permission boundary tests (1152 tests)
- [x] 2026-02-10: v0.17.1 — Verification pass: golden set analysis refactor + auto-generation, contributor permission boundary tests, undo merge route tests, docs/ROLES.md (1059 tests)
- [x] 2026-02-10: v0.17.0 — Annotation engine + merge safety + contributor roles: merge audit snapshots, annotation merging, photo/identity annotations, photo metadata + EXIF, golden set diversity, contributor/trusted contributor roles (1032 tests)
- [x] 2026-02-10: v0.16.0 — ML pipeline + annotation engine + collaboration: post-merge suggestions, rejection memory in clustering, ambiguity detection, ML dashboard, annotation system (submit/approve/reject), structured names, identity metadata, activity feed, welcome modal (969 tests)
- [x] 2026-02-10: v0.15.0 — Upload processing pipeline: staged file sync API, download script, end-to-end orchestrator (943 tests)
- [x] 2026-02-10: v0.14.1 — Skipped faces fix: clustering includes 192 skipped faces, clickable lightbox overlays, correct section routing, stats denominator fix (900 tests)
- [x] 2026-02-10: v0.14.0 — Sync infrastructure: token-authenticated sync API, reliable sync script, backup automation, ML refresh pipeline (891 tests)
- [x] 2026-02-09: v0.13.0 — ML validation session: AD-013 threshold calibration, golden set evaluation, clustering validation, 33 match proposals ready (879 tests)
- [x] 2026-02-09: v0.12.1 — 4 live-site bug fixes: face count badges, nav persistence, logo link, fuzzy search (864 tests)
- [x] 2026-02-08: v0.12.0 — Session 4: photo nav, mobile tabs, search polish, inline actions (847 tests)
- [x] 2026-02-08: Inline face actions — hover confirm/skip/reject buttons on photo overlays, 17 tests
- [x] 2026-02-08: FE-033 — Fuzzy search with Levenshtein distance + match highlighting, 11 tests
- [x] 2026-02-08: FE-053 — Progress dashboard with identification bar, 5 tests
- [x] 2026-02-08: FE-011 — Mobile bottom tab navigation (Photos/Confirmed/Inbox/Search), 6 tests
- [x] 2026-02-08: Identity-context photo navigation — arrows from face cards/search, 11 tests
- [x] 2026-02-08: FE-032 — Search result navigation fix (hash fragment + highlight animation, 4 tests)
- [x] 2026-02-08: DATA-001 — Backfill merge_history for 24 pre-existing merged identities
- [x] 2026-02-08: v0.11.0 — Phase A stabilization: all 4 P0 bugs fixed, 103 new tests (663→766)
- [x] 2026-02-08: Skip hints + confidence gap — ML suggestions for skipped identities, relative ranking
- [x] 2026-02-08: Smoke tests — 21 tests covering all routes, scripts, interactive elements
- [x] 2026-02-08: BUG-003 — 18 merge direction tests confirming auto-correction is working
- [x] 2026-02-08: FE-002/FE-003 — universal keyboard shortcuts (match mode Y/N/S, consolidated global handler)
- [x] 2026-02-08: FE-030/FE-031 — client-side instant name search with 150ms debounce filtering
- [x] 2026-02-08: BUG-004 fix — canonical _compute_sidebar_counts() replaces 4 inline computations, 11 regression tests
- [x] 2026-02-08: BUG-001 fix — lightbox arrows via event delegation, 16 regression tests
- [x] 2026-02-08: BUG-002 fix — face count label now matches displayed face boxes, not raw detection count
- [x] 2026-02-08: v0.10.0 release — face overlay colors, completion badges, tag dropdown, keyboard shortcuts
- [x] 2026-02-07: Proposals admin page + sidebar nav link
- [x] 2026-02-07: AD-001 fix in cluster_new_faces.py (multi-anchor, not centroid)
- [x] 2026-02-07: Multi-merge bug fix (HTMX formaction + checkbox toggle)
- [x] 2026-02-07: Golden set rebuild + threshold analysis (1.00 = 100% precision)
- [x] 2026-02-07: AD-004 rejection memory verified working
- [x] 2026-02-07: Clustering dry-run report (35 matches, Betty Capeluto)
- [x] 2026-02-06: Match mode redesign, Find Similar, identity notes, collection stats
- [x] 2026-02-06: Face tagging UX, photo navigation, lightbox, mobile responsive pass
- [x] 2026-02-06: Landing page, admin export, mobile CSS, docs overhaul
- [x] 2026-02-06: ML algorithmic decision capture (AD-001 through AD-012)
- [x] 2026-02-05: Supabase auth (Google OAuth + email/password + invite codes)
- [x] 2026-02-05: Permission model (public=view, admin=all), 663 tests
- [x] 2026-02-05: Railway deployment with Docker + persistent volume + R2

## Reference Documents
- Detailed backlog: `docs/BACKLOG.md` (120+ items with full context)
- ML decisions: `docs/ml/ALGORITHMIC_DECISIONS.md`
- Ops decisions: `docs/ops/OPS_DECISIONS.md`
- Lessons learned: `tasks/lessons.md`
- Task details: `tasks/phase-a/` (current phase only)
