# Session 99 Context: Modern UI Phase 1

Predecessors:
- PR #7 research/scoping trail on `modern-ui-research`
- `docs/assessments/pr-7-modern-ui-antigravity-revision.md`
- `docs/assessments/pr-7-modern-ui-codex-audit.md`
- `docs/session_context/pr-7-modern-ui-codex-context.md`
- `docs/session_logs/pr-7-modern-ui-codex-log.md`

## Goal
Deliver a visibly premium UI/UX leap on three high-impact surfaces without
changing Rhodesli's architecture, data contracts, or route behavior:
- `/` landing page
- `/identify/{id}` public share-ready identify page
- `/?section=...` workstation root

This is not a stack migration and not a whole-site redesign. It is a tightly
bounded Phase 1 implementation intended to prove that Rhodesli can feel curated,
trustworthy, and distinctly human without looking generic or "AI slop."

## User Directives To Preserve
- Keep FastHTML + HTMX + Tailwind CDN. Do not migrate to React/Next.
- Zero regressions. Preserve 100% of existing functionality.
- Do not break tests, DOM contracts, auth behavior, or HTMX flows.
- Make the UI feel "curated" and premium enough that families trust the site
  with their photos.
- Prioritize consistency across repeated primitives, especially face cards,
  metadata blocks, CTA hierarchy, headers, empty states, and public/admin chrome.
- Use parallel execution only if followed by a deliberate final harmonization pass.
- Keep attribution clear across:
  - user orchestration
  - Antigravity-authored research/revision
  - Codex-authored audit/handoff artifacts
  - final implementation work

## Base-Branch Gate
Session 98 wrap-up is still finishing as this context is written.
Do not start Session 99 implementation on a stale base.

Preferred base:
- latest `main` after Session 98 wrap-up is merged
- plus the PR #7 research/scoping docs, ideally already merged

Acceptable fallback:
- `modern-ui-research` updated with the latest `main` once Session 98 wrap-up lands

Unacceptable:
- implementing on a base that is missing either the Session 98 wrap-up or the
  finalized PR #7 scoping artifacts

## Architecture And Design Non-Negotiables
- `HD-022` stands: FastHTML + HTMX + surgical JS only.
- Preserve `DD-001` and `DD-002` as the visual base, not a generic SaaS reset.
- No React, Next.js, Framer Motion, Shadcn migration, or component-kit rewrite.
- No data-model changes.
- Do not touch `data/` directly.
- Do not expand scope into `/photo/{id}`, `/person/{id}`, `/photos`, `/timeline`,
  `/tree`, or `/tools/compare`.

## Existing Design System Anchors
These surfaces are not starting from zero. Preserve and evolve the strongest
existing direction:
- `docs/DESIGN_DECISIONS.md` DD-001: archival aesthetic, Playfair Display,
  museum/editorial tone
- `docs/DESIGN_DECISIONS.md` DD-002: face-card warmth, lighter sepia,
  denser card presentation
- `app/page_routes.py::landing_page` already uses:
  - `.hero-mosaic`
  - `.font-display`
  - warm sepia/amber palette
  - restrained editorial animations
- `app/main.py::face_card` already uses `face-card-archival`
- `app/main.py::section_header` already uses `font-display`
- `app/main.py::sidebar` already uses branded archival typography

The goal is refinement, elevation, and harmonization, not a visual reboot that
forgets these prior decisions.

## In-Scope Surfaces And Repo Facts

### 1. Landing Page `/`
Primary file:
- `app/page_routes.py::landing_page`

Current strengths to preserve:
- hero mosaic and editorial story framing
- anonymous-only landing behavior
- strong archival tone and OG metadata

Repo-backed invariants:
- `.hero-mosaic`
- redirect behavior for logged-in users is controlled by `GET /` route handling
- landing OG tags remain present

Likely tests:
- `tests/test_landing.py`
- `tests/test_app.py`
- `tests/test_og_meta_tags.py`
- `tests/test_ux_fixes_session94.py`
- `tests/test_design_audit.py`

### 2. Public Identify `/identify/{id}`
Primary file:
- `app/page_routes.py::get(person_id, ...)` at `/identify/{person_id}`

Current strengths to preserve:
- direct crowdsource-identification flow
- source photo links/cards
- OG tags and shareability
- admin shortcut back into workstation

Repo-backed invariants:
- hidden `name="person_id"` input
- `name="name"`
- `name="relationship"`
- `hx_post="/api/identify/{person_id}/respond"`
- `og:title` and `og:image`
- `view-source-photo-link`
- `source-photos-section`
- `identify-ai-note`
- `identify-admin-link` for admins

Likely tests:
- `tests/test_identify.py`
- `tests/test_ux_fixes_session92.py`
- `tests/test_ux_fixes_session94.py`
- `tests/test_session83a_gaps.py`
- `tests/test_growth_loop.py`

### 3. Workstation Root `/?section=...`
Primary files:
- `app/page_routes.py::get(section, ...)` for `/`
- `app/main.py::_admin_dashboard_banner`
- `app/main.py::sidebar`
- `app/main.py::section_header`

Current strengths to preserve:
- command-center shell
- clear admin/workstation distinction
- search, upload, section counts, mobile chrome

Repo-backed invariants:
- sidebar anchor navigation (`href="/?section=to_review"`, etc.)
- visible section count badges
- overall command-center shell
- `id="sidebar"`
- `id="admin-dashboard-banner"`
- `id="mobile-header"`

Likely tests:
- `tests/test_admin_dashboard.py`
- `tests/test_ui_clarity.py`
- `tests/test_search.py`
- `tests/test_route_scoping.py`
- `tests/test_app.py`
- `tests/test_design_audit.py`

## Shared Helper Risk Map
These helpers are the key consistency and leakage boundary:
- `app/main.py::face_card`
  - In-scope only via scoped variant or route-local composition
  - Must not be globally restyled
- `app/main.py::section_header`
  - Must not be globally restyled
- `app/main.py::sidebar`
  - Must not be globally restyled
- `app/main.py::_admin_dashboard_banner`
  - Must not be globally restyled
- `app/main.py::_public_nav_links`
  - Must not be globally restyled
  - It is reused across out-of-scope public routes

Safe pattern:
- add scoped variant parameters
- or add route-local composition/CSS that does not leak

Unsafe pattern:
- changing shared helper defaults in a way that silently restyles out-of-scope routes

## Antigravity-Specific Failure Modes To Avoid
- Claiming repo-backed selectors or invariants without verifying them in code/tests
- Reaching for React/Framer/component-library patterns because they are visually convenient
- Spreading changes into out-of-scope routes through shared helper defaults
- Making one-off route styling that looks good in isolation but drifts across surfaces
- Declaring readiness before targeted tests, smoke checks, and screenshots exist

## Verification Expectations
Required final verification:
- `pytest tests/ -x -q`
- `pytest rhodesli_ml/tests/ -x -q`
- smoke checks on:
  - `/`
  - `/?section=to_review`
  - `/identify/unknown-1` or `test-unidentified-1`
- screenshot checkpoints for the same three surfaces

Strong preference:
- run targeted route-specific tests after each track before merging into the final
  harmonization pass
- if a new helper variant is introduced, add focused tests that lock the variant
  boundary down

## Required Session Outputs
- implementation branch and PR for Session 99
- `docs/session_logs/session-99-log.md`
- `docs/assessments/session-99-assessment.md`
- `docs/session_logs/INDEX.md` updated from Planned to Complete when the session closes
- updates to `docs/DESIGN_DECISIONS.md` if new scoped UI contracts are introduced
- updates to `tasks/lessons.md` if new anti-regression lessons are learned

## Attribution Expectations
The Session 99 assessment and PR description should explicitly distinguish:
- research/scoping source: Antigravity PR #7 revision doc
- audit/handoff source: Codex PR #7 audit/context/log artifacts
- implementation source: Session 99 execution branch/PR
- collaborative boundary: user-directed orchestration and cross-agent review
