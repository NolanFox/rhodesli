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

## HD-017: PreCompact Recovery Hook for Session Continuity
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

## HD-016: Mandatory Self-Assessment Protocol
- **Date:** 2026-02-22
- **Session:** 61B
- **Trigger:** Sessions 60B and 61 shipped features that were partially broken
  in production (ENOSPC deploy failures, enriched prompt gap ML-090). The
  verification gate (HD-003) catches structural issues but not "did we actually
  deliver what was promised?"
- **Decision:** Every session MUST end with a self-assessment that re-reads the
  original prompt and verifies each phase was completed with evidence. Written to
  `docs/session_context/session_NN_assessment.md`. Includes UX evaluation of any
  screenshots taken (separate rule in `.claude/rules/ux-evaluation.md`).
- **Implementation:** `.claude/rules/self-assessment.md` + `.claude/rules/ux-evaluation.md`
- **Alternatives rejected:**
  - Relying on the verification gate alone: HD-003 checks file existence but not
    semantic correctness (e.g., "does the prompt actually get sent to Gemini?")
  - Human-only review: Nolan doesn't always have time to verify every session
  - Session log checkboxes: Easy to check off without verifying (satisficing pattern)
- **Rationale:** The verification gate checks structure; self-assessment checks
  substance. Together they catch both "did the file get created?" and "does the
  feature actually work?"
- **Breadcrumbs:** .claude/rules/self-assessment.md, .claude/rules/ux-evaluation.md,
  HD-003 (verification gate), CLAUDE.md (Session End line)

## HD-018: Tiered Regression Checklist (Smoke vs Full)
- **Date:** 2026-02-25
- **Session:** 69 (planning)
- **Trigger:** Session 68 Phase 1 ran a 15-item regression checklist that took
  significant time. Most sessions only need to verify critical items, not every
  harness feature. Full regression should run only when harness files change.
- **Decision:** Two tiers of regression testing:

  **Smoke Test (5 items) — run every session:**
  1. Stop hook blocks when assessment missing (item #1)
  2. Stop hook approves when assessment exists (item #2)
  3. Tests pass (item #15 — test count >= previous session)
  4. Session log archival works (item #9)
  5. PreToolUse test-before-commit fires (item #6)

  **Full Regression (15 items) — run when harness changes:**
  Items 1-15 from Session 68 context Part 2 checklist. Includes all
  smoke items plus: PreCompact warning (#3), recovery injection (#4),
  parallelization reminder (#5), AD reminder (#7), upload pipeline (#8),
  ux-reviewer (#10), session-evaluator (#11), fix-prompt-writer (#12),
  run_session.sh (#13), GEDCOM admin UI (#14).

- **When to run full regression:**
  - Session modifies `.claude/hooks/`, `.claude/settings.json`, or `.claude/agents/`
  - Session modifies `scripts/run_session.sh`
  - Every 5th session (periodic verification)
- **Alternatives rejected:**
  - Always full: wastes 15-20 min on non-harness sessions
  - No regression: harness drift goes undetected (Session 67 found this)
  - Automated test suite for hooks: desirable long-term but hooks are
    shell/Python scripts that require specific stdin/env setup
- **Breadcrumbs:** docs/session_context/session-68-context.md (Part 2),
  docs/session_logs/session-68-log.md (Phase 1 results)

## HD-019: Multi-Tool Harness Architecture
- **Date:** 2026-02-25
- **Session:** 70
- **Decision:** Canonical source (CLAUDE.md) + adapter pattern for multi-tool
  support. Tool-agnostic rules extracted to `docs/AGENT_HARNESS.md`. Each tool
  gets a thin adapter file that references the canonical source and adds
  tool-specific conventions.
- **Architecture:**
  ```
  CLAUDE.md (canonical, Claude Code native)
      |
      +-- docs/AGENT_HARNESS.md (tool-agnostic rules)
      +-- AGENTS.md (Codex adapter)
      +-- .cursorrules (Cursor pointer)
      +-- .gemini/GEMINI.md (Gemini pointer)
      +-- .antigravity/rules.md (Antigravity adapter)
      +-- scripts/sync-harness.sh (regeneration)
      +-- scripts/setup-worktree.sh (dependency setup)
  ```
- **Rationale:** Different AI coding tools (Claude Code, Codex, Cursor, Gemini
  Code Assist, Antigravity) each read project rules from different files and
  in different formats. A canonical-source + adapter pattern ensures rules stay
  consistent across tools without manual duplication. `sync-harness.sh`
  regenerates all adapter files from the canonical sources.
- **Commit convention:** `[tool-name] type(scope): description` enables
  attribution when multiple tools contribute to the same codebase.
- **Alternatives considered:**
  - Symlinks: Fragile across platforms (Windows, Docker), tools may not follow
    symlinks, and each tool expects a different format/filename.
  - Duplicate files without sync script: Guaranteed drift. Rules would diverge
    within 2-3 sessions.
  - Single file for all tools: Incompatible file paths and formats.
    AGENTS.md vs .cursorrules vs .gemini/GEMINI.md are tool requirements.
  - Inline everything in CLAUDE.md: Already at the 80-line limit (HD-006).
    Multi-tool instructions would bloat it past the limit.
- **Breadcrumbs:** .claude/rules/harness-sync.md, docs/AGENT_HARNESS.md,
  AGENTS.md, .cursorrules, .gemini/GEMINI.md, .antigravity/rules.md

## HD-021: Mechanical Subagent Commit Enforcement
- **Date:** 2026-02-26
- **Session:** 71 (Track C)
- **Decision:** Created `scripts/merge-worktree.sh` that mechanically enforces
  subagent commit discipline before merging. The script checks `git status
  --porcelain` in the worktree and auto-commits any uncommitted files with a
  tagged commit message before proceeding with the merge.
- **Rationale:** Lesson 87 documents that subagents in sessions 64 and 69 left
  uncommitted files in worktrees. These files were lost during merge, requiring
  manual recovery. The `merge-resolver.md` agent doc mentions pre-merge checks
  but relies on the agent remembering to verify — which is unreliable under
  context pressure. A mechanical gate (script with explicit check) is more
  reliable than a documented instruction.
- **Architecture:**
  1. Step 1: Check `git status --porcelain` in worktree. If uncommitted files
     exist, auto-commit with message: `"fix: auto-commit uncommitted subagent
     files (enforcement gate)"`
  2. Step 2: Run tests in the worktree before merge
  3. Step 3: Merge with `--no-ff` for clear merge commits
  4. Step 4: Run tests after merge to catch integration issues
  5. Supports `--dry-run` for preview
- **Alternatives considered:**
  - Documentation only (add to merge-resolver.md): Already existed but didn't
    prevent the issue in sessions 64 and 69. Documented instructions degrade
    under context pressure.
  - Pre-merge hook in git: Git doesn't have a native pre-merge hook. A custom
    hook would be fragile and non-portable.
  - Fail instead of auto-commit: Considered but rejected — failing would require
    the orchestrator to re-enter the worktree context and commit, which is more
    error-prone than auto-committing with a clearly tagged message.
- **Breadcrumbs:** scripts/merge-worktree.sh, Lesson 87, .claude/agents/merge-resolver.md,
  .claude/skills/prompt-parallelizer/SKILL.md

## HD-020: Auto-Evaluation Loop Architecture
- **Date:** 2026-02-25
- **Session:** 70
- **Decision:** `scripts/run_session.sh` orchestrates a full auto-evaluation
  loop: main session (phase-by-phase) -> session-evaluator -> fix-prompt-writer
  -> b-version launch. All stages are timestamped and logged to
  `docs/session_logs/session-NN-autoeval-report.md`.
- **Rationale:** Self-assessment (HD-016) catches ~70% of issues but has a
  fundamental conflict of interest: the same model that built the feature
  evaluates it. The evaluator subagent runs in a fresh context with no
  emotional investment in the work. The fix-prompt-writer generates surgical
  b-session prompts that address only what failed. This creates a
  self-correcting development loop that catches issues that self-assessment
  misses (proven in Session 67: evaluator found 3 phases PARTIAL that
  self-assessment rated PASS).
- **Architecture:**
  1. Phase-by-phase execution with `claude -p` per phase (context isolation)
  2. Evaluator reads: prompt, session log, assessment, git log, test results
  3. Evaluator outputs structured PASS/FAIL with `B-SESSION CONCERNS: FOUND|NONE` marker
  4. Fix-prompt-writer generates targeted b-session prompt (one phase per fix)
  5. B-version runs as a single `claude -p` invocation
  6. Final report aggregates all stages with timestamps
- **Alternatives considered:**
  - Manual review only: Does not scale for overnight/autonomous sessions.
    Nolan cannot review every session before the next one starts.
  - Inline evaluation (evaluator within the same session): Context pollution.
    The evaluator would inherit the same degraded context and biases as the
    main session. Fresh context is essential for honest evaluation.
  - Always run b-version: Wasteful when the main session is clean. The
    structured marker (`B-SESSION CONCERNS: FOUND|NONE`) gates b-version
    launch to only when needed.
  - Human-written b-session prompts: The fix-prompt-writer generates prompts
    using the same best practices (small phases, specific criteria, assessment
    mandatory) but without human latency. Human can still override by editing
    the generated prompt before it runs.
- **Limitations:** Cannot be tested from within a Claude session (requires
  external invocation of `claude -p`). The script itself is testable via
  dry-run with mock claude commands.
- **Breadcrumbs:** scripts/run_session.sh,
  .claude/agents/session-evaluator.md, .claude/agents/fix-prompt-writer.md,
  HD-016 (self-assessment), HD-003 (verification gate)

## HD-021: Worktree Enforcement Scripts

- **Date:** 2026-02-26
- **Session:** 71D
- **Status:** ACCEPTED

- **What:** Two scripts that mechanically enforce worktree discipline:
  1. `scripts/enforce_worktree.sh` — checks that current branch is not
     main/master, exits non-zero if violated. Run at start of each parallel track.
  2. `scripts/merge_tracks.sh` — ordered merge ceremony with uncommitted file
     detection, auto-commit, sequential merging with --no-ff, and pytest test
     gates after each merge.
- **Alternatives considered:**
  - Rule-only enforcement (behavioral): Proven to fail — 4+ instances of tracks
    running on main despite written instructions in CLAUDE.md and lessons.md.
    Behavioral rules degrade under context window pressure.
  - Hook-based enforcement (PreToolUse hook checking branch): Too complex for
    shell scripts, harder to debug, and hooks have their own reliability issues
    (PreCompact cannot block, as learned in HD-017).
  - Manual merge process: Error-prone, no test gates, easy to forget uncommitted
    files in worktrees.
- **Why this works:** Scripts that exit non-zero are mechanically enforced. Unlike
  a written instruction that can be forgotten, a script failure stops execution.
- **Files:** scripts/enforce_worktree.sh, scripts/merge_tracks.sh,
  .claude/rules/worktree-enforcement.md
- **Breadcrumbs:** AD-171, Lesson 87 (subagent commit discipline),
  Lesson 88 (monolithic app prevents parallel execution)

## HD-022: FastHTML + Surgical JS Embedding (Session 74)

**Date:** 2026-02-27
**Status:** ACCEPTED
**Decision:** Retain FastHTML+HTMX as primary framework. Embed standalone JS (D3, vanilla JS) for components requiring rich interactivity.
**Context:** Session 74 UX overhaul identified interactive limitations in pure HTMX: family tree zoom/pan/expand, mobile swipe gestures, smooth animations. Evaluated full framework migration (React/Next.js) vs. surgical embedding.
**Options Considered:**
1. **Full React migration** — Superior interactivity, massive ecosystem. REJECTED: 799+ tests to rewrite, weeks of work, deployment pipeline rebuild, delays job search portfolio.
2. **Keep pure FastHTML+HTMX** — Zero migration cost. REJECTED for tree/mobile: cannot deliver zoom/pan, gestures, fluid animations with HTMX alone.
3. **FastHTML + surgical JS embeds** — ACCEPTED. Keep all routing, auth, data, HTMX partials. Add standalone JS only where HTMX falls short. No build step, no npm, files served from static/js/.
**Consequences:** Tree visualization gets D3/SVG. Mobile gets CSS transitions + vanilla JS event listeners. Face cards get CSS animations. All server communication stays HTMX. JS files are self-contained, no framework dependency.
**Review Trigger:** If 3+ components need complex state management, or mobile UX still underperforms after Session 74, revisit full frontend framework. Track in ROADMAP.md as a future evaluation item.

## HD-024: ECC-Inspired Harness Improvements (Session 88)

**Date:** 2026-03-04
**Status:** IMPLEMENTED
**Decision:** Adopt 6 improvements from evaluating `affaan-m/everything-claude-code` (3.4K stars) against our harness. Focus on mechanical enforcement over prose rules.

**Research:** Full repo analysis via `gh api` — 50+ skills, 14 agents, 35 commands, full hooks system. Most content is framework-specific boilerplate (Django, Spring Boot, Swift, Go) irrelevant to our Python/FastHTML stack. Codex PR #5 attempted this comparison but was blocked by proxy (403) and produced internal retrospection only — closed without merge.

**Changes Implemented:**
1. **Post-edit ruff auto-format** (`.claude/hooks/post-edit-format.sh`) — Runs `ruff format` + `ruff check --fix` on Python files after every Edit/Write. Catches formatting drift immediately. Inspired by ECC's Biome/Prettier PostToolUse hook.
2. **De-hardcoded hooks** (`.claude/hooks/post-commit-gate.sh`) — Replaced session-81 hardcoded text in PostToolUse Bash and Notification hooks with dynamic session number from `.claude/current_session.txt`.
3. **Debug statement audit** (Stop hook addition) — Scans git-modified `.py` files for `print()` and `breakpoint()` at session end. Warning only (not blocking). Inspired by ECC's console.log audit pattern.
4. **Unified test gate** (`scripts/test-gate.sh`) — Extracts pytest logic from PreToolUse hook into a shared script. Supports `fast|full|ml|all` modes. Hooks call the script instead of embedding pytest inline.
5. **`/simplify` enforcement** (session-run.md update) — Added as mandatory post-implementation step. The skill existed but was never systematically invoked. ECC's "de-sloppify" pattern confirms this is standard practice.
6. **`/verify` skill** (`.claude/skills/verify.md`) — Formalized build-test-fix loop with max 3 iterations. Inspired by ECC's verification-loop skill.

**What We Rejected from ECC:**
- **Instinct/continuous-learning system** — Marked `enabled: false` in their own config. Too experimental, adds complexity for unproven value.
- **Session transcript auto-parsing** — Our manual session logs + assessment protocol are more reliable and auditable.
- **Tool-call counting for compaction** — Our `/compact` ban (Lesson 89) is a better strategy than threshold-based suggestions.
- **Framework-specific skills** — Django, Spring Boot, Swift, Go, Java, C++ skills irrelevant to our stack.
- **Content/business skills** — Investor materials, article writing, market research not relevant.

**Breadcrumbs:** `.claude/settings.json`, `.claude/hooks/post-edit-format.sh`, `.claude/hooks/post-commit-gate.sh`, `scripts/test-gate.sh`, `.claude/skills/verify.md`, `.claude/skills/session-run.md`, `pyproject.toml`

## HD-025: Session 97 Packaging — Phase-Scoped Context And Artifact-First Research

**Date:** 2026-03-11
**Status:** ACCEPTED
**Decision:** Package PRD-038 implementation as a dedicated Session 97 prompt/context bundle that requires phase-scoped context loading, explicit worktree isolation, mandatory artifact updates after new research, and fixed session outputs.

**Context:** The user requested a long-running Codex implementation pass for PRD-038, with Gemini review in the loop, zero destructive data behavior, full harness breadcrumbs, and no loss of planning context through compaction. The planning review also found that a large part of the value is in preserving research, user constraints, and evaluation baselines as durable artifacts instead of leaving them in chat state.

**External guidance used:**
1. **OpenAI GPT-5 prompting guide** — write issue-style prompts, keep repo instructions persistent, and specify success criteria clearly.
2. **Anthropic Building Effective Agents** — prefer simple composable patterns, evaluator-optimizer loops, and parallel workers only when boundaries are clean.
3. **Anthropic prompt engineering overview** — give only the relevant context for the current task, not the entire session history.

**What this changes:**
1. **Phase-scoped context** — `docs/session_context/session-97-context.md` is structured so implementation reads only the relevant files for the current act.
2. **Artifact-first research** — new research, user feedback, and architecture decisions must be written to harness artifacts before they are reused downstream.
3. **Worktree-first execution** — the Session 97 prompt requires isolated branches/worktrees and recommends parallel tracks only for disjoint files.
4. **Mandatory session outputs** — session log, assessment, decision-log updates, eval artifacts, and research breadcrumbs are part of the prompt, not optional cleanup.
5. **Codex-specific adaptation** — the prompt avoids Claude-only commands such as `/clear` and instead uses explicit context boundaries plus commit checkpoints to keep active context small.

**Rejected alternatives:**
- **Loose prompt plus chat history** — too fragile for a multi-phase ML change with review handoffs.
- **Single giant context dump** — increases confusion and contradicts current agent-guidance research.
- **Parallelize everything** — harms correctness when files overlap heavily.

**Breadcrumbs:** `docs/prompts/session-97-prompt.md`, `docs/session_context/session-97-context.md`, `docs/assessments/session-97-prep-assessment.md`, `docs/session_logs/session-97-log-stub.md`, `docs/prds/038_longitudinal/RESEARCH_REFERENCES.md`
