# Session 89 Context: Wire GEDCOM into Location Estimation

**Predecessor**: Session 88 (scoring fixes, card failures, harness improvements)
**Prompt**: `docs/prompts/session-89-prompt.md`
**Owner request**: Nolan noticed photo 746dd11e5b4d86a1 (Victoria Capuano, Asheville ~1934) still shows Brooklyn. Wants to understand why GEDCOM enrichment never got wired in despite significant prior work.

## The Problem

Photo 746dd11e5b4d86a1 (Image 961_compress.jpg) shows Victoria Capuano Capeluto with 3 of her children at **33 Elizabeth Street, Asheville, NC** circa Autumn 1934. Victoria is almost certainly pregnant with Nolan's grandmother Betty. The app shows **"Brooklyn, New York"** because Gemini was only given visual cues.

## Root Cause Analysis

### Two Gemini Prompt Systems Exist (Diverged)

There are **two completely separate Gemini prompt paths** that were never unified:

1. **Interactive estimate route** (`app/estimate_routes.py` L358-384):
   - Uses `_GEMINI_DATE_PROMPT` — a stripped-down visual-only prompt
   - Does NOT ask for location estimation at all
   - Does NOT accept GEDCOM context
   - Does NOT log API calls to Supabase `gemini_api_calls` table
   - This is what runs when users use the Estimate page

2. **Batch/combined pipeline** (`rhodesli_ml/gemini_extraction.py` + `scripts/run_combined_pipeline.py`):
   - Uses `build_extraction_prompt()` — the full enriched prompt
   - Has GEDCOM context injection (`gedcom_context` parameter)
   - Has 3-step location analysis (visual + biographical + confidence)
   - Logs all API calls to Supabase via `log_gemini_call()`
   - This is what runs during batch processing (never re-run for existing photos)

### Why the Gap Exists

| Session | What was built | What wasn't connected |
|---------|---------------|----------------------|
| 61C | GEDCOM context builder (`gedcom_context.py`), 5 enrichment variants | Not wired to interactive route |
| 64 | `gemini_api_calls` Supabase table, `log_gemini_call()` | Only wired to batch pipeline + face_alignment, NOT estimate_routes |
| 65b | GEDCOM linking admin UI | Links exist but estimate route doesn't query them |
| 81 | AD-192: GEDCOM-enriched location prompting design. Full Asheville test suite. Dry-run prompt saved. | Prompt only added to `gemini_extraction.py`, not `estimate_routes.py` |

**The interactive estimate route was never updated after the enriched prompt was built.** It still uses the original Feb 14 visual-only prompt.

## What Currently Exists (Working, Tested)

| Component | File | Status |
|-----------|------|--------|
| GEDCOM context builder | `rhodesli_ml/gedcom_context.py` → `build_photo_context()` | 5 variants, tested |
| Enriched Gemini prompt | `rhodesli_ml/gemini_extraction.py` → `build_extraction_prompt()` | Has `gedcom_context` param, location section |
| Asheville ground-truth tests | `rhodesli_ml/tests/test_gedcom_context.py` L378-486 | `TestAshevilleGroundTruth` PASSING |
| Full Asheville dry-run prompt | `docs/session_context/session_81_asheville_prompt.txt` | Reference |
| API call logging | `app/supabase_data.py` → `log_gemini_call()` | Working, used by batch pipeline |
| Supabase table | `gemini_api_calls` (AD-152) | Has model, tokens, cost, config, response_summary |
| GEDCOM links in Supabase | `gedcom_identity_links` table | Admin UI for linking |
| Location display UI | `data/photo_locations.json` + Leaflet maps | Live in prod |
| Geocoding script | `scripts/geocode_photos.py` | Dictionary-based text → coords |
| AD-192 | GEDCOM-enriched location prompting | Design complete |
| AD-193 | Photo location data model + UX | Schema + Leaflet implemented |

## What's Missing (The Gaps)

### Gap 1: Interactive Route Uses Wrong Prompt
`app/estimate_routes.py` L408 sends `_GEMINI_DATE_PROMPT` (visual-only, no location, no GEDCOM). Should use `build_extraction_prompt()` from `rhodesli_ml/gemini_extraction.py`.

### Gap 2: Interactive Route Doesn't Log API Calls
`_call_gemini_date_estimate()` in estimate_routes.py doesn't call `log_gemini_call()`. Every Gemini call should be logged to Supabase per AD-152. The table tracks: model, prompt/completion tokens, cost, latency, status, gemini_config (which should include enrichment_level/variant), response_summary, batch_id.

### Gap 3: No Mechanism to Re-Estimate Existing Photos
When faces are identified or GEDCOM links are added, there's no trigger to re-run location estimation. Need at minimum a batch script with `--photo-id` for manual re-runs.

### Gap 4: `gemini_api_calls` Missing Prompt Variant Column
The `gemini_config` JSONB field can store enrichment_level, but there's no explicit column for prompt variant/version. For analysis of how results shift over time, we need to know which prompt produced which result. Current schema uses `gemini_config JSONB` — should store `{"enrichment_level": "curated", "prompt_version": "v3_gedcom", "gedcom_variant": "first_order"}`.

## Data Flow: Current vs Target

### Current (Broken)
```
Photo → estimate_routes.py → _GEMINI_DATE_PROMPT (visual only) → Gemini
  → date_labels.json (no location asked) → geocode_photos.py → Brooklyn
  → NO Supabase logging
```

### Target (Fixed)
```
Photo → estimate_routes.py → check identified faces → GEDCOM links?
  → YES: build_photo_context() → build_extraction_prompt(gedcom_context=...)
  → NO: build_extraction_prompt() (visual-only fallback)
  → Gemini (full prompt with location + GEDCOM)
  → log_gemini_call() to Supabase (model, tokens, cost, config, response)
  → date_labels.json + photo_locations.json updated
  → Leaflet map shows correct location
```

## API Call Logging Requirements (Owner Priority)

Nolan wants full provenance on every Gemini call for future analysis:
- **Model**: Which Gemini model (e.g., gemini-2.0-flash, gemini-3.1-pro)
- **Prompt variant**: Which prompt was used (visual-only, enriched, GEDCOM variant)
- **Input**: Token count, enrichment level, GEDCOM variant used
- **Output**: Full response (or structured summary), location estimate, date estimate
- **Timing**: When it ran, latency
- **Cost**: USD per call
- **Photo context**: photo_id, which faces were identified, which GEDCOM links were used

This data enables:
1. Analysis of how location/date estimates shift when GEDCOM is added
2. Comparison across prompt variants and models
3. Cost tracking and optimization
4. Potential future fine-tuning or model development

## Key Algorithmic Decisions (Read Before Implementing)

| AD | Title | Relevance |
|----|-------|-----------|
| AD-139 | Gemini 3.1 Pro for estimation | Current model choice |
| AD-146 | Face alignment via coordinate bridging | How face coords are used |
| AD-148 | Session 61C results — curated variant optimal | Best GEDCOM variant |
| AD-152 | Supabase-first data layer + Gemini logging | API call table design |
| AD-159 | Prompt fidelity + enrichment pipeline | gemini_config + response_summary |
| AD-192 | GEDCOM-enriched location prompting | The 3-step location analysis |
| AD-193 | Photo location data model and UX | Schema + Leaflet display |

## Asheville Photo Ground Truth

- **Photo ID**: 746dd11e5b4d86a1 (Image 961_compress.jpg)
- **Faces**: face0, face1, face2, face3 (4 faces detected)
- **People**: Victoria Capuano + 3 children (Selma b.1926, Anita b.1931, Nace b.1933)
- **Location**: 33 Elizabeth Street, Asheville, NC
- **Date**: ~Autumn 1934 (Betty b.1950 and Vida b.1945 absent → pre-1945)
- **Victoria likely pregnant** — deeply personal photo for Nolan
- **GEDCOM evidence**: Leon + Victoria resided at 33 Elizabeth St, Asheville 1928-1940. Leon's occupation listed as 1930 in Asheville.

## Deferred to Future Sessions

- Full batch reprocessing of all 274 photos (cost implications — separate budget decision)
- Auto-trigger: "faces identified → re-estimate location" webhook
- Fine-tuning or custom model development based on API call data
- Geocoding dictionary expansion (Asheville not currently in dictionary — need to add or use Gemini's structured location output directly)

## Post-Session Planning

### Candidate Next Sessions
- **Session 90**: Batch reprocess top-N photos with GEDCOM links (after Session 89 validates the pipeline)
- **Session 90 alt**: Active learning pipeline — use GEDCOM-enriched results as training signal
