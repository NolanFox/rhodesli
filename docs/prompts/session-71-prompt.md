# SESSION 71: UX DOGFOODING FIXES + GEDCOM INTEGRATION + HARNESS ENFORCEMENT

Read CLAUDE.md first. Read ROADMAP.md. Read docs/BACKLOG.md. Read ALGORITHMIC_DECISIONS.md.
Then read `docs/session_context/session-71-context.md` for full planning context and dogfooding findings.

## ROLE
Lead Architect for Rhodesli heritage photo archive. Session 70 shipped 5 threads across 3 parallel subagents with 3671 tests passing. But dogfooding revealed significant UX regressions and integration gaps. This session fixes what real users would hit.

## SESSION GOALS
1. Fix all UX regressions and bugs found during dogfooding
2. Complete GEDCOM integration so it's accessible from the main workflow
3. Implement mechanical subagent commit enforcement (end the 4-session pattern failure)
4. Write missing AD entries for ML vocabulary change
5. Wire parallelization skill into UserPromptSubmit hook
6. Re-verify Session 70's 9 UX fixes in production
7. Test everything with Claude Chrome for browser-level verification

## CONSTRAINTS
- Every prompt MUST mandate updating ALGORITHMIC_DECISIONS.md with full decision provenance
- Deploy via `git push` only (never Railway dashboard)
- Use `/clear` (not `/compact`) between phases
- No single doc file over 300 lines
- Session planning context: `docs/session_context/session-71-context.md`
- Prompt files: `docs/prompts/session-71x-prompt.md`
- Test before every commit: `pytest tests/ -x -q`

---

## PHASE 0: ORIENT + WORKTREE SETUP (10 min)

### 0A: Verify current state
```bash
git pull origin main
pytest tests/ -x -q  # Record count: should be ~3671
git log --oneline -10  # Confirm session 70 merges present
```

Check Railway deploy status — confirm Session 70's final deploy completed successfully.

### 0B: Re-verify Session 70's 9 UX Fixes in Production
Open rhodesli.nolanandrewfox.com in browser. Verify each of these is actually live:
1. Discovery card improvements
2. ML banner vocabulary changes
3. Tab styling updates
4. Triage bar changes
5. All other Phase 2 items from Session 70 Subagent A

Create a verification table in the session log:
| Item | Expected | Actual | PASS/FAIL |
Record any items that are NOT visible in production — they become Track A work.

### 0C: Auto-Eval Test (if not already done)
If `./scripts/run_session.sh` has not been tested yet:
```bash
# Run from project root, NOT from within a Claude Code session
chmod +x ./scripts/run_session.sh
./scripts/run_session.sh --dry-run  # or with session 70's prompt
```
If it errors, capture the FULL error output to `docs/session_logs/auto_eval_errors.txt`.
If it works, log the result. This has been deferred 5 sessions — resolve it now.

### 0D: Set up worktrees
```bash
# Create three parallel worktrees
git worktree add .claude/worktrees/track-a session-71/ux-fixes -b session-71/ux-fixes
git worktree add .claude/worktrees/track-b session-71/gedcom-integration -b session-71/gedcom-integration
git worktree add .claude/worktrees/track-c session-71/harness-infra -b session-71/harness-infra
```

### 0E: Save prompt and create session log
```bash
# Save this prompt
cp <this-file> docs/prompts/session-71-prompt.md

# Create session log
cat > docs/session_logs/SESSION_071.md << 'EOF'
# Session 71 Log
Started: [timestamp]
Theme: UX Dogfooding Fixes + GEDCOM Integration + Harness Enforcement
Prompt: docs/prompts/session-71-prompt.md
Context: docs/session_context/session-71-context.md

## Phase Checklist
- [ ] Phase 0: Orient + worktree setup
- [ ] Track A: UX fixes (face cards, enter key, Run Face Analysis, whitespace)
- [ ] Track B: GEDCOM integration (search ranking, pagination, People tab actions)
- [ ] Track C: Harness infrastructure (subagent enforcement, ML vocabulary AD, parallelization hook)
- [ ] Phase Final: Merge, deploy, browser verify

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed
- [ ] Claude Chrome browser verification passed
- [ ] ALGORITHMIC_DECISIONS.md updated
EOF
```

Commit: `docs: session 71 phase 0 — orient and setup`

/clear

---

## TRACK A: UX FIXES (Worktree: .claude/worktrees/track-a)

Re-read `docs/session_context/session-71-context.md` Section 2 (Dogfooding Findings).

### A1: Fix Enter Key Not Creating Person
**File**: Likely in templates or static JS for the face identification modal.

Find the identity creation input (the one shown in screenshot sh_1 where user types a name like "Rica Sharhon Amato"). Add a keydown event listener:
- On Enter key press, trigger the same action as the Create button click
- Prevent default form submission if inside a form
- Test: Type a name → press Enter → identity should be created (same as clicking Create)

Write a test for this behavior.

### A2: Fix Face Card Photo Size Regression (CRITICAL)
**Context**: Nolan previously reported face photos too small. They are now EVEN SMALLER. This is a regression that needs urgent fixing.

**Files**: CSS for face cards, likely in templates or static/css.

Requirements:
- Face photo on the People page (face card) should be AT LEAST 150x150px, ideally 200x200px
- Reduce whitespace around the photo — the photo is the most important element
- The quality score (e.g., "Quality: 23.27") should either be removed from public view or given context (e.g., "Good quality" / "Low quality")
- Compare current CSS against Session 69/70 changes to find what caused the regression

Before making changes, screenshot or record the current computed sizes. After changes, verify the improvement.

Write tests for minimum photo dimensions.

### A3: Fix "Run Face Analysis" Silent Failure
**File**: Photo detail page, Face Analysis section.

Current behavior: Button click has no visible feedback.
Required behavior:
1. On click: Show loading spinner or "Analyzing faces..." message
2. On success: Display the face analysis results (or refresh the section)
3. On failure: Show an error message explaining what went wrong
4. Disable the button during processing to prevent double-clicks

Investigate: Is the endpoint actually working? Check the server logs for errors when this button is clicked. If the backend is broken, fix the backend. If it's just missing UX feedback, add it.

### A4: Fix AI Analysis Section Collapsed State
**File**: Photo detail page template.

Current: Scene, Visible Text, Tags, Photo Detective Evidence, Subject Ages are all collapsed.
- If data exists: Expand the most useful sections by default (at minimum: Scene and Photo Detective Evidence)
- If no data exists: Don't show empty collapsed sections — either hide them or show "Not yet analyzed" in a single line
- The Date Estimate section is correctly shown expanded — follow that pattern

### A5: Fix "Often Appears With" Name Truncation
**File**: Person page template (shown in sh_5 screenshot).

Current: Names truncated to "Rachel Ama...", "Rica Sharho...", "Solomon Me..."
Fix: Show full names, or at minimum show enough characters to be identifiable (first name + surname). If space is constrained, use a tooltip on hover for the full name.

### A6: Quality Score Display
**File**: Face card template on People page.

Current: Shows raw number "Quality: 23.27" which means nothing to users.
Options (pick one and document in AD):
- Remove from public-facing view entirely (admin only)
- Map to labels: "Excellent" / "Good" / "Fair" / "Poor" with thresholds
- Show as a visual indicator (green/yellow/red dot)

Create AD entry: AD-XXX "Face quality score — user-facing display decision"

### A7: Track A Verification Gate
- [ ] Enter key creates identity in face naming modal
- [ ] Face card photos are ≥150px on People page
- [ ] Whitespace on face cards reduced
- [ ] "Run Face Analysis" shows loading + success/error feedback
- [ ] AI Analysis sections show/hide appropriately
- [ ] "Often appears with" shows non-truncated names
- [ ] Quality score display decision documented in AD
- [ ] All existing tests still pass
- [ ] New tests written for A1-A6

Commit: `feat(ux): session 71 Track A — dogfooding UX fixes`
Push to branch: `git push origin session-71/ux-fixes`

/clear

---

## TRACK B: GEDCOM INTEGRATION (Worktree: .claude/worktrees/track-b)

Re-read `docs/session_context/session-71-context.md` Section 2 (Dogfooding Findings).

### B1: Fix GEDCOM Search Ranking
**File**: The family tree link search endpoint.

Current behavior (from screenshots sh_4, sh_5):
- Results for "Natenel Menashe" are alphabetically sorted
- Generic "Menashe No dates" appears first
- Cuts off at ~10 results with no pagination

Required behavior:
1. **Rank by match strength**: Exact name match first, then close matches, then surname-only matches
2. **Scoring**: Implement a simple scoring system:
   - Exact full name match: 100 points
   - First name + surname match: 80 points
   - Surname-only match with dates overlapping photo era: 60 points
   - Surname-only match, no dates: 20 points
   - Bonus: Person has birth/death dates (+10), person has Rhodes connection (+10)
3. **Pagination**: Add "Show more" button or infinite scroll. Don't cut off at 10.
4. **Display**: Show match score or confidence indicator next to each result

Create AD entry: AD-XXX "GEDCOM search ranking — match strength scoring"

### B2: Add GEDCOM Connection to Identity Creation Flow
**File**: Face identification modal / identity creation flow.

After a user names a face and creates an identity, add a follow-up step:
1. Show a prompt: "Connect [name] to their family tree record?"
2. Display the GEDCOM search results (using the new ranking from B1)
3. Allow user to click "Link" or "Skip for now"
4. If linked, store the GEDCOM connection immediately

This turns GEDCOM linking from a hidden 5-step process into a natural part of the identification flow.

### B3: Add GEDCOM Actions to People Tab
**File**: People page template and routes.

For each person card on the People tab, add action buttons/links:
1. **If NOT linked to GEDCOM**: Show "Connect to Tree" button → opens GEDCOM search modal (same component as B1/B2)
2. **If linked to GEDCOM**: Show "View in Tree" link → navigates to the tree view for that person
3. These actions should be accessible directly from the People page without navigating away

Visual placement: Add as small action links below the face photo, next to existing "View Photo" / "Share" / "Find Similar" actions.

### B4: Verify GEDCOM Data Is Current
Check whether the GEDCOM data has been properly loaded and is queryable:
```sql
-- Check GEDCOM record count
SELECT COUNT(*) FROM gedcom_individuals;
-- Check for Menashe family records specifically
SELECT * FROM gedcom_individuals WHERE surname ILIKE '%menashe%' LIMIT 20;
-- Check if search index is built
-- (whatever the current search mechanism is — full-text, trigram, etc.)
```

If the GEDCOM data is stale or missing, re-import. Document findings in session log.

### B5: Track B Verification Gate
- [ ] GEDCOM search returns results ranked by match strength (not alphabetical)
- [ ] Pagination or "show more" works for >10 results
- [ ] Identity creation flow includes GEDCOM link prompt
- [ ] People tab shows "Connect to Tree" / "View in Tree" per person
- [ ] GEDCOM data verified as current (record count, Menashe family present)
- [ ] All existing tests still pass
- [ ] New tests written for B1-B4

Commit: `feat(gedcom): session 71 Track B — GEDCOM integration and search ranking`
Push to branch: `git push origin session-71/gedcom-integration`

/clear

---

## TRACK C: HARNESS & INFRASTRUCTURE (Worktree: .claude/worktrees/track-c)

Re-read `docs/session_context/session-71-context.md` Section 1 (Session 70 Concerns).

### C1: Mechanical Subagent Commit Enforcement
**This is the most important infrastructure fix. Behavioral rules have failed 4 times.**

Find the orchestration logic that manages subagent worktrees (likely in `.claude/skills/` or `scripts/`).

Add a post-subagent verification step:
```bash
# After each subagent completes, BEFORE merging:
UNCOMMITTED=$(git -C <worktree-path> status --porcelain)
if [ -n "$UNCOMMITTED" ]; then
  echo "WARNING: Subagent left uncommitted files:"
  echo "$UNCOMMITTED"
  # Auto-commit with standard message
  git -C <worktree-path> add -A
  git -C <worktree-path> commit -m "fix: auto-commit uncommitted subagent files (enforcement gate)"
  echo "Auto-committed. Review these files in the merge."
fi
```

This must be a CODE CHANGE in the orchestration script, not a new lesson or documentation entry.

Create AD entry: AD-XXX "Subagent commit enforcement — mechanical gate replacing behavioral rules"

### C2: ML Banner Vocabulary AD Entry
Session 70 Subagent A changed match vocabulary without an AD entry:
- Old: "ML MATCH: MODERATE", "ML MATCH: STRONG", etc.
- New: "Possible match", "Strong match", etc.

Create AD-XXX documenting:
1. The old vocabulary and why it was changed
2. The new vocabulary: what each label maps to in terms of distance thresholds
3. Whether the new labels correctly communicate the algorithmic confidence
4. Risk: "Possible match" on a strong signal could cause users to dismiss valid matches
5. Decision: accept, modify, or revert

Reference the distance thresholds from the similarity calibration work.

### C3: Wire Parallelization Skill into UserPromptSubmit Hook
The parallelization skill scored 8/14 on its first validation test.

Next step: Install it as a hook that fires automatically when a new prompt is received.
- Hook type: UserPromptSubmit (or equivalent in current Claude Code hook system)
- Behavior: When a multi-phase prompt is received, the skill analyzes it and proposes a parallelization plan
- The plan should identify: independent tracks, shared dependencies, merge order, file ownership
- Output: Written to `docs/session_context/session-NNN-parallel-plan.md`

### C4: Auto-Eval Script Verification
If the auto-eval test from Phase 0C produced errors:
- Fix the errors in `./scripts/run_session.sh`
- The script has been 455 lines and 6 stages — verify each stage independently
- Common issues: path assumptions, missing env vars, nested claude -p restrictions
- If the script fundamentally cannot run (architectural limitation), document this honestly and propose an alternative (e.g., GitHub Actions, separate terminal invocation, cron job)

If the auto-eval test passed:
- Document the successful run in SESSION_071.md
- Note: this is a major milestone (5 sessions deferred)

### C5: Research — Best Practices for Multiple Simultaneous Claude Code Sessions
Nolan wants to run multiple Claude Code sessions simultaneously for different tasks.

Research and document:
1. How to set up multiple terminal sessions with different worktrees
2. Merge conflict prevention strategies when sessions touch nearby files
3. Best practices for prompt design when running parallel sessions
4. How to monitor multiple sessions simultaneously
5. Recovery strategies if a merge conflict occurs

Write findings to: `docs/harness/PARALLEL_SESSIONS.md` (under 300 lines)

Key patterns to document:
- File ownership mapping (assign files to tracks before starting)
- Communication protocol (how tracks signal completion)
- Merge ceremony (order, testing, conflict resolution)
- When NOT to parallelize (shared state, database migrations, CSS that affects everything)

### C6: Track C Verification Gate
- [ ] Subagent commit enforcement is a CODE CHANGE (not a doc/lesson)
- [ ] `git status --porcelain` check exists in orchestration logic
- [ ] AD entry for ML banner vocabulary created with threshold mappings
- [ ] Parallelization skill wired into UserPromptSubmit hook (or documented why not)
- [ ] Auto-eval script tested (pass or fail documented with detail)
- [ ] PARALLEL_SESSIONS.md written with best practices
- [ ] All existing tests still pass
- [ ] ALGORITHMIC_DECISIONS.md updated with all new AD entries

Commit: `feat(harness): session 71 Track C — mechanical enforcement + infrastructure`
Push to branch: `git push origin session-71/harness-infra`

/clear

---

## PHASE FINAL: MERGE, DEPLOY, BROWSER VERIFY (15 min)

Back in main worktree.

### F1: Merge Tracks (order matters)
```bash
git checkout main
git pull origin main

# Track C first (docs/scripts only — least conflict risk)
git merge session-71/harness-infra --no-ff -m "merge: Track C harness infrastructure"
pytest tests/ -x -q

# Track A next (UX/templates)
git merge session-71/ux-fixes --no-ff -m "merge: Track A UX dogfooding fixes"
pytest tests/ -x -q

# Track B last (GEDCOM — touches routes that A may also touch)
git merge session-71/gedcom-integration --no-ff -m "merge: Track B GEDCOM integration"
pytest tests/ -x -q
```

If merge conflicts occur:
1. Identify which files conflict
2. Keep BOTH sides where possible (both features are needed)
3. If logic conflicts, Track B's GEDCOM changes take priority (they're the newer integration)
4. Run tests after each conflict resolution

### F2: Deploy
```bash
git push origin main
# Wait for Railway deploy (watch with `railway logs` or check dashboard)
# Run smoke test after deploy completes
```

### F3: Browser Verification with Claude Chrome
After deploy is confirmed, verify in the browser:

| # | Test | Steps | Expected | PASS/FAIL |
|---|------|-------|----------|-----------|
| 1 | Enter key creates identity | Go to photo → Name a face → type name → press Enter | Identity created | |
| 2 | Face card photo size | Go to People tab → check photo dimensions | ≥150px | |
| 3 | Face card whitespace | Visual check on People page | Reduced from before | |
| 4 | Run Face Analysis feedback | Go to photo → click "Run Face Analysis" | Loading indicator shown | |
| 5 | GEDCOM search ranking | Go to person → Family Tree Link → search | Ranked by match strength | |
| 6 | GEDCOM pagination | Search a common surname | >10 results accessible | |
| 7 | GEDCOM from People tab | Go to People → find unlinked person | "Connect to Tree" visible | |
| 8 | Identity creation → GEDCOM prompt | Name a face → create identity | GEDCOM link prompt appears | |
| 9 | Often appears with | Check person page | Names not truncated | |
| 10 | AI Analysis sections | Check photo detail | Useful sections expanded | |
| 11 | Session 70 UX fixes | Re-verify all 9 items | All visible in production | |

### F4: Final Documentation
Update `docs/session_logs/SESSION_071.md`:
- Mark all phase checkboxes
- Record test count (before and after)
- Record all commits
- Note any deviations from plan
- List all AD entries created

Update `docs/SESSION_INDEX.md` with Session 71 row.

Update ROADMAP.md:
- Session 71 → Recently Completed
- Bump version
- Update test count

Update BACKLOG.md:
- Mark completed items
- Add any new items discovered during this session

Update CHANGELOG.md with version bump.

### F5: Clean up worktrees
```bash
git worktree remove .claude/worktrees/track-a
git worktree remove .claude/worktrees/track-b
git worktree remove .claude/worktrees/track-c
git branch -d session-71/ux-fixes session-71/gedcom-integration session-71/harness-infra
```

Commit: `docs: session 71 complete`
Push: `git push origin main`

---

## CRITICAL REMINDERS
- Use `/clear` between phases. Not `/compact`. Non-negotiable.
- Every AD entry needs: what was chosen, what was rejected, why, source material.
- Test before every commit: `pytest tests/ -x -q`
- Deploy via `git push` only.
- If any phase takes >20 min, stop and reassess scope.
- The subagent commit enforcement in C1 MUST be a code change, not documentation.
- Face card photo size fix in A2 MUST result in visually larger photos — verify with pixel measurements.
- GEDCOM ranking in B1 MUST show strongest matches first — verify with a known name search.

## SESSION 70 ITEMS CHECKLIST (nothing missed)
- [x] Subagent commit enforcement → Track C, Phase C1
- [x] Auto-eval loop test → Phase 0C + Track C, Phase C4
- [x] Deploy verification incomplete → Phase 0B
- [x] ML banner vocabulary AD → Track C, Phase C2
- [x] Parallelization skill → UserPromptSubmit hook → Track C, Phase C3
- [x] Enter key bug → Track A, Phase A1
- [x] No GEDCOM connection from main flow → Track B, Phase B2
- [x] People tab → GEDCOM/Tree access → Track B, Phase B3
- [x] GEDCOM data freshness → Track B, Phase B4
- [x] GEDCOM ranking (alphabetical, no pagination) → Track B, Phase B1
- [x] Face card photos too small (regression) → Track A, Phase A2
- [x] Face card whitespace (regression) → Track A, Phase A2
- [x] Run Face Analysis silent failure → Track A, Phase A3
- [x] AI Analysis collapsed sections → Track A, Phase A4
- [x] Often appears with name truncation → Track A, Phase A5
- [x] Quality score display → Track A, Phase A6
- [x] Git worktrees parallelization → Phase 0D + Track C, Phase C5
- [x] Multiple Claude Code sessions best practices → Track C, Phase C5
- [x] Claude Chrome testing → Phase F3
- [x] Harness equipped for parallel sessions → Track C, Phase C5
