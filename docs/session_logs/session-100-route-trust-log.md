# Session 100 Route Trust Log

## Summary
- **Slice:** community/public route trust follow-up
- **Goal:** stop public/share flows from leaking out of the active archive when
  the user is already operating in a community-scoped context.

## Triggered By
- Fox Family and Rhodes live dogfooding
- user reports that public/community pages still dropped into global Rhodes
  routes in ways that felt confusing and low-trust

## Files
- [app/page_routes.py](/Users/nolanfox/rhodesli/app/page_routes.py)
- [app/browse_routes.py](/Users/nolanfox/rhodesli/app/browse_routes.py)
- [tests/test_identify.py](/Users/nolanfox/rhodesli/tests/test_identify.py)
- [tests/test_inline_find_similar.py](/Users/nolanfox/rhodesli/tests/test_inline_find_similar.py)
- [tests/test_session_82e_features.py](/Users/nolanfox/rhodesli/tests/test_session_82e_features.py)
- [session-100-community-route-followup.md](/Users/nolanfox/rhodesli/docs/assessments/session-100-community-route-followup.md)

## What Changed
- community-scoped `/help` cards now link to community-scoped identify/profile pages
- match-confirmation “Explore the Archive” links now stay inside the current
  community
- public photo-card helpers now accept `nav_prefix`
- legacy inline similar panel now preserves community-scoped person/API links

## Verification
- `ruff check app/page_routes.py app/browse_routes.py tests/test_identify.py tests/test_inline_find_similar.py tests/test_session_82e_features.py`
- `pytest tests/test_identify.py tests/test_inline_find_similar.py tests/test_session_82e_features.py tests/test_find_similar_page.py tests/test_collections.py tests/test_public_photo_viewer.py -x -q`
  - `124 passed`

## Notes
- `data/identities.json` remains dirty from live app usage and stays out of this
  slice.
- This log is a bounded follow-up artifact because
  [session-100-fox-family-hotfix-log.md](/Users/nolanfox/rhodesli/docs/session_logs/session-100-fox-family-hotfix-log.md)
  is already at the harness line limit.

## Person Page Similar Follow-Up
- admin `Find Similar` on public person pages now opens the inline neighbors
  review panel instead of forcing a separate page transition
- community-scoped person pages keep the inline similar target inside the
  active archive
- verification:
  - `ruff check app/person_routes.py tests/test_public_person_page.py`
  - `pytest tests/test_public_person_page.py tests/test_find_similar_page.py tests/test_inline_find_similar.py -x -q`
    - `77 passed, 2 skipped`

## Photo Conflict Follow-Up
- public photo pages now flag overlapping face assignments as `Conflict`
  instead of presenting them as clean truths
- overlapping boxes now render `Needs review` overlays
- a photo-level conflict banner appears when the rendered boxes collide
- verification:
  - `ruff check app/page_routes.py tests/test_public_photo_viewer.py`
  - `pytest tests/test_public_photo_viewer.py tests/test_public_person_page.py tests/test_identify.py -x -q`
    - `99 passed, 2 skipped`

## Community HTMX Follow-Up
- shared workstation/admin helpers were still leaking to root Rhodes after HTMX
  re-renders because they emitted bare `/?section=...`, `/photo/...`,
  `/person/...`, and `/api/...` paths
- `app/main.py` now threads `nav_prefix` through section headers, triage bars,
  mini/expanded cards, skipped focus, neighbors/search panels, rename displays,
  and workstation photos
- `app/identity_routes.py` now preserves `nav_prefix` across focus/skip/merge,
  rename, notes, metadata, rejected, skip-hints, and photo-lightbox re-renders
- workstation photo filter controls and modal navigation now stay inside the
  active archive instead of snapping back to Rhodes
- files:
  - [app/main.py](/Users/nolanfox/rhodesli/app/main.py)
  - [app/identity_routes.py](/Users/nolanfox/rhodesli/app/identity_routes.py)
  - [app/page_routes.py](/Users/nolanfox/rhodesli/app/page_routes.py)
  - [tests/test_sidebar_community.py](/Users/nolanfox/rhodesli/tests/test_sidebar_community.py)
  - [session-100-community-htmx-followup.md](/Users/nolanfox/rhodesli/docs/assessments/session-100-community-htmx-followup.md)
- verification:
  - `python3 -m py_compile app/main.py app/identity_routes.py app/page_routes.py`
  - `pytest tests/test_sidebar_community.py tests/test_public_person_page.py tests/test_inline_find_similar.py tests/test_find_similar_page.py tests/test_skipped_focus.py -x -q`
    - `131 passed, 2 skipped`
  - `pytest tests/test_admin_dashboard.py tests/test_public_photo_viewer.py tests/test_identify.py tests/test_photo_navigation.py tests/test_sequential_identify.py tests/test_collections.py -x -q`
    - `132 passed`

## Person/Photo Conflict Context Follow-Up
- full `/person/{id}` pages and the HTMX gallery partial now agree on disputed
  context instead of hiding it on one surface and showing it on another
- overlapping or disputed person-photo assignments now render `Needs review`
  plus a `Conflicting face assignment` hint on the person gallery item
- context-linked photo pages now show a photo-level warning banner when the
  selected person assignment overlaps another face or is already disputed
- files:
  - [app/person_routes.py](/Users/nolanfox/rhodesli/app/person_routes.py)
  - [app/page_routes.py](/Users/nolanfox/rhodesli/app/page_routes.py)
  - [tests/test_public_person_page.py](/Users/nolanfox/rhodesli/tests/test_public_person_page.py)
  - [tests/test_public_photo_viewer.py](/Users/nolanfox/rhodesli/tests/test_public_photo_viewer.py)
  - [session-100-person-photo-conflict-context-followup.md](/Users/nolanfox/rhodesli/docs/assessments/session-100-person-photo-conflict-context-followup.md)
- verification:
  - `python3 -m py_compile app/person_routes.py app/page_routes.py`
  - `pytest tests/test_public_person_page.py tests/test_public_photo_viewer.py -x -q`
    - `60 passed, 2 skipped`
  - `pytest tests/test_public_person_page.py tests/test_public_photo_viewer.py tests/test_identify.py tests/test_photo_navigation.py tests/test_collections.py tests/test_inline_find_similar.py tests/test_find_similar_page.py -x -q`
    - `180 passed, 2 skipped`
