# Session 89 Assessment

## Shipped
- [x] Act 1: Orient — Traced full pipeline, confirmed Asheville tests 4/4 PASS
- [x] Act 2: Unified Gemini prompt (AD-201) — `_GEMINI_DATE_PROMPT` replaced with `build_extraction_prompt()`. GEDCOM context parameter. API call logging. 10 tests.
  - Evidence: `tests/test_estimate_gemini.py` — 10/10 PASS. `_GEMINI_DATE_PROMPT` no longer exists as module attribute.
- [x] Act 3: Admin re-analyze button (AD-202) — POST endpoint, HTMX button, geocoding, data updates. 14 tests.
  - Evidence: `tests/test_reanalyze.py` — 14/14 PASS. Button visibility tested for admin vs non-admin.
- [x] Act 5: Batch reprocessing script — `scripts/reprocess_with_gedcom.py` with --dry-run, --photo-id, --batch.
- [x] Harness: Mechanical /clear enforcement (Lesson 102) — commit counter, escalating warnings, UserPromptSubmit gate.

## Browser Verification (Act 6)
- [x] Deploy to production — 4 deploys total (initial + 3 hotfixes)
- [x] Re-analyze button visible on photo page (admin only) — PASS
- [x] Re-analyze button fires HTMX POST and returns results — PASS
- [x] Gemini API call succeeds, returns date + location — PASS
- [x] Cost displayed ($0.037), model shown (gemini-3.1-pro-preview) — PASS
- [x] Location diff shown ("Brooklyn, New York → ...") — PASS
- [ ] GEDCOM context injected for Asheville photo — **FAIL**: `GEDCOM context: No`

### Root Cause of GEDCOM Failure
Victoria Capuano's identity has NOT been linked to a GEDCOM record via the admin GEDCOM linking UI. The `gedcom_face_links` Supabase table has no row for her identity_id. The code is correct — it loads GEDCOM context when links exist and gracefully degrades when they don't. The Asheville test in `test_gedcom_context.py` passes because it mocks the GEDCOM data. Production needs the admin to link Victoria → GEDCOM record via the admin UI.

### Production Hotfixes
1. `gemini_config.py` + `gemini_extraction.py` missing from Dockerfile → 500 error
2. `gedcom_context.py` missing from Dockerfile → GEDCOM module not found, visual-only fallback
3. `face_ids` field name wrong (`faces` vs `face_ids`) → empty face list, no GEDCOM lookup

## Parallel Work: Codex PR #6 Review
Reviewed PR #6 from OpenAI Codex: "Fix merge button functionality and UX"
- **Bug**: Confirm modal (z-[9997]) hidden behind Compare modal (z-[10000])
- **Fix**: Raise confirm modal z-index to z-[10010]
- **Verdict**: REQUEST_CHANGES
  - z-[10010] too high — breaks toast invariant at z-[10001]. Use z-[10002].
  - z-index hierarchy comment not updated
  - Test adequate but checks exact CSS strings (consistent with codebase convention)
- **Status**: Not yet merged. Needs the 3 requested changes first.

## Deferred
- Asheville photo correction — requires admin to link Victoria Capuano identity to GEDCOM record, then re-analyze
- Full batch reprocessing of all eligible photos
- Codex PR #6 merge — pending requested changes

## Red Flags
- [HIGH] /clear between acts violated AGAIN (Sessions 80+89). Added mechanical enforcement (Lesson 102, commit counter + hooks). Must be monitored.
- [MEDIUM] 3 Dockerfile hotfixes needed — session 89 code added 3 new rhodesli_ml imports but didn't update Dockerfile. Tests should catch this (TestDockerfileModuleCoverage exists but didn't flag it).
- [LOW] Flaky test `test_inline_find_similar.py::test_neighbors_with_container_id` — pre-existing, not session 89.
- [LOW] `_build_gedcom_context_for_photo()` imports from `scripts/run_combined_pipeline.py` — should be refactored to shared module.

## Next Session Should Verify
1. Link Victoria Capuano identity to GEDCOM record via admin UI, then re-analyze
2. Verify GEDCOM context appears as "Yes" after linking
3. Run `scripts/reprocess_with_gedcom.py --dry-run` to see eligible photo count
4. Verify API call logged in Supabase `gemini_api_calls` table
5. Apply Codex PR #6 changes (z-[10002], comment update) and merge
6. Test Estimate page upload still works with enriched prompt
