# Session 98B Assessment

**Date:** 2026-03-12  
**Branch:** `codex/gedcom-search-hotfix`  
**Primary artifact:** `docs/assessments/session-98b-gedcom-search-hotfix.json`

## Scope

Investigate the post-Session-98 production regression reported on the GEDCOM
linking flow:
- person-page GEDCOM panel taking about a minute to populate
- duplicate-looking GEDCOM search rows
- general slowness while the long GEDCOM search request was in flight

## Root Cause

Two issues were confirmed.

1. `app/relationship_routes.py::_load_gedcom_individuals()` was changed to load
   the full rich GEDCOM mirror in request-path code.
   - Production now has `21,944` current GEDCOM individuals.
   - The loader pages in `1,000` rows at a time.
   - The rich current-view query measured about `2.282s` per page.
   - That makes the cold admin search path minute-scale when it tries to scan
     the full mirror before scoring matches.

2. The GEDCOM link panel auto-fires search on page load.
   - `hx_trigger="input changed delay:300ms, load"` means the slow full scan
     starts as soon as an admin opens the person page.
   - On a single-worker deployment, that long request makes unrelated clicks
     feel broken while it is running.

The duplicate-looking search rows were consistent with the old full-scan path
building results from a broad cached mirror plus a UI that only surfaced a
truncated summary. The hotfix removes the full-scan search path and dedupes by
`gedcom_id` before rendering results.

## Hotfix

Changed in the isolated hotfix worktree:
- `app/relationship_routes.py`
  - added `_load_gedcom_individual()` for exact xref lookups
  - kept bulk GEDCOM loads thin instead of rich
  - changed `_search_gedcom_individuals()` to use a Supabase candidate prefilter
    over thin fields instead of loading the full mirror
  - dedupes search results by `gedcom_id`
- `app/main.py`
  - re-exported `_load_gedcom_individual()` for existing route wiring
- `Dockerfile`
  - restored the explicit runtime ML package copy lines required by the repo's
    deployment/runtime coverage tests
- `tests/test_gedcom_routes.py`
  - added regression coverage for deduped candidate results
  - added coverage that link routes use single-row lookup, not bulk mirror load
  - added coverage that thin-field bulk loads remain in place

## Verification

Focused suites:
- `pytest tests/test_gedcom_routes.py -q` -> `48 passed`
- `pytest tests/test_tree_api.py -q` -> `27 passed`
- `pytest tests/test_sync_api.py::TestDockerfileModuleCoverage -q` -> `10 passed`

Required full suites:
- `pytest tests/ -x -q` -> `4137 passed, 21 skipped`
- `pytest rhodesli_ml/tests/ -x -q` -> `588 passed, 2 skipped`

Real-env timings after patch:
- `load_gedcom_face_links` cold -> `1.444s`
- exact rich GEDCOM row lookup -> `3.206s`
- `search_gedcom_individuals("Solly Galante")` cold -> `2.313s`

Before patch:
- live public `/person/...` cold -> `5.789s`
- live `/api/person/.../gallery?view=faces` cold -> `16.584s`
- rich GEDCOM page fetch (`1,000` rows) -> `2.282s`

The user-linked identity
`a0a845d7-4eca-4255-b741-77ff310dc619` now resolves to GEDCOM
`@I132559748883@`.

## Residual Risk

The full bulk thin GEDCOM mirror load is still expensive on cold start because
it pages across all `21,944` current individuals. That is no longer on the
person-page GEDCOM search/link hot path, but tree-wide routes that still need
the entire mirror remain a separate performance follow-up.

## Verdict

Session 98 introduced a real regression in the GEDCOM admin search path.
Session 98B contains a targeted hotfix that removes the minute-scale search
behavior from the reported workflow, adds regression tests, and preserves a
machine-readable timing artifact for the incident.
