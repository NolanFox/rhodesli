# Session 96 Context — Community Data Scoping Hotfix + Bulk Upload Planning

**Predecessor:** [Session 95b context](session-95b-context.md) (community data scoping)
**Date:** 2026-03-09
**Type:** Hotfix + planning

---

## What Triggered This Session
Nolan switched to Fox Family community (`/c/fox-family/`) and found multiple data scoping bugs from screenshots:
1. Photos section showed all 297 Rhodes photos in Fox Family
2. Sidebar counts on upload page showed Rhodes data (People 71, Photos 297)
3. Admin bar links hardcoded to `/admin/section/...` without community prefix
4. Unresolved merge conflict in sidebar docstring from Session 95b worktree merge
5. About page shows Rhodes-specific content from Fox Family sidebar

## Root Cause
Session 95/95b built the community middleware and scoping functions correctly, but integration was incomplete. Routes and components were only partially updated to extract community from `request.state` and pass it through to filtering functions.

## What Shipped (Session 96)
- `render_photos_section()` — community photo filter via `_get_community_photo_ids()`
- `upload_routes.py` — `_compute_sidebar_counts(registry, community=community)`
- `_admin_bar()` — community-aware counts and URL prefixing
- Merge conflict resolved in sidebar docstring
- Test updated: `test_admin_bar_links_to_admin_sections`

## What Was Deferred
- **About page community content** — `/about` still hardcodes Rhodes history. Needs community-specific about pages or generic fallback. See BACKLOG COMMUNITY-001.
- **Tools photo picker** — `/tools/estimate` "SELECT A PHOTO" shows Rhodes photos. By design (tools are cross-community).
- **CI/CD fix** — GitHub Actions workflow fails because `./venv/bin/pytest` doesn't exist in CI. Pre-existing since Session 92. Not blocking deploys (Railway deploys from git push).

## Bulk Upload Discussion (Nolan Feedback)
- 636 photos from Uncle Charlie (Roland Fox's brother), digitized by cousin David
- Files in Google Drive + Google Photos, all small JPGs (~5MB)
- Collection: "Charles Fox Dayton Ohio Collection", Source: "Personal Photos"
- Current web upload caps at 200 files → need local pipeline
- Cross-community overlap: Betty Capeluto and Roland Fox confirmed in Rhodes, appear prominently in this collection
- **Nolan insight**: Link GEDCOM first (for top identities by face count), THEN run Gemini with enriched context. This maximizes value per API dollar.
- Created PRD-037: Post-Upload Intelligence Pipeline
- Created Session 96b prompt for ingest + PRD-037 implementation

## Key Decisions
- **Local pipeline for immediate ingest** (Option A) — fastest path for 636 photos
- **Auto-cluster after upload** (PRD-037 Phase 1) — wire clustering into `_background_ingest()`
- **GEDCOM triage page** (PRD-037 Phase 2) — surface top identities by face count for linking
- **Gemini AFTER GEDCOM linking** — deferred to future session after admin links top identities

## Post-Session Planning

### Session 96b (next, same session family)
- Charlie Fox collection ingest via local pipeline (636 photos)
- Auto-cluster against confirmed identities (Betty Capeluto, Roland Fox should match)
- Upload to R2, push to production
- Build PRD-037 Phase 1 (auto-cluster after upload)
- Build PRD-037 Phase 2 (GEDCOM triage page)
- Prompt: `docs/prompts/session-96b-prompt.md`

### Future Session (after 96b)
- GEDCOM linking for top Fox Family identities (admin manual task)
- Batch Gemini estimation with enriched GEDCOM context
- PRD-037 Phase 3 (batch Gemini UI with cost estimate)
- CI/CD fix (install deps in GitHub Actions)
- About page community content (COMMUNITY-001 remaining gap)

## Breadcrumbs
- PRD: `docs/prds/037_post_upload_intelligence.md`
- Prompt: `docs/prompts/session-96b-prompt.md`
- Assessment: `docs/assessments/session-96-assessment.md`
- Session log: `docs/session_logs/session-96-log.md`
- BACKLOG: COMMUNITY-001 (updated), UPLOAD-001 (new)
- ROADMAP: Session 96 in Recently Completed
- CHANGELOG: v0.97.1
