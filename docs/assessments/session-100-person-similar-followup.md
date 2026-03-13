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
- `app/browse_routes.py`
  - the real full-page `/people/{id}/similar` route now carries admin review
    context instead of acting like a detached public gallery
  - result cards now show:
    - state badges (`Identified`, `Dismissed`, `Rejected`, `Contested`)
    - merge-blocked explanations such as co-occurrence
    - `Review in Queue` links back into the active workstation section
    - cross-community badges when the candidate belongs to another archive
  - the hero now includes an admin summary for mergeable vs blocked vs
    dismissed/contested candidates
- `tests/test_find_similar_page.py`
  - now asserts the new admin summary and queue-review affordances on the
    full-page route

## Verification
```bash
source venv/bin/activate
python3 -m py_compile app/browse_routes.py app/person_routes.py
pytest tests/test_find_similar_page.py tests/test_inline_find_similar.py tests/test_public_person_page.py -x -q
```

Result:
- `python3 -m py_compile ...` passed
- focused pytest gate passed: `80 passed, 2 skipped`

## User Workflow Impact
- admin users can stay on the person page and open similar-face review inline
- community-scoped person pages keep the similar workflow inside the active
  community
- when a separate full-page similar review is used, it now behaves like an
  admin triage surface instead of a dead-end gallery

## Attribution
- User: reported that person-page `Find Similar` was too hidden and dumped into
  a brittle flow where merge work was not practical
- Codex: inline HTMX implementation, full-page admin-triage follow-up, and
  regression tests
