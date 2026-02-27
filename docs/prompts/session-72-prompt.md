# SESSION 72: HARNESS FIX + ML SIMILARITY CALIBRATION (OVERNIGHT)

Read CLAUDE.md first. Read ROADMAP.md. Read ALGORITHMIC_DECISIONS.md.
Then read `docs/session_context/session-72-context.md` for full planning context.

## CRITICAL: ANOTHER SESSION MAY BE RUNNING ON MAIN

Another Claude Code process may be merging branches to main right now.
YOU MUST WORK ON A WORKTREE BRANCH. Do NOT touch main until Phase Final.

```bash
echo "72" > .claude/current_session.txt
git checkout main
git worktree add .claude/worktrees/session-72 -b session-72/harness-ml
cd .claude/worktrees/session-72
```

ALL work in Phases 1 and 2 happens in `.claude/worktrees/session-72`.
You do NOT touch main until Phase Final.

## EXECUTION MODEL
- Single-threaded. No subagents.
- ALL work on branch `session-72/harness-ml` in the worktree.
- Use `/clear` between phases.
- Phase 1 hard cap: 30 minutes. If over time, commit what you have, move on.
- Phase Final merges to main, pushes, deploys.

---

## PHASE 1: PERMANENT HARNESS FIXES (30 min hard cap)

Working directory: `.claude/worktrees/session-72`

### 1A: Test Tiering (15 min)

```bash
pip install pytest-xdist --break-system-packages
```

Create or update `pytest.ini`:
```ini
[pytest]
markers =
    slow: marks tests as slow (integration, e2e, browser)
addopts = --strict-markers
```

Add auto-marking to `conftest.py` (or create `tests/conftest_markers.py`):
```python
import pytest

def pytest_collection_modifyitems(config, items):
    """Auto-mark slow tests by location."""
    for item in items:
        path = str(item.fspath)
        if any(x in path for x in ["/e2e/", "/integration/", "playwright", "browser",
                                      "test_gedcom", "test_upload", "test_photo_process",
                                      "test_deploy"]):
            item.add_marker(pytest.mark.slow)
```

Create `Makefile`:
```makefile
.PHONY: test test-fast test-full

test-fast:
	pytest tests/ -x -q -n auto -m "not slow" --timeout=10

test-full:
	pytest tests/ -x -q -n auto

test: test-fast
```

Verify:
```bash
time make test-fast   # MUST be <30 seconds
make test-full        # All tests still pass
```

If `make test-fast` >30s, add more modules to slow list.
If `make test-fast` has <500 tests, remove modules from slow list.

Commit: `feat(harness): test tiering — make test-fast <30s, pytest-xdist parallel`

### 1B: Claude Code Hooks (10 min)

```bash
cat .claude/settings.json 2>/dev/null | python -m json.tool || echo "no settings"
```

Update `.claude/settings.json` — MERGE with existing content:

PreToolUse — blocks commits to main during parallel sessions:
```json
{
  "matcher": "Bash",
  "hooks": [{
    "type": "command",
    "command": "bash -c 'INPUT=$(cat); CMD=$(echo \"$INPUT\" | jq -r \".input.command // empty\"); if echo \"$CMD\" | grep -q \"git commit\"; then if [ -f .claude/parallel_session_active ]; then BRANCH=$(git branch --show-current); if [ \"$BRANCH\" = \"main\" ]; then echo \"BLOCKED: Cannot commit to main during parallel session.\"; exit 2; fi; fi; fi; exit 0'"
  }]
}
```

PostToolUse — test reminder after commits:
```json
{
  "matcher": "Bash",
  "hooks": [{
    "type": "command",
    "command": "bash -c 'INPUT=$(cat); CMD=$(echo \"$INPUT\" | jq -r \".input.command // empty\"); if echo \"$CMD\" | grep -qE \"git commit|git merge\"; then echo \"REMINDER: Run make test-fast before proceeding.\"; fi; exit 0'"
  }]
}
```

Stop hook — blocks stop without assessment + clean git:
```json
{
  "hooks": [{
    "type": "command",
    "command": "bash -c 'S=$(cat .claude/current_session.txt 2>/dev/null || echo unknown); [ ! -f \"docs/assessments/session-${S}-assessment.md\" ] && echo \"Missing assessment file\" && exit 1; [ -n \"$(git status --porcelain)\" ] && echo \"Uncommitted files\" && git status --porcelain && exit 1; exit 0'"
  }]
}
```

Commit: `feat(harness): Claude Code hooks — branch enforcement + test reminders + stop gate`

### 1C: Merge Script (5 min)

Create `scripts/merge.sh`:
```bash
#!/bin/bash
set -e
[ $# -eq 0 ] && echo "Usage: ./scripts/merge.sh branch1 [branch2...]" && exit 1
git checkout main && git pull origin main 2>/dev/null || true
for BRANCH in "$@"; do
  echo "=== Merging: $BRANCH ==="
  WT=$(git worktree list | grep "$BRANCH" | awk '{print $1}')
  [ -n "$WT" ] && [ "$WT" != "$(pwd)" ] && [ -n "$(git -C "$WT" status --porcelain)" ] && \
    git -C "$WT" add -A && git -C "$WT" commit -m "fix: auto-commit (merge script)"
  git merge "$BRANCH" --no-ff -m "merge: $BRANCH" || { echo "CONFLICT in $BRANCH — fix manually"; exit 1; }
  echo "✓ $BRANCH"
done
echo "=== Running tests ===" && make test-full
echo "=== Done. Next: git push origin main ==="
```
```bash
chmod +x scripts/merge.sh
```

Commit: `feat(harness): scripts/merge.sh — single command merge ceremony`

### 1D: Update CLAUDE.md

Add (replace existing test instructions if any):
```
## Testing
- Per-commit: `make test-fast` (<30s, unit tests, parallel)
- Pre-deploy: `make test-full` (all tests, parallel)
- Merge branches: `./scripts/merge.sh branch1 [branch2...]`
- Parallel sessions: create `.claude/parallel_session_active` to block main commits
```

Keep under 80 lines. Compress other sections if needed.

Commit: `docs: CLAUDE.md — new test and merge commands`

### Phase 1 gate:
```bash
time make test-fast  # <30s?
make test-full       # pass?
```

**STOP. If over 30 minutes, commit and move on.**

/clear

---

## PHASE 2: ML SIMILARITY CALIBRATION (60 min)

Working directory: `.claude/worktrees/session-72`

Re-read ALGORITHMIC_DECISIONS.md. Explore `rhodesli_ml/` directory structure.
Re-read `docs/session_context/session-72-context.md` Section 2.

### 2A: Extract Training Data (15 min)

```bash
grep -rn "merge\|not.same\|confirmed\|rejected\|CONFIRMED\|DISMISSED" app/ --include="*.py" | head -30
ls data/ rhodesli_ml/data/ 2>/dev/null
```

Create `rhodesli_ml/scripts/extract_pairs.py`:
- Load confirmed identities + face embeddings
- Positive pairs: faces merged into same identity
- Negative pairs: "Not Same" marks + random cross-identity pairs
- Per pair: cosine distance, same_collection, quality_ratio
- Save: `rhodesli_ml/data/training_pairs.json`
- Print stats: count, distance distributions

If <50 pairs exist, augment with cross-identity hard negatives at distance <1.5.

```bash
python rhodesli_ml/scripts/extract_pairs.py
```

Commit: `feat(ml): extract confirmed/rejected pairs for similarity calibration`

### 2B: Build + Train Calibrator (20 min)

Create `rhodesli_ml/models/similarity_calibrator.py`:
- Small MLP: [distance, same_collection, quality_ratio, age_gap] → match probability
- 2 hidden layers (32 units), ReLU, Dropout 0.2, Sigmoid output

Create `rhodesli_ml/scripts/train_calibrator.py`:
- BCE loss, hard negative upweighting (2x for distance < 1.2)
- 80/20 stratified split, early stopping patience=10
- Save best model: `rhodesli_ml/models/calibrator_v1.pt`
- Print: accuracy, AUC-ROC, precision@90recall

```bash
python rhodesli_ml/scripts/train_calibrator.py
```

AD entry: AD-XXX "Similarity calibration — MLP on frozen embeddings"
- Chosen: MLP calibrator with metadata on frozen InsightFace embeddings
- Rejected: LoRA backbone fine-tuning (deferred per roadmap)
- Rejected: Threshold tuning alone (ignores metadata signals)

Commit: `feat(ml): similarity calibrator model + training script`

### 2C: Regression Gate (15 min)

Create `rhodesli_ml/scripts/evaluate_calibrator.py`:
- Compare calibrator vs baseline (distance thresholds: <0.95=0.9, <1.10=0.6, <1.20=0.3)
- Metrics: AUC-ROC, precision@90recall, calibration error
- Gate: must beat baseline on ALL three
- Print: comparison table + ship/no-ship

```bash
python rhodesli_ml/scripts/evaluate_calibrator.py
```

Commit: `feat(ml): regression gate — calibrator vs baseline comparison`

### 2D: Shadow Scoring (10 min)

Create `rhodesli_ml/scripts/shadow_score.py`:
- Score all pending suggestions with calibrator AND current thresholds
- Save: `rhodesli_ml/data/shadow_scores.json`
- Print disagreements

```bash
python rhodesli_ml/scripts/shadow_score.py
```

Commit: `feat(ml): shadow scoring — calibrator alongside existing system`

### Phase 2 gate:
```bash
ls rhodesli_ml/data/training_pairs.json
ls rhodesli_ml/models/calibrator_v1.pt
ls rhodesli_ml/data/shadow_scores.json
make test-fast
```

/clear

---

## PHASE FINAL: MERGE TO MAIN + DEPLOY (15 min)

This phase merges your worktree branch into main. Main should be clean by now 
(the other session should have finished hours ago). If not, wait and retry.

### Step 1: Verify main is clean
```bash
cd /path/to/rhodesli   # go back to main worktree (project root)

# Check if other Claude Code is still running
ps aux | grep -i claude | grep -v grep | grep -v $$ | head -5

# Check main state
git checkout main
git status --porcelain  # must be empty
git log --oneline -3    # see what the merge session committed
```

If main has uncommitted changes or unresolved merges from the other session:
```bash
# Resolve whatever's there
git status
# If merge conflicts: open files, fix them, git add, git commit
# If uncommitted files: git add -A && git commit -m "fix: resolve leftover merge state"
```

### Step 2: Merge session-72 branch
```bash
git merge session-72/harness-ml --no-ff -m "merge: session-72 harness fixes + ML calibration"
```

If conflicts (likely in ALGORITHMIC_DECISIONS.md or CLAUDE.md):
- ALGORITHMIC_DECISIONS.md: keep ALL entries, renumber any duplicates
- CLAUDE.md: keep session-72's test commands section, keep everything else from main

```bash
# After resolving any conflicts:
make test-full
```

### Step 3: Update docs
- ROADMAP.md: mark similarity calibration in-progress or complete
- CHANGELOG.md: v0.77.0
- SESSION_INDEX.md: one-line Session 72 summary
- `echo "73" > .claude/current_session.txt`

Create `docs/assessments/session-72-assessment.md`:
- Phase 1 delivered: test tiering (make test-fast time), hooks, merge script
- Phase 2 delivered: pair count, model metrics, gate result, shadow score disagreements
- Deferred items if any
- Test counts

### Step 4: Push + deploy
```bash
git add -A && git commit -m "docs: session 72 assessment + changelog"
git push origin main
```

### Step 5: Clean up worktree
```bash
git worktree remove .claude/worktrees/session-72
git branch -d session-72/harness-ml
```

Railway deploys on push. Session complete.
