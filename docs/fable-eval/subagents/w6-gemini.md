# W6 — DETROIT-PROMOTE-167 Implementation-Readiness Assessment (Gemini prompt-fix promotion)

**Analyst**: Fable 5 subagent (read-only, $0 spend, zero API calls)
**Date**: 2026-07-02
**Scope**: Is promoting the DETROIT-CANDIDATE-FORCE-167 candidate-force from the shadow harness
(`scripts/session153_shadow_eval.py`) into the production prompt builder
(`rhodesli_ml/gemini_extraction.py`) implementation-ready today?

---

## Readiness Decision Table

| Dimension | Status | Evidence |
|---|---|---|
| **Prompt-change implementation status** | **NOT in production.** Production location section is the original single-pass soft guidance ("residence ALWAYS overrides immigration" prose, no Round-2.5, no forced candidates, no AD-242 prior-retry). The validated mechanism exists ONLY in the shadow harness: `build_forced_candidates()` (`scripts/session153_shadow_eval.py:491`), `render_forced_candidates_block()` (`:545`), Round-2.5 v2 tie-breaker (`CANDIDATE_LOCATION_SECTION`, `:210`), tightened CONFIRM (`PRIOR_PREDICTION_BLOCK`, `:584`). `rhodesli_ml/gemini_extraction.py:173-222` (location section) and `:506-518` (location response schema — no `residence_distance_table`, no `round_2_5_summary`) are untouched, exactly as the eval doc states (`docs/feedback/session-167-detroit-eval.md:141-142, 259-262`). | Shadow-validated, production-absent |
| **Eval harness status** | **Runnable today, bounded, deterministic.** CLI supports `--dry-run` ($0), `--photo-ids` (Detroit-only subset), `--variants`, `--max-cost` + `--max-calls` mechanical double-cap with per-call LEDGER + in-loop abort (`:1250-1262`), `--no-db-log` (zero Supabase writes), `--gedcom-context-fixture` (fresh post-Harry-repair fixture `tests/fixtures/session167_gedcom_context.json` exists), `--photo-root`, `--experiment-id`/`--out-path` (provenance). Detroit subset ≈ 6 calls ≈ **$0.19–0.30** (Session 167 actuals: $0.1935 and $0.30). Full 12-photo × 3-variant sweep ≈ $1.5–2.0. **Caveat**: the harness evaluates its OWN embedded candidate prompt; its "baseline" is a verbatim COPY of production as of 2026-04-18 (`:163-165`). It cannot currently exercise a *promoted* production `build_extraction_prompt()` — post-promotion re-validation needs the harness to import the production builder (or a new variant mode). | Ready for shadow re-runs; NOT wired to test the promoted production prompt |
| **Regression gate coverage** | **Narrow: 2 photos.** Detroit gate = 02068 + 01659, pass = top-1 `place` alias-matches {Belle Isle, Detroit} at ≥ medium confidence under `candidate_with_prior`, no regression under `candidate` vs baseline (AD-243 acceptance, `docs/ml/ALGORITHMIC_DECISIONS.md:2805`). Grading is substring alias match in `evaluate_result()` (`:986-1055`) plus the de-gamed `predicted_place_year_distance` (`_canonical_year_distance_for_place`, `:966`). Gate PASSED in the fresh-context run (eval doc `:178-186`). **Gaps**: (a) no mechanical `detroit_gate_pass`/`primary_correct` fields — the gate verdict is assembled by a human reading verdicts (DETROIT-GUARD-VALIDATE-167, `docs/BACKLOG.md:24`); (b) substring matching (`matches_any`, `:1026`) lacks word boundaries (BACKLOG:24); (c) the other 10 test-set photos (Rhodes ×2, Tampa ×2, Dayton ×2, Fader, Newspaper ×2, Congo — `:81-160`) have **never been run WITH the candidate-force** — zero evidence the mandatory-candidate block doesn't degrade GEDCOM-linked photos taken away from home (travel/diaspora frames, the Rhodes-collection caveat at `:86`). | Detroit-positive proven; anti-regression on non-Detroit GEDCOM photos unproven |
| **Validation fields / tests missing** | 27 unit tests exist for the force helpers (`tests/test_detroit_candidate_force.py` — parser, place-key normalization, relative-exclusion, empty-context) but they import from `scripts.session153_shadow_eval`, not from any production module. Missing: (1) structured `prior_decision`/`confirming_event`/`year_distance`/`round_2_5_winner` response fields + mechanical citation-exists validation (DETROIT-GUARD-VALIDATE-167, P1, OPEN); (2) a structural test that `rhodesli_ml.gedcom_context.build_photo_context` output format matches `extract_subject_residences()`'s regex contract (`Person: ` / `  Residential History:` / 4-space rows, `:448-486`) — format drift would make the parser return `[]` → force silently never fires (Lesson 205 fail-open class); (3) production-side threading tests (none exist — nothing to test yet); (4) the Lesson-208 one-photo real-pipeline check DETROIT-PROMOTE-167 itself requires (`docs/BACKLOG.md:23`). | Harness-level coverage good; production-level coverage nonexistent |
| **Risk: promote now vs wait** | **Promoting now is blocked by an unresolved design dependency: `photo_year`.** `build_forced_candidates()` returns `[]` without a FIXED photo year (`:505`); the harness gets it from hand-set archival metadata (`TEST_SET "photo_year": 1918`, `:64-68`) and the de-game property (model can't shift the year to rescue Brooklyn) depends on it being external to the model. Production `/tools/estimate` **estimates** the date — no fixed year exists at prompt-build time (`app/estimate_routes.py:866-868` builds the quick preset in one combined date+location call). Options (none designed): existing `date_labels` year for reanalysis-only; user text-hints (Estimate v2); two-pass (self-estimated year — weakens de-gaming). Secondary risks: quick-preset restructuring changes the location response schema for every caller (`estimate_routes.py`, `admin_routes.py`, `scripts/batch_*.py`, `multimodel_photo_estimate.py`); forced candidates could anchor travel photos to home residences (Rule-3 visual fallback exists but untested at scale). **Waiting is cheap**: 02068 + 01659 were manually corrected in Supabase (Session 156 Track F) — no ongoing user-facing harm; failure class only affects future estimates, and manual override exists. | Wait-cost LOW; premature-promote cost MODERATE-HIGH |
| **What a ~$0.50 bounded paid eval must prove** | (after implementation, not before): (1) 02068 + 01659 pass the Detroit gate under the **promoted production prompt path** (candidate + candidate_with_prior equivalents, ~6 calls, ~$0.20); (2) ≥2 GEDCOM-linked non-Detroit controls (Dayton pair `:112-125`, Fader `:127-133`) do not regress vs their 153b/154 baseline verdicts with the force active (~$0.15–0.25); (3) one end-to-end real-pipeline run per Lesson 208: verify the `gemini_api_calls` row logs `prompt_text` containing the forced block, GEDCOM context non-empty, and the estimate reaches the read path (~1 call, ~$0.03). Total ≈ **$0.40–0.50**, within the DETROIT-PROMOTE-167 pattern of prior bounded evals ($0.19/$0.30 under $0.40–0.50 caps). | Well-defined, affordable, but only meaningful POST-implementation |
| **VERDICT** | **NOT-READY — BLOCKED ON photo_year-source design + production integration design; then NEEDS-PAID-EVAL (~$0.50).** The candidate-force *mechanism* is validated (02068 flips to Detroit/high under fresh AND stale context — eval doc `:178-186, 220-224`), deterministic, and unit-tested. But DETROIT-PROMOTE-167 is a **design-and-implement task, not a flip-a-flag ship**: production has no fixed photo year to feed the force, no integration point (`build_extraction_prompt` has no `forced_candidates`/`photo_year` params), no schema fields for Round-2.5 output, and no post-promotion eval path. Zero of the promotion code exists in `rhodesli_ml/` or `app/`. | — |

---

## Missing pieces (file:line evidence)

1. **`photo_year` source for production** — `scripts/session153_shadow_eval.py:493,505` (force requires fixed
   year; `[]` otherwise) vs `app/estimate_routes.py:866-868` (production single-pass estimates the date it
   would need as input). Undesigned. THE blocker.
2. **`build_extraction_prompt()` has no candidate-force surface** — `rhodesli_ml/gemini_extraction.py:313-321`
   signature lacks `forced_candidates`/`photo_year`; location section `:173-222` has no Round-2.5; response
   schema `:506-518` lacks `residence_distance_table`/`round_2_5_summary`/`candidates` fields.
3. **Force helpers live in a script, not a library** — `scripts/session153_shadow_eval.py:391-578`. Promotion
   means extracting `extract_subject_residences`/`build_forced_candidates`/`render_forced_candidates_block`
   into `rhodesli_ml/` (tests currently import from `scripts.`: `tests/test_detroit_candidate_force.py:23-30`).
4. **Parser↔context-format coupling unguarded** — `extract_subject_residences` regex contract (`:448-486`)
   against `rhodesli_ml.gedcom_context.build_photo_context` output; drift → silent no-op (Lesson 205 class).
   No structural test pins the format.
5. **Gate is not mechanical** — `evaluate_result` (`:986`) emits per-call verdicts only; no
   `detroit_gate_pass`, no citation-exists check, substring (not word-boundary) alias matching. Open items
   DETROIT-GUARD-VALIDATE-167 (P1) + DETROIT-PROVENANCE-167 (P2), `docs/BACKLOG.md:24-25`.
6. **No non-Detroit force regression data** — the force has only ever run against the 2 Detroit controls;
   10-photo remainder of TEST_SET (`:81-160`) untested with the mandatory-candidate block.
7. **Harness cannot eval the promoted prompt** — baseline is a frozen 2026-04-18 copy (`:163-165`);
   post-promotion the harness must import the production builder or the re-validation is theater.
8. **AD entry for the promotion** — AD-243 explicitly gates production deployment on eval evidence
   (`docs/ml/ALGORITHMIC_DECISIONS.md:2804`); the promotion itself will need a new AD (ml-documentation rule).

## Recommended promotion sequence (no API calls until step 4)

1. Design decision: `photo_year` source (suggest: reanalysis path uses existing `date_labels` year;
   first-pass uploads SKIP the force — fail-open exactly as `build_forced_candidates` already does).
2. Extract force helpers to `rhodesli_ml/` + add `forced_candidates` param to `build_extraction_prompt` +
   schema fields; port the 27 tests; add the format-pin structural test ($0).
3. Wire the shadow harness to a `--production-prompt` variant mode ($0, dry-run verifiable).
4. Bounded paid eval per the table row above (~$0.50, user-gated).
5. Lesson-208 one-photo real-pipeline verification; then new AD + ship.

## User Decisions (requires paid eval — logged, NOT executed)

- **UD-1**: Authorize the post-implementation bounded eval, ~$0.40–0.50, ~9 calls
  (Detroit gate ×6 + non-Detroit controls ×2-3 + Lesson-208 pipeline check ×1), `--no-db-log` except the
  final pipeline check, `--experiment-id session1XX_detroit_promote`.
- **UD-2 (optional)**: Full 12-photo × candidate-variant regression sweep with the force active,
  ~$1.5–2.0 — the only way to fully de-risk the mandatory-candidate block on travel/diaspora frames
  before it touches every GEDCOM-linked estimate.
- **UD-3 (data, not eval)**: Investigate Irving Fox's contradictory `1917-1918 Brooklyn` vs `1917 Detroit`
  GEDCOM residences (eval doc `:136-137`) — a genealogy-sourcing question for Nolan; cleanup would reduce
  reliance on the Rule-3 visual fallback.
