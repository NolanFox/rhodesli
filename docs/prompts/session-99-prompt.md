# Session 99 Prompt: Modern UI Phase 1

Context: `docs/session_context/session-99-context.md`
Design source: `docs/assessments/pr-7-modern-ui-antigravity-revision.md`
Audit source: `docs/assessments/pr-7-modern-ui-codex-audit.md`

## Mission
Deliver a substantial UI/UX upgrade on three surfaces only:
- `/` landing page
- `/identify/{id}` public share-ready page
- `/?section=...` workstation root

The result should feel premium, curated, and trustworthy without looking like
generic AI SaaS. This is a FastHTML + HTMX implementation, not a stack change.

## Before You Touch Code
Read these files carefully:
- `docs/session_context/session-99-context.md`
- `docs/assessments/pr-7-modern-ui-antigravity-revision.md`
- `docs/assessments/pr-7-modern-ui-codex-audit.md`
- `docs/session_context/pr-7-modern-ui-codex-context.md`
- `docs/session_logs/pr-7-modern-ui-codex-log.md`
- `docs/DESIGN_DECISIONS.md`
- `tasks/lessons.md`

## Hard Gate: Stable Base Required
Session 98 wrap-up is still finishing.

Do not start implementation on a stale base.
PR #7 (`modern-ui-research`) remains research/scoping only.
Do not add Session 99 implementation commits to that branch.

Preferred base:
- latest `main` after Session 98 wrap-up is merged
- plus the PR #7 docs already present

Fallback:
- `modern-ui-research` updated with latest `main` after Session 98 wrap-up,
  then a fresh Session 99 implementation branch created from that updated branch

If you cannot verify a stable base that includes both:
- Session 98 wrap-up
- finalized PR #7 docs

Then:
- create `docs/session_logs/session-99-log.md`
- record that Session 99 is blocked on base-branch readiness
- do not implement code yet
- comment on the PR/branch state if needed
- stop

## Antigravity Guardrails
- Stay on FastHTML + HTMX + Tailwind CDN. No React/Next migration.
- No Framer Motion, no component-library swap, no architecture detours.
- No data-model changes.
- Do not touch `data/`.
- Do not expand scope into `/photo/{id}`, `/person/{id}`, `/photos`, `/timeline`,
  `/tree`, or `/tools/compare`.
- Every claim that something is "repo-backed" must be verified in code/tests first.
- Do not declare readiness until tests, smoke checks, and screenshots exist.
- Do not globally restyle shared helpers used by out-of-scope routes.

## Branch And Artifact Setup
1. Create a fresh implementation branch from the stable base.
   Recommended name: `session-99/modern-ui-phase-1`
   Never implement directly on `modern-ui-research`.
2. Set the current session to `99` if your workflow uses that convention.
3. Create `docs/session_logs/session-99-log.md` at the start with:
   - phase checklist
   - branch/base SHA
   - attribution ledger
   - exact files/functions touched
   - test and screenshot evidence as you go

## What "Good" Looks Like
- The site should feel like a carefully art-directed heritage product, not a
  startup template.
- The visual language should feel human, editorial, and specific to Rhodesli.
- Motion should be restrained and meaningful.
- Trust should increase, especially on the public identify page.
- Workstation chrome should feel more deliberate and premium without becoming flashy.
- Repeated primitives should feel unified across touched surfaces.

## Common Failure Modes: Do Not Do These
- Do not invent selectors, invariants, or tests.
- Do not rewrite large parts of shared helpers unless scoped variants are added.
- Do not produce three unrelated route-level redesigns with no final sync pass.
- Do not spread "premium" styling into out-of-scope routes by changing helper defaults.
- Do not ship mostly-cosmetic changes if they raise regression risk.
- Do not treat PR #7 as the implementation PR. Open a separate Session 99 implementation PR.

## Execution Plan

### Act 0: Preflight
1. Verify the stable base condition above.
2. Run `git status` and `git log --oneline -10`.
3. Record the chosen base and why in `docs/session_logs/session-99-log.md`.
4. Verify the real code touch points from the context file before planning edits.

### Act 1: Shared Scaffolding (Sequential, Main Thread)
Build the minimum scoped variant system needed for consistency across the three
in-scope surfaces.

Target files to evaluate:
- `app/page_routes.py::landing_page`
- `app/page_routes.py::get(person_id, ...)` for `/identify/{id}`
- `app/page_routes.py::get(section, ...)` for workstation root
- `app/main.py::_admin_dashboard_banner`
- `app/main.py::sidebar`
- `app/main.py::section_header`
- `app/main.py::face_card`
- `app/main.py::_public_nav_links`

Rules:
- Shared helpers used by out-of-scope routes must get scoped variants or route-local composition.
- Do not globally restyle helper defaults.
- Keep the scaffolding small and intentional.
- Prefer explicit namespaces or wrapper classes such as `ui99-landing-*`,
  `ui99-identify-*`, and `ui99-workstation-*` to reduce leakage risk.
- If a new shared primitive is needed, prefer a Session 99-only wrapper/helper
  over mutating a global default.

Commit after this act.

### Act 2: Track A — Landing Page
Upgrade `/` so it looks obviously more premium while preserving:
- hero mosaic
- anonymous-only landing behavior
- major CTA destinations
- OG tags

Aim for:
- stronger typography hierarchy
- better pacing and spacing
- richer editorial composition
- trust and emotional weight
- motion restraint

Likely files:
- `app/page_routes.py`
- any minimal scoped CSS/variant support introduced in Act 1

Likely targeted tests:
- `tests/test_landing.py`
- `tests/test_app.py`
- `tests/test_og_meta_tags.py`
- `tests/test_ux_fixes_session94.py`
- `tests/test_design_audit.py`

Commit after this track.

### Act 3: Track B — Public Identify Page
Upgrade `/identify/{id}` so it feels premium, tactile, and trustworthy while preserving:
- hidden `name="person_id"` input
- `name="name"`
- `name="relationship"`
- `hx_post="/api/identify/{person_id}/respond"`
- source photo cards/links
- shareability and OG tags
- admin shortcut back to workstation

Aim for:
- higher trust for family contributors
- clearer action hierarchy
- better visual connection to the landing page
- no loss of share-ready clarity

Likely files:
- `app/page_routes.py`
- possibly scoped helper support from Act 1

Likely targeted tests:
- `tests/test_identify.py`
- `tests/test_ux_fixes_session92.py`
- `tests/test_ux_fixes_session94.py`
- `tests/test_session83a_gaps.py`
- `tests/test_growth_loop.py`

Commit after this track.

### Act 4: Track C — Workstation Root
Upgrade `/?section=...` chrome only. Do not redesign deep queue logic.

Preserve:
- sidebar anchor navigation
- visible count badges
- search
- upload entry point
- mobile header
- dashboard banner
- section-header view toggles

Aim for:
- denser, more deliberate admin/workbench feel
- stronger visual hierarchy
- consistent typography and spacing
- better premium feel without slowing down work

Likely files:
- `app/page_routes.py`
- `app/main.py`

Likely targeted tests:
- `tests/test_admin_dashboard.py`
- `tests/test_ui_clarity.py`
- `tests/test_search.py`
- `tests/test_route_scoping.py`
- `tests/test_app.py`
- `tests/test_design_audit.py`

Commit after this track.

### Act 5: Track D — Final Harmonization (Sequential, Main Thread)
This is mandatory.

Before final commit:
- compare the touched surfaces side by side
- reconcile repeated primitives
- remove route-level one-offs where a scoped shared primitive is more correct
- ensure public/admin chrome remain distinct but related
- ensure the landing page and identify page clearly belong to the same product
- ensure workstation chrome feels like the same brand in a denser mode

If a helper change would leak into out-of-scope routes, back it out and use a
scoped variant instead.

Commit after harmonization.

### Act 6: Verification, Docs, And PR
Run targeted tests after each act where practical.

Before opening or updating the PR, all of this must be done:
- `pytest tests/ -x -q`
- `pytest rhodesli_ml/tests/ -x -q`
- smoke check `/`
- smoke check `/?section=to_review`
- smoke check `/identify/unknown-1` or `test-unidentified-1`
- capture screenshots for those three surfaces

Minimum smoke-check assertions:
- `/` still renders `.hero-mosaic`
- `/identify/{id}` still renders `name="person_id"` and the identify response post target
- `/?section=to_review` still renders the workstation shell with sidebar navigation

Write:
- `docs/assessments/session-99-assessment.md`

The assessment must include:
- what changed
- exact files/functions touched
- what was Antigravity-authored in implementation
- what design/scoping source came from PR #7
- what audit/handoff source came from Codex artifacts
- targeted test evidence
- full-suite evidence
- screenshot evidence
- remaining risks / follow-ups

If you introduce durable shared variant contracts, update:
- `docs/DESIGN_DECISIONS.md`

If you learn a new anti-regression lesson, update:
- `tasks/lessons.md`

Close the harness loop:
- update `docs/session_logs/INDEX.md`
- mark Session 99 complete with links to the session log and assessment
- make sure the final PR description points to the Session 99 artifacts

Open or update the Session 99 implementation PR with:
- a clear summary
- screenshot set
- explicit link back to PR #7 as the research/scoping source
- explicit attribution boundaries
- explicit note that PR #7 remained research-only and implementation occurred in Session 99

## Parallelization Guidance
You may parallelize Tracks A, B, and C only after Act 1 is complete.

If you do parallelize:
- each track must work from the same scaffolding commit
- each track handoff must list exact files changed
- each track must run its targeted tests before merge
- the main thread must perform Track D harmonization afterward

Do not let subagents invent shared helper contracts independently.

## Acceptance Criteria
- [ ] Stable base chosen after Session 98 wrap-up
- [ ] In-scope surfaces only: `/`, `/identify/{id}`, `/?section=...`
- [ ] No out-of-scope helper leakage
- [ ] Design direction feels premium and Rhodesli-specific, not generic AI SaaS
- [ ] Repeated primitives are harmonized across touched surfaces
- [ ] Both test suites pass
- [ ] Smoke checks completed
- [ ] Screenshots captured
- [ ] Session log and assessment written
- [ ] Session index updated
- [ ] Attribution boundaries remain explicit
