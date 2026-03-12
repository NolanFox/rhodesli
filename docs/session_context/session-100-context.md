# Session 100 Context

## Mission

Use Session 100 to make Rhodesli ready for the next archive without degrading
trust or correctness:
- safe multi-community bootstrap
- neutral root/platform entry
- fixed multi-face face-card behavior
- stronger trust/onboarding surfaces for public contributors
- better discoverability for archive choice and contribution paths

## What The User Wants Preserved

1. Zero regressions.
2. Clear attribution between user, Codex, Antigravity, and collaborative work.
3. FastHTML + HTMX retained.
4. The site should feel curated and premium, not generic.
5. The work should be auditable and reversible.
6. The result should help adoption, not just visual polish.

## Why This Session Exists

Recent work proved two things:
1. Multi-community support is real, but still not safe enough for wider use.
2. The modern UI work improved trust, but it did not solve the broken multi-face
   face-card experience.

Session 100 should convert the current foundation into a launchable next-archive
operating model.

## In-Scope Backlog Items

- `COMMUNITY-015`
- `COMMUNITY-016`
- `COMMUNITY-017`
- practical slice of `COMMUNITY-002`
- remaining generic-content gap from `COMMUNITY-001`
- `UX-042`
- `UX-121`
- `UX-204`

## Out Of Scope

- full self-service archive creation
- per-community role/product model overhaul
- broad redesign of all routes
- data-model migrations not already required by current community support
- React/Next/component-library migration

## Repo Anchors

Primary files:
- `app/main.py`
- `app/page_routes.py`
- `app/admin_routes.py`
- `app/supabase_data.py`

Primary helpers/routes:
- `CommunityMiddleware`
- `community_url_prefix()`
- `_public_nav_links()`
- `sidebar()`
- `face_card()`
- `_build_face_cards_for_entries()`
- `identity_card()`
- `_community_landing_page()`
- `GET /`
- public identify route
- admin community create/edit routes

## Design Rules

1. Workspace selection belongs at the platform layer, not buried inside archive
   content.
2. Once a user enters a community, navigation should stay local unless a
   cross-community handoff is intentional and labeled.
3. Face cards should emphasize one primary face and one clear action hierarchy.
4. Multi-face preview should use progressive disclosure, not dense action salad.
5. Dense multi-face identities need a grid-capable expanded state, not only a
   horizontal strip.
6. If a gallery library is used, it must be tiny, framework-neutral, and proven
   necessary by browser testing.
7. `21st.dev` / `Magic UI` style libraries are inspiration sources only here.
8. Nano Banana is for narrow Rhodesli-specific mockups, not direct component
   generation.
9. Discoverability matters: new visitors should not need prior Rhodesli context
   to understand where to go or how to help.
10. The neutral root must include a public flagship demo/archive path.

## Ownership Split

### Codex
- architecture and scope control
- community routing and correctness
- face-card system implementation strategy
- tests, verification gates, and artifact discipline

### Antigravity
- critical review of the plan
- browser-first UX critique
- community chooser/workspace-switcher/face-card interaction feedback
- screenshot-backed visual review

### Shared
- final gallery interaction choice
- final harmonization across touched surfaces
- audit-ready attribution

## Verification Expectations

Tests:
- community infra/scoping suites
- identify/public trust suites
- design-audit suites
- full app + ML suites before merge

Browser checks:
- `/`
- `/c/fox-family/`
- `/c/fox-family/?section=to_review`
- `/c/fox-family/?section=confirmed`
- fixture-backed public identify route
- one dense multi-face identity card on desktop and mobile
- one first-run contribution/discoverability walkthrough
- root-entry path to a public archive/demo

## Required Artifacts

- `docs/assessments/session-100-codex-research.md`
- `docs/prds/040_multi_community_bootstrap_and_face_cards.md`
- `docs/session_logs/session-100-planning-log.md`
- Antigravity review artifact after critique

## External Pattern Sources

- Slack workspace switching:
  https://slack.com/help/articles/1500011360681-Switch-between-workspaces
- Notion create/join workspace flows:
  https://www.notion.com/help/create-delete-leave-and-join-workspaces
- Figma organization hierarchy:
  https://www.figma.com/best-practices/guide-to-teams-and-projects/
- W3C carousel accessibility:
  https://www.w3.org/WAI/tutorials/carousels/
- MDN scroll snap:
  https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_scroll_snap
