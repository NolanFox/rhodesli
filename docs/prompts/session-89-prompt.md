# Session 89: Wire GEDCOM Context into Location Estimation

## Problem Statement
Photo 746dd11e5b4d86a1 (Image 961_compress.jpg) shows Victoria Capuano Capeluto with 3 of her children at **33 Elizabeth Street, Asheville, NC** circa Autumn 1934. The app displays **"Brooklyn, New York"** because Gemini analyzed the photo using visual cues only (brick apartment + sun porches) and guessed NYC.

The GEDCOM-enriched Gemini prompt was **designed in Session 81 (AD-192)** and has a **full test suite proving it works** (`TestAshevilleGroundTruth` in `rhodesli_ml/tests/test_gedcom_context.py`). But the interactive estimate route (`app/estimate_routes.py`) never wires in the GEDCOM context. This is a design-implementation gap, not a missing feature.

## Ground Truth (Victoria Capuano Photo)
- **Photo**: 746dd11e5b4d86a1 = Image 961_compress.jpg
- **People**: Victoria Capuano (b.1908 Rhodes) + 3 children: Selma (b.1926), Anita (b.1931), Nace (b.1933 Mar)
- **Location**: 33 Elizabeth Street, Asheville, NC (Victoria+Leon resided there 1928-1940)
- **Date**: ~Autumn 1934 (3 of 5 children present; Betty b.1950 and Vida b.1945 not yet born)
- **Victoria is almost certainly pregnant with Betty's mother (my grandmother)** — this is a deeply personal photo for the project owner

## Current Data (WRONG)
```json
// data/photo_locations.json line 1673
{
  "photo_id": "746dd11e5b4d86a1",
  "lat": 40.6782,
  "lng": -73.9442,
  "location_name": "Brooklyn, New York",
  "location_estimate": "Likely New York City (Bronx or Brooklyn), USA, based on brick apartment architecture with sun porches.",
  "confidence": "high"
}
```

```json
// data/date_labels.json line 9395 — Gemini result from Feb 14
{
  "photo_id": "746dd11e5b4d86a1",
  "source": "gemini",
  "model": "gemini-3-flash-preview",
  "location_estimate": "Likely New York City (Bronx or Brooklyn), USA, based on brick apartment architecture with sun porches."
}
```

## Architecture: What Exists vs What's Missing

### EXISTS (built in Sessions 61C/81, tested, working):
| Component | File | Status |
|-----------|------|--------|
| GEDCOM context builder | `rhodesli_ml/gedcom_context.py` → `build_photo_context()` | Tested, 5 variants |
| Enhanced Gemini prompt with location section | `rhodesli_ml/gemini_extraction.py` → `build_extraction_prompt()` | Has `gedcom_context` param |
| Asheville ground-truth test suite | `rhodesli_ml/tests/test_gedcom_context.py` lines 378-486 | PASSING |
| Full Asheville dry-run prompt | `docs/session_context/session_81_asheville_prompt.txt` | Reference |
| Location schema + Leaflet map UI | `data/photo_locations.json` + `app/main.py` lines ~1599-1645 | Live in prod |
| Geocoding script | `scripts/geocode_photos.py` | Working |
| AD-192 | GEDCOM-enriched location prompting design | Complete |
| AD-193 | Photo location data model + UX | Complete |

### MISSING (the gap):
| What | Where | Why |
|------|-------|-----|
| GEDCOM context in estimate route | `app/estimate_routes.py` line 408 | `_call_gemini_date_estimate()` sends `_GEMINI_DATE_PROMPT` (visual only), ignores GEDCOM |
| Batch reprocessing with GEDCOM | No script wired | Can't re-run existing photos with enriched prompts |
| "Re-estimate" trigger | No mechanism | When faces are identified, location isn't re-estimated |

## Deliverables

### Act 1: Orient + Trace the Full Pipeline (10 min)
1. Read this prompt. Read `tasks/lessons.md` and `tasks/todo.md`.
2. Trace the complete data flow for photo 746dd11e5b4d86a1:
   - How was the Gemini result originally generated? (check `data/date_labels.json`)
   - How was it geocoded? (check `scripts/geocode_photos.py`)
   - How is it displayed? (check photo page route)
3. Read `rhodesli_ml/gemini_extraction.py` `build_extraction_prompt()` to understand the GEDCOM injection point
4. Read `app/estimate_routes.py` `_call_gemini_date_estimate()` to see what's missing
5. Confirm the `TestAshevilleGroundTruth` tests pass: `source venv/bin/activate && pytest rhodesli_ml/tests/test_gedcom_context.py::TestAshevilleGroundTruth -v`

### Act 2: Wire GEDCOM Context into Estimate Route (30 min)
**Goal**: When a photo has identified faces with GEDCOM links, the Gemini call should include biographical context.

1. In `app/estimate_routes.py`, modify `_call_gemini_date_estimate()` (or the caller at line ~654) to:
   - Look up identified faces in the photo
   - Check if any have GEDCOM links
   - If yes, call `build_photo_context()` to get GEDCOM context string
   - Pass it to `build_extraction_prompt()` from `rhodesli_ml/gemini_extraction.py`
   - Use the enriched prompt instead of `_GEMINI_DATE_PROMPT`
2. The GEDCOM data sources needed:
   - `parsed_gedcom`: load from `data/gedcom/` (check how `scripts/run_combined_pipeline.py` loads it)
   - `gedcom_face_links`: stored in Supabase `gedcom_identity_links` table (check how admin UI reads it)
   - `identities`: from the identity registry
3. Handle graceful degradation: if no GEDCOM data available, fall back to visual-only prompt (current behavior)
4. Write tests for the new wiring

### Act 3: Reprocess the Asheville Photo (15 min)
**Goal**: Re-run Gemini on photo 746dd11e5b4d86a1 with GEDCOM-enriched prompt and verify it returns "Asheville".

1. Create a script or admin action to re-estimate a single photo with GEDCOM context
2. Run it on 746dd11e5b4d86a1
3. Update `data/date_labels.json` with the new Gemini result
4. Re-run `scripts/geocode_photos.py` to update `photo_locations.json`
5. Verify the map now shows Asheville, NC (lat ~35.5951, lng ~-82.5515)

### Act 4: Batch Reprocessing Capability (20 min)
**Goal**: Enable re-running all photos that have identified faces + GEDCOM links.

1. Create `scripts/reprocess_with_gedcom.py` that:
   - Finds all photos with identified faces that have GEDCOM links
   - Calls the enriched Gemini prompt for each
   - Updates `date_labels.json` and `photo_locations.json`
   - Has `--dry-run` mode that shows what would be reprocessed without calling Gemini
   - Has `--photo-id` flag to process a single photo
   - Logs API costs per call
2. Run `--dry-run` to see how many photos would be affected
3. Do NOT run full batch in this session (costs money) — just validate the capability

### Act 5: Tests + Verification (15 min)
1. `make test-fast` — all existing tests pass
2. `make test-ml` — all ML tests pass
3. Browser verify: navigate to https://rhodesli.nolanandrewfox.com/photo/746dd11e5b4d86a1 and confirm the map shows Asheville (after deploy)
4. Write assessment

## Key File Reference
| File | Purpose | Lines of Interest |
|------|---------|-------------------|
| `app/estimate_routes.py` | Interactive Gemini calls | L385-437: `_call_gemini_date_estimate()`, L654: caller |
| `rhodesli_ml/gemini_extraction.py` | Prompt builder with GEDCOM support | L199+: `build_extraction_prompt(gedcom_context=)` |
| `rhodesli_ml/gedcom_context.py` | GEDCOM context builder | L27+: `build_photo_context()` |
| `rhodesli_ml/tests/test_gedcom_context.py` | Asheville ground truth tests | L378-486: `TestAshevilleGroundTruth` |
| `data/photo_locations.json` | Current (wrong) location data | L1673: photo 746dd11e5b4d86a1 |
| `data/date_labels.json` | Current Gemini result | L9395: photo 746dd11e5b4d86a1 |
| `scripts/geocode_photos.py` | Text → coordinates mapping | L122-150: dictionary match logic |
| `docs/session_context/session_81_asheville_prompt.txt` | Full enriched prompt example | Reference for expected output |
| `docs/ml/ALGORITHMIC_DECISIONS.md` | AD-192, AD-193 | Location estimation design |

## Acceptance Criteria
- [ ] Photo 746dd11e5b4d86a1 shows "Asheville, North Carolina" on the map (not Brooklyn)
- [ ] `app/estimate_routes.py` uses GEDCOM context when available, falls back gracefully
- [ ] Batch reprocessing script exists with `--dry-run` and `--photo-id` modes
- [ ] All tests pass (`make test-fast` + `make test-ml`)
- [ ] No regression to photos without GEDCOM data (they still work as before)
- [ ] AD entry documenting the wiring decision

## Non-Goals (Out of Scope)
- Reprocessing ALL 274 photos (defer to separate batch run)
- Changing the geocoding dictionary in `scripts/geocode_photos.py`
- Modifying the Leaflet map UI
- Any changes to the GEDCOM context builder itself (it's working correctly)
