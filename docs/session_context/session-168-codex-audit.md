# Session 168 — Codex / Fable Audit Log (IN PROGRESS)

**Auditor(s):** Fable 5.0 (architect/auditor) + Codex CLI v0.142.5 (gpt-5.5, xhigh, coder)
**Agent type:** Independent (fresh context per dispatch)
**Date:** 2026-07-01
**Status:** IN PROGRESS — appended per implementation batch.

## Model roles this session
- **Fable 5.0** — holistic deep dive (architect) + post-batch audits (auditor).
- **Codex CLI (gpt-5.5/xhigh)** — implementation (coder), invoked via
  `codex exec "<spec>" </dev/null` (never --full-auto per ai-tool-audit.md).
- **Opus 4.8** — orchestration + design + triage.

## Batch 1 — NL-QUERY-REDOS-167 (commit 33e69c9b)
- **Coder:** Codex CLI (gpt-5.5/xhigh), ~31.5k tokens. **Status:** SHIPPED.
- **Changes:** `MAX_QUERY_LEN=512` early-return; bounded all person/relationship regex
  captures `(.+)`→`(.{1,256})` (identical capture semantics); added blocking
  `pytest rhodesli_ml/tests/` step to `.github/workflows/test.yml`.
- **Codex self-verify:** nl_query 33 passed (0.08s incl. test_very_long_input);
  full ML suite 723 passed; ruff clean; YAML parse OK.
- **Opus review:** cap returns `unknown` for >512 chars (real queries are short —
  no UX regression); quantifier bounds preserve group semantics; CI step is blocking. APPROVED.
- **Fable audit:** PENDING (folded into post-batch audit pass).

## Batch A (Codex) — commit 6501eea7 (F1/F2/F3-lint)
- importorskip guards (7 collect-only offenders) + nl_query regression tests + CI/local lint→rhodesli_ml.
- Codex self-verify + Opus independent verify (validator rc=0, 725 ML pass, ruff clean). APPROVED.

## Batch B (Codex) — commit 1c241cf1 (F4/F5)
- 3 stale test groups refreshed. test_supabase_data.py override-suite → 29 anti-reintroduction guards.
- Opus spot-checked the startup-sync guard (asserts sync never reads removed identity_overrides). APPROVED.

## Batch C (Codex) — commit 39a2b3d8 (F7a/F10)
- /health served-count + dead prefill_description removal. Opus reviewed diff + tests. APPROVED.

## FABLE INDEPENDENT PRE-PUSH AUDIT (auditor, fresh context, ~188k tokens)
**Verdict: everything safe to push EXCEPT one P0 — fixed before push.**

### P0 (CAUGHT + FIXED, commit b-P0) — CI ML step would fail at RUNTIME
- Job A's `--collect-only` validator only sees MODULE-level imports. **5 more modules**
  (`test_mlflow_registry`, `test_promote_model`, `test_progressive_refinement` [TestMLflowTracking],
  `test_calibration_onnx`, `test_date_export_onnx`) import torch/mlflow **inside tests/fixtures** →
  collect clean but FAIL at runtime in CI (**20 failed + 5 errors, rc=1**, reproduced by Opus). Would
  have turned main red on first push — the exact Lesson-209 mode this session set out to kill.
- Also corrected the CI-absent dep set: **insightface transitively provides onnx+sklearn+matplotlib**,
  so the true CI-absent set is `{torch,torchvision,mlflow,pytorch_lightning,lightning,torchmetrics}`.
- **Fix:** added runtime importorskip guards (module-level where dep-wide, per-test where mixed).
  New RUNTIME validator (`scripts/check_ml_suite_ci_safe.py`) → **rc=0 (554 pass, 13 skip)**; full venv
  725 pass. This is the highest-value catch of the session.

### P1 — none.

### P2 (DONE, commit P2) — validator methodology corrected + institutionalized
- `--collect-only` insufficient + BLOCKED set was inaccurate. Landed the run-mode simulation as
  `scripts/check_ml_suite_ci_safe.py` with the corrected dep set; CI step comments point future ML-test
  additions at it.

### P3 (noted, no action)
- CI `timeout-minutes: 10` — ML suite mostly skips heavy tests in CI (+1–4 min); likely fine, 15 would
  remove risk. Judgment call — left at 10.
- nl_query intent shift for >256-char name segments (garbage-in either way) — acceptable per cap design.
- /health `photos` semantic change — no in-repo consumer reads the top-level count (monitor reads
  `supabase` field; smoke test doesn't read it) — intended change.

### Fable clean verdicts (with evidence, not taken on faith)
1. `test_supabase_data.py` rewrite — SOUND, coverage IMPROVED. Ran the OLD file vs current source: exactly
   6 tests fail, all asserting the identity_overrides mechanism removed in S130 (commit 547826e5) for
   *causing* the Lesson-153 corruption. Replacements are meaningful (assert_not_called, AssertionError
   side-effects, real `shadow_write_identities_batch(strict=True)` path). DATA-001 still guarded by
   test_single_source_of_truth (14) + test_data_layer_invariants (13).
2. nl_query — semantically identical for real queries; 3 ReDoS inputs return ≤26ms; cap logic correct.
3. /health — photos_pg fallback correct; data_parity.synced untouched.
4. test_public_photo_viewer — new assertion matches the S165 prevUrl/nextUrl end-clamping template (coverage gain).
5. F541 sweep — 42 mechanical, no placeholders lost.
6. prefill_description — zero remaining consumers.

**AI Tool Usage:** Fable 5.0 (architect: 13-finding dive; auditor: 1 P0 caught pre-push + clean verdicts)
= STRONG (the P0 would have red-mained production; would NOT have been caught without a runtime sim).
Codex CLI gpt-5.5/xhigh (coder, 4 jobs) = STRONG (clean implementations, self-verified each).
