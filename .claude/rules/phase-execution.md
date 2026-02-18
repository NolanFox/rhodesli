# Phase Execution Discipline

Triggers: During execution of any multi-phase session.

## For each phase:

1. **Read only the relevant phase** from the prompt file
   (not the entire prompt — preserve context for actual work)

2. **Execute the phase completely** — do not move on until done

3. **Commit atomically per phase:**
   `git add -A && git commit -m "feat/fix(scope): session NN phase N — [description]"`

4. **Update session log** (`docs/session_logs/session_NN_log.md`):
   - Mark phase checkbox as done: `- [x] Phase N: [name]`
   - Add what was actually built (not what was planned)
   - Note any deviations from the plan

5. **Context management:**
   - If context is above 60%, run `/compact` before next phase
   - Re-read phase-specific section of prompt for next phase
   - Do NOT carry forward mental model of "what I think the next phase says"
     — re-read it fresh

## Why this exists:
The "satisficing" failure pattern: Claude builds enough to feel done
in early phases, then progressively degrades on later phases as
context fills up. Atomic commits + session logging create checkpoints
that make incomplete work visible.

See: docs/HARNESS_DECISIONS.md HD-002
