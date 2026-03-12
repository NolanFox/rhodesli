# Session 100 Person Similar Follow-Up

## Problem
- From an admin person page, `Find Similar` still threw the user into a
  separate public-style flow instead of keeping them in a working review
  context.
- That broke momentum for merge/triage work and matched direct dogfooding
  feedback.

## Change
- `app/person_routes.py`
  - admin `Find Similar` is now an inline HTMX action on the person page
  - results load into `#person-similar-{identity_id}`
- public/non-admin viewers still keep the full-page `/people/{id}/similar`
  route

## Verification
```bash
source venv/bin/activate
ruff check app/person_routes.py tests/test_public_person_page.py
pytest tests/test_public_person_page.py tests/test_find_similar_page.py tests/test_inline_find_similar.py -x -q
```

Result:
- `ruff check ...` passed
- focused pytest gate passed: `77 passed, 2 skipped`

## User Workflow Impact
- admin users can stay on the person page and open similar-face review inline
- community-scoped person pages keep the similar workflow inside the active
  community

## Attribution
- User: reported that person-page `Find Similar` was too hidden and dumped into
  a brittle flow where merge work was not practical
- Codex: inline HTMX implementation + regression tests
