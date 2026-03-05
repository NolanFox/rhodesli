# Session 89e Context

**Predecessor**: Session 89d
**Date**: 2026-03-05

## What Session 89d Shipped
- Sort by estimated date (fixed in BOTH `/?section=photos` and `/photos` routes)
- "Recently Uploaded" and "By Source" sort options
- Re-analyze HX-Trigger refresh (all AI sections update after re-analyze)
- "Last analyzed" timestamp next to Re-analyze button
- Upload provenance fields (uploaded_by, upload_date, job_id) in PhotoRegistry
- Recently Reviewed cards show timestamps + "View photo" links
- Approval handler threads provenance through ingest pipeline
- Raw photo copy to `raw_photos/` during ingest
- R2 upload after approval processing
- `/api/sync/repair-upload` endpoint for fixing broken uploads
- `_invalidate_all_caches()` helper
- 17 new tests

## Critical Issues Found (from user testing 89d deploy)

### P0: Claude Benatar's Photo Lost
- Photo at `inbox_0c57277a_0_unknown` — image broken (404 from R2)
- Root cause: `process_single_image` registered path as `raw_photos/unknown.jpg` but never copied file there
- File was in `uploads/0c57277a/` on Railway volume but that directory no longer exists
- Staging empty, uploads empty — file was likely lost during a Railway deploy/restart
- The crop (`crops/inbox_a4c3a5701b51.jpg`) is also 404
- **ACTION NEEDED**: Check if the photo can be recovered from Supabase storage, backup, or ask Claude Benatar to re-upload
- The fix for FUTURE uploads is deployed (raw_photos copy + R2 upload) but this specific photo is likely lost
- The repair endpoint at `/api/sync/repair-upload` was deployed but can't find the source file

### P1: Site Running VERY SLOWLY
- User reports site barely navigable
- Deploy logs show `face_gemini_alignments` Supabase query on EVERY photo page load
- GEDCOM load failing: `ConnectionTerminated error_code:1`
- Possible causes:
  1. Supabase `face_gemini_alignments` query not cached (HTTP request per page view)
  2. GEDCOM connection issues causing timeouts
  3. Multiple deploys in quick succession may have caused Railway instability
- **ACTION**: Cache the face_gemini_alignments query, add connection retry for GEDCOM

### P2: Leon's Restaurant Photo Missing Features
- Photo `3192877a90a174e9` — user screenshot comparison:
  - **HAS**: Date estimate, Location estimate with map, Scene, Photo Detective with model badge, Geographic Analysis
  - **MISSING**: Face Analysis section (shows "No face descriptions available yet" + "Detect Faces" button)
  - The Victoria photo (`746dd11e5b4d86a1`) has full Face Analysis with per-face descriptions (age, attire, position)
  - This means "Detect Faces" was never run on Leon's Restaurant photo
  - Geographic Analysis IS present on Leon's but user may be comparing to a different view
- **ACTION**: Run "Detect Faces" on Leon's Restaurant photo, or clarify with user

### P3: No Upload Timestamp on Existing Photos
- User wants ALL photos to show when they entered the system, not just community uploads
- Leon's Restaurant was imported in the initial batch — no `uploaded_by`/`upload_date`
- Need a backfill script to set `upload_date` for all existing photos (use file modification time or a batch import date)
- **ACTION**: Write backfill script, add "Added to archive: [date]" display for all photos

### P4: Sort Still Not Verified
- Second deploy with sort fix went out but wasn't verified in browser before context ran out
- Need to verify "Newest First" shows 1980s/1990s photos first
- Need to verify "Recently Uploaded" shows inbox_* photos first
- Need to verify dropdown reflects selected option correctly

## Key Code Locations

| Issue | File | Line | What |
|-------|------|------|------|
| Sort (public route) | `app/main.py` | ~15567 | Fixed: uses `_load_date_labels()` |
| Sort (HTMX pagination) | `app/main.py` | ~15860 | Fixed: same as above |
| Sort (admin route) | `app/main.py` | ~6026 | Already fixed in 89d |
| Repair endpoint | `app/main.py` | ~32113 | `/api/sync/repair-upload` |
| R2 upload helper | `app/main.py` | ~2870 | `_upload_new_files_to_r2()` |
| Cache invalidation | `app/main.py` | ~2840 | `_invalidate_all_caches()` |
| Raw photo copy | `core/ingest_inbox.py` | ~580 | `shutil.copy2` to raw_photos/ |
| Face alignments query | `app/main.py` | grep `face_gemini_alignments` | Supabase query per page load |

## User Feedback (Verbatim)

1. "The photo still does not say what user uploaded it" — wants upload provenance on ALL photos
2. "The photos section still doesn't let you sort by upload time vs. photo date" — wants both sort options (DONE: "Recently Uploaded" added)
3. "You need to find a way to fix Claude Benatar's photos. It is TOTALLY UNACCEPTABLE that we lost a photo. This should NEVER happen." — data integrity is highest priority
4. "The site is running VERY VERY SLOWLY now. Something has broken. I can barely navigate it any more."
5. "It is missing two things that the Victoria photo has, the face analysis at the bottom and the geographic analysis is missing" — Leon's Restaurant needs Detect Faces run
6. "Every photo added should have a time when it entered the system, even if the first ones all entered as a block together" — backfill upload dates
7. "I can also add any credential you need locally" — R2 creds can be added to .env if needed

## Deploy Status
- Commit `9d92136` pushed and deploying (repair endpoint path fix)
- Previous commits: `a05402d` (raw photo copy + R2 upload), `240cc80` (sort fix), `3d3c36a` (provenance)
