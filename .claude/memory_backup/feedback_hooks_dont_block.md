---
name: Hooks must exit 2 to block
description: Claude Code hooks that exit 0 are advisory only — must exit 2 to enforce blocking behavior
type: feedback
originSessionId: 27dd84b2-b7c4-4c48-8614-cb15d02f538c
---
Hooks that exit 0 are advisory only. Must exit 2 to actually block Claude from proceeding.

**Why:** Session 104 — UserPromptSubmit hook warned but never blocked because it exited 0. Claude ignores warnings in system-reminders. Pre-work gate threshold was too high (2+), so it never triggered.
**How to apply:** Any hook intended to PREVENT an action must `exit 2`. Advisory-only hooks (exit 0) will be read and ignored. When writing or auditing hooks, verify the exit code matches the intended enforcement level.
