---
name: session-review
description: 'At session end: critically assess all work against original prompt.
  Identify concerns, red flags, gaps, superficial work. Then automatically spawn
  an auto-fix subagent that resolves all fixable issues. Logs everything clearly
  so we know what slipped by. Writes the mandatory assessment file. MUST run
  every session.'
---

# Session Review + Auto-Fix Skill

## Trigger
MUST run at the end of every session. The Stop hook enforces existence
of the assessment file — session cannot end without it.

## Steps

### 1. Re-Read Original Prompt
```bash
cat docs/prompts/session-NN-prompt.md
```

### 2. Verify Every Act/Phase
For EVERY act in the prompt:
a. Verify artifacts exist on disk (grep, ls, find)
b. Verify tests exist and pass (pytest specific test file)
c. Verify browser/curl evidence exists
d. Flag ANY silent deferrals, shortcuts, or "claimed done but not verified"

### 3. Write Assessment File
Create `docs/assessments/session-NN-assessment.md`:

```markdown
# Session NN Assessment

## Per-Act Status
| Act | Status | Evidence | Concerns |
|-----|--------|----------|----------|
| 0   | PASS/PARTIAL/FAIL | file paths, test names | issues |

## Concerns and Red Flags
- [severity] [description] — Evidence: [specific file/test/output]

## Superficial Work
- Items that appear done but lack proper testing or verification

## Deferred Items
- [item] — Reason: [why] — BACKLOG: [entry reference]
```

### 4. Auto-Fix Phase
Spawn subagent in worktree `session-NN/auto-fix`:
- Fix EVERY concern that can be fixed right now
- Log: "AUTO-FIXED: [description] — was: [problem] now: [solution]"
- Log: "DEFERRED: [description] — REASON: [why can't fix now]"

### 5. Merge Auto-Fix Worktree
Merge fixes back to main.

### 6. Update Assessment
Add final counts to assessment:
```
## Auto-Fix Summary
- Issues found: N
- Auto-fixed: N
- Deferred: N
```

### 7. Enforcement
The Stop hook checks for this file. Session CANNOT end without it.
This replaces manual "evaluate critically" prompts from the user.
