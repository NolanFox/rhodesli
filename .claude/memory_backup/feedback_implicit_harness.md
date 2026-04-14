---
name: Harness is implicit — never repeat standard instructions
description: User should NOT need to repeat parallelization, harness compliance, context clearing, documentation, skills usage — these are the DEFAULT
type: feedback
originSessionId: 27dd84b2-b7c4-4c48-8614-cb15d02f538c
---
User should NOT need to repeat standard operational instructions. These are the DEFAULT behavior:
- Parallelization via worktree subagents
- /clear between acts
- Harness compliance (tests, commits, docs)
- Documentation updates (CHANGELOG, ROADMAP, etc.)
- Skills usage (/simplify, /session-review, /ux-review)

**Why:** Session 125 — user had to repeat the same instructions in Sessions 125, 126, and 127. These are operational procedures, not ad-hoc requests. Now codified in `.claude/rules/session-defaults.md`.
**How to apply:** Only call out EXCEPTIONS to default behavior in prompts. If the prompt doesn't mention parallelization, it means "use your judgment." If it doesn't mention testing, it means "of course test everything."
