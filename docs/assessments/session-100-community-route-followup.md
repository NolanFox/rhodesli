# Session 100 Community Route Follow-Up

## Scope
- Preserve community context across public/share surfaces that still leaked into
  root Rhodes routes during live dogfooding.
- Keep the fix narrow: route prefixes, not a new navigation model.

## Trigger
- User kept hitting context drops while moving through Fox Family and Rhodes
  public flows.
- Remaining leaks were concentrated in:
  - `/help` face cards
  - `/identify/{a}/match/{b}` explore links
  - public `/photos` card grids
  - legacy `/api/find-similar/{id}` inline panel

## Codex Changes
- `app/page_routes.py`
  - `/help` face-card identify CTA now uses `nav_prefix`
  - match-confirmation explore links now stay inside the active community
  - legacy `_build_photo_cards()` accepts `nav_prefix`
  - legacy inline similar panel now threads `request -> community_slug -> nav_prefix`
- `app/browse_routes.py`
  - extracted `_build_photo_cards()` accepts `nav_prefix`
  - extracted inline similar panel now keeps person and API links inside the
    active community
- Tests
  - `tests/test_identify.py`
  - `tests/test_inline_find_similar.py`
  - `tests/test_session_82e_features.py`

## Why This Matters
- It directly addresses the trust break where a user starts inside Fox Family
  and lands in root Rhodes/global public routes.
- It reduces “admin/share/community shell drift” without widening scope into a
  broader navigation redesign.

## Verification
```bash
source venv/bin/activate
ruff check app/page_routes.py app/browse_routes.py tests/test_identify.py tests/test_inline_find_similar.py tests/test_session_82e_features.py
pytest tests/test_identify.py tests/test_inline_find_similar.py tests/test_session_82e_features.py tests/test_find_similar_page.py tests/test_collections.py tests/test_public_photo_viewer.py -x -q
```

Result:
- `ruff check ...` passed
- focused pytest gate passed: `124 passed`

## Still Open After This Slice
- richer admin/person-page similar workflow on dedicated person pages
- broader public/community link audit beyond the touched surfaces
- photo trust issues unrelated to route scoping
- clustering quality and batch-review ergonomics

## Attribution
- User: live workflow reports showing where community context still leaked
- Antigravity: earlier critique that community/share boundaries felt brittle
- Codex: scoped implementation, tests, and audit artifacts for this slice
