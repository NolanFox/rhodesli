---
description: "Analyzes multi-phase session prompts for parallelization opportunities. Outputs dependency graph, file-conflict analysis, and worktree allocation plan with subagent context briefs."
---

# Prompt Parallelizer Skill

## Purpose

Given a multi-phase session prompt, determine which phases can run in
parallel (separate worktrees) vs which must run sequentially. Produces
a ready-to-execute parallelization plan with subagent context briefs.

## Trigger Conditions

- Session prompt has 4+ phases
- At least 2 phases touch different file sets (no overlap)
- Session is not a "fix one critical bug" emergency session
- UserPromptSubmit hook reminds to consider parallelization

## Input

The full session prompt (saved to `docs/prompts/session_NN_prompt.md`).

## Analysis Steps

### Step 1: Phase Extraction

Parse the prompt into discrete phases. For each phase, extract:
- Phase ID and name
- Files likely touched (from explicit mentions + inference)
- External resources needed (Chrome browser, Gemini API, Supabase)
- Estimated duration (S/M/L)

### Step 2: Dependency Graph

Build a DAG of phase dependencies:

```
Phase 0 (Orient) ──> Phase 1 (Core Work)
                 ──> Phase 2 (Docs)
Phase 1 ──> Phase 4 (Merge + Test)
Phase 2 ──> Phase 4
Phase 3 (Independent ML) ──> Phase 4
```

Rules for identifying dependencies:
- **Data dependency:** Phase B reads files that Phase A writes
- **State dependency:** Phase B requires Phase A's side effects (deploy, DB migration)
- **Resource dependency:** Both phases need Chrome browser (serialize)
- **No dependency:** Phases touch disjoint file sets and resources

### Step 3: File Conflict Analysis

For each pair of candidate parallel phases, check for conflicts:

| Conflict Type | Example | Resolution |
|--------------|---------|------------|
| Same file, same section | Both edit `app/main.py` line 200-300 | Sequential |
| Same file, different sections | A edits routes, B edits CSS block | Parallel OK (merge) |
| Different files | A: `docs/`, B: `scripts/` | Parallel OK |
| Shared resource | Both need Chrome | Serialize Chrome access |

**High-conflict files** (always sequential if both touch):
- `app/main.py` (6000+ lines, merge risk)
- `CLAUDE.md`, `ROADMAP.md`, `CHANGELOG.md` (main agent only)
- `SESSION_LOG.md` (main agent only)
- `data/identities.json`, `data/photo_index.json` (data integrity)

**Low-conflict files** (safe to parallelize):
- `docs/` subdirectories (different files)
- `tests/` (new test files, not editing existing)
- `scripts/` (independent scripts)
- `.claude/` (different rule/skill files)

### Step 4: Worktree Allocation

Constraints (from `.claude/agents/parallel-optimizer.md`):
- Max 3-4 active worktrees (resource limit)
- Chrome plugin: ONE agent at a time
- CLAUDE.md, SESSION_LOG.md, ROADMAP.md, CHANGELOG.md = main agent only
- Merge order: lowest conflict risk first (docs > scripts > app code)

Output allocation:

```markdown
### Sequential (must be in order)
1. Phase 0: Orient — reason: sets session context for all phases

### Parallel Group 1
- Subagent A: [phases] — branch: session-NN-a — files: [list]
- Subagent B: [phases] — branch: session-NN-b — files: [list]
- Subagent C: [phases] — branch: session-NN-c — files: [list]

### Merge Order
1. Subagent C (docs-only) — lowest conflict risk
2. Subagent B (scripts) — medium risk
3. Subagent A (app code) — highest risk, merge last

### Post-Merge Sequential
- Phase N: Full test suite + browser verification
- Phase N+1: Evaluation + assessment
```

### Step 5: Generate Subagent Context Briefs

For each subagent, produce a self-contained context brief:

```markdown
## Subagent [X]: [Name]

You are working in a worktree-isolated branch for Rhodesli.

### Your Tasks
1. [Specific task with acceptance criteria]
2. [Specific task with acceptance criteria]

### Files You May Edit
- [explicit list]

### Files You Must NOT Edit
- app/main.py (owned by Subagent A)
- CLAUDE.md, ROADMAP.md (main agent only)

### Context Files to Read First
- [list of files needed for understanding]

### Completion Criteria
- [ ] [specific checklist item]
- [ ] [specific checklist item]
```

## Output Format

The skill produces a `SESSION_PLAN.md` file with:

1. Dependency graph (ASCII art or table)
2. File conflict matrix
3. Worktree allocation plan
4. Subagent context briefs (one per parallel agent)
5. Merge order with conflict expectations
6. Time estimate: sequential vs parallel

## Example: Session 68 (Actual)

Session 68 successfully parallelized 3 workstreams:

| Subagent | Work | Files | Conflict Risk |
|----------|------|-------|---------------|
| A | UX-103 fix | app/main.py, tests/ | HIGH (app code) |
| B | LoRA audit | docs/analysis/ | LOW (docs only) |
| C | Photo retry | docs/analysis/, scripts/ | LOW (docs + scripts) |

Merge order: B (docs) -> C (docs+scripts, RESULTS.md conflict resolved) -> A (app code, RESULTS.md conflict resolved).

Result: 3 parallel streams completed, 2 RESULTS.md conflicts resolved at merge, all 3064 tests pass.

## Subagent Commit Discipline (Lesson 87)

Every subagent MUST before completing:
1. Run the full test suite (`pytest tests/ -x -q && pytest rhodesli_ml/tests/ -x -q`)
2. Commit ALL files (`git status` must show clean working tree)
3. The orchestrator verifies `git status` in each worktree before merge

Failure to commit all files means manual recovery at merge time (happened sessions 64, 69).

## Context Budget (Lesson 86)

Estimate context consumption per subagent. If total exceeds ~60% of context window:
- Stagger execution (2 parallel, then 1)
- Use /clear between merging subagent results
- Subagent briefs should specify max response size

## Anti-Patterns

- **Do not parallelize** if all phases touch app/main.py
- **Do not parallelize** emergency/hotfix sessions (serial focus)
- **Do not create >4 worktrees** (resource exhaustion)
- **Do not skip the merge phase** — always run full test suite after merge
- **Do not let subagents edit shared docs** (CHANGELOG, ROADMAP) — main agent only
- **Do not let subagents complete with uncommitted files** (Lesson 87)

## Related

- `.claude/agents/parallel-optimizer.md` — Agent that runs this analysis
- `.claude/agents/merge-resolver.md` — Agent for resolving merge conflicts
- HD-001: Prompt decomposition (sequential predecessor to this skill)
- Session 66: First successful parallel execution (3 subagents)
- Session 68: Second successful parallel execution (3 subagents)
