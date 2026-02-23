# Session 64 Track A — Data Layer Audit Results

## Face Alignment Storage: JSON-only
- `data/face_alignments.json`: 127 entries, 320KB
- `results/batch_alignment_20260223_020925.json`: 3 photos (first batch)
- `results/batch_alignment_20260223_023456.json`: 124 photos (second batch)
- `face_gemini_alignments` Supabase table: DOES NOT EXIST (was designed but never created)
- `app/face_alignment.py` reads/writes JSON only, zero Supabase references

## Gemini Model: Confirmed gemini-3.1-pro-preview
- Both batch result files record `model=gemini-3.1-pro-preview`
- `rhodesli_ml/gemini_config.py` has `GEMINI_MODEL = "gemini-3.1-pro-preview"` as default
- Cost tracking exists per-photo in results (input_tokens, output_tokens, cost)

## Recalibration Hooks: DEAD CODE
- `rhodesli_ml/recalibration_hooks.py` defines: on_face_merge, on_match_reject, on_identity_confirm
- Tests exist in `rhodesli_ml/tests/test_recalibration_hooks.py`
- **ZERO calls from app/main.py or any app/ code**
- Merge, reject, confirm endpoints do NOT fire hooks

## Calibration in UI: NOT WIRED
- `rhodesli_ml/similarity_calibration.py` has `SimilarityCalibrator` class
- `rhodesli_ml/calibration/inference.py` has `is_calibration_available()` and `cal_backend()`
- Health endpoint (line 7124-7143) checks calibration availability
- Compare/match views use RAW cosine similarity directly (lines 6121-6209, 15432-15459)
- No calibrated probability display anywhere

## JSON Files Still Primary Stores
- face_alignments.json (face alignment data)
- date_labels.json (Gemini date estimates)
- identities.json (identity data — partially migrated)
- photo_index.json (photo metadata)
- embeddings.npy (face embeddings)
- calibration/ directory (calibration models)
- co_occurrence_graph.json, proposals.json, etc.

## Implications for Phase 2-3
1. Need to create face_gemini_alignments table in Supabase
2. Migrate 127 alignment records from JSON → Supabase
3. Wire calibrated scores into compare/match UI
4. Wire recalibration hooks into merge/reject/confirm endpoints
