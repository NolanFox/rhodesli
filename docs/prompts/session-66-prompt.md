# SESSION 66 — Harness Overhaul, Enrichment Validation, GEDCOM Admin, UX Review, Portfolio
# Overnight autonomous prompt — run with: claude --chrome --dangerously-skip-permissions

## ROLE & FRAMING
You are Lead Architect for Rhodesli, a heritage photo consensus engine (FastHTML + InsightFace + Supabase + Railway + R2).

First forward-progress session after four sessions (65a-d) of infrastructure fixes. Upload works. GEDCOM versioning schema exists. Enrichment pipeline fixed in code. Now: fix the harness, validate enrichment, build GEDCOM admin UI, set up automated UX review, write the portfolio piece — with PARALLEL EXECUTION for independent workstreams.

## READ FIRST — MANDATORY
```bash
cat CLAUDE.md
cat docs/session_context/session-66-context.md
cat ROADMAP.md
head -80 docs/ALGORITHMIC_DECISIONS.md
```

## NON-NEGOTIABLE RULES
1. Commit after EVERY completed task.
2. `pytest tests/ -x -q` before each commit. All must pass.
3. Use `head`, `grep`, `tail` — never cat entire large files.
4. **Use /clear between EVERY phase. NEVER /compact.** After /clear: re-read CLAUDE.md + context + SESSION_LOG.md.
5. Deploy via `git push origin main`.
6. Update ALGORITHMIC_DECISIONS.md with full provenance.
7. Context file: `docs/session_context/session-66-context.md`
8. Log all work to SESSION_LOG.md.
9. Screenshots to `docs/screenshots/session-66/`.
10. Assessment: `docs/assessments/session-66-assessment.md` — MANDATORY.
11. If /compact used: RED FLAG in assessment.
12. After every UI change: screenshot → ux-reviewer subagent → fix HIGH issues → re-screenshot.

## BROWSER TESTING — CHROME PLUGIN
Launched with `--chrome`. Nolan logged in as admin.
**Real test photos:** `~/Downloads/rhodesli_photo_testing/` (keep in library — real heritage photos).
**Updated GEDCOM:** `~/Downloads/gedcom_20260224/` (for testing GEDCOM admin UI).
**Synthetic test images only:** Delete after verification. Name `_test_66_delete_me_[N].jpg`.

## CHECKPOINT & RESUME
Between phases: commit + push. On resume: read CLAUDE.md + context + SESSION_LOG.md.

---

## PHASE 0 — ORIENT + SESSION LOG FIX (~8 min)

### 0A: Orient
```bash
echo "66" > .claude/current_session.txt
cat CLAUDE.md
cat docs/session_context/session-66-context.md
cat ROADMAP.md
```

### 0B: Fix SESSION_LOG.md Archival System

**Problem:** Three issues — (1) `docs/SESSION_LOG.md` is a stale duplicate, (2) each session overwrites root `SESSION_LOG.md`, (3) `docs/session_logs/` has files from sessions 47B-61 but with gaps (53, 56-59, 62-65 missing) and inconsistent naming.

**CAUTION: Do not break the harness.** Before changing anything:
```bash
grep -rn "SESSION_LOG" .claude/ scripts/ CLAUDE.md --include="*.sh" --include="*.md" | head -20
```
Update any references that would break.

1. **Clean up `docs/session_logs/`:** Standardize all filenames to lowercase `session-NNx-log.md`. DO NOT delete files.
2. **Remove duplicate:** Merge unique content from `docs/SESSION_LOG.md` into proper per-session files, then delete it.
3. **Fill gaps from git history:**
   ```bash
   git log --oneline -30 -- SESSION_LOG.md
   # Recover missing sessions (53, 56-59, 62-65) from commits
   ```
4. **Archive current SESSION_LOG.md** if it has previous session content.
5. **Create `docs/session_logs/INDEX.md`:**
   ```markdown
   # Session Log Index
   | Session | Date | Log | Assessment | Prompt | Context | Key Commits | Status |
   |---------|------|-----|------------|--------|---------|-------------|--------|

   ## B-Path Analysis
   | Session | Had B-Path? | Trigger Category | Specific Trigger |

   ## Session Analytics
   - Total sessions logged: N
   - Sessions with gaps: [list]
   - Categories: ML / UX / Harness / Docs / Bug Fix
   ```
6. **Update CLAUDE.md** with session log rules.
7. **Write new SESSION_LOG.md** for Session 66.

Commit: `fix(harness): session log archival, recovered logs, session index`
git push

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 1 — SUBAGENTS + INFRASTRUCTURE (~10 min)

### 1A: Create All Subagents

Create SEVEN subagents in `.claude/agents/`:

**ux-reviewer.md** — Senior UX designer reviewing screenshots. Evaluates layout, typography, spacing, contrast, CTAs, navigation, face overlays, GEDCOM data. Output: PASS/NEEDS WORK/FAIL per page with severity-ranked issues.

**session-evaluator.md** — Post-session evaluator replicating Nolan's review. Reads prompt+context+log+git. PASS/FAIL per phase with evidence. Concerns with SPECIFIC next steps. Categorizes: b-session vs future-session. Prints summary.

**fix-prompt-writer.md** — Writes b-session prompts for ONLY b-session concerns. Uses prompt-writing best practices. Saves to `docs/prompts/session-NNb-prompt.md`.

**design-check.md** — Pre-implementation PRD/SDD check. Features >30 min need PRD. Features <30 min need AD entry. Advisory, logged.

**parallel-optimizer.md** — Reviews prompts for parallelization opportunities. Analyzes file dependencies, shared resources, worktree allocation, merge order.

**merge-resolver.md** — Merges parallel worktree branches to main. Order: docs-only first, then code. Runs tests after each merge. Conflict rules: AD entries append, test files keep both.

**enrichment-worker.md** (with `isolation: worktree`):
```markdown
---
name: enrichment-worker
description: Runs enrichment pipeline validation in isolated worktree
tools: Read, Write, Edit, Bash, Grep, Glob
model: sonnet
isolation: worktree
---
```

See context file Parts 2, 7, 8, 9 for full specs.

### 1B: Run GEDCOM Migration on Production Supabase
```bash
cat scripts/supabase_migration_002_gedcom_versioning.sql
# Execute against production
```
Verify tables: `gedcom_versions`, `gedcom_change_log`, `gedcom_enrichment_queue`.

### 1C: Verify Stop Hook
```bash
cat .claude/settings.json | grep -A10 -i "stop\|hook"
cat .claude/hooks/post-session-eval.sh
```

### 1D: Add `.claude/worktrees/` to `.gitignore`

Commit: `feat(harness): 7 subagents, GEDCOM migration, stop hook, worktree support`
git push

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 2 — PARALLEL EXECUTION: SPAWN WORKTREE SUBAGENTS (~2 min spawn + ~20 min parallel)

Three independent workstreams run simultaneously via worktree-isolated subagents. They touch different files with zero overlap.

### 2A: Spawn Three Background Subagents

**RULES FOR SUBAGENTS:**
- Write `RESULTS.md` in worktree root with: what was done, files changed, tests added, issues
- Do NOT modify: CLAUDE.md, SESSION_LOG.md, ROADMAP.md, CHANGELOG.md
- Run `pytest tests/ -x -q` before final commit
- Commit to own branch with descriptive messages

**Subagent A — Enrichment Validation** (branch: `session-66-enrichment`)
```
1. Add --dry-run mode to enrichment if missing
2. Dry-run 10 photos (mix GEDCOM-linked + unlinked), log token counts
3. 5 real Gemini API calls (3 enriched, 2 bare)
4. Verify gemini_config + response_summary populated
5. Write docs/analysis/enrichment_validation_66.md
6. Update AD-159 with validation results
7. Write RESULTS.md
```

**Subagent B — GEDCOM Admin UI** (branch: `session-66-gedcom-ui`)
```
1. Write AD entry for GEDCOM admin UI design
2. Build /admin/gedcom: info panel, upload+parse+diff, apply/cancel, version history, re-enrichment queue
3. Write tests (auth, parse, diff, apply, cancel, history)
4. Test with GEDCOM from ~/Downloads/gedcom_20260224/ via Playwright (Chrome reserved for main agent)
5. Write RESULTS.md
```

**Subagent C — Portfolio Writeup** (branch: `session-66-portfolio`)
```
1. Write docs/portfolio/ml_pipeline_writeup.md (<300 lines)
   Executive summary, Mermaid architecture, decisions table, results, challenges, next steps
2. Write RESULTS.md
```

Log in SESSION_LOG.md: subagents spawned, branches, timestamps.

---

## WHILE SUBAGENTS RUN: Main agent monitors. When ALL complete → Phase 3.

---

## PHASE 3 — MERGE PARALLEL WORK (~5 min)

### 3A: Verify Subagents Complete
```bash
for branch in session-66-portfolio session-66-enrichment session-66-gedcom-ui; do
  echo "=== $branch ===" && git log $branch --oneline -3 && git diff main...$branch --stat
done
```

### 3B: Merge in Order (docs first, code last)

1. **Portfolio (C) first** — docs only, zero conflict risk:
   ```bash
   git merge session-66-portfolio --no-edit
   pytest tests/ -x -q
   ```

2. **Enrichment (A) second** — scripts + docs:
   ```bash
   git merge session-66-enrichment --no-edit
   pytest tests/ -x -q
   ```

3. **GEDCOM UI (B) last** — app code:
   ```bash
   git merge session-66-gedcom-ui --no-edit
   pytest tests/ -x -q
   ```

### 3C: Resolve Conflicts
- AD entries: append all, re-number if needed
- Test files: keep both (different filenames)
- Other: resolve conservatively, full test suite

### 3D: Push
```bash
git push origin main
```

### 3E: Clean Up Worktrees
```bash
git worktree prune
git branch -d session-66-portfolio session-66-enrichment session-66-gedcom-ui 2>/dev/null
```

Log merge results + any conflicts in SESSION_LOG.md.

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 4 — BROWSER VERIFICATION WITH CHROME (~12 min)

Chrome plugin required. Main agent only.

### 4A: Upload Real Photos
`~/Downloads/rhodesli_photo_testing/`:
1. Navigate to `/upload` — screenshot
2. Upload real photo with faces — screenshot during + after
3. **Verify:** "N faces extracted, N added to Inbox" where N > 0
4. Navigate to photo, verify face bounding boxes — screenshot

### 4B: Compare with Known Match
`/compare/pair` with real photos. Screenshot similarity score.

### 4C: GEDCOM Admin UI in Chrome
`/admin/gedcom`:
1. Screenshot page (should show current info from Subagent B's work)
2. Upload GEDCOM from `~/Downloads/gedcom_20260224/`
3. Screenshot diff summary + version history after apply

### 4D: UX Review New Pages
**Delegate screenshots to ux-reviewer.** Fix HIGH issues.

Commit: `test: browser verification — upload, compare, GEDCOM admin`
git push

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 5 — FULL UX REVIEW SWEEP (~10 min)

### 5A: Screenshot Every Major Page
`/`, `/upload`, `/photos`, `/people`, `/compare/pair`, `/estimate`, `/map`, `/admin/gedcom`, a photo page, a person page.

### 5B: Delegate to ux-reviewer
**All screenshots → ux-reviewer subagent.**

### 5C: Fix HIGH Issues
MEDIUM/LOW → BACKLOG.

Commit: `fix(ux): [N] issues from UX review sweep`
git push

---

## ⚠️ /clear — re-read CLAUDE.md + context + SESSION_LOG.md

---

## PHASE 6 — DOCS SYNC + AUTO-EVALUATION (MANDATORY) (~12 min)

### 6A: Docs
- CHANGELOG: Session 66 entry
- ROADMAP: version, tests, next sessions. < 150 lines.
- BACKLOG: completed removed, UX issues added

### 6B: Archive Session Log + Meta-Analysis
Copy SESSION_LOG.md → `docs/session_logs/session-66-log.md`
Update `docs/session_logs/INDEX.md`: session 66 row, analytics, b-path table.

### 6C: Self-Evaluation

**Invoke session-evaluator subagent** (or manual if unavailable).

Per phase: PASS/FAIL/PARTIAL with evidence. Include:
- /clear at every phase boundary? (list each)
- Screenshots for all UI work?
- All subagents invoked as specified?
- Parallel execution: did worktrees work? Merge clean?
- Stop hook fire?
- Test count: any drops?

### 6D: If Failures → B-Path

If any FAIL/PARTIAL:
1. Evaluator categorizes: b-session vs future-session
2. For b-session: **invoke fix-prompt-writer** → `docs/prompts/session-66b-prompt.md`
3. Run 66b prompt
4. Final assessment:
   - "**First pass:** [results]"
   - "**Second pass (fix-up):** [results]"
   - "**B-path trigger:** [cause]"
5. Update INDEX.md B-Path Analysis

### 6E: Print
```bash
echo "=============================================="
echo "SESSION 66 SELF-EVALUATION"
echo "=============================================="
cat docs/assessments/session-66-assessment.md
echo "=============================================="
bash scripts/session_assessment.sh 66
echo "=============================================="
```

Commit: `docs: session 66 assessment, log archive, index`
git push

---

## EXECUTION TIMELINE (estimated)

```
Sequential    : Phase 0 (8m) → Phase 1 (10m)
Parallel      : Subagent A (12m) | Subagent B (18m) | Subagent C (10m)  ← ~20 min total
Sequential    : Phase 3 merge (5m) → Phase 4 Chrome (12m) → Phase 5 UX (10m) → Phase 6 eval (12m)
Total         : ~77 min (vs ~90 min fully sequential)
```

## CRITICAL REMINDERS
- **--chrome.** Nolan logged in as admin. Chrome = main agent only during parallel.
- **Real test photos:** `~/Downloads/rhodesli_photo_testing/`
- **Updated GEDCOM:** `~/Downloads/gedcom_20260224/`
- **/clear between EVERY phase.** Log each boundary.
- **Parallel subagents:** Do NOT modify CLAUDE.md, SESSION_LOG.md, ROADMAP.md, CHANGELOG.md.
- **Merge order:** docs (C) → scripts (A) → app code (B). Tests after each merge.
- **Assessment mandatory.** Failures → fix-prompt-writer → b-session.
- **Archive SESSION_LOG.md** + update INDEX.md at end.

## BEGIN
Start with Phase 0. Read mandatory files. Set current_session.txt to "66". Execute.
