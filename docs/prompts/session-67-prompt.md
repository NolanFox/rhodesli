# SESSION 67 — Harden the Harness: Hook Enforcement + Deferred Work
# Run with: claude --chrome --dangerously-skip-permissions

## THE CORE PROBLEM
We've created 7 subagent markdown files across Sessions 65d-66. NONE of them have ever been invoked in production. The ux-reviewer, session-evaluator, fix-prompt-writer, and parallel-optimizer exist as `.claude/agents/*.md` but Claude consistently chooses not to use them.

**The fix:** Subagent files are suggestions. HOOKS are enforcement. Claude Code hooks fire AUTOMATICALLY at lifecycle events. We need to convert our critical subagents into hooks that fire deterministically — not optionally.

## READ FIRST — MANDATORY
```bash
cat CLAUDE.md
cat docs/session_context/session-67-context.md
cat ROADMAP.md
head -80 docs/ALGORITHMIC_DECISIONS.md
echo "67" > .claude/current_session.txt
```

## NON-NEGOTIABLE RULES
1. Commit after EVERY completed task.
2. `pytest tests/ -x -q` before each commit. All pass.
3. /clear between EVERY phase. NEVER /compact.
4. Deploy via `git push origin main`.
5. Update ALGORITHMIC_DECISIONS.md for every decision.
6. Screenshots to `docs/screenshots/session-67/`.
7. Assessment: `docs/assessments/session-67-assessment.md`.

## CRITICAL: THE HOOK ARCHITECTURE IS THE DELIVERABLE
This session's primary output is a working hook system. If you do nothing else, deliver Phase 0 and Phase 1. Everything else is secondary.

---

## PHASE 0 — ARCHIVE + ORIENT (~5 min)

### 0A: Archive Previous Session Log
```bash
# Archive current SESSION_LOG.md if it has session 66b content
# Follow the archival process from docs/session_logs/INDEX.md
```

### 0B: Orient
```bash
cat CLAUDE.md
cat docs/session_context/session-67-context.md
# Read current .claude/settings.json to understand existing hook config
cat .claude/settings.json
# Check what hooks currently exist
ls -la .claude/hooks/
```

### 0C: Write Session Log
```markdown
# Session 67 Log
## Mission: Harden harness via hooks, deferred work cleanup
## Started: [timestamp]
## Rule: /clear between phases, NEVER /compact
```

Commit: `docs: session 67 orient`
git push

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 1 — BUILD THE HOOK ENFORCEMENT SYSTEM (~25 min)

This is the most important phase. Everything here uses Claude Code's native hook system for DETERMINISTIC execution.

### 1A: Stop Hook — Session Evaluator (Agent Type)

Replace the existing bash Stop hook with an **agent-type** Stop hook. Agent hooks spawn a subagent that can read files, run commands, and verify conditions. This fires EVERY TIME Claude finishes responding.

Update `.claude/settings.json`:
```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "agent",
            "prompt": "You are evaluating whether this Rhodesli session is complete. Read .claude/current_session.txt to get the session number. Then:\n\n1. Read the session prompt from docs/session_context/ or docs/prompts/\n2. Read SESSION_LOG.md for what was done\n3. Check git log --oneline -20 for commits\n4. For EACH phase in the prompt: check PASS/FAIL\n5. Check: does docs/assessments/session-{N}-assessment.md exist?\n6. Check: were screenshots taken for UI work? (ls docs/screenshots/session-{N}/)\n7. Check: was SESSION_LOG.md archived to docs/session_logs/?\n\nIf the assessment file exists AND all phases are logged: respond with {\"decision\": \"approve\", \"reason\": \"Session complete\"}\n\nIf assessment is MISSING or phases are incomplete: respond with {\"decision\": \"block\", \"reason\": \"Missing: [list what's missing]. Complete these before stopping.\"}\n\nCRITICAL: If any phase has FAIL status, also check if a b-path prompt exists at docs/prompts/session-{N}b-prompt.md. If failures exist but no b-path prompt: block and say 'Write a fix-up prompt for failed phases before stopping.'",
            "timeout": 120
          }
        ]
      }
    ]
  }
}
```

**Why this works:** The agent hook BLOCKS Claude from stopping until:
1. Assessment file exists
2. All phases are logged
3. If failures exist, a b-path prompt has been written

This replaces the bash script Stop hook which was informational-only (exit code 0 = never blocks).

### 1B: Stop Hook — UX Review After Screenshots

Add a **prompt-type** Stop hook that checks if screenshots were taken but ux-reviewer wasn't invoked:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "agent",
            "prompt": "... (evaluator from 1A) ...",
            "timeout": 120
          },
          {
            "type": "prompt",
            "prompt": "Check if this session involved UI work by looking at the session log. If screenshots exist in docs/screenshots/session-{N}/ but the session log does NOT mention 'ux-reviewer' or 'UX review': respond with {\"decision\": \"block\", \"reason\": \"Screenshots were taken but ux-reviewer subagent was never invoked. Delegate screenshots to ux-reviewer before stopping.\"}. Otherwise approve. Session data: $ARGUMENTS",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### 1C: UserPromptSubmit Hook — Parallelization Injection

When a prompt is submitted, inject a reminder about parallelization:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo 'REMINDER: Before starting work, analyze the prompt for parallelization opportunities. Phases that touch different files can run in worktree-isolated subagents simultaneously. Use parallel-optimizer subagent or manually identify independent workstreams. Max 3-4 worktrees. Merge order: docs first, then code.'"
          }
        ]
      }
    ]
  }
}
```

### 1D: PreCompact Hook — Block /compact

We've banned /compact but it keeps happening. Block it deterministically:

```json
{
  "hooks": {
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo '{\"decision\": \"block\", \"reason\": \"/compact is BANNED in Rhodesli. Use /clear instead. /compact is lossy. /clear + re-read from disk is the correct pattern.\"}'"
          }
        ]
      }
    ]
  }
}
```

### 1E: Write the Complete settings.json

Combine ALL hooks into one coherent `.claude/settings.json`. Preserve any existing settings (permissions, etc.) and ADD the hooks.

**IMPORTANT:** Test each hook:
```bash
# Test Stop hook agent — will it block if assessment is missing?
# Test PreCompact — does it actually block /compact?
# Verify with: claude --debug (shows hook execution)
```

### 1F: Update CLAUDE.md
Add a section explaining the hook architecture:
```markdown
## Hook Enforcement (Deterministic)
- Stop hook (agent): Blocks session end until assessment exists + all phases logged + b-path written if failures
- Stop hook (prompt): Blocks if screenshots exist but ux-reviewer wasn't invoked
- UserPromptSubmit: Injects parallelization reminder
- PreCompact: BLOCKS /compact (use /clear instead)
These hooks fire AUTOMATICALLY. They are not optional.
```

**AD entry:** AD-166: Hook-enforced harness — agent Stop hook for evaluation, prompt Stop hook for UX review, PreCompact block, UserPromptSubmit parallelization injection.

Commit: `feat(harness): hook enforcement — agent evaluator, UX review gate, compact block, parallel reminder`
git push

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 2 — TEST THE HOOKS (~10 min)

### 2A: Simulate a Session End Without Assessment
Start a mini-task, try to stop. The Stop hook should BLOCK with "Missing: assessment file."

### 2B: Simulate Screenshots Without UX Review
Take a screenshot of any page. Try to stop. The Stop hook should BLOCK with "ux-reviewer was never invoked."

### 2C: Try /compact
The PreCompact hook should block it.

### 2D: Check UserPromptSubmit
Submit any prompt. Verify the parallelization reminder appears in context.

### 2E: Document Results
```markdown
## Hook Test Results
- Stop (agent evaluator): [BLOCKS/DOESN'T BLOCK] when assessment missing
- Stop (UX review gate): [BLOCKS/DOESN'T BLOCK] when screenshots exist without review
- PreCompact: [BLOCKS/DOESN'T BLOCK] /compact
- UserPromptSubmit: [INJECTS/DOESN'T INJECT] parallelization reminder
```

If any hook doesn't work: debug with `claude --debug` and fix before proceeding.

Commit: `test: hook enforcement verified — all 4 hooks working`
git push

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 3 — DEFERRED WORK: SUBAGENT INVOCATIONS (~12 min)

Now that hooks enforce invocation, also do the manual catches from 66/66b.

### 3A: Invoke ux-reviewer on Accumulated Screenshots
```bash
ls docs/screenshots/session-66*/ docs/screenshots/session-66b*/
```
**Use the ux-reviewer subagent:** "Review all screenshots from sessions 66 and 66b."
Log findings. Fix HIGH issues. Add MEDIUM/LOW to BACKLOG.

### 3B: Invoke session-evaluator on Session 66
**Use the session-evaluator subagent:**
"Evaluate Session 66. Original prompt: docs/session_context/session-66-context.md. Log: docs/session_logs/session-66-log.md. Assessment: docs/assessments/session-66-assessment.md."

Compare independent assessment to main agent's self-assessment. Log discrepancies.

### 3C: Review Enrichment Validation
```bash
cat docs/analysis/enrichment_validation_66.md
```
Verify: GEDCOM-linked got 400-1000+ tokens, family members mentioned by name, gemini_config correct.
If doc is vague: re-run 3 enrichment calls with verbose logging.

Commit: `fix: invoke deferred subagents, review enrichment validation`
git push

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 4 — DEFERRED WORK: GEDCOM + CLEANUP (~10 min)

### 4A: Test GEDCOM Upload End-to-End
Use Playwright (not Chrome file dialog):
```python
page.goto("https://rhodesli.nolanandrewfox.com/admin/gedcom")
page.set_input_files("input[type=file]", "~/Downloads/gedcom_20260224/[filename].ged")
# Click upload, screenshot diff summary, screenshot after apply
```

### 4B: Clean Up Production Data
- Remove synthetic `test_upload_verification.jpg` if it exists
- Check for orphaned records from the failed `morris_mazal` upload
- Reconcile photo count discrepancy (273-274 on disk vs 272 in sidebar)

### 4C: Verify Upload Still Works Post-66b
Upload one more real photo from `~/Downloads/rhodesli_photo_testing/` to confirm the fix persists.
**Delegate screenshots to ux-reviewer.**

Commit: `fix: GEDCOM upload verified, production cleanup, upload re-verified`
git push

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 5 — /clear INVESTIGATION + SESSION RUNNER (~8 min)

### 5A: Test /clear in Headless Mode
```bash
# Does /clear work when running with -p flag?
# Test: run a simple prompt, check if /clear executes
claude -p "echo test. Then /clear. Then echo test2." 2>&1 | head -20
```

### 5B: If /clear Doesn't Work in -p Mode
Create `scripts/run_session.sh`:
```bash
#!/bin/bash
# Runs multi-phase sessions with REAL context isolation
# Usage: ./scripts/run_session.sh <prompt-file>
#
# The prompt file should have phase markers: ## PHASE N
# Each phase runs as a separate claude -p invocation
# Checkpoint files connect phases

PROMPT_FILE="$1"
SESSION_ID=$(grep -oP 'session-\K[0-9]+[a-z]?' "$PROMPT_FILE" | head -1)

# Split prompt into phases and run each separately
# Each phase reads from checkpoint, writes to checkpoint
# This gives REAL context window isolation
```

### 5C: Document Finding
Write `docs/harness/clear_investigation.md` with finding + recommendation.

Commit: `docs: /clear investigation + session runner script`
git push

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 6 — RETRY RATE-LIMITED PHOTOS (~10 min)

### 6A: Identify the 144 Rate-Limited Photos
```bash
# Find which photos from Session 64d were rate-limited
grep -rn "rate.limit\|429\|RATE" docs/analysis/ scripts/ --include="*.py" --include="*.md" | head -20
```

### 6B: Retry with Backoff
Run the enrichment pipeline on the rate-limited photos with appropriate backoff. Log results.

### 6C: Document
Update `docs/analysis/enrichment_validation_66.md` with retry results.

Commit: `feat: retry 144 rate-limited photos from session 64d`
git push

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 7 — DOCS + EVALUATION (MANDATORY) (~10 min)

### 7A: Docs
- CHANGELOG: Session 67 entry
- ROADMAP: update version, tests, next sessions (68: LoRA training data audit)
- BACKLOG: completed removed, deferred UX issues added
- ROADMAP < 150 lines

### 7B: Archive Session Log
SESSION_LOG.md → `docs/session_logs/session-67-log.md`
Update `docs/session_logs/INDEX.md`
Update B-Path Analysis table

### 7C: Write Assessment
`docs/assessments/session-67-assessment.md`
The Stop hook SHOULD block you from stopping until this exists. If the hook works correctly, you cannot skip this.

### 7D: If Failures → B-Path
The Stop hook SHOULD also block until a b-path prompt is written for failures.
If it blocks: write `docs/prompts/session-67b-prompt.md`, then run it.

### 7E: Print
```bash
cat docs/assessments/session-67-assessment.md
```

Commit: `docs: session 67 assessment + archive`
git push

---

## EXECUTION TIMELINE

```
Phase 0: Archive + orient (5 min)
Phase 1: BUILD HOOKS — the primary deliverable (25 min)
Phase 2: TEST HOOKS — verify they actually fire (10 min)
Phase 3: Invoke deferred subagents (12 min)
Phase 4: GEDCOM + cleanup + upload re-verify (10 min)
Phase 5: /clear investigation + session runner (8 min)
Phase 6: Retry rate-limited photos (10 min)
Phase 7: Docs + evaluation — Stop hook enforces this (10 min)
Total: ~90 min
```

## PARALLELIZATION OPPORTUNITIES
After Phase 1-2 (hooks must be built first):
- **Parallel A:** Phase 3 (subagent invocations) — touches docs/ only
- **Parallel B:** Phase 4 (GEDCOM + cleanup) — touches app/ and production
- **Parallel C:** Phase 5 (/clear investigation) — touches scripts/ and docs/harness/
- Phase 6 (retry photos) is independent but uses Gemini API

Use worktree subagents for A, B, C if the parallel-optimizer (now enforced via UserPromptSubmit hook) identifies them as safe to parallelize.

## BEGIN
Start with Phase 0. Read mandatory files. Set current_session.txt to "67". Execute.
