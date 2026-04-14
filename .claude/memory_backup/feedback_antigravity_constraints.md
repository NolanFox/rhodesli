---
name: Antigravity session constraints
description: Rules for Antigravity/Codex prompts — data safety, hooks, scope limits learned from Session 124
type: feedback
---

Antigravity prompts MUST include these constraints (Session 124 lesson):

1. **NEVER touch `data/` files** — identities.json, photo_index.json, embeddings.npy are production data. Do not modify, even for testing.
2. **NEVER use `--no-verify`** — pre-commit hooks exist for a reason. If hooks fail, fix the issue.
3. **NEVER commit `.claude/` files** — counter files, session mode are ephemeral.
4. **Scope explicitly** — list exact files to modify. "Review the codebase" leads to shallow 800-line reads.
5. **Don't overstate changes** — commit messages must match actual diff, not aspirational descriptions.
6. **DATA_SOURCE=json for tests** — Antigravity doesn't have Supabase credentials, must set this env var.

**Why:** Session 124 Antigravity used `--no-verify`, modified identities.json during debugging, committed counter files, and its summary claimed changes (kbd styling, htmx transitions) that were already in the code.

**How to apply:** When writing Antigravity prompts, include a "CONSTRAINTS" section with these rules. Include in the prompt template.
