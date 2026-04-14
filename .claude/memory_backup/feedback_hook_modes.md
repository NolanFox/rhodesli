---
name: Hook Session Modes
description: Three hook modes (implementation/interactive/continuation) control enforcement behavior — set via .claude/session_mode.txt
type: feedback
---

Hooks must distinguish between session types. User was frustrated that stop/clear hooks blocked during interactive triage and continuation prompt writing.

**Three modes** (set via `echo "MODE" > .claude/session_mode.txt`):
- `implementation` — Full enforcement: assessment required, /clear between phases, clean git at end
- `interactive` — Ad-hoc triage/exploration: no assessment required, no /clear enforcement, only check clean git
- `continuation` — Writing handoff prompts: never block anything

**Why:** Sessions 107 and earlier had the stop hook blocking every conversation end regardless of context, forcing user to hit ESC. Interactive triage sessions and continuation prompt writing are NOT full implementation sessions.

**How to apply:** At session start, set the mode. Default is `implementation`. Switch to `interactive` for triage. Switch to `continuation` when writing handoff prompts. The hooks read `.claude/session_mode.txt` and adjust enforcement accordingly.

**Key files:** `.claude/hooks/stop-gate.sh`, `.claude/hooks/pre-work-clear-gate.sh`, `.claude/hooks/post-commit-clear-gate.sh`
