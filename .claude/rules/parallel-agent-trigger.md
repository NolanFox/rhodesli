# Parallel Agent Strategy Trigger

Triggers: When planning a session that touches 3+ modules or files, OR when
a ROADMAP/BACKLOG item is tagged "Agent team candidate".

## Rule

Before writing a session prompt for multi-module work, read
`docs/architecture/PARALLEL_AGENT_STRATEGY.md` and decide:

1. **Subagents + worktrees** — for independent bug fixes, file-isolated features
2. **Agent teams** — for cross-layer work needing inter-agent coordination (experimental)
3. **Sequential** — when files overlap or tasks have dependencies

## Decision Checklist

- [ ] Do tasks touch different files? → Parallel subagents
- [ ] Do tasks touch the same file? → Same agent or sequential
- [ ] Do agents need to share findings? → Agent teams
- [ ] Is it a known agent-team candidate? (Check ROADMAP tags)

## Tagged Items (update as needed)

- TOOLS-002: ML Service Extraction — agent team candidate
- WORKSPACE-001: Personal archive auto-creation — agent team candidate

See: docs/architecture/PARALLEL_AGENT_STRATEGY.md
