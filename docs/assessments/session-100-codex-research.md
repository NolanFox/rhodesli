# Session 100 Codex Research

**Date:** 2026-03-11
**Author:** Codex
**Scope:** Multi-community bootstrap, neutral platform entry, workspace UX, and
multi-face face-card patterns for Session 100 planning.

## Repo Facts That Matter

1. Multi-community foundations already exist.
   - `app/main.py` has `CommunityMiddleware` and `community_url_prefix()`.
   - `app/admin_routes.py` already has create/edit community routes.
   - `app/supabase_data.py` already has `create_community()`,
     `get_community_by_slug()`, `add_photo_to_community()`, and
     `add_identity_to_community()`.

2. The biggest remaining product risk is not missing infrastructure.
   - `docs/BACKLOG.md` still flags `COMMUNITY-015`, `COMMUNITY-016`, and
     `COMMUNITY-017` as the concrete blockers to safely operating more than one
     archive.

3. The face-card problem is real and longstanding.
   - `docs/BACKLOG.md` tracks `UX-204`.
   - `docs/assessments/session-82d-assessment.md` explicitly deferred a full
     face-card consistency pass.
   - The current `app/main.py::face_card()` primitive is better than bespoke
     inline markup, but the multi-face presentation still degrades into dense
     micro-thumbnails, tiny actions, and poor hierarchy.

## External Product Signals

1. Workspace choice should be explicit at the platform level.
   - Slack's help docs emphasize switching between workspaces and an "all
     workspaces" view instead of silently dropping users into one space.
   - Notion's help docs distinguish creating a workspace from joining one.
   - Figma's docs keep hierarchy legible: organization -> team -> project ->
     file, which maps well to platform -> community -> collection -> photo.

2. Content context should stay local once chosen.
   - Best-in-class tools do not make users wonder which workspace they are in.
   - They keep switching available, but avoid mixing navigation context and
     content provenance.

3. Carousels are acceptable only when progressive disclosure is necessary.
   - The W3C carousel tutorial and MDN scroll-snap guidance both reinforce the
     same point: make navigation predictable, keyboard-safe, and optional.
   - For Rhodesli, this argues against stuffing many face actions into a tiny
     inline carousel on every card.

4. If a library is needed, it should be tiny and framework-neutral.
   - `keen-slider` and `Swiper Element` are the most plausible fits for
     FastHTML + HTMX.
   - Default should still be CSS `scroll-snap` first, then a small JS helper
     only if mobile/browser verification shows snap-only is not enough.

5. React-first component libraries should be treated as pattern banks, not
   dependencies.
   - Prior Rhodesli research already surfaced `Magic UI` and `21st.dev`.
   - The later Codex audit concluded they are useful as inspiration, but unsafe
     as direct adoption paths because they assume a JS component pipeline and
     can quickly collapse into generic kit-driven UI.

## Translation To Rhodesli

1. `/` should become a neutral platform entry, not implicit Rhodes.
   - Users should explicitly pick Rhodes, Fox Family, or another archive before
     entering archive-scoped upload/browse workflows.

2. Session 100 should be admin-led new-community bootstrap, not full self-serve.
   - The repo already has enough CRUD to let Nolan create new communities.
   - The missing piece is safe routing, scoped links, usable defaults, and a
     polished archive shell.

3. Face cards need a stronger information architecture.
   - One primary face should own the visual weight.
   - Secondary faces should be previewed, not each treated like a full card.
   - Identity-level actions should sit at the identity level, not repeated under
     every tiny thumbnail.

4. Multi-face browsing should use progressive disclosure.
   - Card view: hero face + count badge + short preview strip.
   - Expanded view: scroll-snap strip or lightweight gallery with keyboard and
     touch support.
   - Admin-only actions like detach belong in the expanded gallery or an
     overflow tray, not the always-on tiny footer.

5. Nano Banana is best used as a visual ideation tool, not as direct component
   generation.
   - Prior Antigravity runs produced genuinely useful mockups, but they were too
     generic when the prompts did not force Rhodesli-specific branding, archive
     data, and real user tasks.
   - The right use is: generate targeted mockups for one interaction problem,
     then have Codex translate only the validated parts into repo-safe code.

6. Lens/zoom interactions should be optional and subordinate.
   - Magic UI's `Lens` is a React/shadcn component, so it is not directly
     adoptable here.
   - The interaction pattern is still useful as a reference for inspection.
   - Best Rhodesli use: an optional desktop inspect mode inside an expanded
     gallery or photo modal, not a default treatment on every face card.

## Recommendations For Session 100

1. Start with correctness:
   - `COMMUNITY-015`
   - `COMMUNITY-016`
   - `COMMUNITY-017`

2. Pair that with a launchable admin bootstrap:
   - neutral root
   - polished community landing fallback
   - workspace switcher clarity
   - archive creation runbook

3. Treat face-card unification as a first-class pillar, not polish.
   - Fold `UX-204` into Session 100.
   - Solve multi-face behavior and cross-surface consistency together.

4. Keep self-service onboarding out of this session.
   - `WORKSPACE-001` through `WORKSPACE-006` remain future-facing.
   - Session 100 should make the next family archive workable, not build the
     entire platform-growth motion.

## Sources

- Slack Help Center, workspace switching and all-workspaces patterns:
  https://slack.com/help/articles/1500011360681-Switch-between-workspaces
- Notion Help Center, create/join workspace flows:
  https://www.notion.com/help/create-delete-leave-and-join-workspaces
- Figma best practices, organization/team/project hierarchy:
  https://www.figma.com/best-practices/guide-to-teams-and-projects/
- W3C WAI carousel tutorial:
  https://www.w3.org/WAI/tutorials/carousels/
- MDN CSS scroll snap:
  https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_scroll_snap
- Keen Slider docs:
  https://keen-slider.io/docs
- Swiper docs:
  https://swiperjs.com/get-started
- Magic UI Lens reference:
  https://magicui.design/docs/components/lens
- Prior Rhodesli component-library audit:
  `docs/assessments/pr-7-modern-ui-codex-audit.md`
- Prior Rhodesli Nano Banana audit:
  `docs/assessments/session-82a-eval.md`

## Attribution

- Codex: repo audit, external research synthesis, Session 100 planning
- Antigravity: pending critical review only, not yet performed
