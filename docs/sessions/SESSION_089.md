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

---

## Session 89b: Fix Location Persistence + Model Label + GEDCOM Reasoning

**Date:** 2026-03-05

### Summary
Fixed 3 user feedback items from Session 89: location not persisting after page refresh, hardcoded model label, and missing GEDCOM reasoning in Photo Detective Evidence section.

### Root Causes
1. **Missing `datetime` import** in estimate_routes.py — NameError silently caught by broad except blocks, preventing all file writes
2. **Deploy overwrite** — `_is_volume_user_modified()` didn't protect date_labels.json or photo_locations.json from being overwritten by stale bundle data
3. **Missing model key** in reanalyze entry dict
4. **No location evidence rendering** in `_detective_evidence_section()`

### Key Commits
- 5409ae7: Location persistence + dynamic model label + GEDCOM reasoning display
- b0feb56: Protect reanalyzed data from deploy overwrite
- 1de56bf: Add missing datetime import (actual root cause)

### Browser Verified
Victoria Capuano photo shows "Asheville, North Carolina, USA" after refresh, with "Analyzed with Gemini 3.1-pro" badge and Geographic Analysis card showing visual evidence, genealogical context, and missing child analysis.

### Assessment
See: docs/assessments/session-89b-assessment.md
