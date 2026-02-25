# Photo Retry Analysis Results

## Task
Investigate the 144 failed photos from the batch alignment pipeline and prepare
a retry analysis.

## Key Finding

**The 144 failed photos have already been retried.** 142 of 144 succeeded in
subsequent batch runs. Only 2 photos remain permanently unprocessable.

## Summary

| Metric | Value |
|--------|-------|
| Original failures | 144 |
| Already retried successfully | 142 |
| Permanently failing | 2 |
| Total API cost (all batches) | $2.04 |
| Additional cost for this analysis | $0.00 (confirmed retry failed) |

## Root Cause of 2 Permanent Failures

Both photos (`Image 914_compress.jpg` and `Image 018_compress.jpg`) are
portraits of young girls from the Vida Capeluto NYC Collection. Gemini returns
`FinishReason.PROHIBITED_CONTENT` when the face alignment prompt (which includes
"forensic photo analyst" framing and requests for age/gender/identifying features)
is combined with these images. This is a **content safety policy block**, not a
transient error.

Evidence gathered:
- Gemini API returns HTTP 200 but empty response text
- `finish_reason` is `PROHIBITED_CONTENT` (not rate limiting)
- Simple description prompts work fine for both images
- Both photos have been attempted 4 times each across different batches

## Retry Attempted

Ran `python scripts/run_combined_pipeline.py --photo-ids 81bf7f85ec9814bc 9411826ba358db3c`
as part of this analysis. Both failed again with PROHIBITED_CONTENT. Results in
`results/batch_combined_20260225_135023.json`.

## `--retry-failed` Flag Status

The flag exists and works correctly in `scripts/run_combined_pipeline.py` (line 545).
It reads photo IDs with error status from a previous results JSON and filters the
eligible photos to just those IDs.

## Files Created
- `docs/analysis/photo_retry_analysis.md` -- Full analysis with batch timeline,
  cost breakdown, source distribution, root cause investigation
- `results/batch_combined_20260225_135023.json` -- Results from retry attempt
  (created by the pipeline run during analysis)
- `RESULTS.md` -- This file

## Recommendation

Mark the "Retry 144 failed photos" ROADMAP item as effectively complete.
Coverage is 264/266 photos (99.2%). The 2 blocked photos are an acceptable
loss -- they each contain only 1 face, and the block is a Gemini policy
decision that cannot be resolved by retrying.

A potential future workaround would be to rephrase the alignment prompt to
avoid language that triggers child safety filters (remove "forensic" framing,
reduce biometric analysis specificity). This would be a low-priority task.
