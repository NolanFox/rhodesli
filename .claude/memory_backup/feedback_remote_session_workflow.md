---
name: Remote Session Workflow
description: Best practices for running Claude Code remotely from iOS app while session runs on laptop
type: feedback
---

Use tmux on the laptop so sessions survive disconnects. Claude Code has `/rc` (remote control) feature that generates QR code for mobile connection. Set session mode to "interactive" for remote sessions — skips /clear enforcement and codex audit gates that are friction on mobile.

**Why:** Nolan travels and remote-controls sessions from iOS. Sessions need to survive network drops and be scannable on small screens.

**How to apply:** Before leaving: `tmux new-session -s rhodesli && claude` then `/rc`. Set interactive mode. Structure work for async review — verbose commit messages, update session log after each phase so mobile check-ins show progress.
