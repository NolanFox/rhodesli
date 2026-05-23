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

## Novel-Discovery Audit (REQUIRED for genealogy sessions per Lesson 50 / Discipline §10)
For each fact framed as "new" or "discovery" this session, classify as ONE of:
- **vault-catch-up** — already in user's tree (post-most-recent-GEDCOM-export), or already in vault dossiers / research docs, or already in JewishGen / Ancestry / public sources the user has consulted
- **withdrawn-error** — claimed as discovery but later refuted; preserved for audit trail
- **methodology lesson** — useful but NOT a genealogical novel discovery (count separately)
- **genuine novel discovery** — cross-source signal (e.g., name X appears on document Y where X's presence wasn't expected), OR resolution of a previously-open question, OR new entity link creating further investigation chain

Tally: `# genuine novel : # vault-catch-up : # withdrawn : # methodology`. 0 genuine novel + honest classification = WIN per Lesson 50 spirit. Gold-standard example: "finding Sam Lebow on a Fox wedding certificate as a witness."

## User-Feedback Absorb (REQUIRED if user feedback was received this session per Lesson 49 / Discipline §9)
For each user feedback received between session start + close, produce all 5 outputs:
- (a) **acknowledged correction** — explicit acknowledgement of what was wrong
- (b) **vault-doc propagation** — list of ALL affected docs patched
- (c) **methodology lesson** — what general-purpose failure mode this catches
- (d) **CLAUDE.md Discipline rule update** — if a new general-purpose check emerges
- (e) **Codex audit prompt template update** — if the audit should now check for this pattern

Apply ON EVERY USER FEEDBACK between sessions (per Lesson 49 expansion of Lesson 28 metanalysis-mandatory). This is an expansion of session-close metanalysis to all in-session feedback events.

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
