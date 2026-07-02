# Session 168 Meta-Lessons — The Opus/Fable/Codex Three-Model Split

**Analyst:** Fable 5.0 (meta-analysis) + Opus 4.8 (orchestrator, direct observation)
**Date:** 2026-07-02
**Scope:** two autonomous rounds (infra R1 v0.99.88 · product/growth R2 v0.99.89), 24 commits, CI green, deployed + verified live.
**Codified into:** `~/.claude/skills/multimodel-sprint/SKILL.md` (user-level, shared rhodesli + fox-genealogy). See HD-036.

## Verdict: 7.5/10 — architecture correct, keep the pattern, fix the plumbing
The split works. The independent-audit hard gate **alone** justifies it. The 2.5 points off are execution
mechanics that are all mechanically fixable (four of five cheaply).

### The load-bearing evidence
**The CI torch/mlflow catch is the decisive datapoint.** The orchestrator validated the new CI ML-suite step
with `--collect-only` (rc=0) and formed a justified-but-false "CI-safe" belief. Fable's independent pre-push
audit found 5 modules import torch/mlflow *inside test functions* → pass collection, FAIL at runtime in CI
(~25 failures → red main on first push, the Lesson-209 class this project has already paid for). One catch of
that magnitude pays for every audit run in the session.

**The mechanism matters:** the auditor didn't win by being smarter — it won by **not sharing the orchestrator's
validation history**. A fresh context asked the naive question ("what actually executes in CI?") that the
anchored context skipped. Same phenomenon as Session 164 (Codex IMPL audit BLOCK, 5 P0s) and Session 165
(pre-audit P2 → true root cause). **Independence of context, not model identity, is the active ingredient.**
Corollary: when the orchestrator substitutes for the auditor (as it did in R2 after the audit agent stalled),
the independence property is destroyed — that self-audit was the session's weakest link even though it found
things, because we can't know what it was blind to.

### Role fit (with each model's cost)
| Model | Genuinely best at | Where it cost time |
|---|---|---|
| **Opus (orchestrator)** | triage, risk-gating, live verify-before-dispatch, recovering from subordinate failures | own verification shallow twice (`--collect-only`; crop-dependent test green locally) — orchestrator self-verification is structurally optimistic |
| **Fable (architect/auditor)** | dives producing *dispatchable* findings (Severity+Risk+Effort+pre-triaged batch); fresh-context adversarial audit | stalled as a long subagent twice (R2 audit + prior M11) — 600s watchdog is a hard constraint, not tuning |
| **Codex (coder)** | fast, clean, on-spec impl w/ self-verify | 37-min runaway looping the 65s `make test-fast`; edits main tree → forces sequential dispatch |

**Counterfactual:** a single-model session pushes the torch/mlflow regression (its validation *is* the
orchestrator's). A two-model session (no independent auditor) catches less (Session 137: "neither catches what
the other does"). The third, differently-shaped reviewer earns its place.

## Meta-lessons ML-1 … ML-7 (full text in `tasks/lessons/harness-lessons.md`)
- **ML-1** Independent audit is a HARD gate, not a quality bonus. No push from an autonomous multi-model session without a fresh-context audit of the ACTUAL diff. "The orchestrator checked it" never satisfies the gate.
- **ML-2** Coder specs MUST bound the verify loop: name the exact targeted test command, forbid `make test-fast`, give a wall-clock budget, "at budget stop + report." (37 min → 6 min, same coder.)
- **ML-3** Long subagents stall — design for it: bounded scope per dive/audit (< watchdog horizon), append findings to a file incrementally, always a FRESH-context fallback auditor (never the orchestrator).
- **ML-4** The orchestrator must simulate CI's *constraints*, not just its commands: enumerate what CI LACKS vs local (heavy deps AND data files like crops/embeddings AND secrets/live services) and verify against that subtracted environment.
- **ML-5** Codex coders share one working tree → SEQUENTIAL by default; parallel only with per-coder worktrees + disjoint files + porcelain-clean checks.
- **ML-6** Stop-gate hooks vs background agents are mismatched → bootstrap + commit the gate-file skeletons as the FIRST commit.
- **ML-7** Architect findings must be dispatch-shaped (Severity/Risk/Effort/evidence/user-gated), and the orchestrator must independently reproduce the top finding of each batch before spending a coder.

## Improvements not yet tried (ranked by ROI)
1. **CI-constraint simulator** (highest ROI, small effort) — generalize `scripts/check_ml_suite_ci_safe.py` into `scripts/simulate-ci.sh` that ALSO hides CI-absent data dirs (crops/embeddings/volume JSON) and runs the CI selection. Makes BOTH S168 CI misses mechanically catchable pre-push → converts ML-4 from behavioral rule to hook-enforceable check (the only kind that sticks — Lessons 102/140). **First cut shipped this session: `scripts/simulate_ci_data.py`.**
2. **Incremental-findings protocol** for all long subagents (append-as-you-go) — converts stall from total loss to tail loss. Now baked into the skill (Phase B.3).
3. **`scripts/bootstrap-gate-files.sh`** — mechanize ML-6. **Shipped this session.**
4. **Worktree-isolated Codex dispatch wrapper** — unlock safe parallel coders; only worth it at 3+ independent jobs (Lesson 180 caveat: absolute paths escape worktrees).
5. **Model-selection heuristic** — dispatch by task shape (now written into the skill).
6. **Coder wall-clock watchdog** on the orchestrator side (background timer, alert at 2× budget) — make the manual kill structural.

## Bottom line
Codify the pattern (done — the skill). Add ML-1…7 to harness-lessons (done). Build the CI-constraint
simulator before the next sprint (first cut shipped; extend next) — it's the one improvement that removes an
entire recurring failure class rather than mitigating it.
