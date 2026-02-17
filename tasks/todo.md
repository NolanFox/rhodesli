# Rhodesli Project Backlog

Last updated: 2026-02-17 (Session 40 — Production Cleanup + Sharing)

## Session 40 Completed
- [x] Fix /map 500 error — missing _build_caches() call
- [x] Fix /connect 500 error — _safe_get_identity() for 6 call sites
- [x] Fix collection data — 114 photos reassigned via scripts/fix_collection_metadata.py
- [x] Shareable identification pages — /identify/{id} and /identify/{a}/match/{b} (15 tests)
- [x] Person page comments — submit/display/moderation (9 tests)
- [x] Person page action bar — Timeline, Map, Family Tree, Connections
- [x] Clickable collection link on photo page
- [x] Help Identify CTA for unidentified persons
- [x] Data integrity checker — scripts/verify_data_integrity.py (18 checks)
- [x] Critical route smoke tests — tests/test_critical_routes.py (10 routes)
- [x] Fix test_map.py cache poisoning
- [x] Feedback tracker: docs/feedback/session_40_feedback.md (32 items)
- [x] CHANGELOG v0.42.0, ROADMAP, BACKLOG updated
- [x] 35 new tests (2194 total)

## Remaining from Session 40 Feedback (Future Work)
- [ ] FB-40-18: Face click behavior — overlay → tag/person, thumbnail → person/identify
- [ ] FB-40-20: Photo carousel / gallery mode with left/right arrows
- [ ] FB-40-21: Admin-only elements hidden from public (back image upload, orientation tools)
- [ ] FB-40-22: Photo upload attribution display
- [ ] FB-40-23: "Add Photos" button on collection detail pages
- [ ] FB-40-24: Bulk collection/source editing in admin Photos view
- [ ] FB-40-25: Individual photo collection/source editable by admin
- [ ] FB-40-26: Upload flow collection assignment clarity
- [ ] FB-40-27: Fix search → Focus mode wrong person navigation
- [ ] FB-40-09: Geographic autocomplete with location_dictionary.json
- [ ] FB-40-11: GEDCOM page — label test data, manual linking, show on person pages
- [ ] FB-40-13: Compare UX — two clear modes immediately visible

## Session 39 Completed
- [x] Family tree data structure: build_family_tree(), find_root_couples() (10 tests)
- [x] /tree route with D3 hierarchical tree layout (12 tests)
- [x] Couple-based nodes with face crop avatars, person filter, theory toggle
- [x] FAN relationship model: fan_friend, fan_associate, fan_neighbor
- [x] Relationship editing API: add/update/remove (admin only, non-destructive)
- [x] Confidence levels (confirmed/theory) with filtering (15 tests)
- [x] Person page tree links + connection photo counts + cross-linking (2 tests)
- [x] GEDCOM admin improvements: import history + enrichment status
- [x] Tree in navigation (public nav + admin sidebar)
- [x] Nav consistency tests updated (3 fixes)
- [x] AD-077–AD-080, CHANGELOG v0.41.0, ROADMAP, BACKLOG
- [x] 39 new tests (2159 total)

## Session 35 Completed
- [x] Research: GEDCOM format, python-gedcom library, identity schema
- [x] PRD: docs/prds/009_gedcom_import.md (expanded from stub)
- [x] Test fixture: tests/fixtures/test_capeluto.ged (14 individuals, 6 families)
- [x] GEDCOM parser: rhodesli_ml/importers/gedcom_parser.py (40 tests)
- [x] Identity matcher: rhodesli_ml/importers/identity_matcher.py (21 tests)
- [x] Enrichment: rhodesli_ml/importers/enrichment.py (12 tests)
- [x] Match persistence: rhodesli_ml/importers/gedcom_matches.py
- [x] Relationship graph: rhodesli_ml/graph/relationship_graph.py (20 tests)
- [x] Co-occurrence graph: rhodesli_ml/graph/co_occurrence_graph.py
- [x] Admin GEDCOM UI: /admin/gedcom routes (12 tests)
- [x] Person page family section from relationship graph
- [x] CLI tool: scripts/import_gedcom.py
- [x] Metadata keys: birth_date_full, death_date_full, gender in registry allowlist
- [x] AD-073 through AD-076 documented
- [x] CHANGELOG v0.39.0, ROADMAP, BACKLOG updated
- [x] 107 new tests (2081 app + 272 ML = 2353 total)

## Session 34 Completed
- [x] Data audit: Gemini subject_ages exist for 100% of 271 photos
- [x] PRD 008 updated with data audit findings and algorithm design
- [x] Birth year estimation pipeline (rhodesli_ml/pipelines/birth_year_estimation.py)
- [x] Robust outlier filtering via median + MAD
- [x] Face-to-age matching via bbox left-to-right x-coordinate sorting
- [x] 32 estimates from 46 confirmed identities (3 HIGH, 6 MEDIUM, 23 LOW)
- [x] Timeline age overlay using ML-estimated birth years
- [x] Person page birth year display with confidence styling
- [x] Identity metadata display with ML fallback (~ prefix)
- [x] Validation report (rhodesli_ml/analysis/validate_birth_years.py)
- [x] AD-071 (birth year estimation methodology), AD-072 (UI integration approach)
- [x] 48 new tests (37 ML + 11 integration) — 2246 total
- [x] Documentation: CHANGELOG v0.38.0, ROADMAP, BACKLOG, PRD 008

## Session 33 Completed
- [x] Compare link in admin sidebar (Browse section, between Timeline and About)
- [x] R2 upload persistence for compare uploads (survives Railway restarts)
- [x] Production graceful degradation (save photo to R2 without InsightFace)
- [x] "Contribute to Archive" → admin moderation queue (pending_uploads.json)
- [x] VISION.md — product direction document
- [x] Roadmap sessions 34-39 (birth dates, GEDCOM, geocoding, social graph, kinship v2, life events)
- [x] AD-070 (future architecture directions), AD-069 updated
- [x] 12 new tests (2058 total)
- [x] Documentation: CHANGELOG v0.37.1, ROADMAP, BACKLOG, VISION.md

## Session 32 Completed
- [x] Kinship calibration: 959 same-person, 385 same-family, 605 different-person pairs
- [x] Key finding: family resemblance (Cohen's d=0.43) not reliably separable
- [x] Tiered compare results: STRONG MATCH / POSSIBLE / SIMILAR / WEAK
- [x] CDF-based confidence percentages (sigmoid approximation)
- [x] Person page + timeline cross-links in compare results
- [x] Upload persistence: uploads/compare/{uuid} with metadata
- [x] Multi-face detection + face selector UI
- [x] "Contribute to Archive" CTA (auth-aware)
- [x] AD-067 (kinship calibration), AD-068 (tiered display), AD-069 (upload persistence)
- [x] 30 new tests (2046 total)
- [x] Documentation: CHANGELOG v0.37.0, ROADMAP, BACKLOG, PRD status

## Session 31 Completed
- [x] Fix 1: Context events filtered to person's era (±30/+10 years)
- [x] Fix 2: Sticky share button (controls bar sticks below nav)
- [x] Fix 3: Multi-person filter (?people=uuid1,uuid2, highlighted names)
- [x] Fix 4: Navigation back link (mobile nav visible, Compare link everywhere)
- [x] Fix 5: Collection filter on timeline (?collection= param)
- [x] Face Comparison PRD (007) — research FamilySearch, MyHeritage, Photo Sleuth
- [x] Face Comparison Tool at /compare with face selector + similarity search
- [x] find_similar_faces() in core/neighbors.py — face-level similarity
- [x] Upload-based comparison with graceful degradation (local dev only)
- [x] Compare nav link on all pages (landing, /photos, /people, /timeline, /photo, /person)
- [x] PRD stubs: 008 (birth dates), 009 (GEDCOM), 010 (geocoding), 011 (life events)
- [x] Planned sessions 32-35 added to ROADMAP.md
- [x] AD-064 (era filtering), AD-065 (face comparison engine)
- [x] 5 new timeline tests + 20 face comparison tests (2016 total)
- [x] Documentation: CHANGELOG v0.36.0, ROADMAP, BACKLOG, todo.md

## Session 30 Completed
- [x] PRD: docs/prds/timeline-story-engine.md
- [x] Historical date verification: 15 events cross-referenced from Yad Vashem, Rhodes Jewish Museum, etc.
- [x] data/rhodes_context_events.json: 15 curated events (1522-1997)
- [x] 11 e2e acceptance tests (all FAIL initially per SDD, then 11/11 PASS)
- [x] /timeline route: vertical timeline with decade markers, photo cards, context events
- [x] Person filter with HTMX + age overlay when birth_year available
- [x] Confidence interval bars on timeline photo cards
- [x] Share button with clipboard copy
- [x] Year range filtering (?start=1920&end=1950)
- [x] Context events toggle (?context=off)
- [x] Navigation links: sidebar, landing page, /photos, /people
- [x] 28 unit tests (context events loader, route handler, navigation, data validation)
- [x] Fix: KeyError on invalid person filter ID
- [x] Cache invalidation for context events in sync push
- [x] Documentation: AD-062/063, CHANGELOG v0.35.0, ROADMAP, BACKLOG

## Session 27 Completed
- [x] Phase 0: Identify unlabeled photos (21/271 unlabeled, 7.7%)
- [x] Phase 1: 12 e2e acceptance tests (all FAIL initially per SDD)
- [x] Phase 2: Date badges on photo cards with confidence styling
- [x] Phase 3: Decade filtering, keyword search, tag filtering on /photos
- [x] Phase 4: AI Analysis metadata panel on photo detail pages
- [x] Phase 5: Date correction flow with provenance tracking
- [x] Phase 6: Admin review queue with priority scoring
- [x] Phase 7: 83 new unit tests (1961 total), 12 e2e tests (all passing)
- [x] Phase 8: AD-056–059, CHANGELOG v0.34.0, ROADMAP ML-050, BACKLOG synced
- [x] Deploy safety: corrections_log.json NOT in sync lists (production-origin data)
- [x] Photo ID mismatch fix: dual-keyed caches for inbox_*/SHA256 cross-reference

## Session 26 Completed
- [x] Download 116 community photos from staging (271 total photos)
- [x] Face detection + embeddings (1061 total embeddings, 775 identities)
- [x] Upload new photos/crops to R2
- [x] Push to production, clustering (100 proposals)
- [x] Label 93 new photos with Gemini 3 Flash (250 total labels, 3 passes)
- [x] Post-labeling validation: 9 invalid Formal_Portrait tags cleaned
- [x] Build temporal consistency auditor (31 tests)
- [x] Build search metadata export (22 tests)
- [x] Run audit: 0 temporal flags, 16 missed-face photos
- [x] Run export: 250 search documents in photo_search_index.json
- [x] Retrain CORAL model with 250 labels (+59% data), MLflow tracked
- [x] All ML tests pass (137/137)
- [x] All app tests pass (1557/1557 + 1 fixed search badge test)
- [x] Documentation: AD-053–AD-055, CHANGELOG v0.33.0, ROADMAP, BACKLOG, todo.md
- [x] Docs sync verified

## Session 25 Completed
- [x] Data backup before schema changes
- [x] 11 Playwright e2e acceptance tests (SDD Phase 2)
- [x] Annotation persistence verified working (Priority 1)
- [x] Suggestion state visibility — inline "You suggested" confirmation (Priority 2)
- [x] Admin approval face thumbnails (Priority 3)
- [x] Help Identify UX: triage bar active state + "+N more" clickable (Priority 4)
- [x] Annotation dedup — duplicate suggestions add confirmations (Priority 5)
- [x] Admin skip + undo + audit log at /admin/audit (Priority 6)
- [x] Community confirmation — "I Agree" buttons on existing suggestions (Priority 7)
- [x] E2e test fix for tab state selector
- [x] Documentation: CHANGELOG, ROADMAP, BACKLOG, PRD status, todo.md
- [x] 1878 total tests (1856 baseline + 22 new)

## Session 24b Completed
- [x] FIX 1: Welcome modal tests updated — old _welcome_modal → _welcome_banner (10 tests fixed)
- [x] FIX 2: Frictionless guest tagging — anonymous saves directly, no modal loop (7 tests updated)
- [x] FIX 3: Navigation loss fixed — Help Identify links to skipped section with context
- [x] FIX 5: Modal Escape key audit — all 6 modals now dismissible via Escape (5 new tests)
- [x] Guest modal copy: removed "credit" language, reframed as review-by-family
- [x] 1845 total tests (1838 baseline + 7 net new)

## Session 24 Completed
- [x] Share button copies to clipboard first (not OS share sheet)
- [x] Face tag dropdown works for non-admin users (annotation-based suggestions)
- [x] 5 new tests (non-admin tag search, admin regression, dropdown placeholders)
- [x] Benatar feedback tracker updated (items 14-17)
- [x] Production verified: share button, non-admin tagging, annotation flow
- [x] 1851 total tests

## Session 23b Completed
- [x] Push session 23 ML pipeline (4 commits) to origin/main
- [x] Download Benatar community submission (Sarina2.jpg, Job cf8d0446)
- [x] Face detection: 3 faces extracted, 3 INBOX identities created
- [x] Clustering: no strong matches (best LOW at 1.24 distance)
- [x] Upload photo + 3 crops to R2
- [x] Push data to production (156 photos, 373 identities)
- [x] Fix ingest_inbox.py absolute path bug → relative paths
- [x] Regression test for relative path invariant
- [x] Clear staging, mark job processed
- [x] Production verification: 156 photos, Community Submissions collection visible
- [x] Update Benatar feedback tracker with submission status
- [x] 1827 total tests (1826 app + 1 new)

## Session 23 Completed
- [x] Decision provenance: DATE_ESTIMATION_DECISIONS.md + AD-039 through AD-045
- [x] ML environment setup: venv, pyproject.toml (torchvision, google-genai SDK)
- [x] Gemini evidence-first date labeling script (cultural lag, 4 evidence categories, cost guardrails)
- [x] CORAL date classifier: EfficientNet-B0 backbone, soft label KL divergence
- [x] Heritage augmentations: sepia, film grain, scanning artifacts, resolution degradation, JPEG compression, geometric distortion, fading
- [x] Regression gate: adjacent accuracy ≥0.70, MAE ≤1.5, per-decade recall ≥0.20
- [x] 53 ML pipeline tests + synthetic test fixtures (30 labels + 30 images)
- [x] MLflow experiment tracking initialized (first experiment logged)
- [x] Signal harvester refresh: 959 confirmed pairs, 510 rejected pairs (+17x), 500 hard negatives
- [x] Documentation: README, CHANGELOG v0.31.0, ROADMAP, BACKLOG, current_ml_audit.md
- [x] 1879 total tests (1826 app + 53 ML)

## Session 19f Completed
- [x] Bug 1: annotations.json added to OPTIONAL_SYNC_FILES for Railway volume sync
- [x] Bug 2: Pending upload thumbnails have graceful onerror fallback
- [x] Bug 3: Mobile horizontal overflow fixed (overflow-x:hidden, responsive wrapping, nav hidden)
- [x] Bug 4: Manual search results now show Compare button before Merge
- [x] E2E sidebar test updated (Confirmed → People rename)
- [x] 12 new tests (1672 total including 19 e2e)

## Session 19e Completed
- [x] Fix test data pollution: removed 5 test annotations + 46 contaminated history entries from production
- [x] Quality scores influence Help Identify ordering: clear faces + named matches sort first
- [x] Admin staging preview: session-authenticated endpoint replaces token-only sync API for photo thumbnails
- [x] Remove duplicate Focus Mode button from admin dashboard banner
- [x] Mobile audit: verified all 5 requirements already implemented with test coverage
- [x] Feedback tracking: FEEDBACK_INDEX.md + .claude/rules/feedback-driven.md
- [x] Data safety rules: .claude/rules/data-safety.md + guard tests
- [x] 6 new tests (1641 total)

## Session 19d Completed
- [x] Face quality scoring (AD-038): composite 0-100 score, best-face selection for thumbnails
- [x] Global face crop sizing audit: larger crops everywhere, hover effects
- [x] Mobile responsiveness: verified all features already implemented (hamburger, bottom nav, stacking)
- [x] Photo enhancement research doc (docs/ml/PHOTO_ENHANCEMENT_RESEARCH.md)
- [x] Discovery UX rules (.claude/rules/discovery-ux.md) — 10 principles
- [x] Claude Benatar feedback tracker (docs/feedback/CLAUDE_BENATAR_FEEDBACK.md)
- [x] AD-038 documented in ALGORITHMIC_DECISIONS.md
- [x] CHANGELOG, ROADMAP, BACKLOG sync for v0.28.1
- [x] 13 new tests (1635 total)

## Session 19b Completed
- [x] Search AND-matching: multi-word queries now use AND logic with variant expansion
- [x] Focus Mode button routing verified (already correct from prior session)
- [x] 300px face crops in Focus Mode (w-72, ~288px desktop)
- [x] More matches strip: horizontal scrollable strip of 2nd-5th best matches
- [x] View Photo text links below face crops
- [x] Z-key undo for merge/reject/skip in Focus Mode
- [x] Admin pending uploads photo preview thumbnails
- [x] Actionability ordering verified with 3 unit tests
- [x] 22 new tests (1589 total)

## Session 19c Completed
- [x] Discovery UX research doc (docs/design/DISCOVERY_UX_RESEARCH.md)
- [x] Structured name fields (generation_qualifier, death_place, compact display)
- [x] Smart onboarding (3-step surname recognition flow)
- [x] Personalized landing page (interest surname banner)
- [x] Navigation renaming (Inbox → New Matches, Needs Help → Help Identify)
- [x] Proposal system polish (admin approvals badge, I Know This Person rename)
- [x] 33 new tests (1622 total)

## Session 19 Completed
- [x] Best Match fallback: real-time neighbor computation when proposals empty
- [x] Source photo rendering: filename fallback for photo cache
- [x] Ordering fix: batch vectorized distances via batch_best_neighbor_distances()
- [x] Welcome modal: persistent cookie replaces session-based check
- [x] Smart landing: empty inbox → Needs Help redirect
- [x] Larger face crops + confidence rings
- [x] Sticky action bar
- [x] Collapsible Similar Identities panel (toggle, not dismiss)
- [x] Reject undo toast with unreject link
- [x] 10 new tests (1567 total)

## Session 18c Completed
- [x] Focus Mode for Needs Help: guided single-identity review with photo context, actions, keyboard shortcuts
- [x] Actionability scoring: best ML leads first in Focus and Browse
- [x] Visual badges: Strong lead / Good lead in browse view
- [x] AD-030–037: 8 rejected/under-investigation approaches
- [x] DECISION_LOG.md: 18 major decisions
- [x] SUPABASE_AUDIT.md: auth-only usage
- [x] Lightbox navigation verified (49 tests, fully working)
- [x] Gender metadata assessed (not available in data, would need re-ingest)

## Active Bugs
- (none)

## Setup Required (ONE TIME)
- [ ] Generate sync token: `python scripts/generate_sync_token.py`
- [ ] Set RHODESLI_SYNC_TOKEN on Railway: `railway variables set RHODESLI_SYNC_TOKEN=<token>`
- [ ] Set RHODESLI_SYNC_TOKEN in .env: `echo 'RHODESLI_SYNC_TOKEN=<token>' >> .env`
- [ ] Deploy (push to main or Railway auto-deploy)
- [ ] Test sync: `python scripts/sync_from_production.py --dry-run`

## Ready to Apply (after sync)
- [ ] Sync production data: `python scripts/sync_from_production.py`
- [ ] Re-run ML pipeline: `bash scripts/full_ml_refresh.sh`
- [ ] Apply 19 VERY_HIGH matches: `python scripts/apply_cluster_matches.py --execute --tier very_high`
- [ ] Apply 33 HIGH matches: `python scripts/apply_cluster_matches.py --execute --tier high`
- [ ] After applying, sync to production and confirm in web UI

## Immediate (This Weekend)
- [ ] Re-run validation after sync to check if admin tagging created signal
- [ ] Test new UX features on real phone (mobile responsive, touch swipe, keyboard shortcuts)
- [ ] Share with 2-3 family members for initial feedback
- [ ] Smoke test all fixes on live site

## Near-Term (Next 1-2 Weeks)
- [x] ML-050: Date UX integration — display estimated decade + confidence on photo viewer (2026-02-14, Session 27)
- [x] ML-051: Silver-label all photos via Gemini (250/271 labeled, 4 persistent timeouts)
- [x] ML-052: Train date estimation model on real labels (250 labels, MLflow tracked)
- [x] GEDCOM import pipeline (Session 35) — parser, matcher, graphs, admin UI, enrichment
- [ ] ML-053: Integrate date labeling into upload orchestrator (process_uploads.py)
- [ ] ML-054: Multi-pass Gemini — re-label low-confidence photos with Flash model
- [ ] ML-060: Train similarity calibration model on 959 pairs + 510 rejections
- [ ] ML-061: MLS vs Euclidean golden set evaluation (does sigma_sq help?)
- [ ] OPS-001: Custom SMTP for branded "Rhodesli" email sender
- [ ] FE-041: "Help Identify" mode for non-admin users
- [ ] FE-040–FE-043: Skipped faces workflow for non-admin users
- [ ] scripts/pull_compare_uploads.py — pull R2 compare uploads for local ML ingestion
- [ ] Gemini enrichment on uploaded photos (async, after face detection)
- [ ] Set R2 write credentials on Railway (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME)

## Medium-Term (Next Month)
- [ ] FE-070–FE-073: Client-side analytics and admin dashboard
- [ ] BE-031–BE-033: Upload moderation queue with rate limiting
- [ ] ROLE-006: Email notifications for contributors
- [ ] "Six degrees" connection finder UI (graph data ready from Session 35)
- [ ] GEDCOM visualization — rich family tree view beyond basic lists
- [ ] Cross-reference GEDCOM dates with ML photo date estimates
- [ ] Proximity scoring between individuals
- [ ] Geographic migration analysis (community dispersal patterns)
- [ ] Kinship recalibration after GEDCOM import (AD-067 update)
- [ ] Data visualizations for relationship/geographic data
- [ ] Life events tagging system
- [ ] Richer community-specific context events (Montgomery, Atlanta, Asheville, Havana)
- [ ] Timeline navigation scrubber (Google Photos style)
- [ ] Postgres migration (identities + photo_index -> Supabase)

## Long-Term (Quarter+)
- [x] Family tree integration — GEDCOM import (Session 35), relationships stored, next: visualization
- [ ] Auto-processing pipeline (ML on Railway, no local step)
- [ ] Age-invariant face recognition research
- [ ] Multi-tenant architecture (other communities)
- [ ] CI/CD pipeline (automated tests, staging, deploy previews)

## Completed
- [x] v0.23.0: Navigation hardening + ML pipeline scaffold (1438 tests)
  - Triage filter propagation through focus mode action chain
  - Photo nav boundary indicators (dimmed arrows at first/last)
  - Grammar pluralization helper _pl()
  - rhodesli_ml/ package: 26 files (signal harvester, date labeler, audits)
  - ML audit: 947 confirmed pairs, 29 rejections, calibration feasible
  - Photo date audit: 92% undated, silver-labeling feasible
- [x] v0.22.1: Filter consistency + promotion context (1415 tests)
  - Match mode filters (ready/rediscovered/unmatched) now work
  - Up Next thumbnails preserve active filter in navigation links
  - Promotion banners show specific context (group member names)
  - 15 new tests, lesson 63
- [x] v0.21.0: Data integrity + proposals UI + scalability (1355 tests)
  - Merge-aware push_to_production.py (production wins on conflicts)
  - Zeb Capuano identity restored (24 confirmed)
  - Clustering proposals wired to Focus/Match/Browse modes
  - Staging lifecycle (mark-processed endpoint)
  - Grammar pluralization + collections carousel
  - 4 new .claude/rules/ files
- [x] Phase A: Railway deployment + Supabase auth + permission model
- [x] Phase A stabilization: all 8 P0 bugs fixed, event delegation pattern
- [x] Phase B: Landing page, search, mobile, sync infrastructure
- [x] v0.10.0–v0.12.1: Face overlays, inline actions, fuzzy search, photo nav
- [x] v0.13.0: ML validation — threshold calibration, golden set, clustering validation
- [x] v0.14.0: Token-authenticated sync API + reliable sync script
- [x] v0.14.1: Skipped faces fix — clustering includes 192 skipped faces
- [x] v0.15.0: Upload processing pipeline — staged file sync API, download, orchestrator
- [x] v0.16.0: ML pipeline + annotation engine + collaboration (969 tests)
- [x] v0.17.0: Annotation engine + merge safety + contributor roles (1032 tests)
- [x] v0.17.1: Verification pass — golden set, permission tests, ROLES.md (1059 tests)
- [x] v0.17.2: Quality hardening — EXIF ingestion, error handling, permission tests (1152 tests)
- [x] v0.18.0: UX Overhaul + Contributor Flow (1221 tests)
  - Landing page rewrite with historical Rhodes content
  - Login prompt modals with action context
  - Section rename: Confirmed→People, Skipped→Needs Help
  - Button prominence: View All Photos + Find Similar
  - Compare faces UX: face/photo toggle, clickable names
  - Contributor merge suggestions with admin approval
  - Bulk photo select mode with collection reassignment
