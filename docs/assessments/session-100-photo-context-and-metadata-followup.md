# Session 100 Photo Context And Metadata Follow-Up

**Date:** 2026-03-12  
**Author:** Codex  
**Branch:** `main`

## Purpose

Close the next trust-breaking Rhodesli gaps found during live dogfooding:
- photo metadata saves that appeared to vanish on refresh
- public/community photo pages leaking back to Rhodes/global routes
- photo-page context that made the currently viewed person hard to follow
- state badges and dense layouts that made identified vs dismissed vs contested
  faces harder to trust

## Trigger

The Rhodes dogfooding pass exposed a cluster of related failures:
1. photo provenance edits looked like silent data loss
2. public/community photo pages still had brittle global links
3. the active person context on photo pages was too easy to lose
4. dismissed/contested faces were not clearly surfaced as states

## Changes

1. Cache-building and metadata helpers now load the canonical photo registry via
   `load_photo_registry()` instead of directly reading stale JSON snapshots in
   Postgres mode.
2. Public/community photo CTAs and footer links now preserve the active
   community prefix instead of dropping users into bare Rhodes/global routes.
3. Photo pages now explicitly highlight the context identity when opened with an
   `identity_id`, including:
   - amber overlay emphasis on the matching face
   - a `Viewing` badge on the matching person card
4. Person cards now surface richer trust states:
   - `Viewing`
   - `Identified`
   - `Dismissed`
   - `Proposed`
   - `Contested`
   - `Unidentified`
5. Dense people grids now use full-card links so the layout is less brittle and
   easier to scan.
6. The photo metadata and face-legend overlays moved to the top corners to stop
   obscuring lower-caption text.

## Verification

- `ruff check app/main.py app/page_routes.py tests/test_photo_registry_fallback.py tests/test_public_photo_viewer.py`
- `pytest tests/test_public_photo_viewer.py tests/test_public_person_page.py tests/test_photo_registry_fallback.py tests/test_photo_provenance.py -x -q`
  - `82 passed, 2 skipped`

## Remaining Gaps

- This does not yet solve the full Rhodes confirmed-people filtering/GEDCOM
  sweep workflow.
- This does not yet prove every reported person -> photo mismatch is fixed.
- This does not yet resolve all community-context leaks on every public route.

## Attribution

- User: Rhodes dogfooding report, exact broken flows, and trust-oriented
  feedback
- Codex: root-cause analysis, implementation, verification, and artifacting
