# Session 89d Context: Photos Sorting + Re-analyze Completeness + Upload Provenance

**Date**: 2026-03-05
**Predecessor**: Session 89c (dual-keying fix, retry logic, model badge)

## Origin

User feedback after testing 89c deploy. Seven distinct issues identified across three areas: Photos page sorting, re-analyze update completeness, and upload provenance/tracking.

## Issue 1: Photos Page Sorting Is Broken

**User report**: "Sorting there is completely broken. Newest First doesn't work."

**Screenshot evidence**: Photos page with "Newest First" selected shows photos dated c.1930s first, not newest.

**Root cause**: `render_photos_section()` (app/main.py ~line 5889) sorts by **filename** not by actual date:
```python
# "Newest First" sorts by filename descending
# "Oldest First" sorts by filename ascending
```
This means "Newest First" shows "zeb_capuano_New_Lido..." first because 'z' > 'v' alphabetically. It has nothing to do with the photo's estimated date.

**What should exist**:
- Sort by estimated/corrected date (ascending and descending)
- Sort by face count (exists, seems to work)
- Sort by upload time (no upload_date field exists yet)
- Sort by collection (exists)
- Sort by source
- Sort by uploader (no uploader field exists yet)

**Key files**:
- `app/main.py` ~line 5889-5897: sorting logic
- `app/main.py` ~line 5937-5942: sort dropdown options
- `data/date_labels.json`: has `best_year_estimate` per photo (can sort by this)

## Issue 2: Re-analyze Doesn't Update Photo Detective Evidence Section

**User report**: After re-analyze succeeded (Date: c. 1940, Model: gemini-3.1-pro-preview, GEDCOM: yes), the Photo Detective Evidence section still shows "Analyzed with Gemini 3-flash (v2_rich_metadata)" from the original batch analysis.

**Root cause**: The re-analyze endpoint (estimate_routes.py ~line 1111-1278) updates `date_labels.json` and `photo_locations.json` but:
1. The HTMX response only swaps in a simple "Re-analysis complete" summary div
2. It does NOT refresh the Photo Detective Evidence section, Date Estimate, or Location Estimate sections
3. The Photo Detective Evidence section reads from the `labels` cache which was loaded before re-analyze ran
4. The model badge in Photo Detective reads `label.get("model")` which still has the old batch model

**What should happen**: After re-analyze, the entire AI Analysis section should refresh with new data including the updated Photo Detective Evidence badge.

## Issue 3: No Analysis Timestamp Visible

**User report**: "We still do not have a date when the photo was last sent to Gemini. I thought we were adding that."

**Root cause**: Session 89c added `reanalyzed_at` to the stored data and added code to display it in the model badge, but:
1. The model badge code reads `label.get("reanalyzed_at")` which is only set after re-analyze
2. The original batch analysis doesn't have `reanalyzed_at`, `analyzed_at`, or `timestamp` fields
3. Even after re-analyze, the Photo Detective section doesn't refresh (Issue 2), so the new timestamp never appears

**Fix needed**:
- Store `analyzed_at` timestamp in batch analysis too
- Ensure the model badge refreshes after re-analyze
- Display the timestamp prominently (not just in the badge)

## Issue 4: Re-analysis Complete Box Persistence

**User report**: "Is this re-analysis complete box persistent or does it go away over time?"

**Answer**: It's an inline HTMX swap into `#reanalyze-result-{photo_id}`. It persists until page reload. It is NOT a toast.

**Problem**: If the box disappears on reload and the underlying sections don't update, there's no way to tell the analysis happened. Need a persistent "Last analyzed" indicator.

## Issue 5: Re-analyze Doesn't Do Per-Face Analysis

**User report**: "The API call does not seem to have done the thing where it takes the coordinate of each face and has gemini review those. That was done for the victoria and her kids picture."

**Root cause**: The re-analyze endpoint sends the FULL photo to Gemini as a single image. It does NOT:
- Crop individual faces from bounding boxes
- Send per-face crops to Gemini
- Generate per-face descriptions

Per-face analysis is a separate system: the Face Analysis / "Detect Faces" button (face alignment via coordinate bridging, PRD-015). These are two completely different pipelines.

**User confusion**: "How does the re-analysis button differ from the detect faces / face analysis button?"

**Answer**:
- **Re-analyze**: Sends full photo to Gemini for date/location/scene estimation. Updates date_labels.json and photo_locations.json.
- **Detect Faces**: Runs face coordinate analysis — crops each detected face, sends to Gemini for per-face descriptions (age, gender, clothing, etc.). Updates face_alignment data.

**Decision needed**: Should re-analyze also trigger face detection? Or should they remain separate? The user expects both to happen together.

## Issue 6: Upload Provenance Missing

**User report**: "We should have a date associated with when the photo was uploaded and also it should say who uploaded it (what user)."

**Root cause**: `photo_index.json` schema does NOT store:
- `uploaded_by` (who uploaded)
- `upload_date` (when uploaded)
- `job_id` (which upload batch)

The `pending_uploads.json` on production has this data (uploader_email, submitted_at, job_id) but it's never propagated to photo_index.json or displayed on the photo page.

**Related**: There's a TODO at main.py ~line 20180:
```python
# TODO: When uploaded_by field is added to photo_index.json, show "Uploaded by [Name] on [Date]"
```

## Issue 7: Upload Approval Page UX

**User report**: After approving Claude Benatar's upload, the "Recently Reviewed" section shows only "APPROVED | poisson1957@hotmail.com | 1 file" with:
- No link to the actual photo in the archive
- No timestamp (submitted_at or reviewed_at)
- No photo thumbnail preview
- No way to find the photo in the Photos page (sorting is broken)

**Root cause**: The recently reviewed card template (main.py ~line 25119-25130) is minimal — it only shows status, email, and file count. The `reviewed_at` timestamp IS stored in `pending_uploads.json` but NOT displayed.

**What's needed**:
- Show submitted_at and reviewed_at timestamps
- After processing completes, link to the resulting photo(s) in the archive
- Show thumbnail preview in the reviewed section

## Issue 8: Claude Benatar's Upload Verification

**User report**: "Please also specifically check on the photo Claude uploaded this morning to make sure that it worked."

- Upload email from: poisson1957@hotmail.com
- Job ID from email: 0c57277a
- User approved it in the uploads section
- Need to verify: Did the photo appear in the archive? Can we find it?

This is hard to verify because:
1. `pending_uploads.json` is production-only (Railway volume)
2. No upload_date field to sort by in Photos page
3. No link from approved upload to the photo

## Prior Work References

| Session | What | Relevance |
|---------|------|-----------|
| 89c | Dual-keying, retry, model badge | Direct predecessor |
| 89b | Location persistence, model label | Re-analyze foundation |
| 89 | Re-analyze endpoint (AD-202) | Core feature |
| 86b | Route extraction (estimate_routes.py) | Where re-analyze lives |
| 82e | Help Needed page, mobile menu | UX patterns |
| 66b | Upload fix (cache staleness) | Upload pipeline |
| 62 | Face alignment (PRD-015) | "Detect Faces" feature |

## Key Files

| File | What to Change |
|------|----------------|
| `app/main.py` ~5889-5897 | Fix photo sorting logic (use date_labels for date sort) |
| `app/main.py` ~5937-5942 | Add new sort options (by date, upload time, uploader) |
| `app/main.py` ~25119-25130 | Recently reviewed card — add links, timestamps |
| `app/main.py` ~20180 | Photo page — add upload provenance display |
| `app/estimate_routes.py` ~1257-1278 | Re-analyze HTMX response — refresh all AI sections |
| `core/photo_registry.py` | Add uploaded_by, upload_date fields to schema |
| `core/ingest_inbox.py` ~560-586 | Propagate uploader info to photo_index.json |
