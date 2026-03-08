# GEDCOM Reanalysis — Detailed Schema & Future Analysis

**Parent report:** [GEDCOM_REANALYSIS_REPORT.md](GEDCOM_REANALYSIS_REPORT.md)
**Session:** 93 | **Date:** 2026-03-08 | **AD:** AD-211

---

## Schema Detail: What We Currently Record

**gemini_api_calls table** (Supabase):
- `photo_id`, `model_used`, `call_type` (e.g., "re_analysis")
- `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_usd`
- `latency_ms`, `status`, `error_message`, `rate_limit_type`
- `prompt_text` (full prompt text), `full_response` (JSONB)
- `gedcom_context` (text — the GEDCOM context sent to the model)
- `gemini_config` (JSONB — thinking_level, max_output_tokens, temperature)
- `batch_id`, `created_at`

**date_labels** (JSON + Supabase):
- `estimated_decade`, `best_year_estimate`, `confidence`, `probable_range`
- `reasoning_summary`, `evidence` (structured by category)
- `location_estimate`, `reanalyzed_at`, `reanalyzed_with_gedcom`

**photo_locations** (JSON + Supabase):
- `photo_id`, `lat`, `lng`, `location_name`, `location_estimate`
- `confidence`, `region`, `reanalyzed_at`

## Recommended Schema Additions

```sql
-- Store pre-reanalysis state for delta tracking
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS previous_date_estimate JSONB;
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS previous_location JSONB;

-- Enrichment depth metrics
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS gedcom_token_count INTEGER;
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS gedcom_coverage_pct NUMERIC(5,2);

-- Multi-GEDCOM future
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS gedcom_version TEXT;

-- Value tracking
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS enrichment_changed BOOLEAN;
```

**Priority:**
1. `previous_date_estimate` JSONB — #1 gap. The reprocess script already loads
   old data (lines 145-153), just doesn't persist it to the API call log.
2. `gedcom_token_count` — trivial to add, high analytical value.
3. GEDCOM versioning — hash the GEDCOM file at batch start, store per call.

## Cost Projections

| Scale | GEDCOM-Eligible | Est. Cost | Runtime |
|-------|----------------|-----------|---------|
| Current (295 photos) | 72 | $2.66 | ~79 min |
| 500 photos | ~120 | $4.44 | ~2.2 hrs |
| 1,000 photos | ~250 | $9.25 | ~4.6 hrs |
| 5,000 photos | ~1,250 | $46.25 | ~23 hrs |

## Local/Bespoke ML Models (Future Direction)

At current corpus size (67 high-confidence date estimates), a fine-tuned local
model is not yet viable. The path:

1. **500+ labeled photos**: Minimum for fine-tuning a vision date estimator
2. **Training data**: Use Gemini estimates as labels (teacher-student approach)
3. **Cost reduction**: Local inference at ~$0 vs $0.037/photo
4. **Risk**: Small corpus limits generalization; Gemini estimates have their own biases

This is **second-tier ML work** — worth pursuing once the corpus is 5-10x larger.

## Value-Add Decision Framework (For Scaling)

| Photo Category | API Call Value | Recommendation |
|---------------|---------------|----------------|
| New GEDCOM data linked | HIGH | Always reanalyze |
| Updated model available | MEDIUM | Batch reanalyze all |
| No GEDCOM, never analyzed | MEDIUM | Analyze once |
| Already high-conf, no new data | LOW | Skip |
| Content safety blocked | NONE | Skip until API settings change |

## Breadcrumbs

- **AD-211**: GEDCOM batch reanalysis value assessment (ALGORITHMIC_DECISIONS.md)
- **User feedback**: docs/session_context/session-93-user-feedback.md
- **Parent report**: docs/ml/GEDCOM_REANALYSIS_REPORT.md
- **Before/after examples**: docs/ml/GEDCOM_REANALYSIS_EXAMPLES.md
- **Reprocess script**: scripts/reprocess_with_gedcom.py
- **GEDCOM context builder**: rhodesli_ml/gedcom_context.py
- **Estimate routes**: app/estimate_routes.py (Gemini call + logging)
- **API call logging**: app/supabase_data.py (log_gemini_api_call)
- **Schema SQL**: scripts/sql/create_gemini_api_calls.sql
- **ROADMAP near-term**: Schema additions queued
- **BACKLOG**: DATA-007 marked DONE; multi-GEDCOM future work noted
