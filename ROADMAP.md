# Rhodesli Development Roadmap

Heritage photo identification system. FastHTML + InsightFace + Supabase + Railway + R2.
Current: v0.49.1 · 2373 tests · 271 photos · 181 faces · 46 confirmed

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

## Phase Summary

| Phase | Status | Details |
|-------|--------|---------|
| **A: Stabilization** | COMPLETE | All P0 bugs fixed, 103 tests added |
| **B: Share-Ready Polish** | ~95% complete | 53/54 items done. Remaining: OPS-001 (custom SMTP) |
| **C: Annotation Engine** | COMPLETE | 16/16 items done. Full submit/review/approve workflow |
| **D: ML Feedback** | ~80% complete | Date pipeline + golden set done. Remaining: ML-051-053, FE-040-043 |
| **E: Collaboration** | ~60% complete | Contributor roles + activity feed done. Remaining: Help Identify mode, analytics, moderation queue |
| **F: Scale & Generalize** | ~10% complete | Playwright tests done. Remaining: Postgres, CI/CD, Sentry, model eval |

For full feature checklists, see [docs/roadmap/FEATURE_STATUS.md](docs/roadmap/FEATURE_STATUS.md).
For ML-specific roadmap, see [docs/roadmap/ML_ROADMAP.md](docs/roadmap/ML_ROADMAP.md).

## Open Work (Prioritized)

### High Priority
- [ ] ML-051: Date label pipeline — integrate into upload orchestrator
- [ ] ML-052: New upload auto-dating
- [ ] OPS-001: Custom SMTP for branded email sender

### Medium Priority
- [ ] ML-001: User actions feed back to ML predictions
- [ ] ML-053: Multi-pass Gemini — low-confidence re-labeling
- [ ] FE-041: "Help Identify" mode for non-admin users
- [ ] ROLE-006: Email notifications for contributors

### Low Priority (Phase F)
- [ ] BE-040–042: PostgreSQL migration
- [ ] OPS-002: CI/CD pipeline
- [ ] OPS-004: Error tracking (Sentry)
- [ ] ML-030–032: Model evaluation (ArcFace, ensemble, fine-tuning)
- [ ] GEN-001+: Multi-tenant architecture

## Planned Sessions

### Session 49B: Interactive Review (requires Nolan)
- Birth year bulk review — generate ground truth anchors
- Real GEDCOM upload + match review
- Visual walkthrough of all features
- See: docs/session_context/session_49_interactive_prep.md

### Session 50: Admin/Public UX Unification
- Progressive admin enhancement + admin toolbar
- Route consolidation (?section=photos → /photos)
- Design + admin bar + first pass

### Session 51: Landing Page Refresh
- Live-data entry points, mobile-first

### Session 52+: ML Track (concurrent, safe)
- Similarity calibration, active learning analysis

### Session 43: Life Events & Context Graph (deferred)
- Event tagging: "Moise's wedding in Havana"
- Events connect photos, people, places, dates
- PRD: docs/prds/011_life_events_context_graph.md

### Session 47: ML Gatekeeper + Feature Reality Contract (COMPLETED 2026-02-18)
- [x] ML Gatekeeper Pattern — staged admin review for ML birth year estimates (AD-097)
- [x] Bulk review page at /admin/review/birth-years with Accept/Edit/Reject/Accept All High
- [x] Ground truth feedback loop — confirmed birth years → retraining data (AD-099)
- [x] Feature Reality Contract — anti-phantom-feature harness rule (AD-098)
- [x] User Input Taxonomy documentation (AD-100)
- [x] Dynamic version display from CHANGELOG.md (was hardcoded "v0.6.0")
- [x] ROADMAP.md split (394→90 lines) + BACKLOG.md split (558→102 lines)
- [x] 23 new tests (2365 total)

## Recently Completed

- [x] 2026-02-18: **v0.49.2 — Session 49**: Production Polish. Health check (10/10 routes), Session 47/48 deliverable verification (all PASS), collection name truncation fix, triage bar tooltips, interactive session prep checklist. 5 new tests (2378 total).
- [x] 2026-02-18: **v0.49.1 — Session 48**: Harness Inflection. Prompt decomposition, phase execution, verification gate rules. HARNESS_DECISIONS.md (HD-001-007). Age on face overlays (Session 47 Phase 2F completion). Session log infrastructure. CLAUDE.md compressed (113->77). 4 new tests (2373 total).
- [x] 2026-02-18: **v0.49.0 — Session 47**: ML Gatekeeper + Feature Reality Contract. ML birth year estimates gated behind admin review. Bulk review page. Ground truth feedback loop. Dynamic version display. ROADMAP + BACKLOG splits. AD-097-100. 23 new tests (2365 total).
- [x] 2026-02-18: **v0.48.0 — Session 46**: Match Page Polish + Year Estimation Tool V1. Help Identify sharing fixes, face carousel, deep link CTAs, lightbox face overlays. Year Estimation Tool V1 at /estimate with per-face reasoning. 56 new tests (2342 total).
- [x] 2026-02-18: **v0.47.0 — Session 45**: Overnight Polish. All 12 remaining items from 36-item feature audit. Photo + person inline editing, admin nav consistency, structured logging. 32 new tests (2281 total).
- [x] 2026-02-17: **v0.46.0 — Session 44**: Compare Faces Redesign + Sharing Design System. Unified og_tags() + share_button(). Compare upload-first redesign. Calibrated confidence labels. Shareable comparison pages. 21 new tests (2249 total).

For sessions 1-43: see [docs/roadmap/SESSION_HISTORY.md](docs/roadmap/SESSION_HISTORY.md).

## Reference Documents
- Detailed backlog: `docs/BACKLOG.md`
- Feature status: `docs/roadmap/FEATURE_STATUS.md`
- ML roadmap: `docs/roadmap/ML_ROADMAP.md`
- Session history: `docs/roadmap/SESSION_HISTORY.md`
- ML decisions: `docs/ml/ALGORITHMIC_DECISIONS.md`
- Ops decisions: `docs/ops/OPS_DECISIONS.md`
- Lessons learned: `tasks/lessons.md`
