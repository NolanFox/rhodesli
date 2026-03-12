# Session 100 Person/Photo Conflict Context Follow-Up

## Summary
- **Slice:** disputed person-photo context trust follow-up
- **Goal:** stop person pages and context-linked photo pages from presenting
  disputed face assignments as clean truths.

## Triggered By
- user dogfooding across Rhodes and Fox Family
- live examples where the selected person route implied certainty, but the
  underlying photo had overlapping or conflicting face assignments
- specific trust-breaking cases around Jacob Cohen / Jacob Franco / Rica Revah
  style flows where the gallery implied a clean match while the photo context
  remained disputed

## Files
- [app/person_routes.py](/Users/nolanfox/rhodesli/app/person_routes.py)
- [app/page_routes.py](/Users/nolanfox/rhodesli/app/page_routes.py)
- [tests/test_public_person_page.py](/Users/nolanfox/rhodesli/tests/test_public_person_page.py)
- [tests/test_public_photo_viewer.py](/Users/nolanfox/rhodesli/tests/test_public_photo_viewer.py)

## What Changed
- added bbox-overlap conflict detection for person-photo context in
  [app/person_routes.py](/Users/nolanfox/rhodesli/app/person_routes.py)
- full `/person/{id}` pages now show `Needs review` and
  `Conflicting face assignment` on gallery items whose photo context is
  disputed
- the HTMX person gallery partial now matches the full-page behavior instead of
  hiding the warning state after toggles
- context-linked photo pages now surface a photo-level warning banner when the
  selected person's assignment overlaps another face or is already in a
  disputed state

## Why This Slice Exists
- the earlier Session 100 work improved route continuity and speed loops, but
  it still let a person-first navigation flow overstate certainty
- that was exactly the kind of trust failure the user called out: if the app
  says "this is Jacob Cohen" and the underlying photo is conflicted, the UI
  must say so immediately

## Verification
- `python3 -m py_compile app/person_routes.py app/page_routes.py`
- `pytest tests/test_public_person_page.py tests/test_public_photo_viewer.py -x -q`
  - `60 passed, 2 skipped`
- `pytest tests/test_public_person_page.py tests/test_public_photo_viewer.py tests/test_identify.py tests/test_photo_navigation.py tests/test_collections.py tests/test_inline_find_similar.py tests/test_find_similar_page.py -x -q`
  - `180 passed, 2 skipped`

## Attribution
- **User:** surfaced the real trust-breaking workflows and screenshots
- **Antigravity:** no direct implementation in this bounded slice
- **Codex:** conflict-detection implementation, regression tests, and audit
  trail

## Notes
- [data/identities.json](/Users/nolanfox/rhodesli/data/identities.json) stays
  locally dirty from live app usage and remains out of scope for this slice.
