# Session 90b Assessment (Updated)

## Shipped

- [x] **Upload date sorting fix** — Root cause: production photo_index.json had no upload_date fields. Fixed via sync API push (296/296 photos patched). Verified: upload_newest shows Mar 5 photos, upload_oldest shows Feb 10 photos. Evidence: Chrome browser screenshots (docs/screenshots/session-90b/).
- [x] **Leon's Restaurant location** — Changed from Miami to Tampa, FL in photo_locations.json. Pushed to production via new sync/push endpoint. Evidence: Chrome screenshot shows "Tampa, Florida, United States" location badge, Leaflet map pinned on Tampa, Confidence: high.
- [x] **Sync/push endpoint expansion** — Added photo_locations + date_labels support. Enables future ML data corrections without full redeploy.
- [x] **Track B: Supabase shadow writes** — Tables, functions, backfill script, 17 tests. Merged from worktree (commit 99a37dc).
- [x] **Track D: Hooks cleanup** — Orphaned hooks removed, test pruning. Merged from worktree (commit 27b4a23).
- [x] **Track E: Review UX + PRD-028** — Discoveries raw metrics hidden, photo dropdown fix, PRD-028 written. Merged from worktree (commit 8f60483).
- [x] **Debug endpoint removed** — /api/debug/upload-dates removed after verification (commit 90c630e).
- [x] **Benatar photo enrichment** — Gemini 3.1-pro re-analysis triggered via admin UI. Date: circa 1928 (1920s), medium confidence, range 1922-1935. Location: Unknown (low confidence — expected for studio portrait). Photo Detective evidence cards fully populated with fashion/grooming analysis. Evidence: Chrome screenshot.
- [x] **Browser verification** — Full Claude Chrome verification: sorting (newest/oldest), Leon's Restaurant (Tampa + map), Benatar photo (AI analysis), landing page, People page. 5+ screenshots saved to docs/screenshots/session-90b/.
- [x] **Track A: auth_routes.py extraction** — First route module extracted from main.py (660 lines of auth routes: login, signup, forgot-password, reset-password, OAuth, logout). Worktree subagent in progress for additional extractions.

## In Progress

- **Track A: main.py refactor** — auth_routes.py extracted (660 lines). Worktree subagent continuing additional route extractions. Target: main.py < 15K lines. Current: ~33.8K lines.
- **Track C: Performance optimization** — Pagination refactor started (stashed). Depends on Track A completion for clean merge.

## Deferred

- **Track A completion (< 15K lines)** — Needs dedicated session. auth_routes extracted, 7 more route groups needed.
- **Track C: Performance optimization** — Pagination, O(1) lookups. Depends on Track A file structure.
- **Leon's face alignment** — "Detect Faces" returns 500 on production (AD-110: web requests never run heavy ML). Requires running InsightFace locally, not possible on Railway.
- **Leon's Gemini evidence text** — Location badge says Tampa (correct) but Gemini evidence text still says "Likely San Francisco, CA or New York, NY" (from old analysis). Re-running Gemini would fix but not critical.

## Red Flags

- [LOW] Flaky test: `test_person_card_links_to_person_page` and `test_activity_page` fail in full suite but pass in isolation. Pre-existing order-dependent issues.
- [LOW] Railway auto-deploy from git push still not triggering. Manual `railway deploy` required.
- [LOW] Leon's Gemini evidence text still mentions SF/NYC. Location badge and map are correct (Tampa).
- [LOW] Leon's face alignment unavailable on production (ML models not loaded). Only cosmetic — face labels already show from embeddings.

## Next Session Should Verify

1. Track A: Continue main.py route extraction — target admin_routes, browse_routes, person_routes, tree_routes, sync_routes
2. Track C: Apply pagination (stashed changes) after Track A merges
3. Supabase shadow write tables exist (run backfill_supabase.py on production)
4. Leon's face alignment can be run locally with `scripts/face_alignment.py`
5. Consider re-running Gemini on Leon's photo to fix geographic evidence text
