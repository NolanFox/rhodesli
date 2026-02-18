# Prompt Decomposition Protocol

Triggers: Any prompt over 50 lines received in a session.

## When receiving a long prompt:

1. Save the full prompt to `docs/prompts/session_NN_prompt.md`
   (NN = current session number from ROADMAP.md)

2. Parse the prompt into phases. Create `docs/prompts/session_NN_phases.json`:
   ```json
   {
     "session": "NN",
     "total_phases": 5,
     "phases": [
       {
         "id": 0,
         "name": "Orient",
         "depends_on": [],
         "files_touched": ["CLAUDE.md", "ROADMAP.md"],
         "acceptance_criteria": ["Current state confirmed"],
         "estimated_minutes": 3
       }
     ]
   }
   ```

3. Create session log: `docs/session_logs/session_NN_log.md`
   with a checklist mirroring the phases:
   ```markdown
   # Session NN Log
   Started: [timestamp]
   Prompt: docs/prompts/session_NN_prompt.md

   ## Phase Checklist
   - [ ] Phase 0: Orient
   - [ ] Phase 1: [name]
   ...

   ## Verification Gate
   - [ ] All phases re-checked against original prompt
   - [ ] Feature Reality Contract passed
   ```

## Why this exists:
Context degradation is real and measurable. Saving the prompt to disk
means we can re-read it at the end of the session for verification,
even after the original prompt has been pushed out of context.

See: docs/HARNESS_DECISIONS.md HD-001
