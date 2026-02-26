# Session 70 Planning Context
# "Production Verification + UX Fix Pass + Multi-Tool Harness + Auto-Evaluation Loop + Parallelization Test"

## Source: Session 69 assessment + dogfooding + multi-tool research + auto-eval audit
## Predecessor: Session 69 (v0.74.0 — BUG fixes, design audit, discoveries, parallelization skill)
## Breadcrumbs: Session 69 assessment → this context → Session 70 prompt

---

## 1. CRITICAL PRODUCTION VERIFICATIONS (from Session 69 Red Flags)

These MUST be verified before any new work starts.

### 1A: `batch_best_neighbor_distances` Import [MEDIUM → verify first]
Session 69 assessment red flag: "Discovery system uses `from core.neighbors import
batch_best_neighbor_distances` which may not exist in production if neighbors.py
doesn't have that function."

If this import fails, the entire /discoveries route returns 500 for every admin visit.
This is the same pattern as BUG-1 from session 69 (feature works in tests, crashes
in production due to missing function).

**Verification:** Check that `core/neighbors.py` exports `batch_best_neighbor_distances`.
If it doesn't exist, either create it or update the import to use what does exist.

### 1B: BUG-1 Fix Browser Verification
Session 69 fixed the "Create Identity" button (missing `user_source` parameter).
Must verify in actual browser: open Photo Context modal, type a name, click
"+ Create [Name]" and confirm it works end-to-end.

### 1C: Design Changes Rendering
Session 69 added Playfair Display font, warm card backgrounds, archival styling.
Must verify: fonts actually load in production (CDN? local?), card backgrounds
render correctly, no layout regressions.

### 1D: Discovery System End-to-End
Session 69 showed 1 discovery via Playwright (unidentified → Big Leon Capeluto, 54%).
Must verify: /discoveries loads for admin, confirm/reject buttons work, sidebar
badge count is accurate.

---

## 2. SESSION 69 UX REVIEW ISSUES (13 total)

The ux-reviewer subagent found these issues from production screenshots.
Full report: docs/session_context/session-69-ux-evaluation.md

### HIGH (P1 — fix this session)
- **UX-108**: "Heritage Archive" subtitle fails WCAG AA contrast (~2.1:1) —
  `text-amber-700/80` on slate-900 background. Fix: increase opacity or change color.
- **UX-109**: "To Review" count color inconsistent — amber in top banner, blue in
  sidebar badge. Pick one color and apply consistently.

### MEDIUM (P2 — fix this session if time)
- 5 issues from session-69-ux-evaluation.md (likely: spacing, alignment, hover
  states, responsive behavior). Read the full report during Phase 0.

### LOW (P3 — backlog)
- **UX-110**: Discovery card identity names truncated at 120px
- **UX-111**: Discovery match confidence badge has no tooltip/explanation
- **UX-112**: "Confirm as {name}" button will overflow on long names
- **UX-113**: Discovery empty state returns blank div — no feedback after clearing queue
- Plus 2 more from the evaluation report

### Previously backlogged UX issues
- **UX-104**: Compare "Compare Selected Faces" button not disabled before prerequisites met
- **UX-105**: Missing "Help Identify" CTA for photos with all-unidentified faces

---

## 3. SESSION 69 TECHNICAL DEBT

### DD-003 Threshold Mismatch
Documentation says "P(match) > 0.85" but implementation uses "distance < 1.0".
These are inversely related metrics pointing at the same concept. Pick one
representation, update both docs and code to be consistent. This is a 5-minute
fix but important for anyone reading the codebase.

### Subagent Commit Discipline
Session 69 red flag: "Subagent A test file was not committed in worktree — had
to be manually copied to main." This has happened before (session 64).

Fix: Add to the parallelization skill and/or subagent instructions:
"Every subagent MUST run its test suite AND commit ALL files before completing.
The orchestrator verifies: `git status` in each worktree shows clean working tree
before merge."

### BUG-3 Fix Is Fragile
The collection dropdown fix was `onfocus="this.select()"` — a workaround, not
a real fix. Users navigating with keyboard may not trigger onfocus. Real fix:
don't pre-fill "Uncategorized" (use placeholder text instead), or use a proper
select/dropdown component. Low priority but should be tracked.

### Context Overflow in Session 69
"Context ran out during Phase 4" — the session hit the context window limit
and required continuation. Post-mortem needed:
- Were subagent contexts too large?
- Was the orchestrator holding too much state?
- Should the parallelization skill include context budget estimation?

Add finding to LESSONS_LEARNED.md.

---

## 4. MULTI-TOOL OPERATIONAL GUIDE IMPLEMENTATION

From: multi-tool-operational-guide.md (Nolan's research output)

### What to implement in this session:

**4A: docs/AGENT_HARNESS.md** — Extract universal (tool-agnostic) rules from CLAUDE.md.
This is the canonical set of rules that Claude Code, Codex, and Antigravity all follow.
Content: project identity, commit discipline, decision tracking, architecture invariants,
testing requirements, ML pipeline rules.

**4B: AGENTS.md** — Codex adapter generated from CLAUDE.md.
Strips Claude-specific instructions (/clear, /compact, subagent routing).
Adds Codex-specific conventions (setup scripts, sandbox behavior).
References docs/AGENT_HARNESS.md. Kept under 32KB.

**4C: Antigravity config files:**
- `.cursorrules` — 3-line pointer to CLAUDE.md + AGENT_HARNESS.md
- `.gemini/GEMINI.md` — project rules pointer
- `.antigravity/rules.md` — generated from CLAUDE.md

**4D: scripts/sync-harness.sh** — Regenerates all adapter files from CLAUDE.md.
Auto-run via `.claude/rules/harness-sync.md` (path-scoped rule that triggers
when CLAUDE.md or AGENT_HARNESS.md is modified).

**4E: scripts/setup-worktree.sh** — Dependency setup for new worktrees.
Handles venv creation, pip install, .env copying, test verification.

**4F: Cross-tool operational procedures:**
- Commit message convention: `[tool-name] type(scope): description`
- PR-based review (no direct push to main from non-Claude tools)
- Context fragmentation prevention rules
- `.claude/worktrees/` added to .gitignore

**4G: HD entry** — Document the multi-tool harness architecture decision with full
provenance: why canonical source + adapters, why not symlinks, alternatives considered.

### What to defer:
- Actually using Codex or Antigravity (setup + first task = 2-3 hrs each)
- Antigravity skill creation (.agent/skills/rhodesli-harness/)
- Benchmarking across tools

---

## 5. AUTO-EVALUATION LOOP — AUDIT AND FIX

### Current state (broken):
The auto-evaluation system was designed across sessions 48-67 but never fully wired:

**Components that exist:**
- `.claude/agents/session-evaluator.md` — Subagent that assesses session output
- `.claude/agents/fix-prompt-writer.md` — Subagent that writes remediation prompts
- `scripts/run_session.sh` — Orchestrator script (exists, never tested)
- Stop hook: catches missing assessment files

**Intended flow (never executed):**
```
run_session.sh launches prompt
  → Session completes
  → session-evaluator assesses output:
      - Red flags? Concerns?
      - Evaluate against original prompt
      - Check for missed items, regressions, untested features
  → If issues found:
      - fix-prompt-writer generates session-NNb-prompt.md
      - run_session.sh launches b-version
      - b-version addresses specific failures
  → Final report: what was caught, what was fixed on second pass
```

**Why it's not working:**
1. run_session.sh has never been tested (deferred sessions 67, 68; "cannot nest
   claude -p from within a session")
2. Nolan was asked to test it manually pre-session but hasn't had time
3. The session-evaluator subagent exists but is only invoked manually (session 69
   used it for the assessment, but a human — me — was doing the actual red flag
   analysis in conversation)
4. fix-prompt-writer exists but has never been invoked

### What to fix this session:

**5A: Audit run_session.sh** — Read the script, verify it has the right flow.
Does it actually invoke session-evaluator after the main prompt completes?
Does it invoke fix-prompt-writer if issues are found? Does it launch the b-version?

**5B: Fix run_session.sh** — If the flow is incomplete, complete it. The script
should be a self-contained orchestrator that:
1. Reads the prompt file
2. Launches `claude -p` with the prompt
3. After completion, invokes session-evaluator (as a subagent or second claude call)
4. Parses evaluator output for FAIL/RED FLAG items
5. If issues found, invokes fix-prompt-writer to generate b-version
6. Launches b-version with `claude -p`
7. Writes final report to docs/session_logs/

**5C: Add observability** — The script must log:
- Which evaluator checks passed/failed
- What the fix-prompt-writer generated
- Whether the b-version resolved the issues
- Total time for main + b-version passes

**5D: HD entry** — Document the auto-evaluation architecture

**Note:** run_session.sh still can't be tested from WITHIN a Claude session.
But it CAN be written, audited, and prepared for Nolan's manual test.
The prompt should make this crystal clear: "Nolan: after this session, test
run_session.sh manually with the session 70 prompt itself as input."

---

## 6. PARALLELIZATION SKILL TESTING

Session 69 created `.claude/skills/prompt-parallelizer/SKILL.md` (171 lines)
but never tested it against a real prompt.

### Test plan for session 70:
1. Feed the session 70 prompt itself to the parallelization skill
2. Compare the skill's output (dependency graph, worktree plan) to the
   manually-crafted parallelization in the prompt
3. Document: what did the skill get right? What did it miss?
4. If the skill's analysis differs significantly from the manual plan,
   update the skill with the learnings
5. Log the comparison in a test artifact

### Self-correction mechanism:
If the parallelization skill fails to produce useful output:
- Log the failure mode (wrong dependency analysis? missed file conflicts?)
- Update the skill with the specific failure case as a test fixture
- Re-run against the same prompt to verify the fix
- This is the "learn from failure" loop Nolan requested

---

## 7. PARALLELIZATION ARCHITECTURE FOR SESSION 70

Based on dependency analysis:

```
Phase 0: Orient + Verify (sequential, main)
  └── All production verifications (1A-1D)
  └── Read UX evaluation report

Phase 1: Critical fixes (sequential, main)
  └── batch_best_neighbor_distances import fix if needed
  └── DD-003 threshold alignment
  └── UX-108 contrast fix (HIGH)
  └── UX-109 color consistency (HIGH)

/clear

Phase 2: Parallel execution
  ├── Subagent A (worktree: ux-fixes)
  │   Task: All MEDIUM + LOW UX issues (UX-110 through UX-113 + 5 MEDIUMs)
  │   Context: session-69-ux-evaluation.md + frontend-design SKILL.md
  │   Files: CSS, templates, minor JS
  │
  ├── Subagent B (worktree: multi-tool-harness)
  │   Task: AGENT_HARNESS.md, AGENTS.md, .cursorrules, .gemini/GEMINI.md,
  │         sync-harness.sh, setup-worktree.sh, harness-sync rule
  │   Context: multi-tool-operational-guide.md + CLAUDE.md + HD file
  │   Files: docs/, scripts/, .claude/rules/, config files (NO app code)
  │
  └── Subagent C (worktree: auto-eval-loop)
      Task: Audit + fix run_session.sh, verify session-evaluator + fix-prompt-writer,
            add observability, HD entry
      Context: .claude/agents/*, scripts/run_session.sh, HD file
      Files: scripts/, .claude/agents/ (NO app code)

/clear

Phase 3: Parallelization skill test
  └── Feed session 70 prompt to the skill
  └── Compare output to manual parallelization plan
  └── Document results, update skill if needed

Phase 4: Merge + Test + Deploy
Phase 5: Docs + Evaluation (use auto-eval loop if it's working!)
```

**Key insight:** Subagents B and C don't touch app code at all. They can
run simultaneously with each other AND with Subagent A (which only touches
CSS/templates). This is a clean 3-way parallel split.

---

## 8. FUNDAMENTAL GOALS CHECKPOINT

| Goal | Status after S69 | Session 70 impact |
|------|-------------------|-------------------|
| Usable by others | UNVERIFIED — bugs fixed but not browser-confirmed | Verify first, then UX polish |
| Expandable | IMPROVED — multi-tool harness enables other tools | Build the adapter layer |
| Community adoption | IMPROVED — discovery notifications exist | Fix remaining UX issues |
| Portfolio piece | STRONG — auto-eval loop is a major differentiator | Wire it up properly |

---

## 9. INTERVIEW MATERIAL OPPORTUNITIES

Session 70 produces several strong talking points:
- "I built a self-correcting development harness that automatically evaluates
  session output and generates remediation prompts" (auto-eval loop)
- "I implemented a portable multi-tool harness with canonical source + adapters
  for Claude Code, Codex, and Antigravity" (multi-tool guide)
- "I built an auto-parallelization skill that analyzes prompts for independent
  work streams and generates worktree plans" (parallelization skill)
- "I systematically addressed 13 UX issues found by an automated design reviewer"
  (UX fix pass)
