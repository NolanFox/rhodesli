# Session 89 Log
Started: 2026-03-04
Prompt: docs/prompts/session-89-prompt.md
Context: docs/session_context/session-89-context.md

## Phase Checklist
- [x] Act 1: Orient + Trace Pipeline
- [x] Act 2: Unify Prompts + Wire GEDCOM + API Logging
- [x] Act 3: Admin Re-analyze Button
- [x] Act 4+5: Batch Script (Asheville reprocess deferred to deploy)
- [ ] Act 6: Deploy + Browser Verification + Assessment

## Act 1: Orient
- Read prompt, context, lessons, todo
- Traced data flow for 746dd11e5b4d86a1 (Asheville photo):
  - photo_locations.json shows Brooklyn (WRONG — lat 40.6782, lng -73.9442)
  - Root cause: `_GEMINI_DATE_PROMPT` in estimate_routes.py is visual-only, no location, no GEDCOM
  - Batch pipeline in `gemini_extraction.py` has full enriched prompt with GEDCOM support
  - Two prompt systems never unified
- Read both prompt systems:
  - Interactive: `app/estimate_routes.py` L358-384 — stripped-down, no location section
  - Batch: `rhodesli_ml/gemini_extraction.py` L193+ — full extraction with presets, GEDCOM, location
- GEDCOM loading pattern: `load_gedcom_data()` in `run_combined_pipeline.py` L178+ loads from Supabase (gedcom_face_links + gedcom_individuals with pagination)
- `_load_gedcom_face_links()` in `app/main.py` L27961 — cached, returns identity_id -> {gedcom_id, confidence, linked_by}
- API logging: `log_gemini_call()` in `app/supabase_data.py` L503 — takes photo_id, model_used, call_type + kwargs
- Gemini config: `rhodesli_ml/gemini_config.py` — GEMINI_MODEL="gemini-3.1-pro-preview", MODEL_PRICING dict
- Asheville tests: 4/4 PASS (TestAshevilleGroundTruth)
- Key insight: `build_gedcom_context()` in `run_combined_pipeline.py` L129 is the wrapper that loads GEDCOM and calls `build_photo_context()` — can reuse this pattern

## Act 2: Unify Prompts + Wire GEDCOM + API Logging
- Replaced `_GEMINI_DATE_PROMPT` with `build_extraction_prompt(preset="quick")`
- Added `gedcom_context` parameter to `_call_gemini_date_estimate()`
- Added full API call logging via `log_gemini_call()` in finally block
- Enrichment level, prompt version, GEDCOM variant in `gemini_config` JSONB
- Location display in estimate results
- 10 new tests (all pass)

## Act 3: Admin Re-analyze Button
- POST /api/photo/{photo_id}/reanalyze — admin-only endpoint
- Loads photo from R2/local, builds GEDCOM context, calls Gemini
- Updates date_labels.json + photo_locations.json
- Returns HTMX partial with diff ("Brooklyn → Asheville")
- Button added to AI Analysis section header (admin-only)
- Geocoding for Asheville, Rhodes, NYC, Miami, etc.
- 14 new tests (all pass)

## Acts 4+5: Batch Script
- scripts/reprocess_with_gedcom.py with --dry-run, --photo-id, --batch modes
- Cost estimation, rate limiting, change diffs
- Asheville photo reprocessing deferred to production deploy

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed
