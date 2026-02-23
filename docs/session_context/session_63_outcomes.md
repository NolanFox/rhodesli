# Session 63 Outcomes: Close the Gaps, Calibrate, Re-Run

**Date**: 2026-02-23
**Predecessor**: [Session 61C outcomes](session_61c_outcomes.md), [Session 62 assessment](session_62_assessment.md)
**Prompt**: [docs/prompts/session_63_prompt.md](../prompts/session_63_prompt.md)
**Planning context**: [session_63_planning_context.md](session_63_planning_context.md)

---

## Unresolved Items Status (U1-U10)

| ID | Description | Status | Evidence |
|----|------------|--------|----------|
| U1 | GEDCOM tables not created | **FIXED** | 4 tables in Supabase Postgres (psycopg2) |
| U2 | GEDCOM face links not created | **FIXED** | 61 links (18 admin + 39 auto + 4 review) |
| U3 | Calibration pairs not extracted | **FIXED** | 348 pairs (221 match, 127 non-match) |
| U4 | Similarity calibration not built | **FIXED** | AUC=0.9577, threshold@90%=0.268 |
| U5 | Recalibration hooks not wired | **FIXED** | 3 hooks: merge, reject, confirm |
| U6 | Face alignment not tested on real photos | **FIXED** | 3/3 pass, $0.03, 100% alignment |
| U7 | Face alignment not deployed | **FIXED** | Pushed to Railway, site responding |
| U8 | Deploy verified | **FIXED** | 200 OK on all endpoints |
| U9 | Batch re-run not started | **IN PROGRESS** | 102/~263 photos aligned so far |
| U10 | Documentation gaps | **FIXED** | AD-149, AD-150, AD-151 written |

---

## Face Alignment Real Test Results

| Photo | Faces | Described | Time | Cost | Result |
|-------|-------|-----------|------|------|--------|
| 2-face Vida Capeluto | 2 | 2 | 6.8s | $0.005 | PASS |
| 8-face Betty (confirmed IDs) | 8 | 8 | 11.2s | $0.011 | PASS |
| 12-face Vida group | 12 | 12 | 13.6s | $0.015 | PASS |

**Total**: 22/22 faces described, $0.031, 0 errors.

---

## Calibration Model Stats

- **Model**: Isotonic regression (sklearn.IsotonicRegression)
- **AUC**: 0.9577 (validation set)
- **Pairs**: 348 total (221 match, 127 non-match)
- **Match scores**: 0.112–0.978, mean 0.535
- **Non-match scores**: -0.115–0.297, mean 0.061
- **Threshold@90% precision**: 0.268
- **Threshold@95% precision**: 0.269
- **Decision**: Isotonic regression over Platt scaling (more flexible for non-standard distributions)

---

## GEDCOM Integration

- **Tables created**: 4 (gedcom_individuals, gedcom_events, gedcom_relationships, gedcom_face_links)
- **Data imported**: 21,809 individuals, 40,140 events, 145,574 relationships
- **Face links**: 61 total (18 existing admin + 39 auto-linked + 4 for review)
- **Linking method**: Sephardic surname variant clusters + normalized name matching
- **AD**: AD-151 (GEDCOM face linking)

---

## Batch Re-Run Status

- **5-photo validation**: PASSED ($0.022, 5/5 success)
- **Full batch**: IN PROGRESS — 102/~263 eligible photos aligned as of session end
- **Script**: scripts/run_batch_alignment.py --execute --skip-aligned --delay 2.0
- **Estimated completion**: ~30 more minutes at current pace

---

## Cost Summary

| Activity | Cost |
|----------|------|
| Face alignment real test (3 photos) | $0.03 |
| Batch validation (5 photos) | $0.02 |
| Batch full run (~102 photos so far) | ~$1.50 |
| Total this session | ~$1.55 (well under $12.54 budget) |

---

## New Files Created

| File | Purpose |
|------|---------|
| `rhodesli_ml/similarity_calibration.py` | Isotonic regression calibrator |
| `rhodesli_ml/recalibration_hooks.py` | Event-driven recalibration hooks |
| `rhodesli_ml/tests/test_similarity_calibration.py` | 12 tests |
| `rhodesli_ml/tests/test_recalibration_hooks.py` | 17 tests |
| `scripts/test_face_alignment_real.py` | Real photo face alignment test |
| `scripts/link_faces_to_gedcom.py` | GEDCOM face linking with surname variants |
| `scripts/extract_calibration_pairs.py` | Ground truth pair extraction |
| `scripts/run_batch_alignment.py` | Batch face alignment pipeline |

---

## What Session 64 Should Do

1. **Check batch alignment completion** — verify all ~263 photos aligned, review results JSON
2. **Wire calibrated probabilities to compare UI** — replace raw cosine with P(match) + confidence labels
3. **GEDCOM admin review UI** — interface for reviewing 4 "for review" face links
4. **Community reject UX** — enable explicit non-match collection for calibration improvement
5. **Active learning** — surface uncertain pairs (P(match) 0.4-0.6) for admin labeling
6. **FA-002** — integrate GEDCOM context into face alignment prompts

---

## Deferred to Future Sessions

- **Batch completion** — still running, Session 64 should verify
- **Calibration dashboard** — admin page for monitoring calibration model health
- **FA-002: GEDCOM + face alignment** — pass genealogical context to alignment prompts
- **FA-003: Mobile face description cards** — CSS media queries for small screens
- **FA-004: Auto-trigger alignment on upload** — wire to upload pipeline
