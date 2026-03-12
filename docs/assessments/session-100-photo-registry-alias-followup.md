# Session 100 Photo Registry Alias Follow-Up

## Summary
- **Slice:** photo provenance edit reliability
- **Goal:** make `Collection`, `Source`, and `Source URL` edits persist for
  photos that are viewable by cache/SHA IDs but stored in the editable registry
  under a different canonical ID.

## Triggered By
- user report that photo metadata saves appeared to do nothing and then
  disappeared on refresh
- concrete examples on Fox Family and Rhodes photo pages
- Codex verification that `get_photo_metadata(photo_id)` returned real data for
  user-reported photos while `load_photo_registry().get_photo_path(photo_id)`
  returned `None` for the same IDs

## Root Cause
- the viewer can render some photos by SHA/cache IDs from
  [app/main.py](/Users/nolanfox/rhodesli/app/main.py)'s photo cache
- the editable routes were still checking only the raw
  [PhotoRegistry](/Users/nolanfox/rhodesli/core/photo_registry.py) key
- when those IDs diverged, the photo page loaded but the edit routes treated the
  photo as missing, which matched the user's "silent save" symptom
- the bug was duplicated because the save routes exist in both
  [app/page_routes.py](/Users/nolanfox/rhodesli/app/page_routes.py) and
  [app/photo_routes.py](/Users/nolanfox/rhodesli/app/photo_routes.py)

## Files
- [app/main.py](/Users/nolanfox/rhodesli/app/main.py)
- [app/page_routes.py](/Users/nolanfox/rhodesli/app/page_routes.py)
- [app/photo_routes.py](/Users/nolanfox/rhodesli/app/photo_routes.py)
- [tests/test_photo_provenance.py](/Users/nolanfox/rhodesli/tests/test_photo_provenance.py)

## What Changed
- added `resolve_photo_registry_photo_id()` to bridge viewer/cache IDs back to
  the canonical editable registry ID using direct lookup, alias reversal, and
  filename fallback
- updated collection/source/source-url save routes to use the resolved registry
  ID instead of assuming the viewer ID is editable directly
- covered the regression with a route test that uses a cache-style photo ID and
  the user-provided Facebook post URL shape

## Verification
- `python3 -m py_compile app/main.py app/page_routes.py`
- `pytest tests/test_photo_provenance.py tests/test_public_photo_viewer.py tests/test_collections.py -x -q`
  - `61 passed`

## Attribution
- **User:** surfaced the disappearing save behavior and the concrete Facebook
  photo workflow
- **Antigravity:** no direct implementation in this bounded slice
- **Codex:** root-cause investigation, route fix, regression tests, and audit
  trail

## Notes
- This fixes the registry-ID mismatch path; it does not yet solve broader
  upload-time provenance ergonomics.
