---
name: Stop hook blocks non-session conversations
description: Stop hook fires repeatedly in ad-hoc/investigation conversations that aren't formal sessions, blocking exit and spamming the user
type: feedback
---

Stop hook (`stop-gate.sh`) requires assessment + session log + clean git for whatever session is in `current_session.txt`. When a separate conversation opens for ad-hoc investigation while a session is running, the stop hook blocks exit repeatedly with no way to dismiss.

**Why:** User opened an investigation conversation while Session 112 was running. The hook fired on every response cycle, demanding session 112 artifacts that belong to the other conversation. User couldn't exit or work without constant interruption.

**How to apply:** The stop hook needs a mode or escape hatch for non-session conversations:
- Option A: Check if `session_mode.txt` contains "investigation" or "ad-hoc" and skip enforcement
- Option B: Environment variable or flag file (e.g., `.claude/skip_stop_gate`) that ad-hoc conversations can set
- Option C: Only enforce if the current conversation actually created/modified session artifacts
- User explicitly asked to fix this: "make sure to adjust your hook strategy to account for this"
