# Session 100 Usability Follow-Up

**Date:** 2026-03-12  
**Author:** Codex  
**Branch:** `codex/session-100-usability-followup`

## Purpose

Close the remaining gap between the merged Session 100 speed-loop mechanics and
the real Fox Family workflow entry points.

## Trigger

Antigravity's live review attempt ran out of quota before a full browser pass,
but it surfaced the key remaining issue correctly: the speed loop existed, yet
the most common entry path still made it hard to discover or activate.

## Findings

- The standalone public photo page still exposed a `Name These Faces` CTA that
  targeted `#photo-modal-content`, which only exists in modal contexts.
- The person gallery did not provide a first-class way to jump directly into
  the next unresolved photo for a given person.
- This made the Fox Family workflow feel slower than the underlying Session 100
  mechanics actually were.

## Changes

1. Standalone photo pages now support `?seq=1` for admins and render a real
   full-page speed-loop shell.
2. The full-page speed-loop shell now provides its own `#photo-modal-content`
   container so existing HTMX actions keep working outside modal contexts.
3. Public photo pages now advertise the faster path as
   `Start Speed Loop (...)` instead of routing to a modal-only target.
4. Person galleries now surface a direct `Start Speed Loop` CTA that opens the
   first unresolved photo in the person's ordered gallery context.

## Verification

- `ruff check app/page_routes.py app/photo_routes.py app/person_routes.py tests/test_sequential_identify.py tests/test_public_person_page.py tests/test_public_photo_viewer.py`
- `pytest tests/test_sequential_identify.py tests/test_public_person_page.py tests/test_public_photo_viewer.py -x -q`
  - `73 passed, 2 skipped`

## Attribution

- User: real Fox Family workflow pain points and the requirement that tagging
  become operationally fast
- Antigravity: partial live-review signal that the speed loop was still too
  hidden from the main workflow
- Codex: root-cause analysis, route/CTA fixes, and verification
