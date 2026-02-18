# Rhodesli: Project Backlog

**Version**: 20.0 — February 18, 2026
**Status**: 2365 tests passing, v0.49.0, 271 photos, 46 confirmed identities, 181 faces, 267 geocoded
**Live**: https://rhodesli.nolanandrewfox.com

---

## Current State Summary

Rhodesli is an ML-powered family photo archive for the Rhodes/Capeluto Jewish heritage community. It uses InsightFace/AdaFace PFE with MLS distance metrics, FastHTML for the web layer, Supabase for auth, Railway for hosting, and Cloudflare R2 for photo storage. Admin: NolanFox@gmail.com (sole admin). 46 sessions have delivered deployment, auth, core UX, ML pipeline, stabilization, share-ready polish, ML validation, sync infrastructure, family tree, social graph, map, timeline, compare tool, sharing design system, feature audit polish, match page polish, year estimation tool, and 2342 tests.

---

## Active Bugs

**All P0 bugs resolved.** BUG-001 through BUG-008 fixed as of v0.14.1.
Details: [docs/backlog/FEATURE_MATRIX_FRONTEND.md](backlog/FEATURE_MATRIX_FRONTEND.md#1-bugs)

---

## Latest: Session 47 (v0.49.0 — 2026-02-18)

- ML Gatekeeper Pattern — ML birth year estimates gated behind admin review (AD-097)
- Bulk review page at /admin/review/birth-years with Accept/Edit/Reject/Accept All High
- Ground truth feedback loop — confirmed data → retraining samples (AD-099)
- Feature Reality Contract harness rule — anti-phantom-feature check (AD-098)
- User Input Taxonomy documentation (AD-100)
- Dynamic version display from CHANGELOG.md (was hardcoded "v0.6.0")
- ROADMAP.md split (394→90 lines) + BACKLOG.md split (558→102 lines)
- AD-097–100. 23 new tests (2365 total)

---

## Immediate Priority (Next 1-2 Sessions)

- [ ] **ML-051**: Date label pipeline — integrate into upload orchestrator
- [ ] **ML-052**: New upload auto-dating — run date estimation on new photos
- [ ] **OPS-001**: Custom SMTP for branded "Rhodesli" email sender
- [ ] **FE-040-043**: Skipped faces workflow for non-admin users
- [ ] **Session 43**: Life Events & Context Graph (event tagging, richer timeline)

## Near-Term (3-5 Sessions)

- [ ] **FE-041**: "Help Identify" mode for non-admin users
- [ ] **BE-031-033**: Upload moderation queue with rate limiting
- [ ] **ROLE-006**: Email notifications for contributors
- [ ] **ML-053**: Multi-pass Gemini for low-confidence re-labeling
- [ ] **BE-015-016**: Geographic data model + temporal date handling
- [ ] **FE-061-063**: Quick Compare, batch confirmation, browser performance audit

## Medium-Term

- [ ] **OPS-002**: CI/CD pipeline (automated tests, staging, deploy previews)
- [ ] **OPS-004**: Error tracking (Sentry)
- [ ] **QA-005-007**: Mobile viewport tests, UX walkthroughs, performance benchmarking
- [ ] **AN-022**: Cross-reference genealogy databases (Ancestry, FamilySearch, JewishGen)
- [ ] **DOC-010-013**: In-app help, about page, admin guide, contributor onboarding
- [ ] **FE-080-083**: Client-side analytics and admin dashboard
- [ ] **ROLE-004**: Family member self-identification ("That's me!" button)

## Long-Term

- [ ] **BE-040-042**: PostgreSQL migration (JSON won't scale past ~500 photos)
- [ ] **ML-030-032**: Model evaluation (ArcFace, ensemble, fine-tuning)
- [ ] **GEN-001+**: Multi-tenant architecture (if traction)
- [ ] **AI-001/003-005**: Auto-caption, photo restoration, handwriting OCR, story generation
- [ ] **GEO-003**: Community-specific context events (diaspora cities)
- [ ] **KIN-001**: Kinship recalibration post-GEDCOM

---

## Next Sessions (Prioritized)

### Session 49B (Interactive — requires Nolan)
- Birth year bulk review (generate ground truth anchors)
- Real GEDCOM upload + match review
- Visual walkthrough of all features
- Bug list from manual testing
- See: [docs/session_context/session_49_interactive_prep.md](../session_context/session_49_interactive_prep.md)

### Session 50: Admin/Public UX Unification (1 of 3)
- Pattern: Progressive Admin Enhancement + Admin Bar
- Keep public view as canonical experience (it's better designed)
- Layer admin controls inline when authenticated
- Thin WordPress-style admin toolbar: inbox counts, quick links
- Fix the "two different apps" problem (`/?section=photos` vs `/photos`)
- Consolidate `/admin/pending` and `/admin/proposals` to use `_admin_nav_bar()`
- Add `/admin/review-queue` to admin nav
- This is a 3-session project; Session 50 is design + admin bar + first pass

### Session 51: Landing Page Refresh
- Feature showcase with live-data entry points:
  "Browse 271 photos" | "Explore 46 people" | "View family tree"
- Use FastHTML live-data preview components (auto-updating, no screenshots to maintain)
- Mobile-first design
- CLAUDE.md rule: landing page data must be dynamic, never hardcoded counts

### Session 52+: Concurrent ML Track
- Similarity calibration on frozen embeddings (rhodesli_ml/ only)
- Active learning analysis: which unconfirmed faces would maximize ground truth?
- Runs in rhodesli_ml/ — does NOT touch app/ or data/
- Can run overnight in parallel with app work

---

## Execution Phases

### Phase A: Stabilization — COMPLETE (2026-02-08)
All 8 bugs fixed. 103+ new tests. Event delegation pattern established.

### Phase B: Share-Ready Polish — MOSTLY COMPLETE (2026-02-06 to 2026-02-18)
Landing page, search, mobile, sync, photo viewer, timeline, compare, sharing, year estimation.
Remaining: OPS-001 (branded email).

### Phase C: Annotation Engine — COMPLETE (2026-02-10 to 2026-02-13)
Photo/identity annotations, merge safety, GEDCOM, suggestion lifecycle.

### Phase D: ML Feedback & Intelligence — MOSTLY COMPLETE (2026-02-09 to 2026-02-14)
Threshold calibration, golden set, date estimation pipeline. Remaining: ML-051-053, FE-040-043.

### Phase E: Collaboration & Growth — IN PROGRESS
Contributor roles done. Remaining: Help Identify mode, upload moderation, notifications.

### Phase F: Scale & Generalize — FUTURE
PostgreSQL migration, CI/CD, model evaluation, multi-tenant.

### Harness Engineering — BACKLOG
- [ ] HARNESS-001: Evaluate Ralph Wiggum for overnight runs after 3+ sessions with verification gate (see HD-001)
- [ ] HARNESS-002: Consider native Tasks system for sessions with independent phases (see HD-001)
- [ ] HARNESS-003: Build session log analyzer script for docs/session_logs/*.md patterns (see HD-005)

---

## Sub-Files

| File | Content |
|------|---------|
| [docs/backlog/COMPLETED_SESSIONS.md](backlog/COMPLETED_SESSIONS.md) | All completed session history (Sessions 1-46) |
| [docs/backlog/FEATURE_MATRIX_FRONTEND.md](backlog/FEATURE_MATRIX_FRONTEND.md) | Bugs + Front-End/UX items (Sections 1-2) |
| [docs/backlog/FEATURE_MATRIX_BACKEND.md](backlog/FEATURE_MATRIX_BACKEND.md) | Backend + ML + Annotations + Infra (Sections 3-6) |
| [docs/backlog/FEATURE_MATRIX_OPS.md](backlog/FEATURE_MATRIX_OPS.md) | Testing + Docs + Roles + Vision (Sections 7-10) |
