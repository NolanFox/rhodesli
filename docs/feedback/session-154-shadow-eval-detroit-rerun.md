# Session 154 — Phase A3 Detroit Subset Shadow Eval (Honest Read)

**Date**: 2026-04-29
**Run**: `experiment_id = session154_shadow_eval_1777434398`
**Cost**: $0.168 / 6 calls (well under the $0.50 cap)
**Raw**: `docs/feedback/session-154-shadow-eval-detroit-rerun.json`

## TL;DR

**The Detroit gate from the Session 154 prompt FAILS**, so per the prompt's own
A3 acceptance criteria Phase A4 (full 12-photo eval) is SKIPPED.

Photo 02068 predicts NYC across all three variants — even with 22,808 chars of
GEDCOM context naming Albert Fox's RESI Detroit 1917. Photo 01659 correctly
identifies Detroit under both `candidate` and `candidate_with_prior` but baseline
also fails on it. Worst result: `candidate_with_prior` raised confidence on the
WRONG NYC answer for 02068 from `medium → high` — the AD-242 sycophancy guard
did NOT fire.

This is a real, important finding: prompt structure alone is not enough on
this photo class.

## A3 acceptance gate (from `docs/prompts/session-154-prompt.md` line 144-147)

> Both Detroit photos get `place` = Detroit/Belle Isle/Michigan at `≥medium`
> confidence under `candidate_with_prior`. Neither regresses under `candidate`
> (vs baseline) when given GEDCOM context.

| Photo | candidate_with_prior place | conf | gate met? |
|---|---|---|---|
| 02068 | New York City, New York | high | ❌ FAIL |
| 01659 | Detroit, Michigan | medium | ✅ PASS |

Gate fails on 02068. Per the prompt: "If Phase A3 passes on Detroit, run full
12-photo shadow eval ... [otherwise] SKIP A4." A4 is SKIPPED.

## Per-photo, per-variant table

| photo | variant | place | confidence | top1 | top3 | candidates listed |
|---|---|---|---|---|---|---|
| 02068 | baseline | New York, New York | medium | ❌ | ✅ | NYC, Dayton, Detroit |
| 02068 | candidate | New York City, New York | medium | ❌ | ✅ | NYC, Detroit, Dayton |
| 02068 | candidate_with_prior | New York City, New York | **high** ⚠️ | ❌ | ✅ | NYC, Detroit, Dayton |
| 01659 | baseline | New York, New York | low | ❌ | ✅ | Detroit, Dayton |
| 01659 | candidate | **Detroit, Michigan** | medium | ✅ | ✅ | Detroit, NYC, Dayton |
| 01659 | candidate_with_prior | **Detroit, Michigan** | medium | ✅ | ✅ | Detroit, NYC, Dayton |

All 6 calls had `gedcom_context_present=true` and ≥22,800 chars of subject
biographical data. AD-241 plumbing works.

## What this proves

1. **AD-241 (GEDCOM injection)**: works mechanically. Both Detroit photos
   resolved to ~22-23 KB of context naming Albert Fox + Irving Fox + the
   currently-misregistered "Harry Fox" (the latter is the registry's
   pending-repair anchor; Track B confirmed F+G in 02068 are NOT Harshel).
   Top-3 candidates always include Detroit — Gemini sees the city as a
   candidate. The prompt is just not making it the primary.

2. **AD-242 (prior-prediction retry) sycophancy**: in 02068, the retry made
   things WORSE — it raised the confidence on the wrong NYC answer from
   `medium → high`. The "name a positive supporting feature" guard did not
   fire as designed. The retry's CONFIRM path appears to be too easy for
   Gemini to take — it can confabulate a "supporting feature" without it
   being genuinely diagnostic.

3. **The candidate prompt structure helps on some photos**: 01659 went
   `low NYC → medium Detroit` from baseline to candidate. So the 3-round
   structure DOES nudge toward the correct answer when the visual evidence
   is closer to the surface.

4. **The candidate prompt is NOT enough on its own** when Gemini's prior
   visual judgment is strongly miscalibrated. 02068 has more people +
   more visual ambiguity (the conservatory architecture is curved-glass,
   which Gemini can read as an NYC botanical pavilion if it doesn't
   strongly anchor on the Detroit GEDCOM data).

## What this means for the prompt deployment decision

**Do NOT deploy the candidate prompt to production based on this evidence.**

The Detroit gate was specifically designed to catch the 153b-style failure
(NYBG hallucination). 02068 still fails it under all 3 variants WITH GEDCOM
context. Production deployment would risk regressing other photos similarly.

Two follow-up paths the next session should consider:

**Path A — Strengthen the prompt's geographic anchoring against GEDCOM.** The
current prompt says "subject's own residence outweighs relative's residence"
but it doesn't FORCE Gemini to score the proposed `place` against a residence
match. Add an explicit step: "before naming a primary place, list the
distance in years between the photo's likely date range and each candidate
city's RESI events for the named subjects. The candidate with the smallest
date-distance and ≥1 RESI match wins ties."

**Path B — Multi-frame approach (PRD-061 event clustering).** Since the
visual ambiguity dominates on 02068, more visual evidence might help. PRD-061
proposes clustering 02068 + 01659 + any other Belle Isle frame into a single
"event" and giving Gemini all of them at once. The 01659 candidate run got
Detroit right; pooled visual evidence might pull 02068 along.

Both paths require new design work. Neither is in scope for Session 154.

## Cost / latency

- 6 calls / $0.168 / 257 sec total wall clock.
- candidate_with_prior latencies (72-37 sec) are 2-3× the single-pass
  candidate latencies — Gemini is doing more work on the second pass even
  though the prompt is similar length. Not a deal-breaker but factors into
  any future production decision.

## Pre-existing data anomalies (out of scope for A3 but worth noting)

- The registry's "Harry Fox" identity (Harshel) is in the GEDCOM context for
  both Detroit photos, even though Track B confirmed F+G in 02068 are NOT
  Harshel. The repair is gated; until it lands, the GEDCOM context for
  these photos contains an incorrect name. This may have negligible impact
  on the location prediction (Harshel's residences span Dayton/Brooklyn,
  not Detroit) but it is a known data quality issue.

## Schema verification

The Phase A0 migration landed cleanly. Spot check:
- `experiment_id` column populated for all 6 of this run's rows
- `gemini_config.gedcom_context_present` = true on all 6
- `gemini_config.pass` correctly distinguishes `pass=1` (baseline + candidate)
  from `pass=2` (candidate_with_prior)
- The retry-with-backoff did not fire (no 5xx during this run)
