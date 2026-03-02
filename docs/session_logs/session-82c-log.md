# Session 82c Log: Gemini Re-run with GEDCOM Enrichment
Started: 2026-03-01
Branch: session-82c/gemini-rerun
Prompt: docs/prompts/session-82c-prompt.md

## Phase Checklist
- [x] Phase 0: Orient + Validate Existing Gemini State
- [x] Phase 1: Asheville Litmus Test — 3-Variant Experiment
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

---

## Phase 1: Asheville Litmus Test — 3-Variant Experiment

### Photo Identity
4 faces identified:
1. Betty Capeluto Fox (GEDCOM: @I132123771036@) — daughter
2. Big Leon Capeluto (GEDCOM: @I132126987005@) — husband/father
3. Victoria Capuano Capeluto (GEDCOM: @I132126987020@) — wife/mother
4. Debbie Fox Schapiro (no GEDCOM) — granddaughter

### Experiment Results

| Variant | Location Guess | Accuracy | Cost |
|---------|---------------|----------|------|
| A (no GEDCOM) | "Unknown, likely North America" | 2/10 | $0.0083 |
| B (full GEDCOM) | "Clearwater, Florida" | 0/10 | $0.0122 |
| **C (curated GEDCOM)** | **"Asheville, North Carolina"** | **10/10** | $0.0103 |
| Meta-comparison | — | — | $0.0097 |
| **Total** | | | **$0.0406** |

### Key Findings
1. **Curated GEDCOM (C) = PERFECT**: Exact match to ground truth
2. **Full GEDCOM (B) = WORSE than baseline**: Confused by "later life" Clearwater data, scored 0/10
3. **No GEDCOM (A) = Useless for interior photos**: Only got continent-level accuracy
4. **Signal-to-noise confirmed**: Filtering GEDCOM to ±15yr window eliminates confusing data
5. **Critical data point**: Leon's documented residence at 33 Elizabeth St, Asheville NC

### Meta-Comparison Verdict
- Winning variant: C (curated)
- GEDCOM value: YES — "sole driver for pinpointing Asheville"
- Visual clues: NONE (interior photo, no geographic markers)
- Recommendation: Use curated variant for batch processing

### Budget
- Phase 1 total: $0.04 of $3.00 budget
- Budget remaining: $2.96

---

## Phase 2: Assess Value + Decide Batch Approach

### Assessment
1. **Does GEDCOM enrichment improve location accuracy?** YES — 2/10 → 10/10
2. **Is curated better than full?** YES — full was counterproductive (0/10)
3. **Per-photo cost?** ~$0.01/photo
4. **Projected cost for batch?** 77 GEDCOM-linked photos × $0.01 = ~$0.77
5. **Worth running at scale?** YES

### Decision Gate: PROCEED to Phase 3
- GEDCOM enrichment clearly helped (Asheville identified in C but not A or B)
- Documented as AD-194

### Scope
- 77 of 271 photos have GEDCOM-linked faces
- 33 identities have GEDCOM links
- Only GEDCOM-linked photos benefit from enrichment
- Remaining 194 photos: run baseline (no GEDCOM) for completeness
