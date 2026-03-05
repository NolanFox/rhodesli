# Session 89b Assessment — Location Persistence + Model Label + GEDCOM Reasoning

## Shipped

- [x] **Fix 1: Location persistence after page refresh** — Evidence: Browser screenshot shows "Asheville, North Carolina, USA" after full page refresh, with Leaflet map centered on Asheville. Three root causes found and fixed:
  1. Missing `datetime` import in estimate_routes.py — `datetime.now()` NameError caught by broad except, silently skipping file writes
  2. `photo_locations.json` not created if file didn't exist (only updated if `exists()`)
  3. Deploy overwrite: `_is_volume_user_modified()` didn't protect `date_labels.json` or `photo_locations.json` from being overwritten by stale bundle data on every deploy

- [x] **Fix 2: Dynamic model label** — Evidence: Browser screenshot shows "Analyzed with Gemini 3.1-pro" badge (not hardcoded "Gemini 3-flash"). The `model` key is now stored in the date_labels entry from `GEMINI_MODEL` at call time.

- [x] **Fix 3: GEDCOM reasoning in Photo Detective Evidence** — Evidence: Browser screenshot shows "Geographic Analysis" card with three subsections:
  - VISUAL EVIDENCE: "Hilly terrain with a mix of 1920s-style brick multi-family apartment buildings..."
  - GENEALOGICAL CONTEXT: "Genealogical records confirm that Leon Capeluto and his family resided continuously in Asheville, North Carolina from 1928 through 1940..."
  - MISSING CHILD ANALYSIS: "Three children are present... Betty Susan (born 1935), is absent..."

## Root Causes Found

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| Location doesn't persist | `datetime` not imported → NameError → silent write failure | Added `from datetime import datetime, timezone` |
| Location doesn't persist | Deploy overwrites volume files | Added safety gate for `reanalyzed_at` entries |
| Location doesn't persist | File not created if missing | Changed `if exists()` to create-if-missing |
| Wrong model label | `new_entry` dict missing `model` key | Added `"model": GEMINI_MODEL` to entry |
| No GEDCOM reasoning | `_detective_evidence_section` only showed date evidence | Added Geographic Analysis card with location_evidence |

## Tests Added
- 8 new tests in test_reanalyze.py (model label, location evidence, detective evidence cards)
- 3 new tests in test_deploy_safety_gate.py (date_labels/photo_locations protection)
- All 110 related tests pass, 551 ML tests pass

## Commits
1. `5409ae7` — Location persistence + dynamic model label + GEDCOM reasoning display
2. `b0feb56` — Protect reanalyzed date_labels + photo_locations from deploy overwrite
3. `1de56bf` — Add missing datetime import (actual root cause of write failures)

## Browser Verification
- Victoria Capuano Capeluto photo (746dd11e5b4d86a1): PASS
  - Re-analyze returns Asheville with GEDCOM context
  - Page refresh shows Asheville (persisted)
  - Model badge shows "Gemini 3.1-pro"
  - Geographic Analysis card shows visual + biographical + missing child evidence
  - Leaflet map centered on Asheville, NC

## Deferred
None — all 3 user feedback items resolved.

## Red Flags
- [LOW] The `location_estimate` field in date_labels.json is redundant with `location_name` in photo_locations.json — but both are populated correctly now.
- [LOW] Broad `except Exception` blocks hide errors like the datetime NameError. Consider narrowing these in a future session.

## Next Session Should Verify
1. Re-analyze persists across a deploy (not just a page refresh)
2. The safety gate correctly blocks overwriting reanalyzed entries on next deploy
