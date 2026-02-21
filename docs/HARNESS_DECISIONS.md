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

## HD-008: Production Smoke Test as Session Prerequisite
- **Date:** 2026-02-20
- **Session:** 53
- **Decision:** Every audit/polish session begins with a comprehensive
  production smoke test of all routes. Results logged to
  `docs/ux_audit/PRODUCTION_SMOKE_TEST.md`.
- **Rationale:** Session 53 proved that a systematic curl-based smoke test
  catches issues faster than manual browsing. All 35 routes can be tested
  in under 30 seconds. The test catches broken images, auth leaks, 500 errors,
  and content rendering issues that unit tests miss.
- **Enforcement:** For audit sessions, Phase 1 is always the smoke test.
  For feature sessions, a targeted smoke test of affected routes runs
  at the verification gate.
- **Breadcrumbs:** docs/ux_audit/PRODUCTION_SMOKE_TEST.md,
  .claude/rules/verification-gate.md

## HD-009: HTMX Indicator CSS Must Handle Both Selectors
- **Date:** 2026-02-20
- **Session:** 53
- **Decision:** Any custom CSS overriding HTMX indicator behavior must
  include BOTH `.htmx-request .htmx-indicator` (descendant) AND
  `.htmx-request.htmx-indicator` (combined) selectors.
- **Rationale:** When `hx-indicator="#id"` is used, HTMX adds `htmx-request`
  directly to the indicator element itself. The descendant selector alone
  won't match. This caused a silent bug where upload spinners never showed
  in the triage dashboard.
- **Alternatives considered:** Relying on HTMX's built-in opacity CSS.
  Rejected because the custom CSS uses `display:none/inline` which overrides
  HTMX's opacity transitions, creating inconsistent behavior.
- **Breadcrumbs:** app/main.py CSS block, docs/ux_audit/FIX_LOG.md

## HD-010: Production Verification is Mandatory After UI/Upload Changes
- **Date:** 2026-02-20
- **Session:** 54B
- **Decision:** After any code change affecting UI, uploads, or routes,
  run `python scripts/production_smoke_test.py` and log results.
  After upload-affecting changes, perform actual upload tests with timing.
- **Rationale:** Session 54 skipped real upload testing and buffalo_sc was
  investigated only theoretically. Session 54B corrected this: hybrid
  detection was only discovered to work by actually running the tests.
  The production smoke test script (11 paths, markdown output, non-zero
  on critical failure) makes verification fast and reproducible.
- **Rule file:** .claude/rules/production-verification.md
- **Alternatives considered:**
  - Manual curl commands: Too error-prone, not logged.
  - Only unit tests: Session 53/54 proved unit tests pass while
    production behavior differs (tests pass ≠ production works).
  - Playwright e2e only: Heavier setup, not available for all
    environments. Smoke test is a lighter alternative.
- **Breadcrumbs:** scripts/production_smoke_test.py,
  .claude/rules/production-verification.md,
  docs/ux_audit/UX_AUDIT_README.md

## HD-011: Document Trimming Must Verify Destination Completeness
- **Date:** 2026-02-20
- **Session:** 54c
- **Decision:** When trimming entries from any document (ROADMAP "Recently
  Completed", BACKLOG completed items, etc.), the destination file must be
  verified to contain equivalent content BEFORE or in the SAME commit as
  the removal. Added to verification gate common failure patterns.
- **Rationale:** Session 54c trimmed ROADMAP "Recently Completed" from 14
  to 5 entries, pointing to SESSION_HISTORY.md. But SESSION_HISTORY.md was
  missing sessions 47-54B (never backfilled after the Session 47 ROADMAP
  split). Session 47B (real audit with 4 tests, deploy fix) had no entry
  at all. The gap was caught during review but would have been silent
  context loss otherwise.
- **Root cause:** The Session 47 ROADMAP split created SESSION_HISTORY.md
  with sessions 1-46, but no process ensured new sessions were added to
  SESSION_HISTORY.md as they completed. The "Recently Completed" section
  in ROADMAP was the only record for sessions 47+.
- **Alternatives considered:**
  - Auto-generate SESSION_HISTORY from git tags: Fragile, loses narrative
  - Keep all entries in ROADMAP forever: Violates 150-line limit
  - Script to sync ROADMAP → SESSION_HISTORY: Overhead for infrequent operation
- **Breadcrumbs:** .claude/rules/verification-gate.md (document trimming rule),
  tasks/lessons/harness-lessons.md (Lesson 77)

## HD-012: Silent ML Fallback Detection
- **Date:** 2026-02-20
- **Session:** 54G
- **Trigger:** Session 54F: buffalo_sc not in Docker → silent fallback to
  buffalo_l → 5x latency regression invisible to functional tests. Smoke
  tests passed (200 OK, correct JSON shape). Only latency measurement
  revealed the wrong model was loaded.
- **Decision:** ML model loading must log actual model loaded (INFO) +
  WARNING on any fallback. Applies to all model types: face detection,
  CORAL, similarity calibration, Gemini API.
- **Enforcement:** AD-120 documents the principle. CLAUDE.md ML section
  references it. Code review should check for unlogged fallback paths.
- **Alternatives considered:**
  - Output shape validation: Rejected — both models produce identical
    512-dim embeddings. Shape can't distinguish them.
  - Startup-only logging: Rejected — some models are lazy-loaded on first
    request; must log at actual load time.
- **Breadcrumbs:** AD-119 (specific fix), AD-120 (principle),
  docs/PERFORMANCE_CHRONICLE.md (optimization journey)

## HD-013: Smoke Tests Must Test Actual User Flows
- **Date:** 2026-02-20
- **Session:** 49B
- **Trigger:** Session 54F reported "11/11 smoke tests passing" for compare,
  but `scripts/production_smoke_test.py` only tests GET requests (page loads).
  Compare POST (actual file upload) was never tested. Nolan discovered the
  gap during manual testing. Compare endpoint turned out to be working, but
  the smoke tests could not have detected a real failure.
- **Decision:** Every smoke test for a feature that accepts user input must
  test the input path (POST/upload), not just the page load (GET). Smoke
  tests that only verify "page returns 200" give false confidence about
  upload/submission functionality.
- **Action items:**
  - Add POST-based smoke tests for /api/compare/upload and /upload endpoints
  - Production smoke test should include at least one file upload test
  - Distinguish "page load tests" from "functional flow tests" in test naming
- **Alternatives considered:**
  - Full Playwright e2e in CI: Ideal but requires headless browser + test
    images in CI. Add when CI/CD pipeline exists (Phase F).
  - curl-based POST tests: Simplest to add now. Requires a small test image.
- **Breadcrumbs:** Session 49B triage log, Lesson 78 (if added)

## HD-015: Session Type Routing
- **Date:** 2026-02-20
- **Session:** 49B prep
- **Decision:** Session protocols live in docs/session_protocols/
  with an INDEX.md routing table. CLAUDE.md points to INDEX (1 hop),
  INDEX routes to protocol files (2 hops), protocols point to
  context files (3 hops max). Each protocol type has trigger
  keywords for automatic identification.
- **Problem:** Path-scoped rules trigger on code files but nothing
  triggered on session types. Interactive session rules, browser
  audit protocols, and overnight safeguards existed only in manually
  pasted prompts — invisible to new sessions.
- **Rejected:** Inlining all session rules in CLAUDE.md (bloat),
  using .claude/rules/ for session types (wrong trigger mechanism —
  rules trigger on file paths, not session types).
- **Breadcrumbs:** docs/session_protocols/INDEX.md, CLAUDE.md

## HD-014: Every Deploy Must Include Production Playwright Verification
- **Date:** 2026-02-20
- **Session:** 49B-Deploy
- **Trigger:** Session 49B-Audit fixed 4 issues and wrote Playwright tests but
  never pushed to production or re-ran tests against production. Same pattern
  as 54F (11/11 smoke tests that only tested GET). Sessions 54G also failed
  to verify changes on production.
- **Decision:** After EVERY git push to main:
  1. Wait for Railway deploy to complete (check via MCP or `railway logs`)
  2. Run Playwright verification against production URL (NOT localhost)
  3. Log result: "Production Playwright: X/Y passing"
  4. If Playwright cannot run, log the specific error — do NOT silently skip
- **Enforcement:** Post-deploy hook reminder + CLAUDE.md Session Operations #3 +
  verification gate check
- **Rationale:** "Tests pass locally" is not "production works." This gap has
  recurred across 3+ sessions. The only fix is mandatory production verification
  as a blocking step, not advisory.
- **Alternatives considered:**
  - Advisory only (just a reminder): Already failed — reminders in session logs
    were ignored. Must be a blocking step.
  - CI/CD Playwright: Ideal long-term but requires infrastructure (OPS-002).
    This is the manual interim.
- **Breadcrumbs:** Session 49B-Audit (skipped production verify), Session 54F
  (GET-only smoke tests), HD-013, CLAUDE.md Session Operations, post-deploy hook

## HD-015: PreCompact Recovery Hook for Session Continuity
- **Date:** 2026-02-21
- **Session:** 49E
- **Trigger:** Context compaction loses critical session instructions (prompt
  details, phase tracking, rules). This was identified in HD-001 and GitHub
  issue #25265 as a known failure mode.
- **Decision:** Install a PreCompact hook (`.claude/hooks/recovery-instructions.sh`)
  that injects recovery instructions into the compacted context via
  `additionalContext`. Combined with saving prompts to disk and maintaining
  a checkpoint file (`docs/session_context/session_*_checkpoint.md`).
- **Implementation:**
  1. PreCompact hook fires before auto-compaction
  2. Injects: session number, prompt file path, checkpoint file path, key rules
  3. Checkpoint file updated after every phase with current progress
  4. Prompt saved to `docs/prompts/` at session start
- **Alternatives rejected:**
  - Relying on compaction summary alone: Known to lose critical instructions
    (~20-30% context degradation per HD-001)
  - Manual `/compact` at breakpoints: Requires human intervention, not
    compatible with autonomous sessions
  - SessionStart hook only: Fires too late — context is already compressed.
    PreCompact injects BEFORE compression, ensuring survival.
- **Rationale:** Deterministic recovery > probabilistic memory. Hooks fire
  outside the agentic loop — they always execute regardless of context state.
- **Breadcrumbs:** .claude/settings.json (hooks config),
  .claude/hooks/recovery-instructions.sh, HD-001
