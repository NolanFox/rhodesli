# Prompt Fidelity Investigation — Session 64d Batch

**Session**: 65a Phase 3 | **Date**: 2026-02-23

## Question

Did the Session 64d Gemini alignment batch (`batch_combined_20260223_221339`) actually include GEDCOM genealogical context in prompts? How much context was sent?

## Method

1. Queried `gemini_api_calls` table for 136 calls in the 64d batch
2. Compared `call_type` field: "combined" (GEDCOM-enriched) vs "alignment" (no GEDCOM)
3. Isolated 1-face photos to control for face-count-driven token variation
4. Traced prompt construction through code: `run_combined_pipeline.py` -> `build_gedcom_context()` -> `rhodesli_ml/gedcom_context.py:build_photo_context()`

## Findings

### Call Type Distribution
| Call Type | Count | Description |
|-----------|-------|-------------|
| alignment | 119 | No GEDCOM context — photo had no confirmed+linked identities |
| combined | 17 | GEDCOM context injected as "## Additional Context" section |

### Why Only 17/136 Got GEDCOM

GEDCOM context requires ALL of:
1. Identity is CONFIRMED (not PROPOSED or INBOX)
2. Identity has a `gedcom_face_links` entry mapping to a GEDCOM individual
3. The GEDCOM individual exists in `gedcom_individuals` table

At batch time: 46 of 55 confirmed identities had GEDCOM links, but only 17 of the 136 batch photos contained faces belonging to those linked identities. Most batch photos were community-submitted or inbox photos without confirmed identity assignments yet.

### Token Analysis (Controlling for Face Count)

For 1-face photos (cleanest comparison):

| Metric | Combined (n=12) | Alignment (n=66) | Delta |
|--------|-----------------|-------------------|-------|
| Avg tokens | 1,654 | 1,549 | +106 |
| Min tokens | 1,551 | 1,519 | +32 |
| Max tokens | 1,857 | 1,577 | +280 |
| Range | 306 | 58 | — |

GEDCOM context adds **~106 tokens on average** (range: 32-338 depending on individual's genealogical data richness).

### Token Variation by Face Count (All Calls)

| Faces | Photos | Avg Tokens | Notes |
|-------|--------|------------|-------|
| 1 | 78 | 1,565 | Base case |
| 2-5 | 28 | 1,630 | Moderate increase |
| 6-10 | 22 | 1,728 | ~170 tokens above 1-face |
| 11-18 | 4 | 1,920 | ~360 tokens above 1-face |
| 40 | 1 | 2,568 | Stella Benun 1963 group photo |

Face count is the primary driver of token variation (~25 tokens per additional face coordinate block). GEDCOM context (~106 tokens) is secondary.

### What GEDCOM Context Contains

For a linked individual like Abraham Capuano (GEDCOM: @I132127360989@):
- Name, birth year (1870), birth place (Istanbul, Turkey)
- Death year (1918), death place (Rhodes, Greece)
- Marriage events with dates and places
- For "curated" variant: events filtered to ±15 years of estimated photo date

The context is injected as `## Additional Context` after the face coordinate block.

### Data Quality Issues

1. `gemini_config` field: NULL for all 156 records — the logging code does not persist prompt configuration
2. `response_summary` field: NULL for all records — not populated by the pipeline
3. 2 records have NULL `prompt_tokens` — likely from failed/timeout calls

## Conclusion

**GEDCOM context IS being sent to Gemini for 17/136 photos (12.5%).** The low percentage is not a bug — it reflects the fraction of batch photos that have confirmed identities with GEDCOM links. The "curated" variant adds a modest ~106 tokens of genealogical context per linked individual.

## Recommendations

1. **Log prompts**: Populate `gemini_config` with the actual prompt text (or a hash + key parameters) for future auditability
2. **Track GEDCOM variant**: Log which GEDCOM variant was used ("curated", "full", etc.)
3. **Expand GEDCOM links**: As more identities get confirmed, GEDCOM enrichment percentage will naturally increase
4. **Consider response_summary**: Store a brief summary of Gemini's response for quality auditing

## References
- AD-146: GEDCOM context builder design
- AD-147/148: Flash vs Pro comparison with GEDCOM variants
- AD-152: API call logging schema
