# Gemini Date Labeling Failure Analysis

**Date:** 2026-02-15 (Session 28)

## Summary

All 271 photos are now labeled. 9 photos failed on `gemini-3-flash-preview` with 504 DEADLINE_EXCEEDED but all succeeded with `gemini-2.5-flash` fallback.

## Results

| Model | Attempted | Success | Failure | Failure Rate |
|-------|-----------|---------|---------|--------------|
| gemini-3-flash-preview | 271 | 262 | 9 | 3.3% |
| gemini-2.5-flash (fallback) | 9 | 9 | 0 | 0.0% |
| **Total** | **271** | **271** | **0** | **0.0%** |

## Correlation Analysis

### File Size: NO correlation

Failures are actually *smaller* on average — ruling out "file too large" as a cause.

| Metric | Successes (262) | Failures (9) |
|--------|-----------------|--------------|
| Avg file size | 1,252 KB | 370 KB |
| Median file size | 712 KB | 182 KB |

Size-based failure rates show no threshold effect:
- Files >2 MB: 0.0% failure (40/40 succeeded)
- Files >1 MB: 1.1% failure (92/93 succeeded)
- Files ≤500 KB: 5.4% failure (6/112 failed)

### Image Dimensions: NO correlation

| Metric | Successes | Failures |
|--------|-----------|----------|
| Avg pixels (w×h) | 5.96M | 1.91M |

Smaller images failed slightly more often, but the effect is weak and confounded with the file size finding.

### Face Count: NO correlation

| Metric | Successes | Failures |
|--------|-----------|----------|
| Avg faces | 3.2 | 2.2 |

No meaningful difference.

## Root Cause

The 504 DEADLINE_EXCEEDED errors are **infrastructure-side** issues with the `gemini-3-flash-preview` model — likely:
- Preview model traffic routing/capacity
- Server-side processing queue timeouts
- Not related to image content or size

## Recommendation

For future labeling runs:
1. Use `gemini-3-flash-preview` as primary (free tier, best quality among flash models)
2. Automatic fallback to `gemini-2.5-flash` for any 504/timeout errors
3. No image resize needed — file size is not a factor
4. Consider adding `--fallback-model gemini-2.5-flash` flag to generate_date_labels.py

## Failed Photo Details

| File Size | Dimensions | Faces | Filename |
|-----------|-----------|-------|----------|
| 63 KB | 1551×640 | 4 | sabrina_amato_collection... |
| 91 KB | 818×875 | 1 | semah_franco... |
| 118 KB | 771×532 | 9 | jacob_pasha_israel... |
| 155 KB | 1372×1382 | 1 | asher_touriel... |
| 182 KB | 1458×1424 | 1 | victor_haim_israel... |
| 219 KB | 1294×1365 | 1 | isaac_jack_levy... |
| 533 KB | 1610×2048 | 1 | morris_touriel... |
| 886 KB | 1444×2048 | 1 | isaac_jack_levy... |
| 1084 KB | 1518×2048 | 1 | victor_rebecca_benun... |
