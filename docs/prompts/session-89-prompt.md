# Session 89: Wire GEDCOM Context into Location Estimation

**Context**: `docs/session_context/session-89-context.md`
**Predecessor**: Session 88 (scoring fixes, harness improvements)

## Problem Statement

Photo 746dd11e5b4d86a1 (Image 961_compress.jpg) shows Victoria Capuano Capeluto with 3 of her children at **33 Elizabeth Street, Asheville, NC** circa Autumn 1934. The app displays **"Brooklyn, New York"** because Gemini analyzed the photo using visual cues only (brick apartment + sun porches) and guessed NYC.

The GEDCOM-enriched Gemini prompt was **designed in Session 81 (AD-192)** and has a **full test suite proving it works** (`TestAshevilleGroundTruth` in `rhodesli_ml/tests/test_gedcom_context.py`). But the interactive estimate route (`app/estimate_routes.py`) never wires in the GEDCOM context. This is a **design-implementation gap** — the infrastructure works, it was just never plugged in.

**Second gap**: The interactive estimate route (`_call_gemini_date_estimate()`) doesn't log API calls to the Supabase `gemini_api_calls` table (AD-152). The batch pipeline logs correctly, but interactive calls are invisible. Every Gemini call must be logged for cost tracking, model analysis, and future fine-tuning.

## Ground Truth (Victoria Capuano Photo)
- **Photo**: 746dd11e5b4d86a1 = Image 961_compress.jpg
- **People**: Victoria Capuano (b.1908 Rhodes) + 3 children: Selma (b.1926), Anita (b.1931), Nace (b.1933 Mar)
- **Location**: 33 Elizabeth Street, Asheville, NC (Victoria+Leon resided there 1928-1940)
- **Date**: ~Autumn 1934 (3 of 5 children present; Betty b.1950 and Vida b.1945 not yet born)
- **Victoria is almost certainly pregnant with Nolan's grandmother Betty** — deeply personal photo

## Current Data (WRONG)
```json
// data/photo_locations.json line 1673
{
  "photo_id": "746dd11e5b4d86a1",
  "lat": 40.6782, "lng": -73.9442,
  "location_name": "Brooklyn, New York",
  "location_estimate": "Likely New York City (Bronx or Brooklyn), USA, based on brick apartment architecture with sun porches.",
  "confidence": "high"
}
```

## Two Diverged Prompt Systems (Root Cause)

| System | File | Has GEDCOM? | Has Location? | Logs to Supabase? |
|--------|------|-------------|---------------|-------------------|
| Interactive (Estimate page) | `app/estimate_routes.py` L358-384 `_GEMINI_DATE_PROMPT` | NO | NO | NO |
| Batch pipeline | `rhodesli_ml/gemini_extraction.py` `build_extraction_prompt()` | YES | YES (3-step) | YES |

The interactive prompt is a stripped-down visual-only version from Feb 14. It doesn't even ask for location. The batch prompt has everything — GEDCOM, location, face analysis, cultural markers. They were never unified.

## Prior Work to Build On

| Session | What was built | AD | Breadcrumb |
|---------|---------------|-----|------------|
| 61C | GEDCOM context builder (5 enrichment variants), curated variant optimal | AD-148 | `rhodesli_ml/gedcom_context.py` |
| 64 | `gemini_api_calls` Supabase table, `log_gemini_call()` | AD-152 | `app/supabase_data.py` L503, `scripts/sql/create_gemini_api_calls.sql` |
| 65b | GEDCOM identity linking admin UI, enrichment pipeline fix | AD-159, AD-160 | `gedcom_identity_links` Supabase table |
| 81 | AD-192: GEDCOM-enriched location prompting. Asheville test suite. Dry-run prompt. | AD-192, AD-193 | `rhodesli_ml/tests/test_gedcom_context.py` L378-486 |
| 81 | AD-193: Photo location data model + Leaflet UX | AD-193 | `data/photo_locations.json`, `app/main.py` L~1599 |

**Key reference**: `docs/session_context/session_81_asheville_prompt.txt` — the full enriched prompt that should have been wired in.

## API Call Logging Requirements (Owner Priority)

Every Gemini API call MUST be logged to Supabase `gemini_api_calls` with full provenance:
- **model_used**: Which Gemini model (e.g., gemini-2.0-flash, gemini-3.1-pro)
- **call_type**: 'date_estimation', 'alignment', 'enrichment', 'combined'
- **gemini_config** (JSONB): `{"enrichment_level": "curated", "prompt_version": "v3_gedcom", "gedcom_variant": "first_order", "temperature": 0.1}`
- **response_summary** (JSONB): Key fields from response (location, date, confidence — not full response)
- **prompt_tokens, completion_tokens, total_tokens**: Token counts
- **cost_usd**: Per-call cost
- **latency_ms**: Response time
- **status**: success/error/timeout
- **batch_id**: For grouping related calls

This data enables: analysis of estimate shifts over time, model comparison, cost tracking, potential future fine-tuning. Use existing `log_gemini_call()` from `app/supabase_data.py` — it already supports all these fields.

---

## Session Protocol

- Set `.claude/current_session.txt` to `89`
- Read `tasks/lessons.md` and `tasks/todo.md` at start
- Create `docs/session_logs/session-89-log.md` with phase checklist
- Commit after every act (conventional commits)
- Use `/clear` between acts (NEVER /compact)
- Run `/simplify` after implementation acts
- Use `/session-review` at session end
- Browser verify with Claude Chrome (admin is logged in)
- Screenshots to `docs/screenshots/session-89/`

## Parallelization Analysis

Acts 1 is sequential (orient). Acts 2+3 are sequential (3 depends on 2). Act 4 (batch script) could be parallelized with Act 2 if using a worktree, but they share `estimate_routes.py` understanding — safer to keep sequential. Act 5 (tests/verification) must be last.

**Recommendation**: Sequential execution. This is a focused integration session, not a multi-track session.

---

## Deliverables

### Act 1: Orient + Trace the Full Pipeline (10 min)
1. Read this prompt. Read `tasks/lessons.md`, `tasks/todo.md`, and `docs/session_context/session-89-context.md`.
2. Read the prior ADs: AD-148 (curated variant optimal), AD-152 (API logging), AD-159 (enrichment fix), AD-192 (location prompting), AD-193 (location UX).
3. Trace the complete data flow for photo 746dd11e5b4d86a1:
   - Original Gemini result: `data/date_labels.json` L9395
   - Geocoding: `scripts/geocode_photos.py`
   - Display: photo page route + `data/photo_locations.json` L1673
4. Read both prompt systems:
   - Interactive: `app/estimate_routes.py` L358-384 (`_GEMINI_DATE_PROMPT`)
   - Batch: `rhodesli_ml/gemini_extraction.py` `build_extraction_prompt()`
5. Read how batch pipeline loads GEDCOM: `scripts/run_combined_pipeline.py` (search for `gedcom_context`, `parsed_gedcom`, `gedcom_face_links`)
6. Read how API calls are logged: `app/supabase_data.py` L503 (`log_gemini_call()`)
7. Confirm Asheville tests pass: `source venv/bin/activate && pytest rhodesli_ml/tests/test_gedcom_context.py::TestAshevilleGroundTruth -v`
8. Commit: `docs(session): session 89 orient — trace pipeline, confirm existing tests`

### Act 2: Unify Prompts + Wire GEDCOM + Add API Logging (30 min)
**Goal**: Replace the stripped-down `_GEMINI_DATE_PROMPT` with the full `build_extraction_prompt()` and add GEDCOM context + API logging.

1. In `app/estimate_routes.py`:
   a. Replace `_GEMINI_DATE_PROMPT` usage with `build_extraction_prompt()` from `rhodesli_ml/gemini_extraction.py`
   b. Before calling Gemini, check if the photo has identified faces with GEDCOM links:
      - Get identified faces from identities registry
      - Query `gedcom_identity_links` from Supabase (see how admin UI does it)
      - If links exist: `build_photo_context()` → `build_extraction_prompt(gedcom_context=context)`
      - If no links: `build_extraction_prompt()` (visual-only, same as before but now with location section)
   c. After Gemini call, log via `log_gemini_call()` with full provenance:
      - `call_type='date_estimation'`
      - `gemini_config={"enrichment_level": ..., "prompt_version": ..., "gedcom_variant": ..., "temperature": 0.1}`
      - `response_summary={"location": ..., "date": ..., "confidence": ...}`
      - Token counts, cost, latency
   d. Parse the location from Gemini's response (now included in the enriched prompt output)
   e. Update `photo_locations.json` entry if location is returned

2. GEDCOM data loading (check `scripts/run_combined_pipeline.py` for patterns):
   - `parsed_gedcom`: Load GEDCOM from `data/gedcom/` directory
   - `gedcom_face_links`: Query Supabase `gedcom_identity_links` table
   - `identities`: From identity registry (already loaded in app)
   - Cache these at module level — don't reload per request

3. Graceful degradation matrix:
   | GEDCOM available? | Gemini key? | Behavior |
   |-------------------|-------------|----------|
   | Yes + links exist | Yes | Full enriched prompt with GEDCOM |
   | Yes + no links | Yes | Enriched prompt without GEDCOM (still has location section) |
   | No | Yes | Enriched prompt without GEDCOM |
   | Any | No | ML-only fallback (existing behavior) |

4. Write tests:
   - Test that GEDCOM context is included when links exist
   - Test graceful fallback when no GEDCOM data
   - Test that `log_gemini_call()` is called on every Gemini invocation
   - Test response parsing extracts location correctly
   - Mock Supabase calls in tests

5. Run `make test-fast` + `make test-ml`
6. Write AD entry (AD-2xx): "Unified Gemini Prompt — Interactive Route Uses Enriched Prompt"
   - Document: what was chosen, what was rejected, which sessions built the components
   - Breadcrumb: AD-148, AD-152, AD-192
7. Commit: `feat(estimate): wire GEDCOM context + API logging into interactive estimate route (AD-2xx)`

### Act 3: Reprocess the Asheville Photo (15 min)
**Goal**: Re-run Gemini on photo 746dd11e5b4d86a1 with GEDCOM-enriched prompt. This is the litmus test.

1. Create `scripts/reprocess_with_gedcom.py` with `--photo-id` flag
   - Loads the photo image from R2 or local
   - Builds GEDCOM context for identified faces
   - Calls Gemini with enriched prompt
   - Logs call to Supabase
   - Updates `data/date_labels.json` with new result
   - Updates `data/photo_locations.json` with new location
2. Run: `python scripts/reprocess_with_gedcom.py --photo-id 746dd11e5b4d86a1`
3. Verify output:
   - Location estimate mentions Asheville (not Brooklyn)
   - `photo_locations.json` updated with Asheville coords (~35.5951, -82.5515)
   - Supabase `gemini_api_calls` has a new row with full provenance
4. If Gemini still says Brooklyn: check if GEDCOM context is actually being injected, print the prompt, debug
5. Commit: `fix(data): reprocess Asheville photo with GEDCOM context — location corrected`

### Act 4: Batch Capability + Dry Run (15 min)
**Goal**: Extend the script to support batch reprocessing.

1. Add to `scripts/reprocess_with_gedcom.py`:
   - `--dry-run` mode: list all photos that would benefit from GEDCOM reprocessing (have identified faces + GEDCOM links) without calling Gemini
   - `--batch` mode: process all eligible photos (with rate limiting)
   - `--limit N`: process at most N photos
   - Cost estimation in dry-run output
2. Run `--dry-run` to see how many photos would be affected, log the count
3. Do NOT run full batch in this session — just validate the capability
4. Commit: `feat(scripts): batch GEDCOM reprocessing with dry-run and cost estimation`

### Act 5: Deploy + Browser Verification + Assessment (15 min)
1. `make test-fast` + `make test-ml` — all pass
2. Run `/simplify` on changed code
3. Push to main (triggers Railway deploy)
4. Wait for deploy, then browser verify with Claude Chrome:
   - Navigate to https://rhodesli.nolanandrewfox.com/photo/746dd11e5b4d86a1
   - Screenshot the map — should show Asheville, NC (not Brooklyn)
   - Screenshot the location estimate text
   - Test the Estimate page with a new upload — verify it still works
   - Save screenshots to `docs/screenshots/session-89/`
5. Run `/session-review`
6. Write `docs/assessments/session-89-assessment.md`
7. Update mandatory docs:
   - `CHANGELOG.md` — v0.91.2 session 89 entry
   - `ROADMAP.md` — update relevant items
   - `BACKLOG.md` — update status of any related items
   - `docs/ml/ALGORITHMIC_DECISIONS.md` — new AD entry with breadcrumbs
   - `docs/roadmap/SESSION_HISTORY.md` — session 89 entry
   - `SESSION_LOG.md` + archive to `docs/session_logs/session-89-log.md`
8. Verify all breadcrumbs:
   - AD-2xx references AD-148, AD-152, AD-192, AD-193
   - Context file references predecessor (session 88) and this prompt
   - Assessment references context file and prompt
   - BACKLOG items updated with session 89 reference

## Key File Reference
| File | Purpose | Lines of Interest |
|------|---------|-------------------|
| `app/estimate_routes.py` | Interactive Gemini calls — **THE FILE TO CHANGE** | L358-384: `_GEMINI_DATE_PROMPT`, L385-437: `_call_gemini_date_estimate()`, L654: caller |
| `rhodesli_ml/gemini_extraction.py` | Enriched prompt builder — **USE THIS** | L199+: `build_extraction_prompt(gedcom_context=)` |
| `rhodesli_ml/gedcom_context.py` | GEDCOM context builder — **USE THIS** | L27+: `build_photo_context()` |
| `app/supabase_data.py` | API call logging — **WIRE THIS IN** | L503: `log_gemini_call()` |
| `scripts/run_combined_pipeline.py` | Reference for GEDCOM loading pattern | Search: `parsed_gedcom`, `gedcom_face_links` |
| `rhodesli_ml/tests/test_gedcom_context.py` | Asheville ground truth tests | L378-486: `TestAshevilleGroundTruth` |
| `data/photo_locations.json` | Current (wrong) location data | L1673: photo 746dd11e5b4d86a1 |
| `data/date_labels.json` | Current Gemini result | L9395: photo 746dd11e5b4d86a1 |
| `scripts/geocode_photos.py` | Text-to-coordinates mapping | L122-150: dictionary match |
| `docs/session_context/session_81_asheville_prompt.txt` | Full enriched prompt reference | Shows what Gemini SHOULD receive |
| `docs/session_context/session-89-context.md` | Full context for this session | Root cause analysis, prior work, gaps |
| `scripts/sql/create_gemini_api_calls.sql` | Supabase table schema | AD-152 |

## Acceptance Criteria
- [ ] Photo 746dd11e5b4d86a1 shows "Asheville, North Carolina" on the map (not Brooklyn)
- [ ] `app/estimate_routes.py` uses `build_extraction_prompt()` (not `_GEMINI_DATE_PROMPT`)
- [ ] GEDCOM context included when identified faces have GEDCOM links
- [ ] Every interactive Gemini call logged to Supabase `gemini_api_calls` with full provenance
- [ ] `gemini_config` JSONB includes enrichment_level, prompt_version, gedcom_variant
- [ ] Batch reprocessing script with `--dry-run`, `--photo-id`, and `--batch` modes
- [ ] Graceful fallback: photos without GEDCOM data still work as before
- [ ] All tests pass (`make test-fast` + `make test-ml`)
- [ ] Browser verified via Claude Chrome with screenshots
- [ ] AD entry with breadcrumbs to AD-148, AD-152, AD-192, AD-193
- [ ] Assessment file, session log, CHANGELOG, ROADMAP, BACKLOG all updated

## Non-Goals (Out of Scope)
- Reprocessing ALL 274 photos (defer to batch run session)
- Modifying the Leaflet map UI
- Changes to the GEDCOM context builder itself (it works correctly)
- Auto-trigger for "faces identified → re-estimate" (future session)
- Custom model development from API call data (future)
