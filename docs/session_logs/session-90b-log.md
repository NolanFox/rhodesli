# Session 90b Log

Started: 2026-03-06
Prompt: docs/prompts/session-90b-prompt.md
Context: docs/session_context/session-90b-context.md

## Phase Checklist

- [x] Act 0: Orient — git clean, session files set, prompt read
- [x] Act 1: Fix upload date sorting + photo page metadata
  - Root cause 1: `_build_caches()` called `get_metadata(sha256_id)` but 183/295 photos use `inbox_*` IDs in photo_index.json. Added `filename_to_metadata` fallback dict. Commit: 90226ca
  - Root cause 2 (discovered via debug endpoint): Production volume's photo_index.json predates Session 90 — no upload_date fields. `get_metadata()` returned non-empty metadata (job_id etc) but WITHOUT upload_date, so filename fallback never triggered.
  - Final fix: Merge BOTH direct lookup AND filename fallback metadata (fallback first, direct overwrites). Commit: 13af98d
  - Added upload provenance line to modal photo viewer
  - Added debug endpoint /api/debug/upload-dates (temporary)
  - 2 new tests in test_photo_sort_controls.py
- [x] Act 1b: Push upload_dates to production via sync API
  - Production photo_index.json had 296 photos but 0 with upload_date
  - Pulled prod data, merged local upload_dates by filename, pushed back
  - Result: 296/296 photos with upload_date (155 Feb 10, 2 Feb 13, 114 Feb 14, 23 Mar 5)
- [x] Act 1c: Browser verify sorting
  - upload_newest: Mar 5 photos first (leon_and_nace, test_image, newspapers)
  - upload_oldest: Feb 10 photos first (Image 001, 054, 006...)
  - Verified via WebFetch (Claude Chrome extension disconnected)
- [x] Act 1d: Remove debug endpoint — commit 90c630e
- [x] Act 2: Launch parallel worktree subagents (3 of 5 launched)
  - Track A: main.py refactor — NOT LAUNCHED (deferred to future session)
  - Track B: Supabase shadow writes — COMPLETED + MERGED (commit 99a37dc)
  - Track C: Performance optimization — NOT LAUNCHED (deferred)
  - Track D: Testing + hooks cleanup — COMPLETED + MERGED (commit 27b4a23)
  - Track E: Review UX + PRD-028 — COMPLETED + MERGED (commit 8f60483)
- [x] Act 3: Leon's Restaurant photo location fix
  - Fixed photo_locations.json: Tampa, FL (lat 27.9506, lng -82.4572) instead of Miami
  - Added reanalyzed_at marker to prevent deploy overwrite
  - Commit: 6ba080f
  - ISSUE: init_railway_volume safety gate blocked overwrite on deploy (volume already had reanalyzed entries from prior admin action)
  - FIX: Added photo_locations + date_labels to sync/push endpoint (commit 504ae97)
  - Deploy triggered — awaiting push of photo_locations data to production
- [x] Act 3b: Benatar photo enrichment — COMPLETED
  - Triggered Gemini 3.1-pro re-analysis via admin "Re-analyze Photo" button
  - Result: circa 1928, medium confidence, range 1922-1935, location Unknown
  - Photo Detective evidence cards populated (fashion/grooming analysis)
  - Collection updated to "Community Submissions", source to "Claude Benatar"
- [x] Act 4: Merge tracks — All 3 tracks merged successfully
- [x] Act 5: Browser verification — COMPLETED via Claude Chrome
  - Upload sorting: newest shows Mar 5 photos first, oldest shows Feb 10 first — PASS
  - Leon's Restaurant: Tampa, FL on location badge + map pin — PASS
  - Benatar photo: AI analysis populated (date, evidence cards) — PASS
  - Landing page: loads, 294 photos, v0.93.0 — PASS
  - People page: 70 identified, face cards render — PASS
  - Leon's face alignment: 500 error (expected — AD-110, ML models not on Railway) — KNOWN LIMITATION
  - Screenshots saved to docs/screenshots/session-90b/
- [x] Act 6: Assessment + docs — COMPLETED
- [-] Track A: main.py refactor — IN PROGRESS (multiple worktree subagents)
  - auth_routes.py extracted (660 lines) — merged to main
  - sync_routes.py extracted (513 lines) — merged to main
  - match_facecompare_routes.py extracted (1,750 lines) — merged to main
  - person_routes.py extraction (~3,300 lines) — in progress (worktree)
  - upload_routes.py, admin_routes.py, browse_routes.py, photo_routes.py — subagents launched
  - main.py: 34,449 → ~31,500 after first 3 merges
- [x] Act 7 (mid-flight addition): Back-of-photo feature (PRD-029)
  - User reported: back image upload completely broken on production
  - Root cause: endpoint saves to local but never uploads to R2
  - Also: duplicate routes in main.py AND photo_routes.py
  - PRD written: docs/prds/029_photo_back_and_media_groups.md
  - Context saved: docs/session_context/session-90b-back-photo-context.md
  - Subagent launched in worktree for implementation
  - Scope: fix upload, R2 integration, flip UX, browse filter, media group data model
- [x] Perf: Background cache prewarm — commit fcf18b2

## Commits (main branch)
1. 90226ca — fix(photos): upload date sorting — filename-based metadata fallback
2. 6ba080f — fix(data): Leon's Restaurant photo location — Tampa, FL
3. 87c5924 — debug: add /api/debug/upload-dates endpoint
4. 13af98d — fix(photos): merge both direct + filename metadata to get upload_date
5. 99a37dc — feat(supabase): shadow write infrastructure (Track B merge)
6. 27b4a23 — feat(harness): Track D — hooks cleanup + test pruning
7. 8f60483 — Merge branch 'session-90b/review-ux' (Track E)
8. 53eadc6 — fix(tests): unstaged test_person_links.py change
9. 90c630e — fix(photos): remove debug endpoint + push upload_dates to production
10. 504ae97 — feat(sync): add photo_locations + date_labels to sync/push endpoint
11. 6f2c718 — docs(session): session 90b assessment + changelog + roadmap
12. ebcb9b1 — Merge worktree-agent-a0ecc975 (auth_routes + sync_routes + match_facecompare extractions)
13. fcf18b2 — perf(startup): background cache prewarm + fix _prune_bak_files import

## Key Findings
- Production volume's photo_index.json doesn't have upload_date (predates Session 90)
- init_railway_volume.py won't overwrite it because volume has MORE photos (296 vs 271 local)
- Fix: merge metadata from both direct lookup AND filename fallback in _build_caches()
- Railway auto-deploy from git push was NOT triggering — had to use `railway deploy` manually
- init_railway_volume safety gate blocks photo_locations.json overwrite when volume has reanalyzed entries
- Solution: expanded sync/push endpoint to accept photo_locations + date_labels
- Back image upload broken on production: R2 upload step missing from endpoint
- Duplicate routes exist in both main.py and photo_routes.py after partial extraction

## Browser Verification (Claude Chrome) — Continued Session
- Upload sorting newest: Mar 5 photos first (leon_and_nace, test_image) — PASS
- Upload sorting oldest: Feb 10 photos first (Image 001, 054, 006) — PASS
- Leon's Restaurant: Tampa FL, confidence high, map pin correct — PASS
- Benatar photo: circa 1928, Gemini 3.1-pro, evidence cards — PASS
- Landing page: 296 photos, v0.93.0 — PASS
- People page: 82 identified, face cards render — PASS

## Completion Pass (same day, new context)

- [x] Person routes extraction — person_routes.py (1,632 lines). main.py 27,495 → 25,941.
- [x] Supabase shadow write wiring — save_registry() + save_photo_registry() fire-and-forget to Supabase
- [x] Test import fixes — 9 broken imports from route extraction fixed
- [x] Route priority reorder — _reorder_routes_atomic() after all imports
- [x] Admin user fixture — patches get_current_user in both app.main and app.admin_routes
- [x] CHANGELOG accuracy fix — removed false person_routes.py claim
- [x] Browser verified (Playwright + Chrome): sorting, Leon's, person page all PASS
- Commit: 49f3755

## Deferred to Session 90c
- Leon's face alignment — requires InsightFace locally (AD-110 blocks ML on Railway)
- Leon's Gemini evidence text — still says "SF/NYC", location badge correct (Tampa)
- Leon's face analysis — "No face descriptions available yet" on photo page
- main.py target 15K (at 26K — needs shared.py extraction)
- Track C: Performance/pagination
- 7 flaky order-dependent tests
