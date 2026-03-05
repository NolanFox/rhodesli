# Session 89: Wire GEDCOM Context into Location Estimation

**Date:** 2026-03-04
**Version:** v0.92.0

## Summary
Unified the two divergent Gemini prompt systems (interactive vs batch) and wired GEDCOM genealogical context into the interactive estimate route. Added admin re-analyze button and batch reprocessing script. Asheville photo (746dd11e5b4d86a1) pipeline ready for correction.

## Problem
Photo 746dd11e5b4d86a1 (Victoria Capuano, Asheville ~1934) showed "Brooklyn, New York" because the interactive estimate route used a stripped-down visual-only prompt that didn't ask for location or accept GEDCOM context.

## Key Commits
- 61e37bf: docs(session): session 89 orient — trace pipeline, confirm existing tests
- 1d30605: feat(estimate): wire enriched prompt + API logging into interactive estimate route (AD-201)
- 27d46eb: feat(photo): admin re-analyze button for one-click Gemini re-run (AD-202)
- db0694f: feat(scripts): batch GEDCOM reprocessing with dry-run and cost estimation
- 931fd06: docs(session): session 89 assessment, AD-201/202, CHANGELOG v0.92.0

## What Shipped
1. **AD-201**: Replaced `_GEMINI_DATE_PROMPT` with `build_extraction_prompt(preset="quick")`. GEDCOM context support. API call logging on every interactive Gemini call.
2. **AD-202**: Admin "Re-analyze" button on photo AI Analysis section. POST `/api/photo/{photo_id}/reanalyze` endpoint. Updates date_labels.json + photo_locations.json. Shows diff.
3. **Batch script**: `scripts/reprocess_with_gedcom.py` with --dry-run, --photo-id, --batch, --limit, --max-cost.
4. **Inline geocoder**: Asheville, Rhodes, NYC, Miami, Tampa, etc.
5. **24 new tests** across test_estimate_gemini.py and test_reanalyze.py.

## Deferred
- Actual Asheville photo reprocessing (requires deploy + Gemini API call)
- Full batch reprocessing of all eligible photos
- Auto-trigger for "faces identified → re-estimate" webhook

## Assessment
See: docs/assessments/session-89-assessment.md
