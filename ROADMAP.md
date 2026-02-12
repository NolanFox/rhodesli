# Rhodesli Development Roadmap

Heritage photo identification system. FastHTML + InsightFace + Supabase + Railway + R2.
Current: v0.28.1 · 1635 tests · 155 photos · 181 faces · 24 confirmed · 16 proposals ready

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

## Recently Completed
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
