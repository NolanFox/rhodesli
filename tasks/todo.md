# Rhodesli Project Backlog

Last updated: 2026-02-19 (Session 50 — Estimate Overhaul + Gemini Upgrade)

## Session 50 Completed
- [x] Phase 0: Orient + verify 49C + save prompt
- [x] Phase 1: Compare upload hardening (client/server validation)
- [x] Phase 2: PRD-020 Estimate page overhaul
- [x] Phase 3: Estimate fixes (face count, pagination, nav, upload, evidence)
- [x] Phase 4: Gemini model audit (AD-101-103)
- [x] Phase 5: PRD-015 updated for Gemini 3.1 Pro
- [x] Phase 6: ROADMAP + BACKLOG sync
- [x] Phase 7: Verification gate
- [x] Phase 8: Final docs + changelog

## Session 49C Completed
- [x] Photo page 404 for community/inbox photos (alias resolution)
- [x] Compare upload silent failure (onchange auto-submit)
- [x] Version v0.0.0 in admin footer (Dockerfile COPY)
- [x] Collection name truncation (6 remaining locations)
- [x] 9 new tests (2387 total)

## Session 47 Completed
- [x] ROADMAP.md split (394→90 lines) + sub-files in docs/roadmap/
- [x] BACKLOG.md split (558→102 lines) + sub-files in docs/backlog/
- [x] Session 47 planning context ingested to docs/session_context/
- [x] Phase 1: Diagnostic audit — /estimate 404 on prod, version "v0.6.0" bug, birth years ungated
- [x] ML Gatekeeper Pattern — include_unreviewed param on _get_birth_year(), review decisions JSON
- [x] Admin suggestion card on person pages (Accept/Edit/Reject)
- [x] Bulk review page at /admin/review/birth-years with sortable table
- [x] Accept All High Confidence batch action
- [x] Ground truth feedback loop — confirmed data → data/ground_truth_birth_years.json
- [x] Dynamic version display from CHANGELOG.md (fixed hardcoded "v0.6.0")
- [x] Feature Reality Contract rule (.claude/rules/feature-reality-contract.md)
- [x] Session Context Integration rule (.claude/rules/session-context-integration.md)
- [x] AD-097 through AD-100 documented
- [x] 23 new tests (2365 total)
- [x] CHANGELOG v0.49.0, ROADMAP, BACKLOG updated

## Session 46 Completed
- [x] PRD-018 year estimation tool, research doc, feedback log
- [x] Phase 1: Help Identify sharing — Best Match links, dual photo context, share URL fix
- [x] Phase 2: Face carousel — prev/next arrows for multi-face identities on match page
- [x] Phase 3: Deep link CTAs — "View full profile" / "Help Identify" on match page, "Explore the Archive" on /identify
- [x] Phase 4: Lightbox — face overlays with state colors, metadata bar, View Photo Page link
- [x] Phase 5: Year Estimation Tool V1 — /estimate page, per-face evidence, scene evidence, confidence, share
- [x] core/year_estimation.py — estimation engine (weighted aggregation, bbox ordering, scene fallback)
- [x] Compare/Estimate tab navigation
- [x] AD-092 through AD-096 documented
- [x] 56 new tests (2342 total)
- [x] CHANGELOG v0.48.0, ROADMAP, BACKLOG, feedback log updated

## Session 44 Completed
- [x] Research docs: compare_faces_competitive.md, sharing_design_system.md
- [x] PRD-016 (compare faces redesign), PRD-017 (sharing design system)
- [x] Unified sharing components: og_tags() helper + generalized share_button()
- [x] Share JS deduplication (replaced inline copies with _share_script())
- [x] Compare page upload-first redesign (upload above fold, archive collapsible)
- [x] Calibrated confidence labels (AD-091): 85%+ Very likely, 70-84% Strong, 50-69% Possible, <50% Unlikely
- [x] Share Results + Try Another Photo CTAs on compare results
- [x] Shareable comparison result pages at /compare/result/{id}
- [x] Site-wide og_tags() on /photos, /people, /collections
- [x] Share buttons on /photos and /people pages
- [x] Fixed uuid import bug (4 test failures)
- [x] 21 new tests (2249 total)
- [x] AD-091, CHANGELOG v0.46.0, ROADMAP, BACKLOG

## Session 42 Completed
- [x] Systematic verification audit of all 16 routes + 20 features
- [x] Fix /identify/{id} 500 — set not subscriptable, wrapped in list()
- [x] Fix landing page nav — all 8 public pages linked
- [x] GEDCOM test data warning banner
- [x] Compare page two-mode UX (numbered sections)
- [x] "Add Photos" button on collection pages (admin-only)
- [x] Critical route test mock fixed (set vs list return type)
- [x] 7 new tests (2209 total), all 2563 tests passing
- [x] CHANGELOG v0.44.0, ROADMAP, BACKLOG, audit doc, postmortem

## Remaining from Session 40 Feedback (Future Work)
- [x] FB-40-18: Face click behavior — DONE (Session 41)
- [x] FB-40-20: Photo carousel / gallery mode — DONE (Session 41)
- [x] FB-40-21: Admin-only elements hidden from public — verified correct (Session 42)
- [ ] FB-40-22: Photo upload attribution display (needs data model: `uploaded_by` field)
- [x] FB-40-23: "Add Photos" button on collection detail pages — DONE (Session 42)
- [ ] FB-40-24: Bulk collection/source editing in admin Photos view
- [ ] FB-40-25: Individual photo collection/source editable by admin
- [ ] FB-40-26: Upload flow collection assignment clarity
- [x] FB-40-27: Fix search → Focus mode wrong person — DONE (Session 41)
- [ ] FB-40-09: Geographic autocomplete with location_dictionary.json
- [x] FB-40-11: GEDCOM page — test data warning added (Session 42)
- [x] FB-40-13: Compare UX — two clear modes (Session 42)

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
