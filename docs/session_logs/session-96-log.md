# Session 96 Log — Hotfix: Community Data Scoping Bugs
Started: 2026-03-09
Type: Hotfix (user-reported production bugs)

## Context
User switched to Fox Family community (`/c/fox-family/`) and found multiple data scoping bugs where Rhodes community data leaked into Fox Family views.

## Bugs Found (from screenshots)
1. **Photos section shows all 297 Rhodes photos** in Fox Family (`/c/fox-family/?section=photos`)
2. **Sidebar counts show Rhodes data** on upload page (People 71, Photos 297)
3. **Admin bar missing/not community-scoped** — links hardcoded to `/admin/section/...`
4. **Merge conflict in sidebar docstring** — unresolved git conflict markers in main.py
5. **About page Rhodes-specific** — `/about` from Fox Family shows Rhodes history (DEFERRED)

## Fixes Applied
- [x] `render_photos_section()` — added `community` param, filters via `_get_community_photo_ids()`
- [x] Upload page `_compute_sidebar_counts()` — pass `community=community`
- [x] `_admin_bar()` — accepts community params, scopes counts + link URLs
- [x] Merge conflict resolved in sidebar docstring
- [x] Test updated: `test_admin_bar_links_to_admin_sections`

## Deferred
- About page community-aware content (BACKLOG)
- `/tools/estimate` photo picker shows Rhodes photos (by design — tools are cross-community)

## User Feedback: Bulk Upload
- User wants to upload 636 photos (Uncle Charlie/Fox collection from Google Drive)
- Current 200-file cap requires batching
- Discussed options: local pipeline (recommended), web batches, Google Drive API integration
- Logged as BACKLOG item: TOOLS-006 self-service archive / bulk import

## Tests
- All unit tests pass (pre-existing failures unrelated: test ordering issues)
- Admin bar test updated for new link format
