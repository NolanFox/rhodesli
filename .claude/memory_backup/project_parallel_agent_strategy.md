---
name: Parallel agent strategy for Rhodesli
description: Research on when to use subagents vs agent teams vs sequential work. Subagents for bug fixes, agent teams for multi-module features. TOOLS-002 and WORKSPACE-001 are tagged candidates.
type: project
---

Session 108 researched parallel agent strategies for Rhodesli development.

**Decision framework** at `docs/architecture/PARALLEL_AGENT_STRATEGY.md`:
- **Subagents + worktrees**: Independent bug fixes, file-isolated features. Use `isolation: "worktree"` in Agent tool.
- **Agent teams** (experimental): Multi-module features needing inter-agent coordination. Enable via `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.
- **Sequential**: When files overlap or tasks depend on each other.

**Why:** Nolan wants to try parallelization to speed up sessions. The 108b bug fixes are a first trial.

**How to apply:**
- Before planning any session touching 3+ files, check the parallel strategy doc
- ROADMAP items tagged "Agent team candidate" should use agent teams when they come up
- Current candidates: TOOLS-002 (ML Service), WORKSPACE-001 (Personal archive)
- Rule trigger at `.claude/rules/parallel-agent-trigger.md` fires automatically

**Key constraint for Rhodesli:** `app/main.py` (~9000 lines) is a bottleneck — any two tasks touching it cannot be parallel (Lesson 88).
