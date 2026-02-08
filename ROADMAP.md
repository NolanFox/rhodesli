# Rhodesli Development Roadmap

Heritage photo identification system. FastHTML + InsightFace + Supabase + Railway + R2.
Current: v0.10.0 · 663 tests · 148 photos · 181 faces · 23 confirmed

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
- Only 1 admin (NolanFox@gmail.com) — no contributor roles yet

## Active Bugs (P0)
- [x] BUG-001: Lightbox arrows disappear after first photo — fixed with event delegation (2026-02-08)
- [x] BUG-002: Face count label shows detection count, not displayed/tagged count (2026-02-08)
- [x] BUG-003: Merge direction — already fixed in code, 18 direction-specific tests added (2026-02-08)
- [x] BUG-004: Collection stats inconsistency — canonical _compute_sidebar_counts() (2026-02-08)

## Phase A: Stabilization — COMPLETE
Goal: Fix all active bugs, get site stable enough to share.

- [x] BUG-003: Direction-aware merge — already implemented with 18 tests (2026-02-08)
- [x] BUG-001: Lightbox arrow fix with 16 regression tests, event delegation (2026-02-08)
- [x] BUG-002: Face count label matches visible boxes (FE-025, QA-003) (2026-02-08)
- [x] BUG-004: Collection stats denominator fix — canonical _compute_sidebar_counts() (2026-02-08)
- [x] FE-002: Keyboard shortcuts in Match Mode — Y/N/S for same/different/skip (2026-02-08)
- [x] FE-003: Universal keyboard shortcuts — consolidated global handler for all views (2026-02-08)
- [x] Smoke tests: 21 tests covering all routes, scripts, interactive elements (2026-02-08)
- [ ] FE-004: Consistent lightbox component across sections
- [ ] Smoke test all fixes on live site

## Phase B: Share-Ready Polish
Goal: Landing page, search, mobile — ready for family members.

- [ ] FE-050: Welcome/about landing page with heritage photos
- [ ] FE-051: Interactive hero with real archive photos
- [ ] FE-052: First-time user guided tour
- [ ] FE-053: Progress dashboard ("23 of 181 faces identified")
- [x] FE-030: Global search improvements (2026-02-08)
- [x] FE-031: Fast name lookup with typeahead (2026-02-08)
- [ ] FE-010: Mobile sidebar — hamburger menu or slide-over
- [ ] FE-011: Bottom tab navigation on mobile
- [ ] FE-014: Responsive photo grid (2-col mobile, 4-col desktop)
- [ ] FE-015: Mobile match mode — vertical stacking with swipe
- [ ] OPS-001: Custom SMTP for branded "Rhodesli" email sender
- [ ] BE-020: Admin data export endpoint
- [ ] BE-021: Production-to-local sync script

## Phase C: Annotation Engine
Goal: Make the archive meaningful beyond face matching.

- [ ] BE-010: Structured identity names (first, last, maiden, aliases)
- [ ] BE-011: Identity metadata (birth/death dates, places)
- [ ] BE-012: Photo metadata (date, location, occasion, source)
- [ ] BE-013: EXIF extraction from uploaded photos
- [ ] BE-014: Canonical name registry (variant spellings)
- [ ] AN-001–AN-006: Photo-level annotations (captions, dates, locations, stories)
- [ ] AN-010–AN-014: Identity-level annotations (bio, relationships, generation)
- [ ] BE-001–BE-006: Non-destructive merge system with full history
- [ ] FE-033: Fuzzy name search with canonical names

## Phase D: ML Feedback & Intelligence
Goal: Make the system learn from user actions.

- [ ] ML-001: User actions feed back to ML predictions
- [ ] ML-004: Dynamic threshold calibration from confirmed/rejected pairs
- [ ] ML-005: Reclustering after merges (re-evaluate nearby faces)
- [ ] ML-006: Family resemblance handling (relative vs absolute distance)
- [ ] ML-010–ML-013: Golden set expansion and evaluation dashboard
- [ ] ML-021: Calibrated confidence labels (VERY HIGH/HIGH/MODERATE/LOW)
- [ ] FE-040–FE-043: Skipped faces workflow for non-admin users

## Phase E: Collaboration & Growth
Goal: Enable family members to contribute, not just browse.

- [ ] ROLE-002: Contributor role (propose identifications, add annotations)
- [ ] ROLE-003: Trusted contributor (direct confirmation after N correct proposals)
- [ ] FE-041: "Help Identify" mode for non-admin users
- [ ] FE-070–FE-073: Client-side analytics and admin dashboard
- [ ] BE-031–BE-033: Upload moderation queue with rate limiting
- [ ] ROLE-005: Activity feed (recent identifications, uploads, merges)
- [ ] ROLE-006: Email notifications for contributors

## Phase F: Scale & Generalize
Goal: Production-grade infrastructure and multi-tenant potential.

- [ ] BE-040–BE-042: PostgreSQL migration (Supabase Postgres)
- [ ] AN-020–AN-023: Family tree integration (GEDCOM, timeline view)
- [ ] OPS-002: CI/CD pipeline (automated tests, staging, deploy previews)
- [ ] OPS-004: Error tracking (Sentry)
- [ ] ML-030–ML-032: Model evaluation (ArcFace, ensemble, fine-tuning)
- [ ] QA-004: End-to-end browser tests (Playwright)
- [ ] GEN-001+: Multi-tenant architecture (if traction)

## Recently Completed
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
