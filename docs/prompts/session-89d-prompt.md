# Session 89d: Photos Sorting + Re-analyze Refresh + Upload Provenance

**Context**: `docs/session_context/session-89d-context.md`
**Predecessor**: Session 89c (dual-keying fix, retry logic, model badge)

## Problem Statement

User tested Session 89c deploy and found 7 issues across 3 areas:

### Area A: Photos Page Sorting (BROKEN)
The Photos page sort is completely broken. "Newest First" sorts by **filename** alphabetically, not by photo date. All sort options are unreliable. Users cannot find recently uploaded photos.

### Area B: Re-analyze Update Completeness (PARTIAL)
After clicking Re-analyze on Leon's Restaurant photo, only the inline summary box updated. The Photo Detective Evidence section still shows "Analyzed with Gemini 3-flash (v2_rich_metadata)" — it was never refreshed. No analysis timestamp is visible anywhere. The user cannot tell when the last analysis was done or with what model.

### Area C: Upload Provenance (MISSING)
Photos have no upload timestamp or uploader attribution. After approving a community upload (Claude Benatar / poisson1957@hotmail.com), the admin can't find the photo because: (1) Recently Reviewed shows no link to the photo, (2) Photos page sorting is broken, (3) No upload_date field exists.

## Ground Truth

- **Leon's Restaurant photo**: 3192877a90a174e9 — re-analyze returned "c. 1940, San Francisco/NYC, medium confidence, GEDCOM: yes" but Photo Detective section still shows old Gemini 3-flash results
- **Claude Benatar upload**: Job ID 0c57277a, poisson1957@hotmail.com, 1 file — approved but photo cannot be located in archive
- **Photos page**: 293 photos, "Newest First" shows c.1930s photos first (filename-based sort)

---

## Session Protocol

- Set `.claude/current_session.txt` to `89d`
- Read `tasks/lessons.md` and `tasks/todo.md` at start
- Create `docs/session_logs/session-89d-log.md` with phase checklist
- Commit after every act (conventional commits)
- Use `/clear` between acts (NEVER /compact)
- Browser verify with Claude Chrome (admin is logged in)
- Screenshots to `docs/screenshots/session-89d/`

## Parallelization Analysis

Acts 2, 3, and 4 touch different areas:
- Act 2 (sorting): `app/main.py` render_photos_section (~line 5889)
- Act 3 (re-analyze refresh): `app/estimate_routes.py` + `app/main.py` AI Analysis section
- Act 4 (upload provenance): `app/main.py` admin/pending + photo page + `core/photo_registry.py`

Acts 2 and 4 both touch `app/main.py` but different sections (5889 vs 25119). **Can parallel with worktrees** if careful about merge. Act 3 touches estimate_routes.py (different file) so it's safe to parallel.

**Recommendation**: Acts 2+3 in parallel (different files), then Act 4 sequential (depends on Act 2's sort fix for verification).

---

## Deliverables

### Act 1: Orient + Verify Claude Benatar's Upload (10 min)

1. Read this prompt and context file
2. Read `tasks/lessons.md`, `tasks/todo.md`
3. **Verify Claude Benatar's upload exists in production**:
   - Navigate to production admin/pending page
   - Find job_id `0c57277a` in Recently Reviewed
   - Check if processing completed (look for inbox_0c57277a_* in photo_index)
   - If the photo is in the archive, find its photo_id and URL
   - If not, document what went wrong
4. Confirm the sort bug: navigate to Photos, select "Newest First", observe dates are NOT sorted
5. Confirm re-analyze issue: navigate to photo 3192877a90a174e9, check Photo Detective still shows old model
6. Commit: `docs(session): session 89d orient`

### Act 2: Fix Photos Page Sorting (25 min)

**Goal**: Sort options actually sort by meaningful criteria. Users can find recent photos.

**2a: Fix existing sort options**
1. In `app/main.py` `render_photos_section()` (~line 5889):
   - **"Newest First"**: Sort by `best_year_estimate` descending (from date_labels.json). Photos without date estimates go last.
   - **"Oldest First"**: Sort by `best_year_estimate` ascending. Photos without date estimates go last.
   - Load date_labels once at the start of the function: `labels = _load_date_labels()`
   - For each photo, look up `labels.get(photo_id, {}).get("best_year_estimate", 0)`
   - Fallback: if no date estimate, use a large/small number to push to end

2. **"Most Faces"** should already work (sorts by face count). Verify it works.

3. **"By Collection"** should already work. Verify it works.

**2b: Add new sort options**
1. Add **"Recently Uploaded"** sort option:
   - This requires an upload_date field (see Act 4)
   - For now, sort by photo_id creation order: inbox_* IDs sort by timestamp prefix, SHA256 IDs by filename
   - OR: sort by file modification time from photo_index.json if available
   - If no upload_date exists yet, defer this option to after Act 4

2. Add **"By Source"** sort option:
   - Sort by `photo_data.get("source", "zzz")` then filename

3. Update the sort dropdown to include new options

**2c: Tests**
- Test that "Newest First" returns photos with higher year estimates first
- Test that "Oldest First" returns photos with lower year estimates first
- Test that photos without date estimates are sorted to the end
- Test "By Source" sort

4. Run `make test-fast`
5. Commit: `fix(photos): sort by estimated date instead of filename`

### Act 3: Fix Re-analyze Section Refresh (20 min)

**Goal**: After re-analyze completes, ALL AI Analysis sections update with new data. Timestamp is visible.

**3a: HTMX full-section refresh**
1. In `app/estimate_routes.py` reanalyze handler (~line 1257):
   - After updating date_labels.json and photo_locations.json, invalidate caches
   - Instead of returning just a summary div, return HTMX that triggers a full refresh of the AI Analysis section
   - Options:
     a. Use `HX-Trigger: refreshAnalysis` header + client-side listener that reloads the section via hx-get
     b. Return the full updated AI Analysis section HTML (Date Estimate + Location + Scene + Photo Detective + model badge)
     c. Return the summary div PLUS an `hx-swap-oob` for the entire AI Analysis container
   - **Recommended: Option (c)** — OOB swap is the cleanest HTMX pattern for updating multiple sections

2. The OOB swap should include:
   - Updated Date Estimate section (new year, confidence, range)
   - Updated Location Estimate section (new location, map)
   - Updated Photo Detective Evidence section (new model badge with timestamp)
   - Updated Scene description (if changed)

**3b: Analysis timestamp display**
1. In the model badge area, ensure timestamp displays:
   - "Analyzed with Gemini 3.1-pro on Mar 5, 2026" (with date)
   - If `reanalyzed_at` exists, show it
   - If only batch analysis exists, show a fallback ("Batch analyzed" with no date, or use file modification time)

2. Add a persistent "Last analyzed" indicator near the Re-analyze button:
   - Shows when the analysis was last run
   - Visible without scrolling to Photo Detective section

**3c: Clarify Re-analyze vs Detect Faces**
1. Add a tooltip or subtitle to the Re-analyze button:
   - "Re-analyze" → "Re-analyze Photo" with subtitle "Date, location, and scene analysis"
2. Add a tooltip or subtitle to Detect Faces button:
   - "Detect Faces" → with subtitle "Per-face descriptions and characteristics"
3. Consider: Should Re-analyze also trigger Detect Faces? Decision: NO for now — they're different API calls with different costs. But document this in the UI so users understand.

**3d: Tests**
- Test that re-analyze response includes OOB swap for AI Analysis section
- Test that model badge shows timestamp after re-analyze
- Test the "Last analyzed" indicator

4. Run `make test-fast`
5. Commit: `fix(estimate): re-analyze refreshes all AI sections + timestamp display`

### Act 4: Upload Provenance + Approval UX (25 min)

**Goal**: Photos show who uploaded them and when. Approved uploads link to the resulting photos.

**4a: Add upload metadata to photo_index.json schema**
1. In `core/photo_registry.py`, add optional fields to photo records:
   - `uploaded_by`: email of uploader (or "admin" for admin uploads, "batch" for initial import)
   - `upload_date`: ISO timestamp when photo was uploaded/ingested
   - `job_id`: upload job ID (for linking back to pending_uploads)

2. In `core/ingest_inbox.py` (~line 560), when creating new photo entries:
   - Accept `uploaded_by` and `upload_date` parameters
   - Store them in the photo_index.json entry

3. In the upload approval handler (~line 26282), pass uploader info to ingest:
   - `uploaded_by = upload_record.get("uploader_email")`
   - `upload_date = upload_record.get("submitted_at")`

**4b: Display upload provenance on photo page**
1. In `app/main.py`, in the photo detail page:
   - Below the collection/source info, show: "Uploaded by [email] on [date]"
   - Use the TODO at line 20180 as the insertion point
   - Only show for photos that have `uploaded_by` set

**4c: Fix Recently Reviewed cards**
1. In `app/main.py` (~line 25119-25130), enhance the Recently Reviewed section:
   - Show `submitted_at` timestamp: "Submitted: Mar 5, 2026 at 11:53 AM"
   - Show `reviewed_at` timestamp: "Approved: Mar 5, 2026 at 12:05 PM"
   - After processing completes, show link(s) to the resulting photo(s):
     - Build photo_id from job_id + filename pattern: `inbox_{job_id}_{index}_{filename}`
     - Link to `/photo/{photo_id}`
   - Show thumbnail preview of the uploaded photo

**4d: Tests**
- Test that upload provenance fields are stored in photo_index.json
- Test that photo page shows uploader info
- Test that Recently Reviewed card shows timestamps and photo links

4. Run `make test-fast`
5. Commit: `feat(uploads): upload provenance tracking + approval UX improvements`

### Act 5: Deploy + Browser Verify (15 min)

1. `make test-fast` + `make test-ml` — all pass
2. Push to main (triggers Railway deploy)
3. Wait for deploy completion
4. **Verify sorting**:
   - Navigate to Photos page
   - Select "Newest First" — photos should sort by estimated date descending
   - Select "Oldest First" — photos should sort by estimated date ascending
   - Verify the first photos shown match expected dates
5. **Verify re-analyze refresh**:
   - Navigate to photo 3192877a90a174e9
   - Check Photo Detective Evidence section — should now show new model (gemini-3.1-pro)
   - Check for analysis timestamp
   - If needed, click Re-analyze again and verify ALL sections update
6. **Verify upload provenance**:
   - Navigate to admin/pending
   - Check Recently Reviewed — should show timestamps and photo links
   - Find Claude Benatar's photo in the archive
7. Screenshots to `docs/screenshots/session-89d/`
8. Commit any data updates

### Act 6: Assessment + Docs (10 min)

1. Run `/session-review`
2. Write `docs/assessments/session-89d-assessment.md`
3. Update mandatory docs: CHANGELOG, ROADMAP, SESSION_HISTORY, BACKLOG
4. Final commit: `docs(session): session 89d assessment`

## Acceptance Criteria

- [ ] "Newest First" sorts by estimated date descending (not filename)
- [ ] "Oldest First" sorts by estimated date ascending
- [ ] Photos without date estimates sort to end
- [ ] After re-analyze: Photo Detective Evidence section updates with new model
- [ ] After re-analyze: analysis timestamp visible in model badge
- [ ] "Last analyzed" indicator near Re-analyze button
- [ ] Re-analyze vs Detect Faces distinction clear in UI
- [ ] Recently Reviewed shows timestamps (submitted_at, reviewed_at)
- [ ] Recently Reviewed links to resulting photo(s) after processing
- [ ] Photo page shows uploader and upload date (when available)
- [ ] Claude Benatar's upload verified in production
- [ ] All tests pass (`make test-fast` + `make test-ml`)
- [ ] Browser verified with screenshots

## Non-Goals (Out of Scope)

- Batch re-running all photos through new Gemini model (separate session)
- Re-analyze triggering Detect Faces automatically (keep separate for now)
- Full upload pipeline rewrite (just adding provenance fields)
- Supabase migration for upload tracking (JSON-first for now, migrate later)
- "Sort by uploader" option (needs data backfill for existing photos first)

## Key File Reference

| File | Lines | What to Change |
|------|-------|----------------|
| `app/main.py` ~5889-5897 | Sorting logic | FIX: sort by date_labels year estimate |
| `app/main.py` ~5937-5942 | Sort dropdown | ADD: "By Source" option |
| `app/main.py` ~25119-25130 | Recently Reviewed cards | ADD: timestamps, photo links |
| `app/main.py` ~20180 | Photo page upload info | ADD: "Uploaded by" display |
| `app/estimate_routes.py` ~1257-1278 | Re-analyze response | FIX: OOB swap for all AI sections |
| `app/estimate_routes.py` ~18714-18730 | Model badge | FIX: ensure timestamp displays |
| `core/photo_registry.py` | Photo schema | ADD: uploaded_by, upload_date, job_id |
| `core/ingest_inbox.py` ~560-586 | Photo registration | ADD: pass uploader info through |
