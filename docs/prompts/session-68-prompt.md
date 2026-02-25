# SESSION 68 — Hook Hardening, Regression Tests, ML Progress
# Run with: claude --chrome --dangerously-skip-permissions

## ROLE & FRAMING
You are Lead Architect for Rhodesli, a heritage photo consensus engine (FastHTML + InsightFace + Supabase + Railway + R2). This session hardens the hook infrastructure from Session 67, then makes ML progress in parallel.

## READ FIRST — MANDATORY
```bash
cat CLAUDE.md
cat docs/session_context/session-68-context.md
cat ROADMAP.md
head -80 docs/ALGORITHMIC_DECISIONS.md
echo "68" > .claude/current_session.txt
```

## NON-NEGOTIABLE RULES
1. Commit after EVERY completed task.
2. `pytest tests/ -x -q` before each commit. All pass.
3. /clear between EVERY phase. NEVER /compact. After /clear: re-read CLAUDE.md + context + SESSION_LOG.md.
4. Deploy via `git push origin main`.
5. Update ALGORITHMIC_DECISIONS.md for every decision.
6. Screenshots to `docs/screenshots/session-68/`.
7. Assessment: `docs/assessments/session-68-assessment.md`.
8. After UI changes: screenshot → **delegate to ux-reviewer subagent** → fix HIGH → re-screenshot.

---

## PHASE 0 — ORIENT (~5 min)

### 0A: Archive + Orient
```bash
# Archive previous SESSION_LOG.md
cp SESSION_LOG.md docs/session_logs/session-67-log.md 2>/dev/null
# Update INDEX.md with session 67 entry

echo "68" > .claude/current_session.txt
cat CLAUDE.md
cat docs/session_context/session-68-context.md
cat ROADMAP.md
```

### 0B: Write Session Log
```markdown
# Session 68 Log
## Mission: Hook hardening, regression tests, ML progress (LoRA audit + 144 photo retry)
## Started: [timestamp]
## Rule: /clear between phases, NEVER /compact
```

Commit: `docs: session 68 orient`
git push

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 1 — HARNESS REGRESSION CHECK (~10 min)

Run through EVERY harness feature to confirm nothing is broken. See context file Part 2 for the full checklist.

### 1A: Hook Tests
```bash
# Stop hook: blocks when assessment missing
rm -f docs/assessments/session-68-assessment.md  # ensure it doesn't exist yet
echo '{"stop_hook_active":false}' | CLAUDE_PROJECT_DIR="." bash .claude/hooks/session-stop-gate.sh
# Expected: {"decision": "block", "reason": "Missing: Assessment file..."}

# Stop hook: approves when assessment exists (create a dummy one)
echo "# Dummy" > docs/assessments/session-68-assessment.md
echo '{"stop_hook_active":false}' | CLAUDE_PROJECT_DIR="." bash .claude/hooks/session-stop-gate.sh
# Expected: {"decision": "approve", ...}
rm docs/assessments/session-68-assessment.md  # clean up

# PreCompact manual: verify it warns (but does NOT block — confirmed by research)
echo '{"trigger":"manual"}' | bash .claude/hooks/[find the precompact script]
# Document: exit code, stderr output

# PreCompact auto: recovery injection
echo '{"trigger":"auto"}' | bash .claude/hooks/recovery-instructions.sh
# Should output context re-injection text

# UserPromptSubmit: check parallelization reminder is configured
grep -A5 "UserPromptSubmit" .claude/settings.json
```

### 1B: Subagent Inventory
```bash
ls .claude/agents/
# Expected: ux-reviewer.md, session-evaluator.md, fix-prompt-writer.md, 
#           design-check.md, parallel-optimizer.md, merge-resolver.md, enrichment-worker.md
# Verify each exists and has valid YAML frontmatter
for f in .claude/agents/*.md; do echo "=== $f ===" && head -5 "$f"; done
```

### 1C: Test Suite Health
```bash
pytest tests/ -x -q 2>&1 | tail -5
# Expected: 3588+ tests pass, 0 failures
```

### 1D: Session Infrastructure
```bash
# Session log index exists and is populated
head -20 docs/session_logs/INDEX.md

# run_session.sh exists
ls -la scripts/run_session.sh

# Upload pipeline (quick API check, not full browser test)
# Just verify the health endpoint responds
curl -s https://rhodesli.nolanandrewfox.com/api/health | head -5
```

### 1E: Log Results
```markdown
## Phase 1: Regression Check
| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1 | Stop hook blocks | ? | |
| 2 | Stop hook approves | ? | |
| ... | ... | ... | ... |
```

**If any regression found:** Fix it immediately before proceeding. Document in AD.

Commit: `test: harness regression check — [N]/15 pass`
git push

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 2 — UPGRADE HOOKS (~15 min)

Three specific upgrades based on research findings.

### 2A: Replace Bash Stop Gate with Python Stop Gate

**Why:** The bash grep approach produced a false positive in Session 67 (matched "FAIL" in test description text). Python can do structural parsing.

Create `.claude/hooks/session-stop-gate.py`:
- See context file Part 3 for the full implementation
- Structural markdown parsing (not grep)
- Context-aware FAIL detection (only in phase verdict lines)
- UX review check (only when screenshots exist)
- Proper JSON output
- Make executable: `chmod +x .claude/hooks/session-stop-gate.py`

Update `.claude/settings.json` Stop hook to call the Python script instead of bash.

**Test the new Python gate:**
```bash
# Test 1: No assessment → should block
rm -f docs/assessments/session-68-assessment.md
echo '{"stop_hook_active":false}' | CLAUDE_PROJECT_DIR="." python3 .claude/hooks/session-stop-gate.py
# Expected: block

# Test 2: With assessment → should approve
echo "# Dummy" > docs/assessments/session-68-assessment.md
echo '{"stop_hook_active":false}' | CLAUDE_PROJECT_DIR="." python3 .claude/hooks/session-stop-gate.py
# Expected: approve

# Test 3: Phase FAIL without b-path → should block
# (Create SESSION_LOG with a FAIL phase verdict, verify it catches it)

# Test 4: Screenshots without UX review → should block
mkdir -p docs/screenshots/session-68
touch docs/screenshots/session-68/test.png
echo '{"stop_hook_active":false}' | CLAUDE_PROJECT_DIR="." python3 .claude/hooks/session-stop-gate.py
# Expected: block (screenshots exist but no ux-reviewer mention)

# Clean up test artifacts
rm -f docs/assessments/session-68-assessment.md docs/screenshots/session-68/test.png
```

### 2B: Fix PreCompact — Recovery Instead of Blocking

**Why:** PreCompact exit code 2 does NOT block compaction (confirmed by research). Change strategy to recovery.

1. Update PreCompact manual hook: change from `exit 2` to `exit 0` with loud warning + transcript backup
2. Create `.claude/hooks/post-compact-recovery.sh` — see context file Part 4
3. Register SessionStart compact matcher in settings.json:
```json
"SessionStart": [
  {
    "matcher": "compact",
    "hooks": [
      { "type": "command", "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/post-compact-recovery.sh\"" }
    ]
  }
]
```

**Test:** Cannot fully test from within a session, but verify:
```bash
# Recovery script outputs context
CLAUDE_PROJECT_DIR="." bash .claude/hooks/post-compact-recovery.sh | head -20
# Should output CLAUDE.md contents, session info, etc.
```

### 2C: Update CLAUDE.md Hook Documentation
```markdown
## Hook Enforcement (Deterministic)
- **Stop (command/python):** Blocks session end until: assessment exists, phases logged, b-path written for failures, UX review done if screenshots exist
- **PreCompact (manual):** Warning + transcript backup (CANNOT block — confirmed)
- **PreCompact (auto) / SessionStart (compact):** Re-injects all context from disk after compaction
- **UserPromptSubmit:** Parallelization reminder
- **PreToolUse:** Pytest before git commit
- **PostToolUse:** AD update reminder for ML/core files
NOTE: /compact is banned by convention (CLAUDE.md rule + assessment RED FLAG). It cannot be mechanically blocked.
```

**AD entry:** AD-167: Hook upgrade — Python stop gate replaces bash grep, PreCompact recovery replaces false blocking.

Commit: `fix(harness): Python stop gate, PreCompact recovery, SessionStart compact handler`
git push

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 3 — PARALLEL EXECUTION: THREE INDEPENDENT WORKSTREAMS (~25 min)

After hooks are hardened, three workstreams run in parallel via worktree-isolated subagents. They touch completely different files.

### 3A: Analyze Independence (Quick Check)
```
Workstream A: UX-103 fix — touches app/main.py, app/templates/, docs/screenshots/
Workstream B: 144 photo retry — touches scripts/, results/, Gemini API (no app code)
Workstream C: LoRA training data audit — touches docs/analysis/, ML code (read-only), no app code

Shared files: NONE (AD entries append, each gets different numbers)
Browser: Only A needs Chrome (post-merge for verification)
API: Only B uses Gemini API
```

### 3B: Spawn Three Worktree Subagents

**RULES FOR ALL SUBAGENTS:**
- Write `RESULTS.md` in worktree root
- Do NOT modify: CLAUDE.md, SESSION_LOG.md, ROADMAP.md, CHANGELOG.md
- Run `pytest tests/ -x -q` before final commit (except C which is docs-only)
- Commit to own branch with descriptive messages

**Subagent A — UX-103 P1 Fix** (branch: `session-68-ux103`)
```
UX-103: Full-bleed photo view is a dead end — no CTAs, no metadata overlay, no navigation.

Fix the photo detail/full-bleed view:
1. Add "Back to Photos" navigation
2. Add metadata overlay (photo title, date estimate, source, face count)
3. Add CTAs: "Help Identify" for unknown faces, "Confirm" for proposed matches
4. Add keyboard navigation (left/right arrows for prev/next photo)
5. Ensure face overlay toggle still works
6. Take screenshots of before and after
7. Write tests for new UI elements
8. Write RESULTS.md
```

**Subagent B — 144 Photo Retry** (branch: `session-68-photo-retry`)
```
144 photos from Session 64d failed with "Gemini API call failed."
AUTHORIZED: Nolan has approved the $1.50-4.50 API cost.

1. Find the failed photos list:
   grep -l "failed\|error" results/batch_alignment_*.json
2. Run retry with appropriate backoff:
   python scripts/run_combined_pipeline.py --retry-failed results/batch_alignment_20260223_023456.json
   (If --retry-failed doesn't exist, implement it)
3. Log results: how many succeeded, how many still failed, total cost
4. Update docs/analysis/ with retry results
5. Update AD with retry decision and outcomes
6. Write RESULTS.md
```

**Subagent C — LoRA Training Data Audit** (branch: `session-68-lora-audit`)
```
Prerequisites for LoRA fine-tuning (next ML milestone after date estimation).

Audit the training data:
1. Count confirmed identity pairs (face A confirmed = face B)
2. Count confirmed non-matches (rejected pairs)
3. Assess quality: what percentage have clean crops, frontal faces, good resolution?
4. Check for class imbalance (some people may have many more confirmed photos)
5. Estimate: do we have enough data for meaningful LoRA fine-tuning?
   - Minimum: ~100 confirmed pairs, ~100 negative pairs
   - Ideal: 500+ of each
6. If insufficient: identify which people need more photos and what the community contribution strategy should be
7. Write docs/analysis/lora_training_data_audit.md
8. Update ROADMAP with LoRA readiness status
9. Write RESULTS.md

Reference: Rhodesli ML plan: date estimation (done) → similarity calibration → LoRA
```

Log in SESSION_LOG.md: subagents spawned, branches, what each is doing.

---

## WHILE SUBAGENTS RUN: Main agent waits. When ALL complete → Phase 4.

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 4 — MERGE + BROWSER VERIFY (~10 min)

### 4A: Verify Subagents Complete
```bash
for branch in session-68-lora-audit session-68-photo-retry session-68-ux103; do
  echo "=== $branch ===" 
  git log $branch --oneline -3 2>/dev/null || echo "Branch not found"
  git diff main...$branch --stat 2>/dev/null
done
```

### 4B: Merge in Order (docs first, code last)
```bash
# 1. LoRA audit (C) — docs only, zero conflict risk
git merge session-68-lora-audit --no-edit
pytest tests/ -x -q

# 2. Photo retry (B) — scripts + results
git merge session-68-photo-retry --no-edit
pytest tests/ -x -q

# 3. UX-103 fix (A) — app code, highest conflict potential
git merge session-68-ux103 --no-edit
pytest tests/ -x -q
```

### 4C: Browser Verification (Chrome)
After merge, verify UX-103 fix in Chrome:
1. Navigate to any photo with faces
2. Click to full-bleed view
3. Verify: back navigation, metadata overlay, CTAs, keyboard nav
4. Screenshot before/after
5. **Delegate screenshots to ux-reviewer subagent**

### 4D: Push + Deploy
```bash
git push origin main
# Clean up worktrees
git worktree prune
git branch -d session-68-lora-audit session-68-photo-retry session-68-ux103 2>/dev/null
```

Commit: `merge: UX-103 fix + 144 photo retry + LoRA audit`
git push

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 5 — TEST run_session.sh (~8 min)

### 5A: Create a Minimal Test Prompt
Write a 2-phase test prompt: `scripts/test-session-runner.md`
```markdown
# Test Session — Validates run_session.sh

## PHASE 0 — Phase Zero
Read CLAUDE.md. Write "PHASE_0_COMPLETE" to /tmp/session_runner_test.txt.

## PHASE 1 — Phase One  
Read /tmp/session_runner_test.txt. If it says PHASE_0_COMPLETE, write "PHASE_1_COMPLETE" to the same file.
Print the file contents.
```

### 5B: Run the Test
```bash
chmod +x scripts/run_session.sh
./scripts/run_session.sh scripts/test-session-runner.md
```

### 5C: Verify
```bash
cat /tmp/session_runner_test.txt
# Expected: PHASE_1_COMPLETE
```

### 5D: Document
If it works: note in SESSION_LOG.md and update docs/harness/clear_investigation.md
If it fails: debug, fix the script, re-test

Commit: `test: run_session.sh validated with 2-phase test prompt`
git push

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 6 — DOCS + EVALUATION (MANDATORY) (~10 min)

### 6A: Docs
- CHANGELOG: Session 68 entry (v0.73.1 — hook upgrades, LoRA audit, 144 retry, UX-103)
- ROADMAP: update version, tests, LoRA readiness, next session (69: similarity calibration or LoRA depending on audit)
- BACKLOG: UX-103 resolved, add any new issues from UX review
- ROADMAP < 150 lines

### 6B: Archive Session Log
SESSION_LOG.md → `docs/session_logs/session-68-log.md`
Update `docs/session_logs/INDEX.md`
Update B-Path Analysis table

### 6C: Write Assessment
`docs/assessments/session-68-assessment.md`

**The Python Stop hook SHOULD block you from stopping until this exists.**

For EVERY phase: PASS/FAIL/PARTIAL with evidence:
- Phase 1: Regression check — how many of 15 features verified?
- Phase 2: Hook upgrades — Python gate working? PreCompact recovery registered?
- Phase 3: Parallel execution — all 3 subagents ran? What did each produce?
- Phase 4: Merge + verify — merge clean? UX-103 verified in Chrome? ux-reviewer invoked?
- Phase 5: run_session.sh — did it work?

### 6D: If Failures → B-Path
The Stop hook SHOULD also block until b-path prompt exists for failures.
If blocked: write `docs/prompts/session-68b-prompt.md`, then fix the failed items.

### 6E: Print
```bash
cat docs/assessments/session-68-assessment.md
```

Commit: `docs: session 68 assessment + archive`
git push

---

## EXECUTION TIMELINE

```
Phase 0: Orient (5 min)
Phase 1: Regression check (10 min)
Phase 2: Hook upgrades — PRIMARY DELIVERABLE (15 min)
Phase 3: Parallel — UX-103 | 144 retry | LoRA audit (25 min wall, parallel)
Phase 4: Merge + Chrome verify (10 min)
Phase 5: run_session.sh test (8 min)
Phase 6: Evaluation — Stop hook enforces this (10 min)
Total: ~83 min
```

## PARALLELIZATION SUMMARY
After Phases 0-2 (sequential, harness must be solid first):
- **Subagent A (session-68-ux103):** UX-103 P1 fix — app/main.py, templates
- **Subagent B (session-68-photo-retry):** 144 photos — scripts/, Gemini API
- **Subagent C (session-68-lora-audit):** LoRA audit — docs/analysis/ only

Merge order: C (docs) → B (scripts) → A (app code). Tests after each.

## BEGIN
Start with Phase 0. Read mandatory files. Set current_session.txt to "68". Execute.
