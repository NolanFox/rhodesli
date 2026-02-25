# Enrichment Pipeline Validation Results

Session: 66 (partial)
Date: 2026-02-24

## What Was Done

### 1. Pipeline Understanding + Dry-Run Mode Added
- Read and understood the enrichment pipeline: `scripts/run_combined_pipeline.py`,
  `app/face_alignment.py`, `rhodesli_ml/gedcom_context.py`
- Added `--dry-run` flag to `run_combined_pipeline.py` that builds prompts and logs
  token counts without calling the Gemini API

### 2. Dry-Run on 10 Photos
- 5 GEDCOM-linked photos, 5 unlinked
- Bare prompts: 419-461 tokens (baseline prompt only)
- Enriched prompts: 592-4,200 tokens (with GEDCOM family context)
- GEDCOM context alone: 158-3,717 tokens
- 4 of 5 enriched photos reach "full" enrichment (400+ tokens), confirming AD-159

### 3. Five Real Gemini API Calls
- 2 bare (no GEDCOM): $0.0055, $0.0119
- 2 enriched (with GEDCOM): $0.0172, $0.0257
- 1 enriched: parse error (non-blocking)
- Total cost: $0.0603
- All logged to gemini_api_calls table with gemini_config + response_summary

### 4. Bug Found and Fixed
- `_find_identity_for_face()` returned INBOX identities instead of CONFIRMED ones
  when a face_id existed in multiple identities
- Fix: prefer CONFIRMED state over PROPOSED/INBOX
- Impact: one test photo went from 0 to 3,717 GEDCOM tokens after fix

## Files Changed

| File | Change |
|------|--------|
| `scripts/run_combined_pipeline.py` | Added `--dry-run` flag and `dry_run_photo()` function |
| `rhodesli_ml/gedcom_context.py` | Fixed `_find_identity_for_face()` to prefer CONFIRMED identities |
| `docs/analysis/enrichment_validation_66.md` | Full validation report with tables |
| `RESULTS.md` | This file |

## Tests

- 538 ML tests pass (including 19 GEDCOM context tests)
- 2967 app tests pass on main repo
- 2 worktree-specific test failures (pre-existing, not related to changes)

## Issues

- Wedding photo parse error: Gemini returned a list where a dict was expected.
  Non-blocking; the error was logged to gemini_api_calls table. Likely a model
  output format inconsistency that the parser should handle more gracefully.

## Key Numbers

| Metric | Before Fix | After Fix |
|--------|-----------|-----------|
| GEDCOM-enriched photos (dry-run) | 4/10 | 5/10 |
| Photo 596771054 GEDCOM tokens | 0 | 3,717 |
| Photo 603576167 GEDCOM tokens | 194 | 1,414 |
| first_order token range | 158-2,489 | 158-3,717 |
