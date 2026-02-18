# Feature Status by Phase

Detailed feature checklist for all phases. For current priorities, see [ROADMAP.md](../../ROADMAP.md).

---

## Phase A: Stabilization -- COMPLETE

Goal: Fix all active bugs, get site stable enough to share.

- [x] BUG-003: Direction-aware merge -- already implemented with 18 tests (2026-02-08)
- [x] BUG-001: Lightbox arrow fix with 16 regression tests, event delegation (2026-02-08)
- [x] BUG-002: Face count label matches visible boxes (FE-025, QA-003) (2026-02-08)
- [x] BUG-004: Collection stats denominator fix -- canonical _compute_sidebar_counts() (2026-02-08)
- [x] FE-002: Keyboard shortcuts in Match Mode -- Y/N/S for same/different/skip (2026-02-08)
- [x] FE-003: Universal keyboard shortcuts -- consolidated global handler for all views (2026-02-08)
- [x] Smoke tests: 21 tests covering all routes, scripts, interactive elements (2026-02-08)
- [x] FE-004: Consistent lightbox component -- consolidated #photo-lightbox into #photo-modal (2026-02-08)
- [x] FE-032: Fix search result navigation -- hash fragment scroll + highlight (2026-02-08)
- [x] DATA-001: Backfill merge_history for 24 pre-existing merges (2026-02-08)
- [ ] Smoke test all fixes on live site

## Phase B: Share-Ready Polish

Goal: Landing page, search, mobile -- ready for family members.

- [x] FE-050: Welcome/about landing page with heritage photos (2026-02-06)
- [x] FE-051: Interactive hero with real archive photos (2026-02-06)
- [x] FE-052: First-time user welcome modal (2026-02-10)
- [x] FE-053: Progress dashboard ("23 of 181 faces identified") (2026-02-08)
- [x] FE-030: Global search improvements (2026-02-08)
- [x] FE-031: Fast name lookup with typeahead (2026-02-08)
- [x] FE-033: Fuzzy name search with Levenshtein distance (2026-02-08)
- [x] FE-010: Mobile sidebar -- hamburger menu or slide-over (2026-02-06)
- [x] FE-011: Bottom tab navigation on mobile (2026-02-08)
- [x] FE-014: Responsive photo grid (2-col mobile, 4-col desktop) (2026-02-06)
- [x] FE-015: Mobile match mode -- vertical stacking with swipe (2026-02-06)
- [x] FE-054: Landing page stats fix + historical Rhodes content rewrite (2026-02-10)
- [x] FE-055: UI clarity -- section descriptions, Skipped->Needs Help, Confirmed->People, empty states (2026-02-10)
- [x] FE-056: Button prominence -- View All Photos + Find Similar as styled buttons (2026-02-10)
- [x] FE-057: Compare faces UX overhaul -- face/photo toggle, clickable names, sizing (2026-02-10)
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
- [x] FE-075: Consistent share button across all surfaces (2026-02-12)
- [x] FE-076: Premium photo flip animation (2026-02-12)
- [x] BE-024: Admin back image upload + transcription editor (2026-02-12)
- [x] BE-025: Non-destructive image orientation (2026-02-12)
- [x] FE-077: Photo viewer polish (2026-02-12)
- [x] FE-078: Public person page at /person/{id} (2026-02-13)
- [x] FE-079: Public /photos and /people browsing pages (2026-02-13)
- [x] FE-090: Person page links from photo viewer (2026-02-13)
- [x] FE-091: "Public Page" link on identity cards (2026-02-13)
- [x] FE-100: Timeline Story Engine at /timeline (2026-02-15)
- [x] FE-101: Person filter + age overlay on timeline (2026-02-15)
- [x] FE-102: Share button + year range filter on timeline (2026-02-15)
- [x] DATA-010: Rhodes historical context events -- 15 curated events (2026-02-15)
- [x] FE-103: Timeline collection filter (2026-02-15)
- [x] FE-104: Timeline multi-person filter (2026-02-15)
- [x] FE-105: Timeline sticky controls (2026-02-15)
- [x] FE-106: Timeline context events era filtering (2026-02-15)
- [x] FE-107: Timeline mobile nav (2026-02-15)
- [x] FE-110: Face Comparison Tool at /compare (2026-02-15)
- [x] FE-111: Compare navigation across site (2026-02-15)
- [x] ML-065: Kinship calibration -- empirical thresholds (2026-02-15)
- [x] FE-112: Tiered compare results with CDF confidence (2026-02-15)
- [x] FE-113: Compare upload persistence + multi-face selection (2026-02-15)
- [x] FE-114: Unified sharing design system (2026-02-17)
- [x] FE-115: Compare page upload-first redesign (2026-02-17)
- [x] FE-116: Calibrated match confidence labels (2026-02-17)
- [x] FE-117: Shareable comparison result pages (2026-02-17)
- [x] FE-118: Site-wide OG tags + share buttons (2026-02-17)

## Phase C: Annotation Engine

Goal: Make the archive meaningful beyond face matching.

- [x] BE-010: Structured identity names (2026-02-10)
- [x] BE-011: Identity metadata -- set_metadata() with allowlisted keys (2026-02-10)
- [x] BE-012: Photo metadata -- set_metadata/get_metadata (2026-02-10)
- [x] BE-013: EXIF extraction -- core/exif.py (2026-02-10)
- [x] BE-023: Photo provenance model -- source/collection/source_url (2026-02-10)
- [x] FE-064: Upload UX overhaul (2026-02-10)
- [x] BE-014: Canonical name registry -- surname_variants.json (2026-02-11)
- [x] AN-001: Annotation system core -- submit/review/approve/reject (2026-02-10)
- [x] AN-002-006: Photo-level annotations display + submission form (2026-02-10)
- [x] AN-010-014: Identity metadata display + annotations (2026-02-10)
- [x] BE-001-006: Non-destructive merge with audit snapshots (2026-02-10)
- [x] FE-033: Fuzzy name search with Levenshtein distance (2026-02-08)
- [x] AN-030: Suggestion state visibility (2026-02-13)
- [x] AN-031: Admin approval UX with face thumbnails (2026-02-13)
- [x] AN-032: Annotation dedup + community "I Agree" (2026-02-13)
- [x] FE-092: Triage bar active state + clickable "+N more" (2026-02-13)

## Phase D: ML Feedback & Intelligence

Goal: Make the system learn from user actions. See also [ML_ROADMAP.md](ML_ROADMAP.md).

- [ ] ML-001: User actions feed back to ML predictions
- [x] ML-004: Dynamic threshold calibration (2026-02-09, AD-013)
- [x] ML-005: Post-merge re-evaluation (2026-02-10)
- [x] ML-006: Ambiguity detection (2026-02-10)
- [x] ML-010: Golden set rebuild (2026-02-09)
- [x] ML-012: Golden set evaluation (2026-02-09)
- [x] ML-011: Golden set diversity analysis (2026-02-10)
- [x] ML-013: Evaluation dashboard (2026-02-10)
- [x] ML-021: Calibrated confidence labels (2026-02-09)
- [x] ML-040-047: Date estimation pipeline (2026-02-13 to 2026-02-14)
- [x] ML-050: Date UX integration (2026-02-14)
- [ ] ML-051: Date label pipeline -- integrate into upload orchestrator
- [ ] ML-052: New upload auto-dating
- [ ] ML-053: Multi-pass Gemini -- low-confidence re-labeling
- [ ] FE-040-043: Skipped faces workflow for non-admin users

## Phase E: Collaboration & Growth

Goal: Enable family members to contribute, not just browse.

- [x] ROLE-002: Contributor role (2026-02-10)
- [x] ROLE-003: Trusted contributor (2026-02-10)
- [ ] FE-041: "Help Identify" mode for non-admin users
- [ ] FE-070-073: Client-side analytics and admin dashboard
- [ ] BE-031-033: Upload moderation queue with rate limiting
- [x] ROLE-007: Contributor merge suggestions (2026-02-10)
- [x] ROLE-005: Activity feed at /activity (2026-02-10)
- [x] FE-060: Anonymous guest contributions (2026-02-10)
- [ ] ROLE-006: Email notifications for contributors

## Phase F: Scale & Generalize

Goal: Production-grade infrastructure and multi-tenant potential.

- [ ] BE-040-042: PostgreSQL migration (Supabase Postgres)
- [ ] AN-020-023: Family tree integration (GEDCOM, timeline view)
- [ ] OPS-002: CI/CD pipeline (automated tests, staging, deploy previews)
- [ ] OPS-004: Error tracking (Sentry)
- [ ] ML-030-032: Model evaluation (ArcFace, ensemble, fine-tuning)
- [x] QA-004: End-to-end browser tests (Playwright) (2026-02-08)
- [ ] GEN-001+: Multi-tenant architecture (if traction)

---

## Planned Sessions

### Session 43: Life Events & Context Graph
- Event tagging: "Moise's wedding in Havana"
- Events connect photos, people, places, dates
- Richer timeline with life events interspersed
- PRD: docs/prds/011_life_events_context_graph.md

---

## Reference Documents
- Detailed backlog: `docs/BACKLOG.md` (120+ items with full context)
- ML decisions: `docs/ml/ALGORITHMIC_DECISIONS.md`
- Ops decisions: `docs/ops/OPS_DECISIONS.md`
- Lessons learned: `tasks/lessons.md`
- Task details: `tasks/phase-a/` (current phase only)
