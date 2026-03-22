# PRD-055: Estimate v2 — GEDCOM Context + Text Hints + Geography Retry

**Author:** Session 133
**Date:** 2026-03-22
**Status:** Draft
**Session:** 133 (PRD only)
**References:** TOOLS-005, PRD-033, PRD-034, AD-139, AD-192, AD-201

---

## Problem Statement

The current `/tools/estimate` accepts only a photo upload. The Gemini pipeline
already supports GEDCOM context internally (used for archive photos with known
identities), but standalone users have no way to provide this enrichment.

Three gaps exist:

1. **No GEDCOM input** — Users with family trees cannot leverage the most powerful
   feature of the pipeline: cross-referencing birth years, death years, and
   locations against visual evidence. The enriched prompt (AD-192) produces
   significantly better results but is only available for archive photos.

2. **No text hints** — Users often know partial context ("This is from a wedding
   in Rhodes, probably 1930s") but have no way to share it. This context could
   narrow Gemini's estimate from a 20-year range to a 5-year range.

3. **No geography retry** — When the initial estimate assumes the wrong location
   (e.g., guesses USA when the photo is from Greece), there is no way to correct
   the geographic assumption and re-estimate. The unified prompt (AD-201) already
   includes location analysis, but the user cannot steer it.

## User Flows

### Flow 1: Photo + GEDCOM Text

1. User uploads a photo on `/tools/estimate`
2. User pastes GEDCOM text into an optional textarea ("Paste family tree info")
3. System parses GEDCOM for names, birth/death years, locations
4. System builds enriched Gemini prompt with biographical constraints
5. Results show evidence cards with GEDCOM-derived reasoning highlighted

### Flow 2: Photo + Text Hints

1. User uploads a photo
2. User types free-text hints into an optional field ("What do you know about this photo?")
3. System appends hints to the Gemini prompt as user-provided context
4. Results show which hints influenced the estimate

### Flow 3: Geography Retry

1. User receives an initial estimate
2. User sees the estimated location and disagrees
3. User clicks "Try different location" and selects or types a location
4. System re-runs Gemini with the user-supplied geography as a constraint
5. Results show the revised estimate alongside the original for comparison

### Flow 4: Photo Only (Current Behavior)

1. User uploads a photo with no additional context
2. System runs the existing visual-only Gemini prompt
3. Results display as they do today — no regression

## Acceptance Criteria

### Flow 1: GEDCOM
- [ ] Textarea labeled "Paste family tree info (optional)" appears below upload
- [ ] GEDCOM text is parsed for person records (name, birth year, death year, birthplace)
- [ ] Parsed records are passed to `build_extraction_prompt()` as `gedcom_context`
- [ ] Evidence cards show "Family tree context" badge when GEDCOM influenced result
- [ ] Invalid/empty GEDCOM text falls back to visual-only estimation
- [ ] Gemini API call logged with `enrichment_level=gedcom_user_provided`

### Flow 2: Text Hints
- [ ] Input field labeled "What do you know about this photo? (optional)" appears
- [ ] Hints are appended to the Gemini prompt in a structured "User context" section
- [ ] Results indicate which hints were used ("You mentioned: wedding in Rhodes")
- [ ] Empty hints field falls back to visual-only estimation

### Flow 3: Geography Retry
- [ ] "Try different location" button appears on results page
- [ ] Clicking reveals a location input (text field or dropdown of common locations)
- [ ] Re-estimate reuses the same uploaded image (no re-upload required)
- [ ] New result shows alongside original with "Original estimate" / "Revised estimate"
- [ ] Second Gemini call logged as `trigger=geography_retry`
- [ ] Rate limit applies to retries (counts toward same IP limit)

### Flow 4: Backward Compatibility
- [ ] Upload-only flow works identically to current behavior
- [ ] No regression in estimate quality for photo-only uploads
- [ ] Existing tests continue to pass

## Data Model Changes

### gemini_api_calls table (existing)

| Column | Change | Description |
|--------|--------|-------------|
| `enrichment_level` | Extend values | Add `gedcom_user_provided`, `text_hints`, `geography_retry` |
| `user_context` | **NEW column** (text, nullable) | Raw text hints provided by user |
| `retry_parent_id` | **NEW column** (uuid, nullable, FK) | Links retry calls to original |

No new tables needed. The existing `gemini_api_calls` table already tracks
prompt text, response, and enrichment level.

### Upload storage

Re-estimates reuse the same R2 upload key (`uploads/estimate/{upload_id}{suffix}`).
No additional storage needed for retries.

## Technical Notes

- `_call_gemini_date_estimate()` already accepts `gedcom_context` parameter
- `build_extraction_prompt()` already handles GEDCOM enrichment via `preset="quick"`
- GEDCOM parsing can use a lightweight regex extractor (name/date/place from
  INDI records) — no full GEDCOM library needed for paste input
- Text hints are injected as a new prompt section, not mixed into GEDCOM context
- Geography retry passes location as `photo_metadata={"user_location": "Rhodes, Greece"}`

## Out of Scope

- **GEDCOM file upload** — Only paste input in v2. File upload parsing is a
  future enhancement (requires server-side GEDCOM library).
- **Multi-turn conversation** — Covered by TOOLS-004 (NL Query + Chatbot).
- **Automatic GEDCOM matching** — No attempt to match faces in the photo to
  GEDCOM individuals. User provides context, system uses it as-is.
- **Billing/rate limiting changes** — Uses existing rate limits. Premium tiers
  are a separate PRD (PRD-033 revenue model).
- **Archive-integrated estimate** — This PRD covers the standalone `/tools/estimate`
  only. The archive `/estimate` route already has GEDCOM context from the registry.

## Priority Order

1. **Flow 2: Text Hints** — Simplest to implement (string append to prompt),
   highest immediate value for standalone users. ~1 session.
2. **Flow 1: GEDCOM Text** — Moderate complexity (GEDCOM parsing), high value
   for genealogist segment. ~1 session.
3. **Flow 3: Geography Retry** — Requires UI for side-by-side comparison and
   session state for re-estimate. ~1 session.

Total estimate: 2-3 sessions.

## Success Metrics

| Metric | Target |
|--------|--------|
| Users providing context (text or GEDCOM) | >20% of uploads |
| Geography retry usage | >10% of estimates |
| Estimate accuracy improvement with context | Narrower range by 30%+ |
| Gemini API cost per enriched estimate | <$0.10 (same as current) |

## References

- Current implementation: `app/estimate_routes.py`
- Gemini prompt: `rhodesli_ml/gemini_extraction.py` (`build_extraction_prompt()`)
- Gemini config: `rhodesli_ml/gemini_config.py` (model selection, pricing)
- PRD-033: Date Estimator Standalone (`docs/prds/033_date_estimator_standalone.md`)
- PRD-034: Standalone Tool Suite (`docs/prds/034_standalone_tool_suite.md`)
- AD-139: Gemini 3.1 Pro selection
- AD-192: GEDCOM-enriched location estimation
- AD-201: Unified Gemini prompt (date + location)
