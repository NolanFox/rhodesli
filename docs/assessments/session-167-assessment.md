# Session 167 Assessment — Multi-Track Autonomous Feature Sprint

**Status: COMPLETE** (4 tracks merged to main + deployed; 1 track committed-pending on sibling branch).
**Type:** EXPERIMENT — autonomous parallel throughput, Opus-orchestrated / Codex-coded / Codex-audited.

## Shipped (evidence)
- [x] **Track A — Ops hardening** — branch `session-167/ops-hardening`, 7 commits. `scripts/supabase_monitor.py`, `scripts/backfill_gedcom_estimates.py` (survey), `migrations/.../session167_gemini_api_calls_lineage_cols.sql`, Codex-pin refresh, GEDCOM-TEST-FIX no-op confirmed. +619 tests. Codex audit: `session-167-track-a-codex-audit.md`.
- [x] **Track B — Estimate v2 (PRD-055)** — branch `session-167/estimate-v2`, 2 commits. GEDCOM paste + text hints + geography retry in `app/estimate_routes.py`. 30 tests. Audit raw: `session-167-track-b-codex-audit.raw.txt`.
- [x] **Track C — Self-service archive (PRD-060)** — branch `session-167/onboarding`, 1 commit. `app/onboarding_routes.py`, feature-flag OFF, Codex P1 fixed. +38 tests. Decisions: `docs/feedback/session-167-track-c-decisions.md` (D1 → any logged-in user).
- [x] **Track D — Detroit fix** — branch `session-167/detroit-fix`, 2 commits. Round-2.5 + toothy guard. Eval $0.30: 01659 PASS, 02068 FAIL. 28 tests. Audit: `session-167-track-d-codex-audit.md`.
- [x] **Merge + gate** — all 4 merged to main (20 commits, 0 conflicts). `make test-fast` **4471 pass**, ruff clean.
- [-] **Track E — rhodes-wiki RHODES-WIKI-004** — IMPLEMENTED + tested (249) on `session-167/rhodes-wiki-004`, NOT committed (cross-repo boundary; M12). Handoff: TRACK-E-COMMIT-167.

## Deferred (with BACKLOG)
- DETROIT-CANDIDATE-FORCE-167 (P1, running this session cont.) — the real 02068 fix.
- TRACK-E-COMMIT-167 (P1) — commit rhodes-wiki work from its own session.
- NL-QUERY-REDOS-167 (P2, pre-existing) — ReDoS in nl_query, untouched by 167.
- DETROIT-GUARD-VALIDATE-167, DETROIT-PROVENANCE-167, HARNESS-CROSS-REPO-GUARDS-167, SELF-SERVICE-ARCHIVE-ENABLE-167.

## Red flags
- **Harness gap (P2):** cross-repo write-deny doesn't enforce under `bypassPermissions` (M8); commit-hook breaks sibling-repo commits + trips on "git commit" prose (M12/M13). → HARNESS-CROSS-REPO-GUARDS-167.
- **Pre-existing ML failure** surfaced by the merge gate (NL-QUERY-REDOS-167); CI runs only the app suite, so it was latent. → add ML suite to CI.

## Next session should verify FIRST
1. Production health 200 + Estimate v2 renders the new fields + supabase_monitor importable.
2. DETROIT-CANDIDATE-FORCE-167 re-eval result (did 02068 finally predict Detroit?).
3. TRACK-E-COMMIT-167 from a rhodes-wiki session.

## AI Tool Usage
- **Tool:** Codex CLI v0.142.4 (gpt-5.5, xhigh) — coding engine for all 5 tracks + 1 session-level plan-audit + per-track boundary audits + 1 orchestrator-run Track D audit.
- **Agent type:** Independent (fresh context) for audits.
- **Findings:** plan-audit 2 P0 + 4 P1 + 4 P2 (all dispositioned, corrected live); per-track P1s fixed or BACKLOG'd.
- **Value:** STRONG — the plan-audit's Track-B brief-vs-PRD catch + Track-D candidate-omission root-cause + Track-C fail-open write-path P1 each prevented a real defect. Full record: `docs/session_context/session-167-codex-audit.md` + per-track files.
- **Would we have found these ourselves?** The brief-vs-PRD contradiction and the candidate-omission root cause: unlikely without the boundary audit.

## Experiment verdict
5-way parallelism with Opus-orchestrator/Codex-coder/Codex-auditor **works**, given: disjoint file ownership, a boundary audit before deep work, explicit shared-doc freeze, mechanical (not behavioral) $/write caps, and one session per repo. Throughput beat overhead. 13 meta-lessons in `session-167-meta-lessons.md`.
