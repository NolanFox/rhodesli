# Interactive Session Feedback Protocol

Triggers: During any session with mode=interactive (set in .claude/session_mode.txt).

## Rule
During interactive sessions, the user provides real-time feedback while using the app.
Every piece of feedback MUST be documented immediately, even if you're investigating
something else. Use background subagents so documentation doesn't block investigation.

### On receiving feedback:
1. **Assign an FB-NNN ID** (continuing from the last FB number in this session)
2. **Spawn a background subagent** to write the entry to `docs/feedback/session-NNN-feedback.md`
3. **Continue your current work** — don't context-switch to document manually
4. **Acknowledge the feedback** briefly to the user ("Got it, documenting as FB-NNN")

### Feedback entry format:
```
### FB-NNN: [Title]
- **Severity:** P0/P1/P2/P3
- **Context:** [What user was doing, what happened, what should have happened]
- **Screenshot:** [if captured]
- **Root cause:** [if identified]
- **Fix:** [FIXED in session / IN PROGRESS / BACKLOG — effort estimate]
- **BACKLOG:** [ID if deferred]
```

### At session end:
- All FB entries must be in the feedback file
- Each entry must have a severity, root cause (or "TBD"), and disposition (FIXED/BACKLOG)
- P0 items that weren't fixed need explicit justification

## Why This Exists
Session 111: User gave rapid-fire feedback during triage. Claude was investigating a P0
data issue and lost track of UX feedback items. Feedback documentation must be decoupled
from investigation/fix work to prevent context overflow from causing dropped items.

See: docs/HARNESS_DECISIONS.md (add HD-025)
