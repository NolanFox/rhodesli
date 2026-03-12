# PRD-040 / SDD-040: Session 100

**Title:** Multi-Community Bootstrap, Neutral Platform Entry, and Face Card Consistency  
**Status:** Ready for Review  
**Date:** 2026-03-11  
**Authors:** User direction + Codex planning  
**References:** `docs/prds/035_multi_community_platform.md`, `docs/prds/036_workspace_onboarding.md`, `docs/BACKLOG.md`, `docs/assessments/session-100-codex-research.md`, `docs/assessments/session-100-antigravity-plan-review.md`

## Goal
Make it safe and practical to launch another family archive while fixing the
broken multi-face card experience that currently undermines trust and workflow
clarity.

Session 100 should produce four outcomes:
1. Rhodesli can support a new archive without silently routing users into the
   Rhodes context.
2. Community-scoped navigation and content feel reliable across public and admin
   surfaces.
3. Face cards become a real shared system, with a usable multi-face pattern
   instead of cramped, repeated mini-cards.
4. First-time visitors can understand what Rhodesli is, choose the right
   archive, and find a clear contribution path without admin handholding.

## Why Now
1. The user wants to start using additional family archives soon.
2. Current multi-community support is close, but not safe enough to scale:
   `COMMUNITY-015`, `COMMUNITY-016`, and `COMMUNITY-017` remain open.
3. The current face-card system is visually and structurally weak for
   multi-face identities, and the Fox Family screenshot confirms it is now
   product-facing, not just technical debt.

## Non-Goals
1. No full self-service archive creation in Session 100.
2. No role-model overhaul or community-membership productization yet.
3. No React/Next/component-library migration.
4. No broad redesign of every route.
5. No data-model churn beyond what already exists in the current community
   tables and helpers.

## Product Decisions
1. `/` becomes a neutral platform entry.
   - No more silent Rhodes default for anonymous users.
   - It must explain the platform and include a clear public flagship demo path.

2. Session 100 is admin-led community bootstrap.
   - New archives are still created/administered by Nolan or another admin.
   - Self-service onboarding remains deferred to PRD-036 follow-up work.

3. Community context must survive every internal route handoff.
   - Photo, person, identify, workstation, and admin flows keep the active
     community unless a cross-community handoff is intentional and labeled.

4. Face cards become a single shared system with explicit modes.
   - `summary`: primary face + count badge + compact metadata
   - `gallery`: expanded multi-face view with stable actions
   - `public`: share-safe, trust-oriented presentation
   - `workstation`: denser admin mode with review actions

5. Multi-face identities use progressive disclosure, not thumbnail clutter.
   - Default card: hero face + `Faces (N)` + 2-3 preview faces
   - Expanded state: strip or gallery for small sets, grid fallback for dense
     sets
   - Admin actions move to the expanded state or identity-level action row

6. Library policy for the face gallery is conservative.
   - First choice: CSS `scroll-snap` + tiny vanilla JS only where needed.
   - Escalation path: `keen-slider` or `Swiper Element` only if browser testing
     shows snap-only is materially insufficient.

7. `21st.dev`, `Magic UI`, and similar libraries are inspiration-only here.
   - They can inform composition, motion, or layout references.
   - They are not drop-in dependencies for Rhodesli.

8. Nano Banana can support design exploration, but only with strict prompts.
   - One narrow interaction at a time.
   - Must include Rhodesli branding, real archive context, and the exact
     workflow problem.
   - Mockups are evidence for direction, not implementation artifacts.

9. Zoom/lens behavior is optional, not the core fix.
   - The core fix is larger primary crops, better hierarchy, density-aware
     gallery behavior, and easy source-photo context.
   - If lens-style inspection exists, it lives in the expanded state or photo
     modal, not on every face card by default.

## Session 100 Scope

### Pillar A: Community Bootstrap Hardening
Backlog:
- `COMMUNITY-015`
- `COMMUNITY-016`
- `COMMUNITY-017`
- practical slice of `COMMUNITY-002`

Outcome:
- A new archive can be created, browsed, and shared without leaking back into
  Rhodes routes.

Focus:
- community-prefixed internal links
- neutral root behavior
- archive selection and context persistence
- proposals/content parity

### Pillar B: Community Shell and Trust Surfaces
Backlog:
- remaining generic-content gap from `COMMUNITY-001`
- `UX-042`
- `UX-121`

Outcome:
- A new archive looks intentional on day one and gives contributors a clear
  next step.

Focus:
- generic community landing/about fallback
- public flagship demo path from `/`
- clearer identify-page source-photo context
- contribution/help guidance that is not Rhodes-specific
- a visible contribution widget on community landing pages

### Pillar C: Face Card System and Multi-Face Repair
Backlog:
- `UX-204`
- the multi-face card failure shown in the Fox Family screenshot

Outcome:
- Multi-face identities are understandable and usable on both desktop and
  mobile.

Focus:
- shared `face_card()` contract
- identity-level card shell
- preview strip for small sets
- grid fallback for dense sets
- action hierarchy that does not collapse into tiny repeated links
- source-photo context and inspect path in the expanded state

## Repo Touch Map

### Codex-Led Core Files
- `app/main.py`
  - `community_url_prefix()`
  - `_public_nav_links()`
  - `sidebar()`
  - `face_card()`
  - `_build_face_cards_for_entries()`
  - `_face_pagination_controls()`
  - `identity_card()`
- `app/page_routes.py`
  - `_community_landing_page()`
  - `GET /`
  - public identify route
  - route-local links that still leak bare `/photo/...` or `/person/...`
- `app/admin_routes.py`
  - community create/edit flows
- `app/supabase_data.py`
  - existing community CRUD only as needed for safe bootstrap behavior

### Antigravity-Led UX Surfaces
- neutral root / community chooser composition
- workspace switcher visual behavior
- community landing and help/contribute shells
- face-card multi-face interaction model and browser-verified presentation
- optional Nano Banana mockups for the expanded gallery and neutral community
  chooser, provided they stay Rhodesli-specific

### Shared Verification Surface
- `/`
- `/c/fox-family/`
- `/c/fox-family/?section=confirmed`
- `/c/fox-family/?section=to_review`
- `/c/fox-family/identify/{id}` or fixture-backed equivalent

## Ownership Split

### Codex-Owned
1. Route correctness and scope control
2. Community prefix audit and fixes
3. Neutral-root architecture and safe default behavior
4. `COMMUNITY-016` API/content parity
5. Face-card system extraction and shared-helper discipline
6. Regression tests and final merge-quality verification

### Antigravity-Owned
1. Critical review before implementation
2. Browser-first UX critique on community chooser, workspace switcher, and
   community landing
3. Face-card interaction and multi-face presentation critique
4. Visual system proposals for trust and clarity on public community surfaces
5. Browser verification and screenshot audit once implementation exists

### Shared
1. Final decision on strip vs grid thresholds
2. Final harmonization of public/admin community chrome
3. Screenshot evidence and route-by-route verification
4. Clear attribution artifacts for later audit

## Execution Order

### Act 0: Preflight And Baseline
1. Capture live/browser evidence for current Fox Family and Rhodes flows.
2. Log the specific community-link failures and face-card pain points.
3. Freeze the in-scope routes and shared helpers.

### Act 1: Community Correctness
1. Fix `COMMUNITY-015`.
2. Fix `COMMUNITY-016`.
3. Add tests that prove community context survives internal links and content
   loads.

### Act 2: Neutral Platform Entry
1. Rework `/` so anonymous users are not silently placed into Rhodes.
2. Add an archive chooser / platform shell that preserves Rhodes as a public
   flagship demo destination.
3. Keep logged-in admin workstation behavior explicit and tested.

### Act 3: Community Shell
1. Finish the practical workspace switcher slice.
2. Add generic community copy fallbacks so a new archive does not inherit Rhodes
   prose.
3. Add an active contribution CTA on community landing pages.
4. Tighten identify/contribute trust surfaces.
5. Remove dead ends in the first-run public path.

### Act 4: Face Card System
1. Define the shared face-card contract and mode system.
2. Refactor the worst multi-face admin/public card paths onto that contract.
3. Implement preview-strip plus expanded-gallery behavior with a grid fallback
   for dense identities.
4. Keep out-of-scope routes on the old path until explicitly migrated, unless a
   safe shared primitive can be adopted without leakage.
5. Ensure the expanded state exposes source-photo context and an inspect path
   without turning the base card into a gadget.

### Act 5: Harmonization And Verification
1. Browser-verify Fox Family, Rhodes, and root entry points.
2. Verify mobile behavior for multi-face cards.
3. Confirm no route regression in admin workflows or public share flows.
4. Explicitly test first-run discoverability:
   - Can a new visitor pick the right archive?
   - Can a new contributor find how to help?
   - Can a new admin understand how to launch the next archive?
   - Is the root materially better than a blank neutral lobby?

## Verification Gates

Required tests before merge:
- `pytest tests/test_community_infra.py -q`
- `pytest tests/test_community_scoping.py -q`
- `pytest tests/test_identify.py -q`
- `pytest tests/test_ux_fixes_session94.py -q`
- `pytest tests/test_design_audit.py -q`
- `pytest tests/test_admin_dashboard.py -q`
- `pytest tests/ -x -q`
- `pytest rhodesli_ml/tests/ -x -q`

Required browser checks:
- neutral `/` entry
- Fox Family public landing
- Fox Family workstation navigation
- identify page source-photo path
- multi-face card behavior on desktop and mobile

Required artifacts:
- `docs/session_logs/session-100-log.md`
- before/after screenshots for root, Fox landing, workstation, identify, and at
  least one multi-face card
- explicit attribution ledger

## Success Criteria
1. Nolan can create or use another community without Rhodes-context leakage.
2. Anonymous users can understand the platform before entering an archive.
3. Community-specific pages no longer feel like Rhodes with a different slug.
4. Multi-face identities no longer render as cramped stacks of tiny cards with
   duplicated actions.
5. The final implementation stays FastHTML + HTMX, regression-safe, and easy
   for Claude to audit by contribution source.
6. Adoption is easier because archive choice, contribution pathways, and public
   trust cues are more discoverable.
7. Dense group-photo identities remain usable because the expanded gallery can
   switch from strip to grid and retains source-photo context.

## Deferred Until After Session 100
1. Personal archive auto-creation (`WORKSPACE-001`)
2. Full self-service uploads and community memberships
3. Per-community permissions overhaul
4. Full-site face-card migration across every route
5. Wider growth work like public community directory and anonymous contribution
   accounts

## Attribution Plan
- User: product direction, scope priorities, success bar
- Codex: research, repo-grounded plan, correctness architecture, test strategy
- Antigravity: critical review, visual/interaction critique, browser evidence
- Collaborative boundary: implementation decisions documented in the session log
  and review artifacts
