# Session 167 — Track D Codex Audit (Detroit prompt fix)

**Auditor:** Codex CLI v0.142.4 (gpt-5.5, xhigh)
**Agent type:** Independent (fresh context) — run by orchestrator after the track
agent conn-dropped before saving its own audit.
**Scope:** `scripts/session153_shadow_eval.py` + `tests/test_shadow_eval_prompt_structure.py`
diff vs main (Round-2.5 residence-distance tie-breaker + toothy sycophancy guard).
**Date:** 2026-06-30 · tokens ~70,481 · raw: `session-167-track-d-codex-audit.raw.txt`
**Value:** STRONG — the top P1 explains the 02068 failure.

## Findings + disposition

**No P0.**

- **P1 — Round-2.5 cannot rescue an omitted candidate** (ROOT CAUSE of 02068 fail).
  The model proposes 2–3 candidate locations first, then only scores those; if it
  never lists Detroit, the GEDCOM tie-breaker can't pick it.
  **Fix:** force any GEDCOM place with `year_distance ≤ 5` into `candidates[]` /
  `residence_distance_table` via a deterministic pre-extraction step.
  → **BACKLOG: DETROIT-CANDIDATE-FORCE-167** (the next concrete step on Path A).
- **P1 — Sycophancy guard is prompt-only, not confabulation-proof.** No schema fields
  for `prior_decision`/`confirming_event`/`year_distance`/`round_2_5_winner`, and
  `evaluate_result` doesn't verify the guard's claims → a model can invent a named
  event and pass. **Fix:** structured prior-crosscheck fields + mechanical validation
  (exact citation substring in supplied GEDCOM context, numeric year_distance, winner
  consistency). → **BACKLOG: DETROIT-GUARD-VALIDATE-167**.
- **P1 — Default provenance clobbers Session 167.** `experiment_id` defaults to
  `session154_...` and the Detroit output overwrites the session-154 json.
  **Fix:** derive defaults from a required session label + timestamped filename +
  refuse overwrite without `--overwrite`. → **BACKLOG: DETROIT-PROVENANCE-167** (P2-effort).
- **P2 — Date selection gameable** (year_distance uses the model's own photo-year).
  Fix: fix the eval photo-year from metadata / grader recompute. → BACKLOG (folded into FORCE-167).
- **P2 — `evaluate_result` can mask wrong primaries** (`candidate_has_answer` reads as
  partial success; alias raw-substring match). Fix: explicit `primary_correct` /
  `detroit_gate_pass = top1 && conf∈{med,high}` + word-boundary alias norm. → BACKLOG (GUARD-VALIDATE-167).
- **P2 — Tests are string-presence only.** Add behavioral tests around a validator with
  synthetic outputs (invented citation, wrong winner, year_distance>5, missing Detroit
  candidate, stale output path). → folded into the fix BACKLOG items.
- **P3 — call counters inconsistent** (`n_calls = len(results)` not `call_count`). Minor.

## Net
Track D delivered an honest diagnosis: Path A (residence-distance scoring + toothy guard)
is **necessary but not sufficient** — 01659 now PASSES (Detroit/high), 02068 still FAILS
because the candidate-omission gap (top P1) bypasses the whole tie-breaker. The next
concrete step is DETROIT-CANDIDATE-FORCE-167, then re-run the bounded eval (needs ~$0.30
Gemini $). Nothing here blocks committing the honest-partial work.

---

## Fresh-context continuation audit (Session 167 cont., 2026-06-30)

**Auditor**: Codex CLI v0.142.4 (gpt-5.5, xhigh) | **Agent type**: Independent (fresh context)
**Scope**: commit `e967fa57` ONLY — new fixture `tests/fixtures/session167_gedcom_context.json`,
3 new tests in `tests/test_detroit_candidate_force.py`, the `## Fresh-context attempt` section
of `docs/feedback/session-167-detroit-eval.md`, and the two raw eval JSONs. No production code
changed. **Verdict: SAFE — P0 None, P1 None.**

### Findings + dispositions
- **P2 — doc claimed Rule 2 as the deterministic decider.** REAL accuracy issue: the forced
  table shows Detroit and Brooklyn EACH have one distinct subject at d=0 (Irving's Detroit is
  1917 = d=1), so it is a 1-vs-1 tie and the honest decider is Rule 3 (visual). The
  `candidate` run's Rule-2 self-report miscounted. **FIXED** — doc now labels the Rule-2 line
  a model self-report and states the deterministic 1-vs-1 tie + Rule-3 decider (3 edits).
- **P3 — call-count (doc "6 calls" vs raw `n_calls` 4+1).** "6 actual Gemini calls" is correct;
  raw `n_calls = len(results)` counts result rows only (silent first pass adds no row — the
  pre-existing artifact Codex flagged in the earlier Track-D audit). **FIXED** — doc annotates
  the distinction.
- **P3 — Harry-removal test only checked parsed residences.** **FIXED** — added a header
  assertion (`"Harry" not in header`, Irving + Albert present).
- **P2 — raw JSON 390 lines > 300-line doc cap. REJECTED:** `doc-size-enforcement.md` / the
  `test_*_doc` checks govern `.md` documentation, not machine-generated `.json` data artifacts.
  Consistent with the already-committed `session-167-detroit-eval-raw.json` / `-v2-raw.json`.
- **P3 — fixture not data-minimized. REJECTED (by design):** the fixture must be the EXACT
  context the production pipeline builds and the eval consumes; slicing it would make the
  regression test unfaithful. Mirrors the existing full-context `session154_gedcom_context.json`.

### Value assessment
**MODERATE** — no security/correctness bug, but the Rule-2 P2 caught a genuine honesty gap in
the writeup (deterministic tie was being narrated as a Rule-2 win). Worth the ~3-min fix.
