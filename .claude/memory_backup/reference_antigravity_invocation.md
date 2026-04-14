---
name: Antigravity invocation methods
description: How to run Antigravity — GUI paste is default, Gemini CLI headless is the future option. Research from Session 125.
type: reference
---

## Default: Antigravity GUI (paste prompt)

Write prompt to `docs/prompts/session-NNx-antigravity-prompt.md`, user pastes into Antigravity IDE.
More token-efficient than Gemini CLI. User prefers this for now.

## Future Option: Gemini CLI Headless

Antigravity has NO CLI/headless mode (GUI-only IDE). But Gemini CLI can do the same work:

```bash
# Headless with auto-approve
cat docs/prompts/session-NNx-antigravity-prompt.md | gemini -p "Execute these instructions" -y

# With model selection
gemini -p "..." -m gemini-2.5-pro -y

# Scoped to specific dirs
gemini -p "..." --include-directories app -y
```

Key flags: `-p` (headless), `-y` (auto-approve), `--include-directories`, `--approval-mode auto_edit`

**Why deferred:** Antigravity GUI is more token-efficient. Gemini CLI headless is viable but costs more tokens.

**When to revisit:** If user asks for fully autonomous overnight runs, or if Antigravity adds a CLI mode.

## Antigravity Prompt Conventions

- File: `docs/prompts/session-NNx-antigravity-prompt.md`
- Must specify owned files explicitly (usually page_routes.py, person_routes.py)
- Must list DO NOT TOUCH files
- Must specify branch name and commit message
- Must request audit doc before implementation
- Constraint: CSS/template ONLY, no logic/data/auth

Sources:
- Gemini CLI headless docs: https://google-gemini.github.io/gemini-cli/docs/cli/headless.html
- Antigravity vs Gemini CLI: https://cloud.google.com/blog/topics/developers-practitioners/choosing-antigravity-or-gemini-cli
