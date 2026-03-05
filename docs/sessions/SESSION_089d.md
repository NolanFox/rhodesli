# Session 89d: Photos Sorting + Re-analyze Refresh + Upload Provenance

**Date**: 2026-03-05
**Version**: v0.92.1 → v0.92.2
**Predecessor**: Session 89c

## Summary

Fixed 3 areas from user testing of Session 89c deploy:

1. **Photos page sorting** — "Newest First" was sorting by filename, not date. Fixed both `/?section=photos` and `/photos` routes to use `best_year_estimate` from Gemini analysis. Added "By Source" and "Recently Uploaded" sort options.

2. **Re-analyze section refresh** — After clicking Re-analyze, only the inline summary updated. Now returns `HX-Trigger: refreshAnalysis` header which triggers the AI sections div to reload via `/api/photo/{id}/ai-sections`. "Last analyzed" timestamp visible next to Re-analyze button.

3. **Upload provenance** — Added `uploaded_by`, `upload_date`, `job_id` fields to PhotoRegistry. Photo page shows "Uploaded by [email] on [date]" for community uploads. Recently Reviewed cards show submitted/approved timestamps and "View photo" links.

## Key Changes

| File | Change |
|------|--------|
| `app/main.py` | Fixed sort in `/photos` + `/api/photos/more` routes, added ai-sections endpoint, upload provenance display, Recently Reviewed timestamps/links |
| `app/estimate_routes.py` | Re-analyze returns HX-Trigger header |
| `core/photo_registry.py` | Added uploaded_by/upload_date/job_id to valid metadata keys |
| `core/ingest_inbox.py` | Thread uploaded_by/upload_date through process pipeline |

## Tests

17 new tests:
- `tests/test_photo_sorting.py` — 8 tests (6 original + 2 /photos route)
- `tests/test_reanalyze_refresh.py` — 4 tests
- `tests/test_upload_provenance.py` — 5 tests

## Known Issues

- Claude Benatar upload photo broken (filename "unknown", image missing from R2)
- Upload provenance only for future uploads (no backfill)
- Duplicate sort logic between two photo routes (should extract helper)
