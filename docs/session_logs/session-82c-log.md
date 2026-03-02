# Session 82c Log: Gemini Re-run with GEDCOM Enrichment
Started: 2026-03-01
Branch: session-82c/gemini-rerun
Prompt: docs/prompts/session-82c-prompt.md

## Phase Checklist
- [ ] Phase 0: Orient + Validate Existing Gemini State
- [ ] Phase 1: Asheville Litmus Test — 3-Variant Experiment
- [ ] Phase 2: Assess Value + Decide Batch Approach
- [ ] Phase 3: Batch Preparation (conditional)
- [ ] Phase 4: Surface Results in App (conditional)
- [ ] Phase 5: Documentation + PR

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed

---

## Phase 0: Orient + Validate Existing State

### Gemini State Audit

**API Key**: GEMINI_API_KEY available in .env

**Existing Data Files** (results/):
- 11 run results from Session 61C: run_A1_flash_none.json through run_E2_pro_co_occurrence.json
- 7 batch_combined files from Sessions 64d-65
- 2 batch_alignment files
- gedcom_enrichment_comparison_report.md — comprehensive analysis

**Pipeline Code**:
- `rhodesli_ml/gemini_config.py` — Model config (gemini-3.1-pro-preview, pricing)
- `rhodesli_ml/gemini_extraction.py` — Unified extraction with presets (full/quick/compare)
- `rhodesli_ml/gedcom_context.py` — 5-variant GEDCOM context builder
- `app/face_alignment.py` — Coordinate bridging + Gemini analysis
- `scripts/run_batch_alignment.py` — Batch pipeline

**Supabase Tables**: Cannot verify from local (no SUPABASE_SERVICE_KEY in env). Tables exist per AD-153.

**Prior Experiment (Session 61C)**:
- 11 runs × 20 photos = 210 API calls, $2.46 total
- **Winner**: gemini-3.1-pro-preview + curated GEDCOM (C2)
- $0.02/photo, 0% error rate, location: vague → city-level in 4/5 cases
- GEDCOM token cost negligible (80-800 tokens vs ~1100 image tokens)

### Asheville Photo Identification

**Victoria Capuano Capeluto**: Identity `964f4c07-e9e5-43e2-933c-7fd8bfd234b8`
- Born: 25 September 1905, Rhodes, Greece
- Died: 20 June 1989, Clearwater, Florida
- GEDCOM xref: `@I132126987020@`
- 7 anchor faces, 8 candidate faces across 15 photos

**Big Leon Capeluto** (spouse): Identity `b6d9ea5b-bf90-463a-bab3-682acac7753d`
- Born: 24 June 1904, Milas, Türkiye
- Died: 1 Dec 1983, Pinellas, Florida
- GEDCOM xref: `@I132126987005@`
- GEDCOM test fixture references "33 Elizabeth Street, Asheville" residence

**Best Asheville photo candidate**: `inbox_staged-20260210-182610_7_596771420.719238`
- Filename: 596771420.719238.jpg
- Source: personal photos
- 4 faces detected: Victoria + 3 others (matches "3 of her 4 children")
- Previous batch alignment: error (Gemini API call failed)
- No existing location data for this photo

**Also noted**: `inbox_facebook-20260210_1_victoria_capuano_with_family_in_atl_...`
- Filename includes "with_family_in_atl" (Atlanta, not Asheville)
- 3 faces: Victoria + 2 others

### Decision
Proceed with `inbox_staged-20260210-182610_7_596771420.719238` as the Asheville litmus test photo. Run 3-variant experiment in Phase 1.
