# Session 167 — Track A (Ops Hardening) — Codex Audit

**Auditor**: Codex CLI v0.142.4 (gpt-5.5, xhigh — per `~/.codex/config.toml`)
**Agent type**: Independent (fresh context, no prior knowledge of the work)
**Scope**: Track A new files — `scripts/supabase_monitor.py`,
`scripts/backfill_gedcom_estimates.py`,
`scripts/migrations/session167_gemini_api_calls_lineage_cols.sql`, and their tests
**Invocation**: `codex exec "<prompt>" </dev/null` (never `--full-auto`)
**Date**: 2026-06-30

Two independent audit passes were run (kicked off EARLY per the fox-genealogy
HARNESS_VALUE_LOG lesson): one on the monitor, one on the survey + migration.

---

## Pass 1 — `scripts/supabase_monitor.py` + tests

**Verdict**: no P0. One STRONG P1 (acted on), several P2 test-coverage gaps (acted
on), one P3 (acted on).

> Note: Codex ran the test file outside the venv so the collection ERROR'd on
> `ModuleNotFoundError: fasthtml`. That is a Codex-environment artifact, NOT a
> real failure — the suite passes in the project venv. The static findings below
> are what mattered.

### P1 (FIXED) — `skipped` masked the over-quota failure
The monitor treated `/health` `supabase="skipped"` as healthy. But that field is
the app's once-per-hour throttled ping (`_ping_supabase`), so it is USUALLY
`"skipped"` — and Management-API `ACTIVE_HEALTHY` does not catch a DB-size REST/Auth
402. Net: the monitor could exit 0 during the exact over-quota outage it exists to
catch.
**Fix** (commit `5260cea5`): added `check_supabase_rest()` — a FRESH, unthrottled
`GET {SUPABASE_URL}/auth/v1/health` probe as the PRIMARY reachability signal
(catches 402 + NXDOMAIN directly, never masked by the throttle). `"skipped"` is now
INCONCLUSIVE (`ok=None`), only literal `"ok"` passes. Added an `inconclusive` flag
→ WARN (exit 0) so an all-skip state is never a false green.
**Assessment**: STRONG. Real semantic bug that unit tests with canned responses
would not have surfaced; would have defeated the monitor's whole purpose.

### P2 (FIXED) — `--require-mgmt` only tested at the function level
No `run_monitor(require_mgmt=True, token=None)` or `main([..., "--require-mgmt"])`
assertion. **Fix**: added `test_run_monitor_require_mgmt_no_token_alerts` +
`test_main_require_mgmt_threads_through`.

### P2 (FIXED) — alert output contract untested
No `ALERT:`→stderr, `--json`, or stdout/stderr-split assertions. **Fix**: added
`test_main_exit_one_on_alert_prints_alert_to_stderr`, `test_main_json_output`,
`test_main_exit_zero_on_healthy` (asserts stdout + empty stderr).

### P2 (FIXED) — no secret-leakage assertion
Tests dropped request headers, so token-only-in-headers + no-leak-in-output was
unverified. **Fix**: `FakeClient.calls` now records headers; added
`test_rest_probe_sends_apikey_header_only`, `test_project_sends_bearer_header_only`,
and `test_token_never_appears_in_output` (asserts neither the Management PAT nor the
anon key appears in the formatted report or the JSON).

### P2 (FIXED) — missing mgmt/keep-alive transport-exception coverage
**Fix**: added `test_project_mgmt_transport_exception_fails` +
`test_keep_alive_transport_exception_reported`.

### P3 (FIXED) — FakeClient comment claimed callable-raising support it lacked
**Fix**: implemented callable support in `FakeClient._resolve` (used by the new
transport-error tests).

Monitor tests: 22 → **35**, all green.

---

## Pass 2 — `scripts/backfill_gedcom_estimates.py` + migration + tests

(Findings appended on completion of the second `codex exec` run; see below.)

<!-- PASS2_FINDINGS -->

---

## AI Tool Usage (summary)
- **Tool**: Codex CLI v0.142.4 (gpt-5.5, xhigh) — independent, fresh context.
- **Task**: security/correctness/test-quality audit of Track A scripts + migration.
- **Pass 1 findings**: 0 P0, 1 P1, 5 P2, 1 P3 — ALL acted on (P1 + P2s + P3 fixed).
- **Value assessment**: STRONG — the P1 (`skipped`-masking) was a genuine logic
  defect that would have rendered the monitor blind to the exact failure it targets.
  Would-we-have-found-it-ourselves: unlikely without this audit; the happy-path tests
  all passed.
