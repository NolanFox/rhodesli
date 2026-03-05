# Session 89d Assessment

## Shipped

- [x] **Act 1: Orient** — Confirmed all 3 issues in production browser
- [x] **Act 2: Fix Photos Sorting** — `render_photos_section` sorts by `best_year_estimate` from date_labels. "By Source" option added. 6 tests. Commit: `fdba566`
- [x] **Act 3: Re-analyze Section Refresh** — HX-Trigger `refreshAnalysis` header + `/api/photo/{id}/ai-sections` endpoint. "Last analyzed" timestamp near Re-analyze button. 4 tests. Commit: `704e03e`
- [x] **Act 4: Upload Provenance** — `uploaded_by`, `upload_date`, `job_id` in PhotoRegistry. Photo page shows uploader info. Recently Reviewed cards show timestamps + photo links. Approval handler threads provenance through ingest pipeline. 5 tests. Commit: `3d3c36a`
- [x] **Act 5: Deploy + Verify** — Two deploys. Found and fixed critical bug: `/photos` route had SEPARATE filename-based sort. Hotfix commit: `240cc80`

## Critical Bug Found During Verification

The `/photos` public route (line 15557) had its own sort implementation that was still using `filename` instead of `best_year_estimate`. The `render_photos_section` sort (line 6016) was correct but only used by `/?section=photos`. The `/api/photos/more` pagination endpoint had the same bug. Both fixed in hotfix commit.

## Deferred / Not Fixed

1. **Claude Benatar's uploaded photo** — Image broken at `inbox_0c57277a_0_unknown`. The filename was captured as "unknown" during upload processing, and the raw photo wasn't uploaded to R2. This is a production data issue requiring manual re-processing from upload staging.
2. **Upload provenance for existing photos** — Only future community uploads will have `uploaded_by`/`upload_date`. No backfill for the 294 existing photos.
3. **"Recently Uploaded" sort** — Added but limited: sorts `inbox_*` photos first (community uploads), then by photo_id. True upload timestamp sorting requires `upload_date` field backfill.

## Red Flags

- **MEDIUM**: Duplicate sort logic in two code paths (`/?section=photos` vs `/photos`). This is a maintainability debt — should extract shared sort helper.
- **LOW**: Sort tests only covered `/?section=photos` path, not `/photos` route. Added regression tests for `/photos` in hotfix.

## Test Summary

- 17 new tests across 3 test files (6 sort + 4 re-analyze + 5 provenance + 2 /photos route)
- All pass locally (`make test-fast`: 2517 pass, 1 pre-existing xdist flake)

## Next Session Should Verify

1. Sort working in production after sort fix deploy
2. Claude Benatar photo LOST — raw file and crop both 404 from R2, uploads dir gone from Railway. Need recovery attempt or re-upload request
3. Site performance degradation — face_gemini_alignments Supabase query on every page load
4. Leon's Restaurant missing Face Analysis (needs Detect Faces button clicked)
5. All photos need upload_date backfill
6. See `docs/prompts/session-89e-prompt.md` for full plan
