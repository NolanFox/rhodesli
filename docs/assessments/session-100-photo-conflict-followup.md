# Session 100 Photo Conflict Follow-Up

## Problem
- Live dogfooding surfaced a severe trust failure: one photo could present
  overlapping face assignments as if they were all clean truths.
- Example class: two identities occupying effectively the same face box.

## Change
- `app/page_routes.py`
  - detect high-IoU overlapping face boxes during public photo-page rendering
  - mark those faces as `Conflict` instead of presenting them as unambiguous
  - surface a `Potential tag conflicts detected` banner in the photo people
    section
  - use `Needs review` overlay labeling for conflicting boxes

## Why This Is Safe
- no face/identity data is deleted or rewritten
- no clustering thresholds or merge invariants change
- the UI stops overstating confidence when the rendered evidence is internally
  contradictory

## Verification
```bash
source venv/bin/activate
ruff check app/page_routes.py tests/test_public_photo_viewer.py
pytest tests/test_public_photo_viewer.py tests/test_public_person_page.py tests/test_identify.py -x -q
```

Result:
- `ruff check ...` passed
- focused pytest gate passed: `99 passed, 2 skipped`

## Attribution
- User: reported major confidence loss from mismatched/overlapping face labeling
- Codex: render-time conflict detection and regression coverage
