# SESSION 73: CLEANUP + SHARE-READINESS

Read CLAUDE.md first. Read ROADMAP.md. Read ALGORITHMIC_DECISIONS.md.

## EXECUTION MODEL
- Single-threaded on main. No worktrees. No subagents.
- Use `make test-fast` for per-commit testing.
- Use `make test-full` before final push.
- This is a cleanup + polish session. No new features. No ML work. No harness redesign.
- Target: under 45 minutes total.

---

## PHASE 1: FILE NAMING + DUPLICATE CLEANUP (15 min)

### 1A: Fix Session Log Naming Convention

The project convention for session logs is: `session-NN-log.md` (lowercase, hyphens, "-log" suffix).
Recent sessions broke this. Fix:

```bash
cd docs/session_logs
# Rename incorrectly named files
git mv SESSION_071D.md session-71d-log.md 2>/dev/null || mv SESSION_071D.md session-71d-log.md
git mv SESSION_072.md session-72-log.md 2>/dev/null || mv SESSION_072.md session-72-log.md

# Check for any other convention violations
ls *.md | grep -v "^session-" | grep -v "^discoveries_audit" | grep -v "^INDEX"
# Fix any others found using the same pattern
```

Update `docs/session_logs/INDEX.md` — ensure all entries reference the correct filenames.

Search the entire repo for references to the old filenames and update them:
```bash
grep -rn "SESSION_071D\|SESSION_072" --include="*.md" --include="*.py" --include="*.sh" .
```

### 1B: Enforce Naming Convention in Harness

Add to CLAUDE.md under a "## Naming Conventions" section (keep total file under 80 lines — compress other sections if needed):
```
## Naming Conventions
- Session logs: `docs/session_logs/session-NN-log.md` (lowercase, hyphens, "-log" suffix)
- Session prompts: `docs/prompts/session-NNx-prompt.md`
- Session context: `docs/session_context/session-NNx-context.md`
- Session assessments: `docs/assessments/session-NN-assessment.md`
- Branch names: `session-NN/description`
```

### 1C: Remove Duplicate Scripts

Session 72 created canonical tools (scripts/merge.sh + Claude Code hooks). Sessions 71/71D created older versions that are now redundant. Remove them:

```bash
# List what exists
ls scripts/merge*.sh scripts/enforce*.sh scripts/merge-worktree*.sh 2>/dev/null

# Remove duplicates — keep ONLY scripts/merge.sh
git rm scripts/merge-worktree.sh 2>/dev/null || true
git rm scripts/enforce_worktree.sh 2>/dev/null || true  
git rm scripts/merge_tracks.sh 2>/dev/null || true
```

Search for any references to the deleted scripts and update them:
```bash
grep -rn "merge-worktree\|enforce_worktree\|merge_tracks" --include="*.md" --include="*.sh" --include="*.json" .
```

Update any docs that reference the old scripts to point to `scripts/merge.sh` and Claude Code hooks instead.

Also check: does `docs/harness/worktree-enforcement.md` reference `enforce_worktree.sh`? If so, update it to reference the Claude Code PreToolUse hook as the canonical enforcement mechanism.

### 1D: Fix Stop Hook for Merge Sessions

The stop hook currently reads `current_session.txt` and requires `session-{N}-assessment.md`. This breaks during merge-only sessions (the 71D merge had to create a fake assessment).

Fix: update the stop hook in `.claude/settings.json` to also accept assessment files that contain the current session number as a substring OR allow a `--merge` flag in the session file:

```bash
# In .claude/settings.json stop hook, change the check to:
# If current_session.txt contains "merge" → skip assessment check
# Otherwise → require assessment file
```

The simplest fix: if `current_session.txt` contains the word "merge" (e.g., "71d-merge"), skip the assessment requirement.

Commit: `fix(harness): naming convention, remove duplicate scripts, fix stop hook`

/clear

---

## PHASE 2: INVESTIGATE + FIX REAL BUGS (15 min)

### 2A: Investigate Track A Revert Mystery

Session 71 reported "Track A edits were reverted 3 times by unknown process." This is a time bomb. Find the cause:

```bash
# Check git hooks
ls -la .git/hooks/ | grep -v ".sample"
cat .git/hooks/pre-commit 2>/dev/null

# Check for husky or lint-staged
cat package.json 2>/dev/null | grep -i "husky\|lint\|prettier\|format"
ls .husky/ 2>/dev/null

# Check Claude Code hooks that might modify files
cat .claude/settings.json | python3 -m json.tool

# Check for any file watchers or formatters
grep -rn "format\|prettier\|autopep8\|black\|ruff" .claude/ --include="*.json" --include="*.md"
```

Document what you find. If there's a formatter/linter silently modifying files:
- Either configure it to exclude app/main.py
- Or disable it and document why in CLAUDE.md
- Add an AD entry if this is a substantive decision

If you can't find the cause, document that too — "investigated, no hook found, may have been Claude Code subagent interference" is an acceptable conclusion.

### 2B: Fix Enter Key Properly

Session 71's fix was a 400ms retry fallback, which is a hack around a race condition. Fix it properly:

```bash
# Find the current implementation
grep -n "400\|retry\|keydown\|Enter\|enter.*key" app/main.py | head -20
```

The real fix depends on what you find, but likely options:
1. If HTMX is swapping the form: attach the event listener via HTMX's `htmx:afterSettle` or `htmx:afterSwap` event instead of DOMContentLoaded
2. If it's a delegation issue: use event delegation on a stable parent element (`document.addEventListener('keydown', ...)` with target filtering)
3. If the form submits but doesn't process: check the server-side handler

The fix should NOT involve setTimeout, retry loops, or arbitrary delays. Remove the 400ms hack and replace with a proper solution.

Write a test that verifies Enter key triggers identity creation.

Commit: `fix(ux): proper enter key handler — remove 400ms hack`

/clear

---

## PHASE 3: SHARE-READINESS ASSESSMENT (10 min)

This is NOT a feature-building phase. This is an honest evaluation of whether Rhodesli is ready to share with family members.

### 3A: Quick Smoke Test

Open https://rhodesli.nolanandrewfox.com/ in the browser (or use curl/Playwright).

Check these 10 things. For each, record PASS/FAIL/CONCERN:

1. Landing page loads, looks professional
2. Photos page loads, photos render from R2
3. People page loads, face cards are ≥150px, quality labels show (not raw numbers)
4. Click a person → person detail page loads with "Often appears with" (non-truncated)
5. Click a photo → photo detail page with face boxes, AI sections expanded
6. Discoveries page shows confidence labels (not percentages), clickable navigation
7. New Matches page loads, triage bar visible
8. GEDCOM search returns ranked results with "Show more"
9. "Link to Tree" / "View in Tree" buttons visible on People page
10. Mobile viewport (resize to 375px) — does it not break horribly?

### 3B: Blocker Assessment

Based on the smoke test, create `docs/share-readiness.md`:

```markdown
# Share-Readiness Assessment
Date: [today]
Assessed by: Claude Code (Session 73)

## Status: [READY / BLOCKED / ALMOST]

## Blockers (must fix before sharing)
- [list anything that would confuse or embarrass]

## Concerns (would be nice to fix)
- [list anything suboptimal but not blocking]

## What Works Well
- [list strengths]

## Recommended Next Steps
- [ordered list of what to do before sharing]
```

Be brutally honest. "Ready" means a non-technical family member could visit the URL, browse photos, see identified people, and not hit anything broken or confusing. "Blocked" means there's something that would make you not want to send the link.

### 3C: Final Docs

Update:
- CHANGELOG.md: v0.77.1
- SESSION_INDEX.md: Session 73 one-liner
- `echo "74" > .claude/current_session.txt`

Create `docs/assessments/session-73-assessment.md` with:
- What was cleaned up
- Revert mystery findings
- Enter key fix details  
- Share-readiness verdict

```bash
make test-full
git add -A && git commit -m "docs: session 73 — cleanup, enter key fix, share-readiness assessment"
git push origin main
```

---

## WHAT NOT TO DO
- No ML work (calibrator is parked until more eval data)
- No new harness tooling (Session 72 resolved this)
- No GEDCOM feature work
- No landing page redesign
- No new documentation frameworks or templates
- No worktrees or parallelization
- If any phase takes longer than its time budget, stop and move on
