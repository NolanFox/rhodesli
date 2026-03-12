# Session 100 Confirmed-GEDCOM Sweep Follow-Up

**Date:** 2026-03-12  
**Author:** Codex  
**Branch:** `main`

## Purpose

Make the confirmed-people workflow usable for “who still needs a family-tree
link?” instead of forcing the user through a slow person-page drill-down loop.

## Trigger

Rhodes dogfooding exposed three related problems:
1. confirmed people had no GEDCOM-linking filter
2. `Link Tree` on people cards dropped users to a separate page
3. the `#gedcom` anchor on person pages was brittle

## Changes

1. Confirmed people now support a bounded filter set:
   - `All`
   - `Needs Tree`
   - `Linked`
2. The confirmed header subtitle now reflects the active tree-link filter so
   the sweep is legible.
3. Unlinked confirmed admin cards now open the GEDCOM search panel inline via
   the existing expansion slot instead of jumping away to the person page.
4. Person-page GEDCOM sections now expose a real `id="gedcom"` anchor so the
   old deep-link path still lands correctly when used.
5. GEDCOM panels can recover the identity name from the registry when invoked
   without an explicit `name` query parameter.

## Verification

- `ruff check app/main.py app/page_routes.py app/relationship_routes.py tests/test_gedcom_routes.py tests/test_ui_clarity.py`
- `pytest tests/test_gedcom_routes.py tests/test_ui_clarity.py -x -q`
  - `59 passed`

## Remaining Gaps

- This improves the GEDCOM sweep, but it does not yet inline the full tree-link
  workflow for every other surface.
- It does not yet add broader confirmed-people filters beyond GEDCOM status.
- It does not yet resolve the remaining similar/merge and person-photo trust
  complaints.

## Attribution

- User: Rhodes workflow goal, GEDCOM sweep requirement, and direct bug report on
  the awkward `Link Tree` path
- Codex: implementation, regression tests, and artifacting
