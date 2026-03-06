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
- [ ] Act 3b: Benatar photo enrichment — DEFERRED (needs Gemini API call on production)
- [x] Act 4: Merge tracks — All 3 tracks merged successfully
- [ ] Act 5: Browser verification — partial (WebFetch only, Chrome extension disconnected)
- [ ] Act 6: Assessment + docs — IN PROGRESS

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

## Key Findings
- Production volume's photo_index.json doesn't have upload_date (predates Session 90)
- init_railway_volume.py won't overwrite it because volume has MORE photos (296 vs 271 local)
- Fix: merge metadata from both direct lookup AND filename fallback in _build_caches()
- Railway auto-deploy from git push was NOT triggering — had to use `railway deploy` manually
- init_railway_volume safety gate blocks photo_locations.json overwrite when volume has reanalyzed entries
- Solution: expanded sync/push endpoint to accept photo_locations + date_labels

## Deferred
- Track A: main.py refactor (biggest track, needs dedicated session)
- Track C: Performance optimization (depends on Track A)
- Act 3b: Benatar photo enrichment (needs Gemini API call on production admin UI)
- Full browser verification (Chrome extension disconnected mid-session)
