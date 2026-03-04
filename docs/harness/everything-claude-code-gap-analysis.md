# Everything-Claude-Code Benchmark vs Rhodesli Harness (Gap Analysis)

## Scope and Evidence

This review compares Rhodesli's current harness behavior against external best-practice expectations for Claude Code harnesses, then maps improvements to concrete Rhodesli files.

### Research constraints

I attempted to fetch `https://github.com/affaan-m/everything-claude-code` directly (`git clone`, `curl`, GitHub API, raw URLs). The current environment blocks outbound GitHub access via proxy `403`, so a line-level external repo diff was not possible in this run.

Commands attempted:
- `git clone --depth 1 https://github.com/affaan-m/everything-claude-code.git`
- `curl -I -L https://github.com/affaan-m/everything-claude-code`
- Python `requests` to GitHub API and raw files

### Internal evidence used

- Canonical + adapter harness docs: `CLAUDE.md`, `docs/AGENT_HARNESS.md`, `AGENTS.md`
- Harness generation and automation: `scripts/sync-harness.sh`, `scripts/run_session.sh`, `.claude/settings.json`
- Iteration pain points: `tasks/lessons/harness-lessons.md`, `docs/assessments/session-77-assessment.md`, `docs/assessments/session-82f-assessment.md`, `docs/roadmap/CLAUDE_OPUS_EVALUATION_2026-03.md`

---

## What Rhodesli Already Does Well

1. **Canonical-source + adapter architecture** is already strong and maintainable (`CLAUDE.md` + generated adapters via `sync-harness.sh`).
2. **Decision provenance** is mature (`HD-*` logs with rationale and alternatives).
3. **Dual test suite discipline** is explicitly documented in tool-agnostic and Codex adapter files.
4. **Failure memory exists** through lessons docs that capture repeated patterns (context loss, unverified completion, worktree drift).
5. **Automation hooks exist** for stop gates, pre-commit reminders, and recovery injection.

These are the same categories most advanced harness playbooks emphasize.

---

## Where Results Still Degrade (Observed Gaps)

### Gap 1: Session-specific hook text leaks into global harness behavior

Evidence: `.claude/settings.json` still emits hardcoded Session 81 copy in `PostToolUse` (`/clear GATE`, file names, temp paths). That is brittle for future sessions and can create false ritual compliance.

**Impact:** Noise and instruction drift; high chance of agents ignoring hooks that look stale.

### Gap 2: Cross-tool quality gates are asymmetric

Evidence: Claude hook path runs `pytest ... -n auto -m "not slow" --timeout=10` only when `git commit` is detected in Claude tool flow, while Codex/other tools can bypass this path. The roadmap already flags this risk (Session 82b example).

**Impact:** "Passed locally" varies by tool; regressions can slip through when contributors are outside Claude-native flow.

### Gap 3: Completion claims still require multiple retries

Evidence from lessons and assessments:
- Self-reported completion failures and missing wiring patterns recur.
- Session 77 delivered only a subset of requested scope due environment/test constraints.
- Session 82 required multiple sub-sessions and deferred/stranded work to close gaps.

**Impact:** Throughput tax from rework sessions and confidence erosion.

### Gap 4: Browser evidence persistence is inconsistent

Evidence: Session 82f assessment notes browser verification happened, but screenshots were not persisted from extension workflow.

**Impact:** Verification becomes harder to audit later; "trust me" reporting risk.

### Gap 5: Harness docs/rules still have consistency debt

Evidence: `docs/HARNESS_DECISIONS.md` is already very large; session history files also exceeded intended doc limits in assessments.

**Impact:** Retrieval quality drops; rules become harder to apply consistently.

---

## Improvement Plan (Low-Risk, Non-Breaking)

## 1) Add a cross-tool **Preflight Contract**

Create one lightweight script (`scripts/harness_preflight.sh`) that reports:
- venv present?
- app tests runnable?
- ML tests runnable?
- browser tool available?
- network constraints detected?

Then require every tool/session to paste preflight output at start.

**Why this helps:** Converts hidden environment limitations into explicit scope constraints before coding.

## 2) Add a **Machine-Readable Completion Contract** per prompt/session

Use a small checklist file (YAML/JSON) per session with required deliverables:
- code tasks
- tests to run
- browser artifacts required
- docs/decision updates

Automations (or final validation script) can enforce all boxes before finalization.

**Why this helps:** Reduces "claimed done vs actually done" drift noted in lessons.

## 3) Unify test gating into one script used by all tools

Add `scripts/harness_test_gate.sh`:
- default: fast gate
- pre-merge/release: full dual-suite gate
- outputs explicit PASS/WARN/FAIL markers

Have hooks call this script instead of embedding pytest logic in hook JSON.

**Why this helps:** Removes tool-specific test behavior and makes gate changes centralized.

## 4) Replace hardcoded session text in hooks with templated variables

Refactor `.claude/settings.json` hook messages:
- use `.claude/current_session.txt`
- avoid hardcoded prompt paths (`session-81`)
- avoid temp-file assumptions (`/tmp/session_81_checklist.md`)

**Why this helps:** Prevents stale operational instructions and reduces alert fatigue.

## 5) Add browser artifact persistence rule

For any browser verification path, require at least one persisted artifact path in session outputs (or explicit reason why unavailable).

**Why this helps:** Converts transient verification into auditable evidence.

## 6) Add quarterly external benchmark review protocol

Create a small recurring process:
- pick 1-2 external harness repos
- score Rhodesli against a fixed rubric
- record accepted/rejected deltas in `HARNESS_DECISIONS.md`

**Why this helps:** Makes improvement proactive instead of incident-driven.

---

## Suggested Priority Order

1. **P0 (immediate):** hook de-hardcoding + unified test gate script.
2. **P1:** preflight contract + browser artifact persistence rule.
3. **P2:** machine-readable completion contract.
4. **P3:** recurring external benchmark cadence.

This order improves reliability quickly without altering application runtime behavior.

---

## Safe Integration Notes

- All proposals are harness/process-only; no app runtime path changes.
- Keep each new doc <300 lines and split by concern.
- Add changes incrementally with one harness decision entry per major step.
- Use `scripts/sync-harness.sh` only when adapter content actually changes.

