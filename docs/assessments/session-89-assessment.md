# Session 89 Assessment

## Shipped
- [x] Act 1: Orient — Traced full pipeline, confirmed Asheville tests 4/4 PASS
- [x] Act 2: Unified Gemini prompt (AD-201) — `_GEMINI_DATE_PROMPT` replaced with `build_extraction_prompt()`. GEDCOM context parameter. API call logging. 10 tests.
  - Evidence: `tests/test_estimate_gemini.py` — 10/10 PASS. `_GEMINI_DATE_PROMPT` no longer exists as module attribute.
- [x] Act 3: Admin re-analyze button (AD-202) — POST endpoint, HTMX button, geocoding, data updates. 14 tests.
  - Evidence: `tests/test_reanalyze.py` — 14/14 PASS. Button visibility tested for admin vs non-admin.
- [x] Act 5: Batch reprocessing script — `scripts/reprocess_with_gedcom.py` with --dry-run, --photo-id, --batch.

## Deferred
- Act 4: Actual Asheville photo reprocessing — requires deploy + Gemini API call in production. Will be done via admin button click during browser verification or via `scripts/reprocess_with_gedcom.py --photo-id 746dd11e5b4d86a1`.
- Act 6 browser verification — requires deploy. Deferred pending push.

## Red Flags
- [LOW] Flaky test `test_inline_find_similar.py::test_neighbors_with_container_id` — pre-existing, passes in isolation. Not related to session 89 changes.
- [LOW] `_build_gedcom_context_for_photo()` imports from `scripts/run_combined_pipeline.py` — this is a batch pipeline file. If the import fails in production (missing dependency), GEDCOM context will gracefully degrade to None. Should be refactored to a shared module in a future session.

## Next Session Should Verify
1. Deploy and click "Re-analyze" on photo 746dd11e5b4d86a1 — confirm Asheville appears
2. Run `scripts/reprocess_with_gedcom.py --dry-run` to see eligible photo count
3. Verify API call logged in Supabase `gemini_api_calls` table
4. Test Estimate page upload still works with enriched prompt
