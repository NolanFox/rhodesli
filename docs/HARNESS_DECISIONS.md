# Harness Decisions Log

Captures workflow, tooling, and harness engineering decisions for the
Rhodesli project. Each entry records what was decided, what alternatives
were considered, and why — so future sessions (or future projects
replicating this harness) understand the reasoning.

For ML decisions, see: ALGORITHMIC_DECISIONS.md
For deployment decisions, see: docs/ops/OPS_DECISIONS.md

---

## HD-001: Prompt Decomposition with Phase Isolation
- **Date:** 2026-02-18
- **Session:** 48
- **Decision:** When receiving prompts over 50 lines, save to disk,
  parse into phases, and create session log before execution.
- **Rationale:** Session 47 demonstrated that context degradation
  causes later phases to be claimed-but-not-wired. Saving the prompt
  to disk allows re-reading at verification time even after the
  original has been pushed out of context. Research found a ~20-30%
  performance drop with accumulated vs. fresh context.
- **Alternatives considered:**
  - Agent Teams (multiple Claude instances with separate contexts):
    Adds significant coordination overhead and token cost. Most
    Rhodesli phases touch app/main.py, so parallelism would cause
    file conflicts. Better pattern for us is sequential with fresh
    context per phase.
  - Native Tasks system (shipped Jan 2026): Supports dependency DAGs
    and subagent fresh context windows, but doesn't auto-decompose
    prompts into phases and doesn't verify completion against spec.
  - Ralph Wiggum plugin: Good for overnight iteration loops but
    completion is self-reported (same model that claims phantom
    features). Will layer this on later if Phase Isolation +
    Verification Gate proves effective.
- **Breadcrumbs:** .claude/rules/prompt-decomposition.md,
  docs/session_context/session_48_harness_research.md

## HD-002: Commit-Per-Phase with Session Logging
- **Date:** 2026-02-18
- **Session:** 48
- **Decision:** Atomic git commits after each phase. Session log
  tracks what was actually built (not just what was planned).
- **Rationale:** The satisficing pattern — Claude builds enough to
  feel done in early phases, then degrades on later phases. Atomic
  commits create recoverable checkpoints. Session logs create an
  auditable record that the verification gate checks against.
- **Alternatives considered:**
  - Single commit at end: No recoverability if session fails partway.
  - Commit only on significant changes: Ambiguous threshold leads to
    skipped commits, which leads to lost work.
- **Breadcrumbs:** .claude/rules/phase-execution.md

## HD-003: Verification Gate (Feature Reality Contract)
- **Date:** 2026-02-18
- **Session:** 48
- **Decision:** Mandatory end-of-session re-read of original prompt
  with structured verification of each phase against the Feature
  Reality Contract checklist.
- **Rationale:** This is the single most valuable harness improvement.
  No existing tool (Ralph Wiggum, Native Tasks, Agent Teams)
  independently verifies that work matches the spec. Ralph Wiggum's
  completion is self-reported. Tasks track status but not reality.
  The C compiler project (Anthropic case study, 16 agents, 2000
  sessions) used an external test suite as the verification signal —
  Claude didn't decide when it was done, the tests did. Our Feature
  Reality Contract is the adaptation of that pattern for a solo
  developer workflow.
- **Evidence from Session 47 audit:**
  - 9/11 features: REAL (verification would have confirmed quickly)
  - birth_year_estimates.json: data existed in rhodesli_ml/data/ but
    wasn't copied to app data/ — "Deploy correctly?" check catches this
  - BACKLOG breadcrumbs: items created but not cross-referenced —
    "Breadcrumbs present?" check catches this
- **Breadcrumbs:** .claude/rules/verification-gate.md,
  docs/session_logs/ (created per session)

## HD-004: Harness Decisions File
- **Date:** 2026-02-18
- **Session:** 48
- **Decision:** Create HARNESS_DECISIONS.md with HD-NNN format,
  following the same provenance pattern as ALGORITHMIC_DECISIONS.md
  (AD-NNN) and OPS_DECISIONS.md (OD-NNN).
- **Rationale:** When replicating this harness on a new project,
  the HD file explains WHY each rule exists — not just WHAT the rule
  says. Without this, future projects copy rules blindly without
  understanding which ones are load-bearing vs. experimental. Also
  enables iterative improvement: if HD-001 proves ineffective, the
  reasoning is preserved for a better solution.
- **Alternatives considered:**
  - Embed rationale in the rules themselves: Rules should be concise
    and actionable. Long rationale in .claude/rules/ wastes tokens
    on every session. Better to keep rules lean with "See HD-NNN"
    pointers.
  - Single DECISIONS.md for everything: Too large, too noisy. The
    three-file split (AD for ML, OD for ops, HD for harness) keeps
    each file focused and under the 300-line limit.
- **Breadcrumbs:** CLAUDE.md key docs table, this file

## HD-005: Session Log Infrastructure
- **Date:** 2026-02-18
- **Session:** 48
- **Decision:** Per-session logs in docs/session_logs/ recording
  planned vs. actual work, with verification gate results.
- **Rationale:** Before this, session outcomes were only visible in
  git history (commits) and conversation transcripts (ephemeral).
  Session logs provide a persistent, grep-able record of what was
  planned, what was built, and what the verification gate found.
  This enables pattern detection (e.g., "phases 7-9 consistently
  fail across sessions" -> split into smaller sessions).
- **Breadcrumbs:** .claude/rules/prompt-decomposition.md,
  .claude/rules/verification-gate.md

## HD-006: Progressive Disclosure Document Architecture
- **Date:** 2026-02-06 (Session 8)
- **Decision:** CLAUDE.md stays under 80 lines and points to focused
  docs. No single doc over 300 lines. Path-scoped rules in
  .claude/rules/ trigger only when relevant files are touched.
- **Rationale:** SYSTEM_DESIGN_WEB.md was 1373 lines and ate ~25%
  of context window. Progressive disclosure means Claude reads only
  what it needs. Path-scoped rules are zero-cost until triggered.
- **Breadcrumbs:** CLAUDE.md, .claude/rules/*, lessons.md #23-24

## HD-007: ALGORITHMIC_DECISIONS.md as Decision Provenance Standard
- **Date:** 2026-02-06 (Session 8, formalized)
- **Decision:** Every ML/algorithmic decision documented with what
  was chosen, what was rejected, why, and source material. AD-NNN
  format. Every prompt must mandate updating this file.
- **Rationale:** Prevents re-deriving decisions that were already
  thoroughly evaluated. When Claude Code starts a new session and
  reads AD entries, it doesn't repeat mistakes or revisit settled
  questions. Also serves as portfolio documentation showing rigorous
  engineering process.
- **Breadcrumbs:** ALGORITHMIC_DECISIONS.md, .claude/rules/ml-decisions.md
