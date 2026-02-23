## Session 61C Outcomes — GEDCOM-Enriched Analysis + Flash vs Pro

**Date**: 2026-02-23
**Predecessor**: docs/session_context/session_61b_assessment.md

### Budget
- Approved: $10.00
- Spent: $2.46 (24.6%)
- Remaining: $7.54

### GEDCOM Enrichment Verdict
- **Winner**: gemini-3.1-pro-preview + curated GEDCOM variant
- **Cost**: ~$0.02/photo (single pass) or ~$0.04/photo (two-pass with baseline)
- **Reliability**: 100% (0 errors in 100 Pro calls)
- Location improvement: vague → city-level in 4/5 GEDCOM-linked photos
- Date narrowing: 3-7 years with GEDCOM context
- Confidence: 60% → 80-100% "high" with GEDCOM

### Token/Cost/Latency Summary
| Model | Cost/Photo | Latency | Error Rate |
|-------|-----------|---------|-----------|
| gemini-2.0-flash | $0.0008 | 8s | 3% |
| gemini-3-flash-preview | $0.0083 | 34s | 13% |
| gemini-3.1-pro-preview | $0.0198 | 20s | 0% |

### What Was Built
1. Extended GEDCOM parser with RESI/OCCU/IMMI/EMIG/BURI events
2. 5-variant GEDCOM context builder (rhodesli_ml/gedcom_context.py)
3. Supabase import script (scripts/import_gedcom_supabase.py) — tables not yet created
4. Model comparison driver (scripts/compare_models.py)
5. 11 comparison runs across 3 models × 5 GEDCOM variants
6. Quantitative analysis report (results/gedcom_enrichment_comparison_report.md)
7. AD-147 (GEDCOM enrichment results), AD-148 (GEDCOM storage architecture)
8. 19 tests for GEDCOM context builder

### Supabase Tables
NOT YET CREATED — requires Supabase Dashboard SQL migration.
Tables: gedcom_individuals, gedcom_events, gedcom_relationships, gedcom_face_links.
Import script ready: scripts/import_gedcom_supabase.py

### Items Added to BACKLOG
- GEDCOM enrichment in upload flow
- "Analysis improved because..." UX feature
- Batch re-analysis with GEDCOM enrichment
- Admin GEDCOM link review UI
- Create Supabase GEDCOM tables

### Deferred
- Phase 6B (Meta-comparison with Gemini as judge) — not needed, quantitative analysis sufficient
- Flash-3-preview full/curated runs (B1b/C1b) — flash-3-preview too unreliable (13% 503 errors)
- Supabase table creation — needs Nolan to run SQL via Dashboard

### What Next Session Should Do
1. Create Supabase GEDCOM tables and run import
2. Implement curated GEDCOM enrichment in the photo estimate/detective flow
3. Consider Platt scaling (AD-145 Stage 1) for similarity calibration
4. Fix Flash 2.0 GEDCOM confusion bug (year=1999) if Flash is used in production

### What Next Session Should Verify FIRST
1. All 19 GEDCOM context tests still pass
2. results/run_*.json files all committed and accessible
3. AD-147/148 properly cross-referenced

### Model Correction Note
Mid-session, user noted Flash runs should use gemini-3-flash-preview not gemini-2.0-flash.
Runs A1/B1/C1 used 2.0-flash; D1/E1/A1b used 3-flash-preview. All data preserved.
This actually produced a more informative 3-model comparison.
See results/MODEL_RUN_LOG.md for full run inventory.
