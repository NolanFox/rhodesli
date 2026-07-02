# W6 — Gemini / Estimate + DETROIT-PROMOTE-167 Readiness (analysis only, $0, zero API calls)

**Synthesis of** `subagents/w6-gemini.md` (full file:line evidence). Question: is promoting the
DETROIT-CANDIDATE-FORCE-167 mechanism from the shadow harness into production
(`rhodesli_ml/gemini_extraction.py`) ready to ship today?

## Readiness decision table

| Dimension | Status | Evidence |
|-----------|--------|----------|
| **Prompt-change implementation** | **NOT in production.** Validated mechanism lives ONLY in the shadow harness: `build_forced_candidates()` (`scripts/session153_shadow_eval.py:491`), `render_forced_candidates_block()` (`:545`), Round-2.5 tie-breaker (`:210`), tightened CONFIRM (`:584`). Production location section (`rhodesli_ml/gemini_extraction.py:173-222`) + response schema (`:506-518`) are untouched — original single-pass soft guidance | Shadow-validated, production-absent |
| **Eval harness** | **Runnable today, bounded, deterministic.** `--dry-run` ($0), `--photo-ids` (Detroit subset), `--max-cost`/`--max-calls` double-cap + in-loop abort (`:1250`), `--no-db-log`, fresh GEDCOM fixture. Detroit subset ≈6 calls ≈**$0.19–0.30** (S167 actuals). **Caveat:** baseline is a frozen 2026-04-18 copy of production (`:163`) — the harness canNOT yet exercise a *promoted* production builder | Ready for shadow re-runs; not wired to test the promoted prompt |
| **Regression gate** | **Narrow: 2 photos** (02068 + 01659). Pass = top-1 place alias-matches {Belle Isle, Detroit} ≥ medium under `candidate_with_prior`, no regression under `candidate` (AD-243, `ALGORITHMIC_DECISIONS.md:2805`). Gate PASSED in the fresh run. **Gaps:** no mechanical `detroit_gate_pass` field (human-assembled); substring match lacks word boundaries; the **other 10 test-set photos never run WITH the force** → zero evidence it doesn't degrade GEDCOM-linked travel/diaspora photos | Detroit-positive proven; anti-regression unproven |
| **Validation fields/tests missing** | 27 unit tests exist but import from `scripts.session153_shadow_eval`, not any production module. Missing: structured Round-2.5 response fields + citation-exists check (DETROIT-GUARD-VALIDATE-167, P1); a structural test pinning `gedcom_context.build_photo_context` output to the parser's regex contract (`:448-486`) — format drift → parser returns `[]` → force silently never fires (Lesson 205 fail-open); production threading tests (nothing to test yet); the Lesson-208 one-photo real-pipeline check | Harness coverage good; production coverage nonexistent |
| **Risk: promote now vs wait** | **Blocked by an undesigned dependency: `photo_year`.** `build_forced_candidates()` returns `[]` without a FIXED year (`:505`); the de-gaming property depends on the year being external to the model. Production `/tools/estimate` **estimates** the date in one combined call (`app/estimate_routes.py:866-868`) — no fixed year exists at prompt-build time. Secondary: restructuring the quick preset changes the location schema for every caller (estimate/admin/batch/multimodel). **Wait-cost is LOW:** 02068+01659 already manually corrected in Supabase (S156 Track F); failure only affects *future* estimates and manual override exists | Wait-cost LOW; premature-promote cost MODERATE-HIGH |
| **What a ~$0.50 bounded eval must prove (POST-implementation)** | (1) 02068+01659 pass the Detroit gate under the **promoted production path** (~6 calls, ~$0.20); (2) ≥2 GEDCOM-linked non-Detroit controls (Dayton pair, Fader) don't regress with the force active (~$0.15–0.25); (3) one Lesson-208 real-pipeline run verifying the `gemini_api_calls` row logs the forced block, GEDCOM context non-empty, estimate reaches the read path (~$0.03). Total ≈**$0.40–0.50** | Well-defined, affordable, only meaningful post-implementation |
| **VERDICT** | **NOT-READY — BLOCKED ON `photo_year`-source design + production-integration design; THEN NEEDS-PAID-EVAL (~$0.50).** The mechanism is validated, deterministic, unit-tested — but this is a **design-and-implement task, not a flag flip**: zero promotion code exists in `rhodesli_ml/` or `app/`; no fixed photo year to feed the force; no integration point; no schema fields; no post-promotion eval path | — |

## Recommended promotion sequence (no API calls until step 4)
1. **Design `photo_year` source** (suggest: reanalysis uses existing `date_labels` year; first-pass
   uploads SKIP the force — fail-open, as `build_forced_candidates` already does).
2. Extract force helpers to `rhodesli_ml/` + add `forced_candidates`/`photo_year` params to
   `build_extraction_prompt` + schema fields; port the 27 tests; add the format-pin structural test ($0).
3. Wire the harness to a `--production-prompt` variant mode ($0, dry-run verifiable).
4. Bounded paid eval (~$0.50, user-gated).
5. Lesson-208 one-photo real-pipeline verification → new AD → ship.

## User Decisions (require paid eval — logged, NOT executed)
- **UD-1:** Authorize the post-implementation bounded eval (~$0.40–0.50, ~9 calls, `--no-db-log`
  except the final pipeline check).
- **UD-2 (optional):** Full 12-photo × candidate-variant regression sweep with the force active
  (~$1.5–2.0) — the only way to fully de-risk the mandatory-candidate block on travel/diaspora frames.
- **UD-3 (data, not eval):** Resolve Irving Fox's contradictory `1917-1918 Brooklyn` vs `1917 Detroit`
  GEDCOM residences — a genealogy-sourcing question that reduces reliance on the Rule-3 visual fallback.
