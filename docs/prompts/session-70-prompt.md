# Session 70 Prompt
## Mission: Production verify + UX fix pass + multi-tool harness + auto-eval loop + parallelization test
## Predecessor: Session 69 (v0.74.0 — BUG fixes, design audit, discoveries, parallelization skill)
## Context: docs/session_context/session-70-context.md
## Rule: /clear between phases, NEVER /compact

---

## Pre-Session Manual Tasks (Nolan does BEFORE launching)

1. **Test run_session.sh**: Run `./scripts/run_session.sh` outside Claude. Note output/errors. THIS HAS BEEN DEFERRED 3 SESSIONS — do it now.
2. **LoRA identity review**: If not done before session 69, review Vida/Big Leon/Victor in admin.
3. **Browser check**: Open rhodesli.nolanandrewfox.com, confirm session 69 deploy is live (Playfair Display font visible? Discoveries badge in sidebar?)

---

## Phase 0: Archive + Orient + VERIFY PRODUCTION (15 min)
- [ ] Read: CLAUDE.md, docs/session_context/session-70-context.md, ROADMAP.md, LESSONS_LEARNED.md
- [ ] Read: docs/session_context/session-69-ux-evaluation.md (full UX review report — 13 issues)
- [ ] Read: .claude/skills/prompt-parallelizer/SKILL.md (will test in Phase 3)
- [ ] Read: .claude/agents/session-evaluator.md, .claude/agents/fix-prompt-writer.md
- [ ] Read: scripts/run_session.sh (understand current state before fixing)
- [ ] Archive session 69 log, update INDEX.md
- [ ] Set .claude/current_session.txt to "70"
- [ ] Create SESSION_LOG.md

### Production Verification Checklist (MUST ALL PASS before proceeding):
- [ ] **1A**: Check `core/neighbors.py` — does `batch_best_neighbor_distances` exist?
  - If NO: either create the function or fix the import in the discoveries code
  - If YES: verify /discoveries route returns 200 in production (curl or Playwright)
- [ ] **1B**: BUG-1 fix verified — open Photo Context modal, type name, click Create. Works?
- [ ] **1C**: Design changes render — Playfair Display loads, warm card backgrounds visible?
- [ ] **1D**: /discoveries loads — badge count matches, confirm/reject buttons functional?
- [ ] Log ALL verification results in SESSION_LOG.md with PASS/FAIL

If ANY verification FAILS: fix it before proceeding. These are P0 carryover items.

## Phase 1: Critical Fixes (15 min)
- [ ] **DD-003 threshold alignment**: Docs say "P(match) > 0.85", code uses "distance < 1.0"
  - Pick one representation, update both DD-003 and implementation to match
  - This is a documentation + code alignment task, not a behavior change
- [ ] **UX-108** [HIGH]: "Heritage Archive" subtitle contrast fails WCAG AA
  - Fix: increase opacity or change text color on sidebar subtitle
  - Verify: WCAG AA contrast ratio >= 4.5:1 after fix
- [ ] **UX-109** [HIGH]: "To Review" count color inconsistent (amber banner vs blue sidebar)
  - Fix: pick one color, apply consistently across all "To Review" references
- [ ] **Subagent commit discipline**: Add rule to parallelization skill:
  "Every subagent MUST run tests AND commit ALL files. Orchestrator verifies
  `git status` shows clean working tree in each worktree before merge."
- [ ] **Context overflow post-mortem**: Add to LESSONS_LEARNED.md:
  - Session 69 Phase 4 hit context limit and required continuation
  - Root cause analysis: were subagent contexts too large? orchestrator holding too much?
  - Recommendation for future sessions: parallelization skill should estimate context budget
- [ ] **BUG-3 fragility note**: Add BACKLOG entry — replace onfocus="this.select()" with
  proper placeholder text or select component. Track as UX-114.
- [ ] Commit all fixes

## /clear — Read context file + SESSION_LOG before continuing

## Phase 2: Parallel Execution (30 min)

Three worktree-isolated subagents. All independent — no shared app code files.

### Subagent A: UX Fix Pass
**Worktree:** `session-70/ux-fixes`
**Context to load:**
- docs/session_context/session-69-ux-evaluation.md (MANDATORY — the 13 issues)
- /mnt/skills/public/frontend-design/SKILL.md
- docs/DESIGN_DECISIONS.md
- Current CSS + templates for affected views

**Tasks:**
- [ ] Fix all 5 MEDIUM severity issues from UX evaluation
- [ ] Fix UX-110: Discovery card identity name truncation (increase max-width or use ellipsis with tooltip)
- [ ] Fix UX-111: Add tooltip/explanation to confidence badge ("54% match confidence based on facial similarity distance")
- [ ] Fix UX-112: "Confirm as {name}" button overflow handling (text truncation or wrapping)
- [ ] Fix UX-113: Discovery empty state — show "All discoveries reviewed!" message, not blank div
- [ ] Fix UX-104: Disable "Compare Selected Faces" button until prerequisites met
- [ ] Fix UX-105: Add "Help Identify" CTA for photos with all-unidentified faces
- [ ] Write tests for each fix
- [ ] DD entries for any design decisions made
- [ ] VERIFY: `git status` clean, all files committed before completing

### Subagent B: Multi-Tool Harness Setup
**Worktree:** `session-70/multi-tool-harness`
**Context to load:**
- The uploaded multi-tool-operational-guide.md (copy to docs/session_context/ first)
- CLAUDE.md (the canonical source to extract from)
- HARNESS_DECISIONS.md

**Tasks:**
- [ ] Create `docs/AGENT_HARNESS.md` — extract tool-agnostic rules from CLAUDE.md:
  - Project identity and tech stack
  - Commit discipline (run tests before every commit)
  - Decision tracking (AD/DD/HD/OD mandatory updates)
  - Architecture invariants (Gatekeeper pattern, confirmed data as ground truth)
  - Testing requirements (never reduce test count)
  - ML pipeline rules (roadmap order, ground truth anchors)
- [ ] Create `AGENTS.md` — Codex adapter:
  - Generated from CLAUDE.md, strips Claude-specific instructions
  - Adds Codex conventions (setup scripts, sandbox behavior)
  - References docs/AGENT_HARNESS.md
  - Header: "Auto-generated from CLAUDE.md. Do not edit directly."
  - Under 32KB
- [ ] Create `.cursorrules` — 3-line Antigravity pointer
- [ ] Create `.gemini/GEMINI.md` — Antigravity project rules pointer
- [ ] Create `.antigravity/rules.md` — Generated from CLAUDE.md
- [ ] Create `scripts/sync-harness.sh` — Regenerates adapters from CLAUDE.md
- [ ] Create `scripts/setup-worktree.sh` — Dependency setup for new worktrees
  (venv, pip install, .env copy, test verification)
- [ ] Create `.claude/rules/harness-sync.md` — Path-scoped rule:
  triggers when CLAUDE.md or AGENT_HARNESS.md modified, auto-syncs adapters
- [ ] Add `.claude/worktrees/` to .gitignore
- [ ] Add commit message convention to AGENT_HARNESS.md:
  `[tool-name] type(scope): description`
- [ ] HD entry: multi-tool harness architecture decision with full provenance
- [ ] VERIFY: `git status` clean before completing

### Subagent C: Auto-Evaluation Loop
**Worktree:** `session-70/auto-eval-loop`
**Context to load:**
- scripts/run_session.sh (current state)
- .claude/agents/session-evaluator.md
- .claude/agents/fix-prompt-writer.md
- HARNESS_DECISIONS.md
- docs/session_context/session-70-context.md section 5

**Tasks:**
- [ ] Audit run_session.sh:
  - Does it invoke session-evaluator after main prompt completes?
  - Does it invoke fix-prompt-writer if issues found?
  - Does it launch a b-version?
  - Document current state vs intended state
- [ ] Fix run_session.sh to implement the full flow:
  1. Accept prompt file as argument
  2. Launch `claude -p` with the prompt
  3. After completion, invoke session-evaluator (second `claude -p` call
     with evaluator prompt + session log + assessment as input)
  4. Parse evaluator output for FAIL/RED FLAG items
  5. If issues found, invoke fix-prompt-writer (third `claude -p` call)
  6. Launch b-version with `claude -p`
  7. Write final report to docs/session_logs/session-NN-autoeval-report.md
- [ ] Add observability logging:
  - Which evaluator checks passed/failed
  - What fix-prompt-writer generated
  - Whether b-version resolved issues
  - Timing for each stage
- [ ] Update session-evaluator.md if needed:
  - Must check: all phases from prompt completed?
  - Must check: red flags (same analysis I do manually each time)?
  - Must check: tests pass? deploy verified? docs updated?
  - Must check: any new imports that might not exist in production?
- [ ] Update fix-prompt-writer.md if needed:
  - Input: evaluator output with specific failures
  - Output: targeted b-version prompt addressing ONLY the failures
  - Must include: context file reference, session log reference
  - Must NOT: re-run entire session (only fix what's broken)
- [ ] HD entry: auto-evaluation loop architecture
- [ ] VERIFY: `git status` clean before completing

## /clear — Read context file + SESSION_LOG before continuing

## Phase 3: Parallelization Skill Test (10 min)

This tests the skill built in session 69 against a real prompt.

- [ ] Read .claude/skills/prompt-parallelizer/SKILL.md
- [ ] Feed THIS session 70 prompt to the skill (invoke it as a subagent or inline)
- [ ] Capture the skill's output: dependency graph, worktree plan, context briefs
- [ ] Compare skill's analysis to the ACTUAL parallelization used in Phase 2:
  - Did it correctly identify the 3-way parallel split?
  - Did it identify that none of the 3 subagents touch app code?
  - Did it flag the sequential dependency (Phase 0/1 must complete before Phase 2)?
  - Did it suggest reasonable context briefs for each subagent?
- [ ] Document comparison in: docs/analysis/parallelization_skill_test_session70.md
  - What the skill got right
  - What it missed
  - Specific improvements needed
- [ ] If the skill's output was poor:
  - Update the skill with the failure case
  - Re-run against the same prompt
  - Verify improvement
  - Log the learning loop in the test document
- [ ] If the skill's output was good:
  - Note this as validation evidence
  - Consider: can the UserPromptSubmit hook trigger this automatically?

## Phase 4: Merge + Test + Deploy (10 min)
- [ ] Merge ux-fixes worktree → run tests
- [ ] Merge multi-tool-harness worktree → run tests
- [ ] Merge auto-eval-loop worktree → run tests
- [ ] Full test suite: should be 3595+ with new UX tests
- [ ] Clean up worktrees and branches
- [ ] Push to main
- [ ] Verify Railway deploy triggers
- [ ] Browser verify (Playwright or manual):
  - UX-108 contrast fix visible
  - UX-109 color consistency
  - Discovery card improvements (UX-110-113)
  - All session 69 features still working

## Phase 5: Docs + Evaluation (10 min)
- [ ] Update: CHANGELOG.md (v0.74.1 or v0.75.0), ROADMAP.md, BACKLOG.md
- [ ] Update: AD entries, DD entries, HD entries from this session
- [ ] Update: SESSION_LOG.md with all phase results
- [ ] Write: session-70-assessment.md

### AUTO-EVAL TEST: If the auto-eval loop (Subagent C) produced a working
run_session.sh, AND Nolan has tested it pre-session, THEN invoke the
session-evaluator subagent on this session's output as a real test:
- [ ] Invoke session-evaluator on session-70-log.md + session-70-assessment.md
- [ ] If it finds issues: invoke fix-prompt-writer for a session-70b prompt
- [ ] Document what the auto-eval caught vs what was already addressed
- [ ] This is the FIRST LIVE TEST of the system — log everything

- [ ] Archive session log
- [ ] Update INDEX.md

---

## Success Criteria

**Must have:**
- All 4 production verifications PASS (1A-1D)
- DD-003 threshold aligned
- UX-108 + UX-109 (HIGH) fixed
- Auto-eval loop audited and run_session.sh fixed

**Should have:**
- All 13 UX issues addressed (MEDIUM + LOW)
- Multi-tool harness files created (AGENT_HARNESS.md, AGENTS.md, configs)
- Parallelization skill tested and results documented
- Subagent commit discipline rule added

**Nice to have:**
- Auto-eval loop tested live on session 70 output
- Full browser verification of all UX fixes
- sync-harness.sh tested by modifying CLAUDE.md and verifying adapters regenerate

---

## Post-Session Manual Task (Nolan does AFTER session completes)

**TEST run_session.sh** with session 70's own prompt as input:
```bash
./scripts/run_session.sh docs/prompts/session-70-prompt.md
```
This is the definitive test of the auto-eval loop. It has been deferred
for 4 sessions. The script is now fixed (Subagent C). Run it.

Report back: Did the evaluator catch anything? Did fix-prompt-writer generate
a b-version? Was the b-version useful?

After this test, RESUME DOGFOODING. The core user loop should now be working.

---

## MANDATORY RULES
- Update ALGORITHMIC_DECISIONS.md for every ML/algorithm decision
- Update DESIGN_DECISIONS.md for every UX/design decision
- Update HARNESS_DECISIONS.md for every workflow/tooling decision
- No doc file over 300 lines
- ROADMAP.md under 150 lines
- Deploy via git push, NOT Railway dashboard
- /clear between phases, NEVER /compact
- Commit after every phase
- Run smoke test after deploys

---

## Naming Convention
- Prompt: session-70-prompt.md
- Context: session-70-context.md (copy to docs/session_context/)
- Log: SESSION_LOG.md (archived to docs/session_logs/session-70-log.md)
