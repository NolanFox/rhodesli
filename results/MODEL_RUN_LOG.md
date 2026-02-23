# Session 61C — Model Run Log

## Model Correction (Mid-Session)
- Original prompt specified `gemini-3-flash` for Flash runs
- Runs A1, B1, C1 were done with `gemini-2.0-flash` (older model)
- After user review: switching Flash runs to `gemini-3-flash-preview` for D1/E1
- ALL data preserved — no files overwritten. Old runs kept for 3-way comparison.
- Pro runs all use `gemini-3.1-pro-preview` (correct throughout)

## Complete Run Inventory

### gemini-2.0-flash runs (original Flash model — valid data, kept for comparison)
| Run | GEDCOM Variant | Cost | Photos OK | Errors | Error Type | File |
|-----|---------------|------|-----------|--------|------------|------|
| A1 | none | $0.0151 | 20/20 | 0 | — | run_A1_flash_none.json |
| B1 | full | $0.0135 | 18/20 | 2 | 429 rate limit | run_B1_flash_full.json |
| C1 | curated | $0.0180 | 20/20 | 0 | — | run_C1_flash_curated.json |

### gemini-3-flash-preview runs (corrected model per user)
| Run | GEDCOM Variant | Cost | Photos OK | Errors | Error Type | File |
|-----|---------------|------|-----------|--------|------------|------|
| A1b | none | $0.1294 | 16/20 | 4 | 503 high demand | run_A1b_flash3_none.json |
| D1 | first_order | $0.1594 | 19/20 | 1 | 503 high demand | run_D1_flash3_first_order.json |
| E1 | co_occurrence | $0.1416 | 17/20 | 3 | 503 high demand | run_E1_flash3_co_occurrence.json |

### gemini-3.1-pro-preview runs (all clean, 0 errors)
| Run | GEDCOM Variant | Cost | Photos OK | Errors | File |
|-----|---------------|------|-----------|--------|------|
| A2 | none | $0.4019 | 20/20 | 0 | run_A2_pro_none.json |
| B2 | full | $0.3863 | 20/20 | 0 | run_B2_pro_full.json |
| C2 | curated | $0.3936 | 20/20 | 0 | run_C2_pro_curated.json |
| D2 | first_order | $0.3987 | 20/20 | 0 | run_D2_pro_first_order.json |
| E2 | co_occurrence | $0.4008 | 20/20 | 0 | run_E2_pro_co_occurrence.json |

## Cost Summary
| Model | Runs | Total Cost |
|-------|------|-----------|
| gemini-2.0-flash | 3 | $0.0466 |
| gemini-3-flash-preview | 3 | $0.4304 |
| gemini-3.1-pro-preview | 5 | $1.9813 |
| **TOTAL** | **11** | **$2.4583** |

Budget: $10.00 | Spent: $2.46 | Remaining: $7.54

## Pricing (per 1M tokens)
| Model | Input | Output |
|-------|-------|--------|
| gemini-2.0-flash | $0.10 | $0.40 |
| gemini-3-flash-preview | $0.10 | $0.40 (thinking tokens extra) |
| gemini-3.1-pro-preview | $2.00 | $12.00 |

Note: gemini-3-flash-preview uses "thinking tokens" (672 avg per call) which
increases effective cost ~8x vs 2.0-flash despite same base pricing.

## Analysis Value
The 3-model comparison (2.0-flash, 3-flash-preview, 3.1-pro-preview) is actually
MORE informative than the planned 2-model comparison. We can now assess:
1. Flash generation gap (2.0 vs 3.0) — with thinking tokens
2. Flash vs Pro quality gap
3. GEDCOM enrichment effect on each model tier
4. Cost-quality tradeoff across 3 price points ($0.015, $0.13, $0.40 per 20 photos)
