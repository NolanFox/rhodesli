# Session 153b Phase 5 — Shadow Eval Partial Results

**Date:** 2026-04-19
**Script:** `scripts/session153_shadow_eval.py` (with 2nd Detroit control added — 01659)
**Gemini model:** `gemini-3.1-pro-preview`
**Experiment ID:** `session153_shadow_eval_1776612828` (generated, not logged — see schema drift below)

---

## Status: PARTIAL — eval did not complete

The script was run twice in Session 153b. Second run (stable, not piped through `tail`) progressed through ~5 calls in ~7 minutes, then hung on photo 3/12 while awaiting Gemini API response. After 18 minutes of no progress I killed it. Gemini API was returning 503 / 504 intermittently (observed on photo 2), and photo 3's call appeared to be stuck awaiting response.

Total Gemini calls completed: **4 out of 24** (photos 1 baseline + candidate, photos 2 baseline + candidate).
Total Supabase logs: **0** (schema drift — see below).
JSON raw output file: **NOT WRITTEN** (script killed before final write).

## Detroit regression gate — partial results

The explicit gate from Session 153b prompt Phase 5:

> The candidate prompt (3-round scaffold) MUST predict Detroit / Belle Isle for ALL Detroit photos at ≥medium confidence

### Photo 1 — `02068_p_13akf5twbc3600.jpg` (Belle Isle Conservatory frame A, Albert + 2 others)
- **Baseline**: `place='Unknown' conf=low verdict=wrong` — baseline didn't even confidently guess; it said "Unknown" at low confidence. Wrong per the gate (Detroit expected).
- **Candidate**: `place='New York Botanical Garden (Bronx, New York)' conf=medium verdict=wrong` — candidate CONFIDENTLY predicted the wrong city (NYC, which is exactly the historical bug we were trying to fix).
- **Gate result on photo 1**: **FAIL for candidate.** Candidate confidently-wrong is arguably worse than baseline-uncertain.

### Photo 2 — `01659_p_13akf5twbc1045.jpg` (Belle Isle Conservatory frame B, same group)
- **Baseline**: 504 Gateway Timeout → `place=None conf=None verdict=error`
- **Candidate**: 503 Service Unavailable → `place=None conf=None verdict=error`
- **Gate result on photo 2**: INDETERMINATE (both variants errored out; not a meaningful signal).

### Photos 3–12
- Never reached / not run.

## Honest verdict on the prompt-swap decision

**Do NOT deploy the candidate prompt based on what we have.**

- 1 of the 2 Detroit photos that completed showed candidate confidently-wrong (NYC) on a photo the prior session said should correctly be Detroit.
- The 3-round candidate scaffold does not have enough contextual signal to override the NYC-default bias at test-time; the shadow eval empirically shows this.
- A candidate that confidently hallucinates NYC is worse than a baseline that says "Unknown" — we'd regress admin trust in Gemini's geography predictions.

## What would need to change before we retest

1. **API stability**: Gemini 3.1 Pro was giving 503 / 504 during the run. A retry-with-backoff would get past this, but increases per-run cost.
2. **Candidate prompt redesign**: the confident-NYC answer suggests the candidate scaffold is not seeing (or not weighting) enough Detroit-specific signal. Options:
   - Inject collection metadata (e.g., `collection=fox-charlie-001` maps to Dayton/Detroit geography)
   - Let Gemini see the third Belle Isle frame alongside — multi-frame event clustering (→ PRD-061)
   - Include GEDCOM subject-residence pins (Albert Fox Detroit 1917-1918 EVEN list)
3. **Schema fix**: `gemini_api_calls` table is missing an `experiment_id` column. All Supabase log writes failed with PGRST204 during this run. Needs `ALTER TABLE gemini_api_calls ADD COLUMN experiment_id TEXT;`.

## Recommendation for Session 154+

- **Do NOT** propose a prompt-swap deployment PR based on these results.
- Fix the `gemini_api_calls` schema drift (trivial ALTER TABLE).
- Treat candidate-prompt design as an open research question tied to PRD-061 (event clustering) — a Belle Isle multi-frame input may be the unlock, not a better single-image prompt.
- Re-run the full 12-photo shadow eval after fixing Gemini API stability / retry logic AND the schema. Budget ~30 min + $2 Gemini spend.

## Cost observed (partial run)
- Photo 1 baseline: $0.0072
- Photo 1 candidate: $0.0125
- Photo 2 baseline: $0.0021 (error)
- Photo 2 candidate: $0.0023 (error)
- **Total: ~$0.024** (under the $2 cost cap — cap not the limiter; API stability is)

## Schema drift log

```
Could not find the 'experiment_id' column of 'gemini_api_calls' in the schema cache
PGRST204
```
Every single Gemini call log write attempt failed with this. The script catches the exception and continues, so the eval data is NOT persisted to Supabase. It would have been persisted to the JSON file had the script reached its final `write_text()` call, but it didn't. Backlog item: add `experiment_id TEXT` column to `gemini_api_calls`.

## Breadcrumbs
- Script: `scripts/session153_shadow_eval.py`
- Raw log: `/tmp/shadow_eval_153b.log` (local only, not committed)
- Session 153b Phase 5 prompt requirement: `docs/prompts/session-153b-prompt.md` Phase 5
- Parent prompt audit: `docs/feedback/session-153-gemini-prompt-audit.md`
