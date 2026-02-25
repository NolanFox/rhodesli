# Session 67 Context: Harden the Harness via Hooks + Deferred Work

## Source
- **Date:** 2026-02-25
- **Origin:** Sessions 66 + 66b review — subagents never invoked, parallelization not applied
- **Predecessor:** Session 66b (v0.72.1 — upload fix finally verified)

---

## PART 1: THE FUNDAMENTAL PROBLEM — SUBAGENTS vs HOOKS

### What We Built (Sessions 65d-66)
7 subagent files in `.claude/agents/`:
- ux-reviewer.md, session-evaluator.md, fix-prompt-writer.md
- design-check.md, parallel-optimizer.md, merge-resolver.md, enrichment-worker.md

### What Actually Happened
**Zero invocations.** Not one subagent was ever used in a real session. Claude consistently chose not to invoke them, even when the prompt explicitly said "delegate to ux-reviewer" or "invoke session-evaluator."

### Why This Happens
Subagent files are **suggestions** — Claude reads the description and MAY invoke them, but the LLM can always decide "I'll just do it myself." In practice, the main agent prefers to handle everything in its own context rather than delegating.

### The Fix: Hooks Are Enforcement
Claude Code hooks fire **deterministically** at lifecycle events. They are not optional. Three hook types:

| Type | How It Works | When to Use |
|------|-------------|-------------|
| `command` | Runs a shell script | Deterministic rules (block /compact, inject reminders) |
| `prompt` | Single LLM call (Haiku) | Quick yes/no judgments |
| `agent` | Spawns a subagent with tool access | Complex verification (read files, check state, run tests) |

**Key insight:** An `agent`-type Stop hook spawns a subagent that can read files, run commands, and BLOCK Claude from stopping until conditions are met. This is how we enforce evaluation, UX review, and b-path writing.

---

## PART 2: HOOK ARCHITECTURE

### Hook 1: Stop — Session Evaluator (Agent Type)
**Event:** Stop (fires when Claude finishes responding)
**Type:** agent (spawns subagent with Read, Grep, Glob, Bash access)
**Timeout:** 120 seconds
**Behavior:**
1. Reads .claude/current_session.txt for session number
2. Reads the session prompt and SESSION_LOG.md
3. Checks git log for commits
4. Verifies assessment file exists
5. Verifies all phases logged
6. If failures found: checks if b-path prompt exists
7. Returns `{"decision": "approve"}` or `{"decision": "block", "reason": "..."}`

**If it blocks:** Claude CANNOT stop. It must complete the missing work, then try again. The hook re-evaluates.

### Hook 2: Stop — UX Review Gate (Prompt Type)
**Event:** Stop
**Type:** prompt (single Haiku call)
**Timeout:** 30 seconds
**Behavior:** Checks if screenshots exist but ux-reviewer was never mentioned in the session log. If so, blocks.

### Hook 3: UserPromptSubmit — Parallelization Reminder
**Event:** UserPromptSubmit (fires before Claude processes ANY prompt)
**Type:** command
**Behavior:** Echoes a reminder to analyze the prompt for parallelization opportunities. This gets injected into Claude's context at the start of every prompt.

### Hook 4: PreCompact — Block /compact
**Event:** PreCompact (fires before compaction)
**Type:** command
**Behavior:** Returns block decision. /compact is permanently banned.

### All hooks live in `.claude/settings.json`
Multiple hooks on the same event run in parallel. Agent hooks are more expensive (they spawn subagents) but are the only way to do file-based verification.

---

## PART 3: DEFERRED ITEMS FROM SESSIONS 66 + 66b

### Never Invoked (3 sessions deferred)
1. **ux-reviewer:** Screenshots from 66/66b exist but were never analyzed by the subagent
2. **session-evaluator:** Session 66 was self-assessed by the main agent (generous grading)
3. **fix-prompt-writer:** Never tested — we manually wrote the 66b prompt

### Skipped in 66b
4. **GEDCOM upload test:** End-to-end with real GEDCOM file from ~/Downloads/gedcom_20260224/
5. **/clear in headless mode:** Still unknown if /clear works in `-p` mode
6. **Enrichment validation review:** docs/analysis/enrichment_validation_66.md contents not verified for quality

### Cleanup Needed
7. **Production data:** synthetic test_upload_verification.jpg, orphaned morris_mazal records
8. **Photo count discrepancy:** 273-274 on disk vs 272 in sidebar
9. **Rate-limited photos:** 144 from Session 64d still pending retry

---

## PART 4: THE PATTERN WE MUST BREAK

| Issue | How Many Times Raised | Root Cause |
|-------|----------------------|------------|
| Subagents not invoked | 3 sessions (66, 66b, now 67) | Subagents are optional; needs hooks |
| /clear not used | 3 sessions (65d, 66, 66b) | Either headless mode limitation or LLM ignores it |
| Upload "fixed" but broken | 5 sessions (65a-66b) | Verification checked mechanism, not outcome |
| Parallelization not applied | 2 sessions (66b skipped it entirely) | No enforcement, just a prompt suggestion |
| Assessment undersells gaps | 3 sessions | Main agent grades itself; needs independent evaluator |

**Every one of these is solved by hooks, not prompts:**
- Subagents not invoked → Stop hook BLOCKS until they're used
- /clear not used → PreCompact blocks /compact; /clear investigation determines if we need session runner script
- Verification quality → Stop hook agent verifies outcomes, not mechanisms
- Parallelization → UserPromptSubmit injects reminder; future: agent hook analyzes for parallel opportunities
- Assessment quality → Stop hook agent does independent evaluation

---

## PART 5: TECHNICAL REFERENCE

### .claude/settings.json Structure
```json
{
  "permissions": { ... },  // existing permissions
  "hooks": {
    "Stop": [
      {
        "hooks": [
          { "type": "agent", "prompt": "...", "timeout": 120 },
          { "type": "prompt", "prompt": "...", "timeout": 30 }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          { "type": "command", "command": "echo '...'" }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          { "type": "command", "command": "echo '{\"decision\": \"block\", \"reason\": \"...\"'" }
        ]
      }
    ]
  }
}
```

### Debugging Hooks
```bash
claude --debug  # Shows hook execution details
/hooks           # View and manage hooks in interactive mode
```

### Hook Gotchas
- Stop hooks with `type: "agent"` consume tokens (they spawn a subagent)
- Multiple hooks on the same event run in parallel
- If a Stop hook blocks, Claude continues working and tries to stop again later
- PreCompact hooks cannot return block decisions (they're informational only) — need to verify this
- The `$ARGUMENTS` placeholder gets replaced with the hook's JSON input data

---

## PART 6: SESSION PRIORITY ORDER

1. **HOOKS (Phase 1-2):** Build + test the 4 hooks. This is THE deliverable.
2. **DEFERRED SUBAGENT WORK (Phase 3):** Actually invoke ux-reviewer, session-evaluator, review enrichment
3. **GEDCOM + CLEANUP (Phase 4):** Test GEDCOM upload, clean production, verify upload
4. **/clear INVESTIGATION (Phase 5):** Determine if we need session runner script
5. **RATE-LIMITED PHOTOS (Phase 6):** Retry the 144 from 64d
6. **EVALUATION (Phase 7):** Stop hook should enforce this automatically
