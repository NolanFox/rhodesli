# Session 167 — ESTIMATE-BACKFILL-166 Survey (READ-ONLY)

_Generated: 2026-06-30T17:57:29.523886+00:00 by `scripts/backfill_gedcom_estimates.py --survey`. No writes, no Gemini calls, no $ spend._

## What this is
Lesson 205: the GEDCOM-context loader was dead from the Session-164 schema
redesign until Session 166 fixed it, so estimates produced in that window ran
VISUAL-ONLY (no age anchoring / residence history / spouse-death ceiling). This
survey finds GEDCOM-linked photos whose LATEST estimate ran without GEDCOM and
would benefit from a re-run.

## Method
Primary signal = the LATEST `gemini_api_calls` row per photo, by `created_at`,
inspecting `gemini_config.enrichment_level`:
`none`/`faces` = visual-only (candidate); `gedcom`/`gedcom+faces`/`full` = enriched.
`date_labels` flags are shown as corroboration only (older batch rows omit them).

## Totals
- date_labels rows total: **560**
- gemini_api_calls rows total: **1063**
- GEDCOM-linked identities: **96**
- GEDCOM-linked photos (any face): **740**
- Linked photos by latest-call enrichment_level: `{'gedcom': 70, '<unknown>': 10, 'full': 1, 'gedcom+faces': 276, 'faces': 3, 'none': 3}`
- Outage window used: `2026-04-13` .. `2026-06-12`

## Backfill candidates
GEDCOM-linked photos whose **latest** estimate ran visual-only: **6**
(of which inside the outage window: **2**).

| photo_id | in_window | latest_level | latest_call_at | stored_year | stored_location | stored_gedcom_flag |
|---|---|---|---|---|---|---|
| `inbox_fader-002_11_2C303F28-9322-4B5C-9928-CF0D0353E598` | True | faces | 2026-04-15T00:20:48.894385+00:00 | None | None | None |
| `inbox_fader-002_12_C686B5A8-115D-4002-8DBC-864BED5CA7F6` | True | faces | 2026-04-15T00:20:59.770634+00:00 | None | None | None |
| `inbox_55868a49_6_69835310_481178612663039_7889927619368452096_n` | False | none | 2026-03-31T00:56:55.826195+00:00 | 1928 | United States | None |
| `inbox_55868a49_8_15037258_1414640118561175_4049133849589388863_n` | False | none | 2026-03-31T00:56:32.417083+00:00 | 1978 | Florida, United States | None |
| `inbox_ed9ff2de_0_gukaylo_burd_smilg_kleinfled_4_generations_IMG_3534` | False | none | 2026-03-31T01:10:17.208053+00:00 | 1945 | United States | None |
| `inbox_fox-charlie-001_17_01633_p_13akf5twbc0908` | False | faces | 2026-03-31T00:57:13.700087+00:00 | 1985 | Florida, United States | None |

## Re-run (NOT executed this session — requires Nolan's $ approval)
```bash
# Survey again (read-only):
python scripts/backfill_gedcom_estimates.py --survey

# Re-run the candidates WITH GEDCOM context (SPENDS Gemini $, WRITES prod):
python scripts/backfill_gedcom_estimates.py --execute --i-have-nolans-approval
```
Each re-run should use `scripts/multimodel_photo_estimate.py run-gemini` (GEDCOM-
enriched prompt) then `finalize`. Verify `_build_gedcom_context_for_photo` returns
non-empty before bulk-running (Lesson 205/206/208).
