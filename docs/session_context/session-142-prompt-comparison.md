# Session 142: Gemini Prompt Comparison

**Date**: 2026-03-27
**Auditor**: Claude Opus 4.6 + Codex CLI v0.115

## Comparison: Old (generate_date_labels.py) vs New (build_extraction_prompt "full")

### Old Prompt (Rhodes Collection, 271 labels)
- **Source**: `rhodesli_ml/scripts/generate_date_labels.py` PROMPT constant
- **Preset**: Custom (single monolithic prompt, not preset system)
- **Model**: Mixed (gemini-3-flash, gemini-2.5-pro, gemini-3.1-pro)
- **Confidence**: 217 high, 54 medium (80% high)

**Unique fields produced:**
- `capture_vs_print` — distinguishes original photo date from scan/print date
- `cultural_lag_applied` / `cultural_lag_note` — explicit Sephardic cultural lag adjustment
- `evidence` — structured per-cue evidence with ratings
- `reasoning_summary` — narrative explanation of date estimate
- `visible_text` — OCR'd text from photo
- `is_color` — color vs B&W classification

### New Prompt (Fox Family, 82 labels)
- **Source**: `rhodesli_ml/gemini_extraction.py` build_extraction_prompt("full")
- **Preset**: "full" (modular extraction system)
- **Model**: gemini-3.1-pro-preview (consistent)
- **Confidence**: 37 high, 45 medium (45% high)

**Unique fields produced:**
- `face_analysis` — per-face age, gender, description with bbox alignment
- `group_composition` — arrangement, type, people_count
- `cultural_markers` — cultural/ethnic indicators
- `photo_technique` — photography method analysis
- `face_coordinates_sent` — whether face coords were included

### Gap Analysis (Codex P0 findings)

| Feature | Old Prompt | New Prompt | Impact |
|---------|-----------|-----------|--------|
| Capture vs print | YES | NO | Critical for reprints — old photos in new frames get wrong dates |
| Cultural lag | YES | Partial | Rhodes-specific context in preamble but no explicit output field |
| Per-cue evidence | YES | NO | Reduces interpretability of estimates |
| OCR/visible text | YES | NO | Misses signage clues for location/date |
| Face analysis | NO | YES | Enables age trajectory for temporal co-occurrence |
| Group composition | NO | YES | Identifies family group patterns |
| Scene description | YES (populated) | YES (empty) | New prompt schema includes it but doesn't populate |

### Confidence Distribution Concern

Old prompt: 80% high confidence
New prompt: 45% high confidence

This could indicate:
1. Fox Family photos are harder to date (many informal/candid vs Rhodes studio portraits)
2. The new prompt is more calibrated (less overconfident)
3. Missing cultural context (capture_vs_print, cultural_lag) reduces certainty

### Recommendations (from Codex Prompt Audit)

1. **P0**: Merge the best of both — add `capture_vs_print` and `visible_text` to the full preset
2. **P0**: Fix scene_description population (Codex found it's in schema but empty)
3. **P1**: Add `reasoning_summary` equivalent to full preset for interpretability
4. **P1**: Use `curated` GEDCOM context with year window (not `first_order` which loads entire tree)
5. **P1**: Per-face output should include `age_range` and `clothing` (not just `estimated_age`)
6. **P2**: A/B test on 10 shared photos to measure date accuracy delta

### Decision: What to adopt for next batch run

For the remaining 199 photos:
- Keep "full" preset (face_analysis, group_composition are essential for PRD-059)
- ADD: `capture_vs_print` guidance to the prompt
- ADD: `visible_text` extraction back
- ADD: `reasoning_summary` output field
- FIX: scene_description population
- KEEP: face coordinate left-to-right sorting (Codex P0 fix already applied)

Logged as AD-NNN (pending) in ALGORITHMIC_DECISIONS.md.
