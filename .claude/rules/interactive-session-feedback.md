# Interactive Session Feedback Protocol

Triggers: When user provides feedback during a session (explicit or while using the app).
The session may START as implementation and SWITCH to interactive mid-session — that's fine.

## Rule
When the user gives feedback, the session enters interactive mode. Feedback is the
highest priority work — it represents real user experience with the live product.

### CRITICAL: No feedback is deferred. Fix everything.
- Do NOT put feedback items in BACKLOG unless the user explicitly says to defer
- Every FB item must be FIXED in the current session
- If a fix would take >30 min, tell the user and get explicit approval to defer
- "BACKLOG" is not an acceptable default disposition — it's an escape hatch

### On receiving feedback (IMMEDIATE — within 10 seconds):
1. **Acknowledge**: "Got it, FB-NNN" — the user must know it was captured
2. **Log immediately** via background subagent:
   - Write entry to `docs/feedback/session-NNN-feedback.md`
   - Include BACKLOG ID placeholder, ROADMAP breadcrumb if applicable
   - This MUST NOT block your current work — spawn background agent
3. **Assign severity** (P0-P3) based on user impact
4. **Continue current work** until a natural commit point, then switch to fixes

### Feedback entry format:
```
### FB-NNN: [Title]
- **Severity:** P0/P1/P2/P3
- **Context:** [What user was doing, what happened, what should have happened]
- **Screenshot:** [if captured]
- **Root cause:** [if identified]
- **Fix:** FIXED in session / IN PROGRESS
- **Commit:** [hash when fixed]
- **BACKLOG:** [only if user explicitly approved deferral]
```

### Parallelization strategy for feedback fixes:
- **Independent fixes** (different files): Launch parallel worktree subagents
- **Dependent fixes** (same file): Fix sequentially, smallest first
- **While fixing**: Keep accepting new feedback — log it, don't drop it
- **After each fix**: Run `make test-fast`, commit atomically
- **Dual-audit**: Codex CLI audit after all feedback fixes (batch, not per-fix)

### Mode switching:
When the user starts giving feedback mid-session:
```bash
echo "interactive" > .claude/session_mode.txt
```
This activates this protocol. Implementation work pauses at next commit point.
Resume implementation only after ALL feedback items are FIXED.

### At session end:
- ALL FB entries must have disposition: FIXED (with commit hash)
- Zero items with disposition "BACKLOG" unless user explicitly approved
- Feedback file must exist even if empty (proves protocol was followed)

## Why This Exists
Session 111: User gave rapid-fire feedback during triage. Claude was investigating a P0
data issue and lost track of UX feedback items. Feedback documentation must be decoupled
from investigation/fix work to prevent context overflow from causing dropped items.

Session 137: User explicitly requested that feedback is never deferred — fix everything
in the current session. Deferring to BACKLOG is a failure mode, not a workflow.

See: docs/HARNESS_DECISIONS.md HD-025, HD-031
