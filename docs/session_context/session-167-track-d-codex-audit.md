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
