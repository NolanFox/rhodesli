# Session 48: Prompt Decomposition Research Context

## Problem Statement
When Claude Code gets a long, multi-phase prompt, it exhibits a
predictable failure pattern: early phases get built correctly, later
phases get "documented" or claimed but not fully wired. This happens
because context fills up as implementation progresses, there's no
external checkpoint verifying completion, and the model satisfices.

## Research Findings (Feb 2026)

### Pattern 1: Fresh Context / Phase Isolation
- Context degradation is real and measurable: ~20-30% performance
  drop with accumulated vs. fresh context
- ClaudeLog guide recommends finishing individual components before
  integration, with thorough notes at each checkpoint
- Native Tasks system (shipped Jan 23, 2026): Tasks persist to
  ~/.claude/tasks/ with dependency DAGs. Subagents can pick up tasks
  with fresh context windows.
- Ralph Wiggum plugin: Keeps Claude in a loop working through a
  TODO.md file. Each iteration gets fresh-ish context. Used for
  overnight autonomous execution.
- Agent Teams (experimental): Multiple Claude instances with separate
  context windows, coordinated by a lead agent.

### Pattern 2: Parallel vs. Sequential Analysis
- Agent Teams architecture supports parallel execution
- C compiler case study (Anthropic): 16 Claude agents, ~2,000
  sessions, git-based file locking for coordination
- Addy Osmani's analysis: tasks sized to "self-contained units that
  produce a clear deliverable," ~5-6 tasks per agent
- For Rhodesli: most phases touch app/main.py, so parallelism would
  cause file conflicts. Sequential subagents with fresh context per
  phase is the better pattern.

### Pattern 3: End-of-Session Verification
- Least well-served by existing tools
- Ralph Wiggum: self-reported completion (same model that fabricates)
- C compiler: external test suite as verification signal (gold standard)
- Native Tasks: track status but don't verify reality
- MISSING FROM ECOSYSTEM: a "spec-vs-reality reconciler" that takes
  the original prompt and independently verifies each deliverable

### Our Decision
Combine three patterns:
1. Prompt saved to disk + phase decomposition (from Pattern 1)
2. Sequential execution with commit-per-phase (from Pattern 2 analysis)
3. Feature Reality Contract as mandatory verification gate (Pattern 3)

This is the minimum viable version. Layer on Ralph Wiggum for
overnight runs later if this proves effective.

See: HARNESS_DECISIONS.md HD-001, HD-002, HD-003
