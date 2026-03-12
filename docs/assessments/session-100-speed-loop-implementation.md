# Session 100 Speed Loop Implementation

**Date:** 2026-03-12  
**Author:** Codex  
**Branch:** `codex/session-100-speed-loop`

## Purpose

Turn the Fox Family workflow from a slow, context-dropping review path into a
usable tagging loop without changing the data model or regressing the earlier
Fox Family performance hotfix.

## What Was Implemented

1. **Context-preserving sequential tagging**
   - `photo_view_content()` now carries person-gallery context (`identity_id`,
     `sort_by`) and archive context (`community_slug`) through the photo partial
     loop.
   - HTMX round-trips in the tag-search/tag/create/quick-action flow now keep
     the same archive prefix and the same gallery ordering context.

2. **Cross-photo auto-advance**
   - Sequential mode still auto-advances within a photo.
   - When the current photo is complete and the user is operating inside a
     person-gallery context, the flow now auto-loads the next photo that still
     has unresolved faces.

3. **First-class noise handling**
   - Sequential mode now surfaces an explicit `Ignore Stranger` action.
   - This maps to the existing `SKIPPED` state rather than inventing a new
     model/state. That preserves reversibility and keeps the ML/user-review
     contract intact.

4. **Dense multi-face fallback**
   - The public photo page now switches from the old horizontal strip to a
     grid layout when a photo contains many faces.
   - This is the first concrete fix for the “group photo is unusable” complaint.

5. **Safer queue links**
   - Confirmed-face modal links, public-photo links, and `Name These Faces`
     CTAs now preserve community/person context more consistently.

## Files Changed

- [app/page_routes.py](/Users/nolanfox/rhodesli/app/page_routes.py)
- [app/photo_routes.py](/Users/nolanfox/rhodesli/app/photo_routes.py)
- [app/identity_routes.py](/Users/nolanfox/rhodesli/app/identity_routes.py)
- [tests/test_sequential_identify.py](/Users/nolanfox/rhodesli/tests/test_sequential_identify.py)
- [tests/test_public_photo_viewer.py](/Users/nolanfox/rhodesli/tests/test_public_photo_viewer.py)

## Why This Shape

- It reuses the existing sequential-mode/photo-partial architecture instead of
  introducing a second review subsystem.
- It uses scoped routing/context fixes and HTMX round-trip discipline rather
  than a frontend-stack change.
- It adopts Antigravity’s highest-ROI recommendation from the mockup pack:
  implement the speed loop first, before building a full cluster queue.

## Verification

Focused gates:
- `ruff check app/page_routes.py app/photo_routes.py app/identity_routes.py tests/test_sequential_identify.py tests/test_public_photo_viewer.py`
- `pytest tests/test_sequential_identify.py tests/test_public_photo_viewer.py tests/test_photo_navigation.py tests/test_inline_face_actions.py tests/test_public_person_page.py tests/test_identify.py -x -q`
  - `151 passed, 2 skipped`

Full suites:
- `pytest rhodesli_ml/tests/ -x -q`
  - `590 passed`
- `pytest tests/ -x -q`
  - blocked in this working tree by a user-created local `data/identities.json`
    delta during live app usage, not by the code changes

Clean-worktree verification:
- clean worktree at commit `0605f95`
- `pytest rhodesli_ml/tests/ -x -q`
  - `590 passed`
- `pytest tests/ -x -q`
  - first cold run hit an e2e app-server startup timeout
  - second warm run passed: `4146 passed, 21 skipped`

Follow-up CI stabilization:
- GitHub CI later exposed one additional fast-test failure in
  `tests/test_photo_sorting.py::TestPhotoSortBySource::test_by_source_option_in_dropdown`
  caused by iterating `_photo_cache.items()` directly while tests patched the
  shared cache.
- Codex fixed that by snapshotting the cache items in
  `render_photos_section()` before iterating.
- Focused re-verification after that fix:
  - `ruff check app/main.py`
  - `pytest tests/test_photo_sorting.py tests/test_sequential_identify.py tests/test_public_photo_viewer.py -x -q`
    - `45 passed`

## Important Verification Note

The failing app-suite assertion in this working tree was:
- `tests/test_data_integrity.py::TestOrphanedIdentities::test_confirmed_anchors_in_face_to_photo`

The failure pointed at a live local identity edit:
- `a0a845d7-4eca-4255-b741-77ff310dc619` / `inbox_f49a5e87ca4a`

That is a workspace-data issue, not a Session 100 code regression. The correct
next step is to verify the branch in a clean worktree rather than touch the
user’s live local `data/identities.json`.

## Attribution

- User: operational Fox Family feedback, screenshots, and the “speed-run
  tagging” requirement
- Antigravity: mockup/review direction for speed loop, ignore-noise, and dense
  multi-face grid behavior
- Codex: implementation, regression tests, route-context hardening, and
  verification discipline
