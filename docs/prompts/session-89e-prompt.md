# Session 89e: Data Recovery + Performance Fix + Upload Backfill

**Context**: `docs/session_context/session-89e-context.md`
**Predecessor**: Session 89d (sort fix, re-analyze refresh, upload provenance)

## Problem Statement

User tested Session 89d deploy and found 5 critical issues:

### P0: Claude Benatar's Photo LOST (Data Integrity)
Photo at `inbox_0c57277a_0_unknown` has broken image. The raw photo file was never copied to `raw_photos/` or uploaded to R2 during processing. The source file in `uploads/0c57277a/` on Railway is gone (directory doesn't exist). The face crop is also 404. **This photo may be permanently lost unless it can be recovered from backups or Supabase storage.**

### P1: Site Running Very Slowly
User reports site is barely navigable. Deploy logs show `face_gemini_alignments` Supabase HTTP query executing on EVERY photo page load (not cached). GEDCOM connection also failing with `ConnectionTerminated`. Multiple rapid deploys may have destabilized Railway.

### P2: Leon's Restaurant Missing Face Analysis
Photo `3192877a90a174e9` shows "No face descriptions available yet" with "Detect Faces" button. The Victoria photo (`746dd11e5b4d86a1`) has full per-face analysis (age, attire, position). Leon's needs "Detect Faces" run.

### P3: No Upload Timestamp on Existing Photos
User wants ALL photos to show when they entered the system. Currently only future community uploads will have `uploaded_by`/`upload_date`. Need backfill script for the 294 existing photos.

### P4: Verify Sort Fix
The `/photos` route sort fix was deployed but not browser-verified.

## Session Protocol

- Set `.claude/current_session.txt` to `89e`
- Read `tasks/lessons.md` and `tasks/todo.md` at start
- Create `docs/session_logs/session-89e-log.md` with phase checklist
- Commit after every act (conventional commits)
- Use `/clear` between acts (NEVER /compact)
- Browser verify with Claude Chrome (admin is logged in)

---

## Deliverables

### Act 1: Orient + Data Recovery Attempt (15 min)

1. Read this prompt and context file
2. Read `tasks/lessons.md`, `tasks/todo.md`
3. **Attempt to recover Claude Benatar's photo**:
   - Call `/api/sync/repair-upload` with job_id `0c57277a` (already deployed)
   - Check Supabase storage bucket for any remnant of the upload
   - Check Railway volume backups (if auto_backups exist)
   - Check if the pending_uploads.json has the original filename
   - If recovery fails: document clearly, add BACKLOG item, prepare message for Claude Benatar to re-upload
4. **Check performance**: time a page load, identify the slow query
5. Commit: `docs(session): session 89e orient`

### Act 2: Fix Performance (20 min)

**Goal**: Site loads fast again.

1. **Cache face_gemini_alignments query**: The Supabase query for face alignments runs on every photo page load. Cache it in memory with a TTL or load once at startup.
   - Grep for `face_gemini_alignments` in app/main.py
   - Add caching (similar to `_date_labels_cache` pattern)
2. **Fix GEDCOM connection**: Add retry/timeout for GEDCOM load that's failing with `ConnectionTerminated`
3. **Test**: Verify page load time improves
4. Run `make test-fast`
5. Commit: `fix(perf): cache face alignments query + GEDCOM retry`

### Act 3: Upload Date Backfill (20 min)

**Goal**: Every photo shows when it entered the system.

1. **Write backfill script** (`scripts/backfill_upload_dates.py`):
   - For inbox_* photos: extract approximate date from job_id or set to batch import date
   - For SHA256 photos (original batch): set upload_date to initial import date (use git log for first commit of photo_index.json, or a fixed date like "2026-02-06")
   - Store in photo_index.json via `PhotoRegistry.set_metadata()`
2. **Update photo page display**: Show "Added to archive: [date]" for ALL photos, not just community uploads
   - If `uploaded_by` exists: "Uploaded by [email] on [date]"
   - If `upload_date` exists but no uploader: "Added to archive: [date]"
   - If neither: "Source: [source]" (existing fallback)
3. **Run backfill locally** then push to production
4. Tests + commit: `feat(photos): backfill upload dates for all photos`

### Act 4: Run Detect Faces on Leon's Restaurant (10 min)

**Goal**: Leon's Restaurant photo has per-face analysis like Victoria's photo.

1. Navigate to Leon's Restaurant photo in browser: `/photo/3192877a90a174e9`
2. Click "Detect Faces" button
3. Verify face descriptions appear (age, attire, position for each person)
4. Screenshot evidence
5. Commit any data updates

### Act 5: Verify Sort + Browser Check (10 min)

1. Navigate to `/photos?sort_by=newest` — verify 1980s/1990s photos first
2. Navigate to `/photos?sort_by=oldest` — verify 1900s/1910s photos first
3. Navigate to `/photos?sort_by=recently_uploaded` — verify inbox_* photos first
4. Verify dropdown reflects selected sort option
5. Check site performance — pages should load fast now
6. Screenshots to `docs/screenshots/session-89e/`

### Act 6: Assessment + Docs (10 min)

1. Write `docs/assessments/session-89e-assessment.md`
2. Create `docs/sessions/SESSION_089e.md`
3. Update `docs/session_logs/session-89e-log.md`
4. Update CHANGELOG.md, ROADMAP.md, BACKLOG.md
5. Final commit: `docs(session): session 89e assessment`

## Acceptance Criteria

- [ ] Claude Benatar's photo: recovered OR documented as lost with BACKLOG item
- [ ] Site loads fast (no per-page Supabase query for alignments)
- [ ] ALL photos show archive entry date
- [ ] Leon's Restaurant has per-face analysis
- [ ] Sort verified in production browser
- [ ] All tests pass
- [ ] Assessment written

## Non-Goals

- Re-running Gemini on all photos
- Redesigning the upload pipeline
- Adding sort-by-upload-date as a separate option beyond "Recently Uploaded" (already added in 89d)

## Key File Reference

| File | What to Change |
|------|----------------|
| `app/main.py` grep `face_gemini_alignments` | Cache the Supabase query |
| `app/main.py` ~20316 | Update upload provenance display for all photos |
| `core/photo_registry.py` | Already has uploaded_by/upload_date in valid_keys |
| `scripts/backfill_upload_dates.py` | NEW: set upload_date for all existing photos |
