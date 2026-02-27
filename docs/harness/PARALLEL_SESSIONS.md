# Parallel Sessions Best Practices

How to run multiple Claude Code sessions in parallel using git worktrees.
Covers setup, file ownership, merge ceremony, and recovery.

See also: `.claude/skills/prompt-parallelizer/SKILL.md` (analysis skill),
`.claude/agents/merge-resolver.md` (merge agent), HD-021 (commit enforcement).

---

## 1. Setting Up Multiple Terminal Sessions

### Create worktrees

From the main repo, create one worktree per parallel track:

```bash
# From repo root
git worktree add .claude/worktrees/session-71-a -b session-71-a
git worktree add .claude/worktrees/session-71-b -b session-71-b
git worktree add .claude/worktrees/session-71-c -b session-71-c
```

### Set up each worktree

Each worktree needs its own venv and env file:

```bash
cd .claude/worktrees/session-71-a
./scripts/setup-worktree.sh
```

Or manually:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp ../../.env .env  # Copy from main worktree
```

### Launch Claude Code in each

Open a separate terminal for each worktree:

```bash
# Terminal 1 (Track A)
cd .claude/worktrees/session-71-a
claude

# Terminal 2 (Track B)
cd .claude/worktrees/session-71-b
claude

# Terminal 3 (Track C)
cd .claude/worktrees/session-71-c
claude
```

Each session gets its own context brief (see parallelizer skill output).

---

## 2. File Ownership Mapping

The single most important rule for parallel sessions: **no two tracks
may edit the same file**. Assign explicit file ownership before starting.

### High-Conflict Files (NEVER parallelize)

These files cause merge failures when edited concurrently:

| File | Rule | Owner |
|------|------|-------|
| `app/main.py` | Sequential only | ONE track at a time |
| `CLAUDE.md` | Main agent only | Orchestrator |
| `ROADMAP.md` | Main agent only | Orchestrator |
| `CHANGELOG.md` | Main agent only | Orchestrator |
| `SESSION_LOG.md` | Main agent only | Orchestrator |
| `data/identities.json` | Data integrity | ONE track at a time |
| `data/photo_index.json` | Data integrity | ONE track at a time |
| `data/embeddings.npy` | Data integrity | ONE track at a time |

### Low-Conflict Files (safe to parallelize)

| Category | Why safe | Example |
|----------|----------|---------|
| `docs/` subdirectories | Different files per track | Track A: `docs/prds/`, Track C: `docs/harness/` |
| New test files | Additive, no overlap | Track A: `tests/test_ux_fixes.py`, Track B: `tests/test_gedcom.py` |
| `scripts/` | Independent scripts | Track C: `scripts/new-helper.sh` |
| `.claude/rules/` | Different rule files | Track C: `.claude/rules/new-rule.md` |
| `rhodesli_ml/` subpackages | Independent modules | Track D: `rhodesli_ml/training/` |

### Ownership Map Template

Create this BEFORE launching subagents:

```markdown
## File Ownership — Session NN

| Track | May Edit | Must NOT Edit |
|-------|----------|---------------|
| A | app/main.py, tests/test_ux*.py | docs/, scripts/ |
| B | (waits for A to finish app/main.py) | docs/, scripts/ |
| C | docs/, scripts/, .claude/ | app/, core/, tests/ |
```

---

## 3. Merge Ceremony

After all subagents complete, merge back to main in a specific order.

### Pre-Merge: Use the Canonical Merge Script

```bash
# From main branch — merge branches in order (docs first, then code)
./scripts/merge.sh session-71-c session-71-a session-71-b
```

The script automatically:
1. Merges each branch with `--no-ff`
2. Runs tests after each merge
3. Reports failures and stops on error

### Merge Order: Lowest Risk First

1. **Docs-only tracks** (zero conflict risk)
2. **Scripts/infrastructure tracks** (low conflict risk)
3. **App code tracks** (highest conflict risk, merge last)

This order means if a docs merge succeeds, you can focus entirely
on resolving any app code conflicts without worrying about doc state.

### Between Each Merge

```bash
# After each merge, verify
source venv/bin/activate && pytest tests/ -x -q
```

If tests fail after a merge, revert and investigate:

```bash
git reset --hard HEAD~1
# Then manually inspect the diff
git diff main..session-71-a -- app/main.py
```

### Conflict Resolution Priorities

| File | Resolution Rule |
|------|----------------|
| `ALGORITHMIC_DECISIONS.md` | Append all entries, renumber if needed |
| `tests/*.py` | Keep both (different filenames expected) |
| `conftest.py` | Merge carefully, keep all fixtures |
| `app/main.py` | Use main branch for shared sections |
| `RESULTS.md` | Concatenate (happened sessions 68, 70) |

---

## 4. When NOT to Parallelize

### Hard Rules (never parallelize)

- **Emergency/hotfix sessions**: Serial focus, no coordination overhead
- **All tracks touch app/main.py**: Merge risk exceeds parallelization savings
- **Single-phase sessions**: No parallelization opportunity
- **Context budget exceeded**: >3 subagent results flood orchestrator (Lesson 86)

### Soft Rules (parallelize with caution)

- **Shared test fixtures**: If two tracks both modify `conftest.py`, serialize
- **Chrome browser needed**: Only one agent can use the Chrome plugin at a time
- **Production database**: If two tracks both write to Supabase, serialize
- **< 3 phases**: Overhead of worktree setup may exceed time savings

### Decision Criteria

Parallelize when:
- 4+ phases with at least 2 touching disjoint file sets
- Not an emergency session
- Expected time savings > 30 minutes
- Max 3-4 worktrees (resource limit)

---

## 5. Recovery Strategies

### Subagent left uncommitted files

The `scripts/merge.sh` script is the canonical merge tool (HD-021).
If merging manually:

```bash
cd .claude/worktrees/session-71-a
git status --porcelain
# If files exist:
git add -A
git commit -m "fix: auto-commit uncommitted subagent files"
```

### Merge conflict that can't be auto-resolved

```bash
# Option 1: Manual resolution
git merge session-71-a  # Conflict
# Edit files to resolve
git add -A && git commit

# Option 2: Accept one side entirely
git merge --abort
git merge -X theirs session-71-a  # Accept subagent's version
# OR
git merge -X ours session-71-a    # Accept main's version
```

### Subagent broke tests

```bash
# Revert the merge
git reset --hard HEAD~1

# Go into the worktree and fix
cd .claude/worktrees/session-71-a
source venv/bin/activate
pytest tests/ -x -q  # See what's broken
# Fix, commit, then re-merge from main
```

### Worktree cleanup

After successful merge:

```bash
git worktree remove .claude/worktrees/session-71-a
git worktree remove .claude/worktrees/session-71-b
git worktree remove .claude/worktrees/session-71-c
git branch -d session-71-a session-71-b session-71-c
```

### Context overflow during merge

If the orchestrator's context is filling up from subagent results:

1. Merge one branch at a time
2. Use `/clear` between merges
3. Re-read CLAUDE.md and session log after clearing
4. Subagent briefs should specify max response size (Lesson 86)

---

## History

| Session | Tracks | Result | Lessons |
|---------|--------|--------|---------|
| 66 | 3 subagents | Success | First parallel execution |
| 68 | 3 subagents | Success, 2 RESULTS.md conflicts | Merge order matters |
| 69 | 3 subagents | Partial — uncommitted test file | Lesson 87 (commit discipline) |
| 70 | 3 subagents | Success | Context budget estimation needed |
| 71 | 3 tracks (A+B sequential, C parallel) | In progress | Lesson 88 (monolithic file) |
