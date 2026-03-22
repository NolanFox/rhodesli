# Session 133: Parallel Agent Execution Research

**Date:** 2026-03-22 | **Scope:** Subagents, agent teams, cross-model verification, industry state of the art

---

## 1. Our Current Approach (What Works, What Doesn't)

**Source:** `docs/architecture/PARALLEL_AGENT_STRATEGY.md` (Session 108), memory files from Sessions 97-132.

### What Works

- **Subagents + worktrees for bug fixes**: Sessions 108b, 111, 120 used 2-4 parallel worktree subagents for independent fixes. Reliable when files don't overlap. merge.sh handles ordered merging with test gates.
- **Cross-AI audit pattern**: "Codex implements, Claude audits" is our strongest workflow. Session 118 Codex audit found a real security bug (upload community override). Sessions 123-131 all ran Codex audits with measurable value.
- **File-ownership discipline**: Explicitly mapping which subagent owns which files prevents merge conflicts. Lesson 88 (app/main.py bottleneck) is well-internalized.

### What Doesn't Work

- **Codex degrades after ~6 hours**: Sessions 97-100 showed diminishing returns. 12h Session 100 had data integrity regressions. Our 4h cap is correct but not mechanically enforced.
- **Codex misses data integrity issues**: Surface-level correctness (tests pass, commits clean) but merge chain regressions, orphaned faces, and split-brain went undetected. Antigravity (Session 99) was similar — overstated changes, modified production data during debugging.
- **Agent teams untried**: Despite documenting the option in Session 108, we have never actually used `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`. The two tagged candidates (TOOLS-002, WORKSPACE-001) were either completed sequentially or via manual parallel sessions.
- **No dedicated checker subagent**: Our Codex audits are ad-hoc (run when remembered). No systematic pattern where a checker reviews every subagent's output before merge.
- **Audit logging inconsistent**: Sessions 124-132 used Codex without consistent ROI logging (prompted the AI Tool Audit rule in Session 133).

---

## 2. Industry State of the Art (March 2026)

### The February 2026 Multi-Agent Wave

Every major tool shipped multi-agent support in the same two-week window (Feb 2026):

| Tool | Parallel Support | Isolation | Notes |
|------|-----------------|-----------|-------|
| **Claude Code** | Agent Teams + worktree subagents | Git worktrees (built-in) | `--teammate-mode`, task list coordination |
| **Cursor** | Up to 8 parallel agents + Background Agents | Git worktrees | Bugbot auto-reviews PRs |
| **Windsurf** | 5 parallel Cascade agents (Wave 13) | Git worktrees | SWE-1.5 proprietary model |
| **Codex CLI** | Desktop app command center | Sandboxed containers | Diff-view review on completion |
| **Grok Build** | 8 simultaneous agents | Sandboxed | xAI's entry |
| **Devin** | Parallel sessions | Cloud sandboxes | Cognition's autonomous agent |

Sources: [NxCode Agent Teams Guide](https://www.nxcode.io/resources/news/claude-agent-teams-parallel-ai-development-guide-2026), [Lushbinary Comparison](https://lushbinary.com/blog/ai-coding-agents-comparison-cursor-windsurf-claude-copilot-kiro-2026/), [Agentmaxxing](https://vibecoding.app/blog/agentmaxxing)

### Subagents vs Agent Teams: The Decision Framework

The industry consensus (from [Claude Code docs](https://code.claude.com/docs/en/agent-teams), [Han Heloir Yan's comparison](https://medium.com/data-science-collective/sub-agent-vs-agent-team-in-claude-code-pick-the-right-pattern-in-60-seconds-e856e5b4e5cc)):

| Criterion | Subagents | Agent Teams |
|-----------|-----------|-------------|
| Communication | Report results to parent only | Share task list, communicate with each other |
| Best for | Independent tasks, batch changes | Research, competing hypotheses, cross-layer features |
| Coordination cost | Zero (parent merges) | Moderate (task list sync, message passing) |
| Token cost | Lower (each runs independently) | Higher (each teammate is a full Claude instance) |
| Failure blast radius | Isolated to one worktree | Can cascade through shared task list |

**Key insight from MIT Missing Semester 2026**: Running the same task on multiple agents (stochastic sampling) and taking the best solution is a valid pattern. LLMs are non-deterministic, so parallel runs can find different solutions. Source: [Missing Semester Agentic Coding](https://missing.csail.mit.edu/2026/agentic-coding/)

### The Specialist-Agent Review Pattern (New in 2026)

The most significant new pattern is **specialist checkers** rather than a single "review" step. Instead of one checker agent, spin up focused reviewers ([CodeScene analysis](https://codescene.com/blog/agentic-ai-coding-best-practice-patterns-for-speed-with-quality)):

- **Correctness agent**: Logic bugs, edge cases, error handling
- **Security agent**: Auth guards, injection, secrets exposure
- **Performance agent**: Hot paths, N+1 queries, algorithmic complexity
- **Requirements agent**: Does the code satisfy acceptance criteria?

This maps directly to what we already do informally: Codex for security audit, our test suite for correctness, manual browser verification for requirements.

### Cross-Model Verification (Validated Pattern)

The "implement with Claude, audit with Codex" pattern is now an industry-recognized workflow ([SmartScope automation guide](https://smartscope.blog/en/blog/claude-code-codex-review-loop-automation-2026/), [Chandler Nguyen dual-wielding](https://chandlernguyen.com/blog/2026/03/13/codex-gpt-5-4-vs-claude-code-opus-4-6-dual-wielding-ai-coding-tools/)):

- **Claude Code strengths**: Fast execution, fluid multi-file changes, strong at depth/data integrity
- **Codex strengths**: More deliberate critique, rigorous in review mode, catches security issues
- **Complementary styles**: Speed (Claude) x rigor (Codex) produces better outcomes than either model reviewing itself
- **Two schools**: "Resume" (Codex remembers prior findings, verifies fixes) vs "Fresh session" (independent reviewer each time). Fresh session is better for security audits; resume is better for iterative refinement.
- **GitHub Agent HQ** (Feb 2026): Lets you assign multiple agents (Copilot, Claude, Codex) to the same issue and compare results at the platform level.

Source: [codex-pr-review skill](https://github.com/johnpsasser/codex-pr-review), [ARIS framework](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep)

### Quality Gates in CI (New Pattern)

A safer CI pattern for agentic code review ([Roman Fedytskyi](https://medium.com/@roman_fedyskyi/a-safer-ci-pattern-for-agentic-code-review-94a484b5e3c4)):

1. **Scope**: Agent starts with read-only repo access, narrow network
2. **Context**: Semantic retrieval finds related files within approved boundaries
3. **Validation**: Nothing the agent suggests matters until engineering gates pass
4. **Observability**: Every prompt, tool call, and validation result gets audit trail

This matches our hook enforcement philosophy (exit 2 to block, not exit 0 to warn).

---

## 3. Recommendations for Rhodesli

### R1: Formalize the Checker Subagent Pattern (Immediate)

Instead of ad-hoc Codex audits, standardize a **post-implementation checker subagent** that runs after every merge:

```
Orchestrator
├── Implementation subagent(s) — worktree isolation
├── [merge results]
└── Checker subagent — runs on merged code
    ├── Security scan (auth guards on POST routes, input validation)
    ├── Data integrity (face-identity mappings, merge chain validity)
    └── Test coverage delta (new code has tests)
```

This can be a Claude Code subagent (not Codex) for speed. Reserve Codex cross-model audits for sessions with security-sensitive changes or data migrations.

### R2: Try Agent Teams for WORKSPACE-001 (Next Opportunity)

WORKSPACE-001 (personal archive auto-creation) spans auth, upload, permissions, and UI — exactly the cross-layer pattern where agent teams add value. Each teammate owns a layer:

- Teammate A: Auth + permissions (app/auth.py, middleware)
- Teammate B: Upload pipeline (app/upload_routes.py, core/storage.py)
- Teammate C: UI (app/page_routes.py, templates)
- Teammate D: Tests (tests/)

Enable with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`. Document the experience for future reference.

### R3: Adopt the "Fresh Session" Audit for Security, "Resume" for Polish

- **Security-sensitive sessions**: Fresh Codex audit (independent, no prior context bias)
- **UX polish sessions**: Resume-style audit (Codex sees prior feedback, tracks fixes)
- Log every audit with the structured format from `.claude/rules/ai-tool-audit.md`

### R4: Do NOT Over-Parallelize (Lesson Reinforcement)

Our data shows single-agent sequential work is correct for:
- Anything touching `app/main.py` (Lesson 88 — still a 9000-line bottleneck)
- Data migrations (Codex missed merge chain regressions in Sessions 97-100)
- Any write path to identities or photos (split-brain risk)

Parallel work is correct for:
- Independent bug fixes in different files (proven in Sessions 108b, 111)
- Test writing (subagent can write tests while orchestrator implements)
- Documentation and code changes simultaneously

### R5: No Harness Changes Needed (Yet)

Our current infrastructure (worktree support, merge.sh, hook enforcement, test gates) is sufficient. The main gaps are behavioral, not mechanical:
- We don't consistently run checker subagents (fix: add to session-defaults.md when pattern is proven)
- We don't log audit ROI consistently (fix: already addressed by ai-tool-audit.md rule)
- We haven't tried agent teams (fix: try on next cross-layer feature, then decide)

---

## 4. What's New in 2026 vs Older Patterns

| Before Feb 2026 | After Feb 2026 |
|-----------------|----------------|
| Manual parallel sessions (separate terminals) | Built-in worktree isolation in all major tools |
| Single-model review | Cross-model verification as recognized pattern |
| Ad-hoc task delegation | Structured task lists with teammate communication |
| "Run tests" as quality gate | Specialist checker agents (security, perf, correctness) |
| Sequential agent execution only | 5-8 parallel agents standard in Cursor, Windsurf, Claude |
| Stochastic sampling not discussed | MIT teaches running same task on multiple agents |
| No platform-level multi-agent | GitHub Agent HQ assigns multiple AI agents to one issue |

The fundamental shift: parallel AI agents went from "power user hack" to "built-in feature" in February 2026. The tooling is mature enough that the question is no longer "can we parallelize?" but "when should we?"

---

## Sources

- [Claude Code Agent Teams Docs](https://code.claude.com/docs/en/agent-teams)
- [NxCode: Claude Agent Teams Guide 2026](https://www.nxcode.io/resources/news/claude-agent-teams-parallel-ai-development-guide-2026)
- [MIT Missing Semester: Agentic Coding](https://missing.csail.mit.edu/2026/agentic-coding/)
- [SmartScope: Claude Code x Codex Review Loop](https://smartscope.blog/en/blog/claude-code-codex-review-loop-automation-2026/)
- [Chandler Nguyen: Codex vs Claude Code Dual-Wielding](https://chandlernguyen.com/blog/2026/03/13/codex-gpt-5-4-vs-claude-code-opus-4-6-dual-wielding-ai-coding-tools/)
- [CodeScene: Agentic Coding Best Practices](https://codescene.com/blog/agentic-ai-coding-best-practice-patterns-for-speed-with-quality)
- [Han Heloir Yan: Subagent vs Agent Team](https://medium.com/data-science-collective/sub-agent-vs-agent-team-in-claude-code-pick-the-right-pattern-in-60-seconds-e856e5b4e5cc)
- [Roman Fedytskyi: Safer CI for Agentic Review](https://medium.com/@roman_fedyskyi/a-safer-ci-pattern-for-agentic-code-review-94a484b5e3c4)
- [incident.io: Shipping Faster with Worktrees](https://incident.io/blog/shipping-faster-with-claude-code-and-git-worktrees)
- [Agentmaxxing: Parallel Agents Guide](https://vibecoding.app/blog/agentmaxxing)
- [Lushbinary: AI Coding Agents Compared](https://lushbinary.com/blog/ai-coding-agents-comparison-cursor-windsurf-claude-copilot-kiro-2026/)
- [codex-pr-review GitHub skill](https://github.com/johnpsasser/codex-pr-review)
- [Anthropic 2026 Agentic Coding Trends Report](https://resources.anthropic.com/hubfs/2026%20Agentic%20Coding%20Trends%20Report.pdf)
