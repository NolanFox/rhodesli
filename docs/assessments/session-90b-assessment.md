# Session 90b Assessment

## Shipped

- [x] **Upload date sorting fix** — Root cause: production photo_index.json had no upload_date fields. Fixed via sync API push (296/296 photos patched). Verified: upload_newest shows Mar 5 photos, upload_oldest shows Feb 10 photos. Evidence: WebFetch verification, debug endpoint showed distribution {155 Feb 10, 2 Feb 13, 114 Feb 14, 23 Mar 5}.
- [x] **Leon's Restaurant location** — Changed from Miami to Tampa, FL in photo_locations.json. Pushed to production via new sync/push endpoint. Evidence: `curl` shows `Tampa, Florida, United States` in location badge, map data-lat=27.9506.
- [x] **Sync/push endpoint expansion** — Added photo_locations + date_labels support. Enables future ML data corrections without full redeploy.
- [x] **Track B: Supabase shadow writes** — Tables, functions, backfill script, 17 tests. Merged from worktree (commit 99a37dc).
- [x] **Track D: Hooks cleanup** — Orphaned hooks removed, test pruning. Merged from worktree (commit 27b4a23).
- [x] **Track E: Review UX + PRD-028** — Discoveries raw metrics hidden, photo dropdown fix, PRD-028 written. Merged from worktree (commit 8f60483).
- [x] **Debug endpoint removed** — /api/debug/upload-dates removed after verification (commit 90c630e).
- [x] **Worktrees cleaned up** — All stale worktrees pruned.

## Deferred

- **Track A: main.py refactor** — NOT LAUNCHED. Biggest track, needs dedicated session.
- **Track C: Performance optimization** — NOT LAUNCHED. Depends on Track A for file structure.
- **Benatar photo enrichment** — Needs Gemini API call on production (admin re-analyze button).
- **Leon's Gemini evidence text** — Location badge says Tampa (correct) but Gemini evidence text still says "Likely San Francisco, CA or New York, NY" (from old analysis). Re-running Gemini would fix but not critical.
- **Full browser verification** — Chrome extension disconnected mid-session. Used WebFetch + curl for verification.

## Red Flags

- [LOW] Flaky test: `test_person_card_links_to_person_page` fails in full suite but passes in isolation. Pre-existing order-dependent issue.
- [LOW] Railway auto-deploy from git push still not triggering. Manual `railway deploy` required.
- [LOW] Leon's Gemini evidence text still mentions Miami/SF. Location badge and map are correct.

## Next Session Should Verify

1. Leon's Restaurant photo shows Tampa on location badge — VERIFIED via curl
2. Upload date sorting works on production — VERIFIED via WebFetch
3. Supabase shadow write tables exist (run backfill_supabase.py on production)
4. Track A main.py refactor should be the priority for next session
5. Benatar photo needs Gemini analysis via admin UI
