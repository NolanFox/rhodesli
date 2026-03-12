# Session 100 Community HTMX Follow-Up

**Date:** 2026-03-12  
**Author:** Codex

## Purpose
Document the Session 100 continuation slice that fixed community-context leaks
inside shared workstation/admin HTMX helpers after live dogfooding showed that
Fox Family and Rhodes flows still snapped back to root Rhodes routes.

## Trigger
- User feedback showed that community-scoped cards and panels could still drop
  into root Rhodes when rendered from:
  - New Matches / browse and focus flows
  - skipped focus flows
  - inline similar / neighbors panels
  - rename, notes, metadata, and other HTMX re-renders
  - workstation photo grids
- Root cause: several shared helpers still emitted bare `/?section=...`,
  `/photo/...`, `/person/...`, and `/api/...` paths even when the parent page
  was community-scoped.

## Implemented
1. Shared workstation helpers now accept and honor `nav_prefix`.
   - `section_header()`
   - `identity_card_mini()`
   - `identity_card_expanded()`
   - `_build_triage_bar()`
   - `neighbors_sidebar()`
   - `search_results_panel()`
   - `manual_search_section()`
   - `name_display()`
   - skipped-focus helper stack

2. Identity HTMX routes now preserve community context on re-render.
   - focus/skip/merge flows now thread `request -> nav_prefix`
   - rename, notes, metadata, rejected, skip-hints, and photo-lightbox helpers
     now return community-scoped links instead of root links

3. Workstation Photos now stay archive-scoped.
   - `render_photos_section()` accepts `nav_prefix`
   - collection/source/media/sort filter controls keep the active archive
   - modal partial navigation stays inside the current archive
   - photo-card public links/shares use archive-scoped URLs

## Why This Matters
- It addresses a direct trust break: a user can start inside Fox Family and stay
  there while confirming, skipping, renaming, opening similar panels, or moving
  through workstation photos.
- It reduces a class of “first click works, second click leaks to Rhodes”
  regressions that were caused by HTMX re-render helpers, not top-level routes.

## Verification
```bash
python3 -m py_compile app/main.py app/identity_routes.py app/page_routes.py
source venv/bin/activate
pytest tests/test_sidebar_community.py tests/test_public_person_page.py tests/test_inline_find_similar.py tests/test_find_similar_page.py tests/test_skipped_focus.py -x -q
pytest tests/test_admin_dashboard.py tests/test_public_photo_viewer.py tests/test_identify.py tests/test_photo_navigation.py tests/test_sequential_identify.py tests/test_collections.py -x -q
```

Result:
- `py_compile` passed
- focused community gate passed: `131 passed, 2 skipped`
- broader shared-helper gate passed: `132 passed`

## Boundaries
- This slice does **not** claim to finish all Session 100 workflow/product work.
- It specifically hardens community-scoped helper output and photo-grid routing.
- `data/identities.json` remained dirty from live app usage and was not touched.

## Attribution
- User: live Rhodes/Fox workflow reports showing that community trust still
  broke after card resets and inline actions.
- Antigravity: no direct implementation role in this bounded slice.
- Codex: helper-level path audit, implementation, regression tests, and this
  artifact.
