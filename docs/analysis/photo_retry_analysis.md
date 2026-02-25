# Photo Retry Analysis: 144 Failed Gemini API Calls

**Date:** 2026-02-25
**Analyzed by:** Agent task, Session 68 prep

## Executive Summary

Of the 144 photos that originally failed in batch `batch_alignment_20260223_023456`,
**142 were already successfully retried** in subsequent batches. Only **2 photos**
remain permanently unprocessable due to Gemini content safety filters.

No further retry spending is needed. The $1.50-4.50 budget is unnecessary.

## Original Batch Statistics

| Metric | Value |
|--------|-------|
| Batch file | `results/batch_alignment_20260223_023456.json` |
| Model | gemini-3.1-pro-preview |
| Total photos attempted | 266 |
| Succeeded | 122 (45.9%) |
| Failed | 144 (54.1%) |
| Total cost | $0.7496 |
| Error type (all 144) | "Gemini API call failed" |

## Retry History

Retries were already performed in subsequent batches:

| Batch | Photos | Overlap w/ Failed | Retried OK | Still Failed |
|-------|--------|-------------------|------------|--------------|
| batch_combined_20260223_221012 | 10 | 10 | 8 | 2 |
| batch_combined_20260223_221339 | 136 | 136 | 134 | 2 |
| batch_combined_20260224_191419 | 5 | 3 | 2 | 1 |
| batch_combined_20260225_135023 | 2 | 2 | 0 | 2 |

**Net result: 142 of 144 successfully retried. 2 permanently failing.**

## Total API Spend Across All Batches

| Batch | Cost |
|-------|------|
| batch_alignment_20260223_020925 | $0.0223 |
| batch_alignment_20260223_023456 | $0.7496 |
| batch_combined_20260223_101346 | $0.0022 |
| batch_combined_20260223_101515 | $0.0016 |
| batch_combined_20260223_101745 | $0.0022 |
| batch_combined_20260223_102016 | $0.0004 |
| batch_combined_20260223_221012 | $0.0782 |
| batch_combined_20260223_221339 | $1.1085 |
| batch_combined_20260224_114350 | $0.0132 |
| batch_combined_20260224_191419 | $0.0603 |
| batch_combined_20260225_135023 | $0.0000 |
| **Total** | **$2.0385** |

## The 2 Permanently Failing Photos

### Root Cause: Gemini PROHIBITED_CONTENT

Both photos return `FinishReason.PROHIBITED_CONTENT` when sent with the
face alignment prompt. The images themselves are valid (simple description
prompts work fine). The content safety filter is triggered by the combination
of the "forensic photo analyst" role prompt + detailed facial analysis
instructions + these specific images.

| Photo ID | Filename | Collection | Faces | Dimensions | Attempts |
|----------|----------|------------|-------|------------|----------|
| 9411826ba358db3c | Image 914_compress.jpg | Vida Capeluto NYC | 1 | 1440x2048 | 4 (all failed) |
| 81bf7f85ec9814bc | Image 018_compress.jpg | Vida Capeluto NYC | 1 | 2896x2048 | 4 (all failed) |

**Evidence:**
- HTTP 200 OK is returned (API call succeeds)
- `response.text` is None (no content generated)
- `finish_reason` is `PROHIBITED_CONTENT`
- Both photos depict children (young girls) -- likely triggers child safety filters
  when combined with detailed facial analysis instructions
- Simple prompts ("describe this photo") work fine for both images

### Why These 2 Photos Specifically?

Both photos are of young children:
- Image 914: "A young girl with brown hair and braces wearing a white robe"
- Image 018: "A young girl standing outside wearing a plaid dress"

Gemini's safety system appears to block detailed facial biometric analysis
(age estimation, identifying features, gender classification) when the subject
is a child. This is consistent with Google's responsible AI policies around
child safety.

## Recommendations

1. **No further retry needed** -- These 2 photos will continue to fail with the
   current prompt. The root cause is a policy filter, not a transient error.

2. **Possible workaround** -- Rephrase the prompt to avoid "forensic" language
   and reduce the specificity of facial analysis requests. However, this would
   require modifying `build_alignment_prompt()` and testing across all photos.

3. **Alternative** -- Accept 264/266 (99.2%) coverage. These 2 photos each have
   only 1 face, so the impact is minimal (2 faces out of ~775).

4. **Update ROADMAP** -- The "Retry 144 failed photos" task is effectively
   DONE (142/144 already retried, 2 permanently blocked by content safety).

## Source/Collection Distribution of Original 144 Failures

| Source | Count |
|--------|-------|
| community-batch (inbox) | 116 |
| ancestry (inbox) | 12 |
| staged (inbox) | 9 |
| facebook (inbox) | 4 |
| legacy (SHA256 IDs) | 2 |
| benatar (inbox) | 1 |

All community-batch, ancestry, staged, facebook, and benatar photos
were successfully retried. Only the 2 legacy photos remain.
