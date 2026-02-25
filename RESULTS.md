# Session 66 Results: Portfolio ML Pipeline Writeup

## What Was Done

Created a portfolio-quality technical writeup of the Rhodesli ML pipeline for interview use. The document covers the full system: face detection, similarity calibration, date estimation, Gemini alignment with GEDCOM enrichment, and the human-in-the-loop feedback architecture.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `docs/portfolio/ml_pipeline_writeup.md` | Created | 134-line technical writeup of the ML pipeline |
| `RESULTS.md` | Created | This summary file |

## Source Files Read (Not Modified)

- `docs/ml/ALGORITHMIC_DECISIONS.md` -- All 163 ML decisions (AD-001 through AD-163)
- `rhodesli_ml/gedcom_context.py` -- GEDCOM context builder (5 enrichment variants)
- `rhodesli_ml/gemini_config.py` -- Centralized model config and pricing
- `rhodesli_ml/gemini_extraction.py` -- Unified extraction prompt architecture
- `rhodesli_ml/similarity_calibration.py` -- Isotonic regression calibrator (AUC 0.9577)
- `rhodesli_ml/calibration/model.py` -- Siamese MLP (32K params)
- `rhodesli_ml/calibration/inference.py` -- ONNX/PyTorch dual-backend inference
- `rhodesli_ml/utils/api_logger.py` -- Full API call cost tracking
- `rhodesli_ml/training/train_date.py` -- CORAL ordinal regression training
- `core/neighbors.py` -- Face similarity search (multi-anchor, single-linkage)
- `core/clustering.py` -- Agglomerative clustering with MLS + temporal priors
- `core/temporal.py` -- CLIP-based era classification, Bayesian penalties
- `core/grouping.py` -- Union-Find face grouping
- `scripts/run_combined_pipeline.py` -- Combined Gemini processing pipeline
- `results/batch_combined_20260223_221339.json` -- Batch results (134/136 success)
- `results/batch_alignment_20260223_023456.json` -- Earlier batch (122/266, 144 rate-limited)
- `results/gedcom_enrichment_comparison_report.md` -- 3-model x 5-variant comparison
- `results/calibration_pairs_session63.json` -- 348 calibration pairs

## Key Numbers in the Writeup

- 271 photos, 775 faces, 55 confirmed identities
- AUC 0.9577 (isotonic similarity calibration)
- 269/271 photos aligned via Gemini ($1.86 total)
- ~$0.008 per photo (Gemini 3.1 Pro)
- 21,809 GEDCOM individuals imported to Supabase
- ~3,553 tests across two test suites
- 163 algorithmic decisions documented (AD-NNN format)
