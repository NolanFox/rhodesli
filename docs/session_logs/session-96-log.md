# Session 96 Log — Hotfix: Community Data Scoping + Bulk Upload Planning
Started: 2026-03-09
Type: Hotfix (user-reported production bugs) + planning

## Context
User switched to Fox Family community (`/c/fox-family/`) and found multiple data scoping bugs where Rhodes community data leaked into Fox Family views. Also raised need to bulk-upload 636 Fox family photos.

## Bugs Found (from 5 screenshots)
1. **Photos section shows all 297 Rhodes photos** in Fox Family (`/c/fox-family/?section=photos`) — `render_photos_section()` didn't filter by community
2. **Sidebar counts show Rhodes data** on upload page (People 71, Photos 297) — `_compute_sidebar_counts()` called without `community=` on upload route
3. **Admin bar missing/not community-scoped** — `_admin_bar()` hardcoded links to `/admin/section/...`, didn't accept community params, counted all identities globally
4. **Merge conflict in sidebar docstring** — unresolved git conflict markers in main.py:4276-4282 from Session 95b worktree merge
5. **About page Rhodes-specific** — `/about` from Fox Family shows Rhodes community history, not generic or community-specific content (DEFERRED)

## Root Cause Analysis
The CommunityMiddleware and foundational scoping functions (`_get_community_photo_ids`, `_get_community_identity_ids`, `_compute_sidebar_counts`) were correctly implemented in Session 95/95b. However, integration was incomplete — routes and components were only partially updated to:
1. Extract community from `request.state`
2. Pass community to scoping utility functions
3. Filter results before rendering

## Fixes Applied
- [x] `render_photos_section()` in `app/main.py` — added `community` param, calls `_get_community_photo_ids(community)` to filter photos before building the grid
- [x] `page_routes.py` call site — passes `community=community` to `render_photos_section()`
- [x] `upload_routes.py:207` — `_compute_sidebar_counts(registry, community=community)` instead of `_compute_sidebar_counts(registry)`
- [x] `_admin_bar()` in `app/main.py` — now accepts `community_slug` and `community` params, scopes identity counts via `_get_community_identity_ids()`, prefixes links with `community_url_prefix()`
- [x] Merge conflict resolved in sidebar docstring (kept worktree-agent version)
- [x] Test updated: `test_admin_bar_links_to_admin_sections` — assertions now check `section=to_review` and `/upload` instead of old `/admin/section/...` paths

## Files Changed
- `app/main.py` — render_photos_section community filter, _admin_bar community params, merge conflict
- `app/page_routes.py` — pass community to render_photos_section
- `app/upload_routes.py` — pass community to _compute_sidebar_counts
- `tests/test_admin_bar.py` — updated assertions

## Deferred
- **About page community content** — `/about` hardcodes Rhodes history. Needs community-specific about pages or generic fallback. BACKLOG: COMMUNITY-001 remaining gap.
- **Tools photo picker** — `/tools/estimate` "SELECT A PHOTO" section shows Rhodes photos. By design: tools are cross-community standalone features.

## User Feedback: Bulk Upload (636 Charlie Fox Photos)

### Background
- Uncle Charlie (Roland's brother) — collection digitized by cousin David
- 636 photos in Google Drive + Google Photos album
- Files are small JPGs (~5MB each)
- Common use case: scanning services digitize entire collections

### Options Discussed
| Option | Description | Effort | Speed |
|--------|-------------|--------|-------|
| **A: Local pipeline** (recommended) | Download to folder → `core.ingest_inbox` in batches → R2 upload → push | 0 sessions (existing infra) | Fastest |
| **B: Web upload batches** | Upload ~200 at a time through `/c/fox-family/upload` (3-4 batches) | 0 sessions | Slow |
| **C: Google Drive API** | Paste shared folder link → app fetches + processes | 1-2 sessions (new feature) | Best UX |

### Decision
- **Immediate**: Option A — local pipeline for Charlie Fox photos
- **Future**: Option C as part of TOOLS-006 self-service archive creation
- Logged as BACKLOG: UPLOAD-001

### Pipeline Steps (for reference)
1. Download all 636 photos from Google Drive to local folder
2. `python -m core.ingest_inbox --dir raw_photos/fox_charlie/ --job-id fox-charlie --source "Charlie Fox Collection" --collection "Charlie Fox Tampa"`
3. Upload new photos + crops to R2 via boto3
4. Tag photos with Fox Family community in `photo_communities` table
5. Push to production
6. Verify at `/c/fox-family/?section=photos`

## Tests
- 3863 unit tests pass (pre-existing 16 failures are test ordering issues, pass in isolation)
- Admin bar test updated for new link format
- No new regressions from fixes

## Commits
- `7c834a5` — fix: community data scoping — photos, sidebar counts, admin bar

## Harness Updates
- CHANGELOG: v0.97.1 entry added
- BACKLOG: COMMUNITY-001 updated (~70% done), UPLOAD-001 added
- ROADMAP: Session 96 in Recently Completed, COMMUNITY-001 status updated
- Assessment: `docs/assessments/session-96-assessment.md`
