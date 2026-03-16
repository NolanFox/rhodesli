# Parallel Agent Strategy for Rhodesli

**Date:** 2026-03-16 | **Session:** 108 | **Status:** Research complete, ready to trial

## TL;DR

For Session 108b's 3 bug fixes: **use subagents with worktree isolation**, not agent teams. Agent teams are overkill for well-scoped bug fixes with no inter-agent coordination needed. Save agent teams for future multi-module features (TOOLS-002, WORKSPACE-001).

## Options Compared

### Option A: Subagents with Worktree Isolation (RECOMMENDED for 108b)

Each bug fix runs as a subagent in its own git worktree. The orchestrator delegates, each agent works in isolation, results merge back.

```
Orchestrator (main)
├── Subagent 1: FB-013 (worktree: fix/fb-013) — compare modal on person page
├── Subagent 2: FB-014 (worktree: fix/fb-014) — photo context link
└── Subagent 3: FB-015 (worktree: fix/fb-015) — sidebar photo search
```

**Why this fits 108b:**
- 3 independent bugs touching different files (no overlap)
- No inter-agent coordination needed
- Each fix is self-contained (< 30 lines)
- Subagents report results back; orchestrator merges and verifies
- Lower token cost than agent teams

**File ownership (zero overlap):**
| Bug | Primary File | Secondary |
|-----|-------------|-----------|
| FB-013 | `app/page_routes.py` (person page) | None |
| FB-014 | `app/page_routes.py` (photo_view_content) | None |
| FB-015 | `app/identity_routes.py` (search endpoint) | None |

**Wait — FB-013 and FB-014 both touch `app/page_routes.py`.** This means they CANNOT run in fully parallel worktrees without merge conflicts. Options:
1. Run FB-013 and FB-015 in parallel (different files), then FB-014 sequentially after FB-013 merges
2. Run all 3 sequentially but use subagents for speed (each one completes faster than orchestrator doing it)
3. Give both FB-013 and FB-014 to one subagent since they touch the same file

**Recommendation: Option 3** — one subagent handles FB-013 + FB-014 (both in page_routes.py), another handles FB-015 (identity_routes.py). Two parallel tracks.

### Option B: Agent Teams (experimental)

Multiple Claude Code instances with shared task list, inter-agent messaging, and centralized lead coordination.

**How to enable:** Set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in settings.json or environment.

**Why NOT for 108b:**
- Experimental feature with known limitations (no session resumption, task status lag)
- 3 bug fixes don't need inter-agent communication
- Coordination overhead exceeds benefit for small tasks
- Higher token cost (each teammate = separate Claude instance)

**When to use agent teams for Rhodesli:**
- TOOLS-002 (ML Service Extraction) — spans Docker, API, app integration, tests
- WORKSPACE-001+ — auth, upload, permissions, UI all in parallel
- Major refactors touching 5+ modules
- Research + competing hypothesis debugging

### Option C: Manual Parallel Sessions (current approach)

What we've done in Sessions 97-100 with Codex + Claude Code.

**Pros:** Full control, proven pattern
**Cons:** Manual merge, no shared context, no automated coordination

## Implementation Guide for 108b

### Step 1: Create the worktree branches
```bash
git worktree add .claude/worktrees/fb-013-014 -b fix/fb-013-014
git worktree add .claude/worktrees/fb-015 -b fix/fb-015
```

### Step 2: Launch subagents with worktree isolation
In the orchestrator session, use the Agent tool with `isolation: "worktree"`:
```
Agent(subagent_type="general-purpose", isolation="worktree", prompt="Fix FB-013 and FB-014...")
Agent(subagent_type="general-purpose", isolation="worktree", prompt="Fix FB-015...")
```

### Step 3: Merge results
```bash
./scripts/merge.sh fix/fb-013-014 fix/fb-015
```

### Step 4: Deploy and browser-verify

## When to Graduate to Agent Teams

Consider agent teams when ALL of these are true:
1. 3+ genuinely independent work streams
2. Agents need to share findings or coordinate (not just report results)
3. Task duration > 30 minutes per agent
4. Work spans different architectural layers

## Anti-Patterns to Avoid

1. **Over-parallelizing**: 3 bugs that touch the same file → sequential, not parallel
2. **Vague delegation**: "Fix the search" fails; "Extend GET /api/search in identity_routes.py:648 to also query _photo_cache filenames" succeeds
3. **No merge strategy**: Always define merge order before launching parallel work
4. **Skipping tests**: Each subagent must run tests before completing

## Sources

- [Orchestrate teams of Claude Code sessions](https://code.claude.com/docs/en/agent-teams) — Official Anthropic docs
- [Claude Code Sub-Agents: Parallel vs Sequential Patterns](https://claudefa.st/blog/guide/agents/sub-agent-best-practices) — Best practices comparison
- [How to Run Multiple Claude Code Agents in Parallel with Git Worktrees](https://docs.bswen.com/blog/2026-03-16-claude-code-parallel-agents-git-worktrees/) — Worktree setup guide
- [Git Worktree Isolation in Claude Code](https://medium.com/@richardhightower/git-worktree-isolation-in-claude-code-parallel-development-without-the-chaos-262e12b85cc5) — Real-world experience report
- [Claude Code Agent Teams: The Complete Guide 2026](https://claudefa.st/blog/guide/agents/agent-teams) — Comprehensive agent teams guide
- [Boris Cherny on built-in worktree support](https://www.threads.com/@boris_cherny/post/DVAAnexgRUj/) — Official announcement
- [How we're shipping faster with Claude Code and Git Worktrees](https://incident.io/blog/shipping-faster-with-claude-code-and-git-worktrees) — incident.io case study

## Rhodesli-Specific Considerations

1. **app/main.py is a bottleneck**: At ~9000 lines, any feature touching main.py blocks parallel work on other main.py features. This is Lesson 88.
2. **Hooks must work in worktrees**: Our test-gate.sh and commit hooks reference project root paths — verify they resolve correctly in worktree directories.
3. **Data files are shared**: Worktrees share the same `.git` database but data/ files are per-worktree. Be careful with identities.json/photo_index.json.
4. **Our merge.sh script exists**: `./scripts/merge.sh` already handles ordered merging with test gates between branches.
