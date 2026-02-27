# Session 71 Planning Context
# Date: 2026-02-26
# Breadcrumbs: Session 70 Assessment → Dogfooding Feb 26 → "Evaluating Claude Code tools" → Session 64 worktree patterns

---

## 1. SESSION 70 ASSESSMENT — ALL CONCERNS WITH REQUIRED ACTIONS

### Concern 1: Subagent Commit Problem (CRITICAL — 4th occurrence)
- **History**: Sessions 64, 69, 70 (twice). Subagent A fails to commit its own files.
- **Root cause**: Behavioral rules (Lesson 87, parallelization skill, subagent briefs) have provably failed. Adding more documentation won't fix this.
- **Required fix**: MECHANICAL ENFORCEMENT in orchestrator. After each subagent completes, orchestrator runs `git -C <worktree-path> status --porcelain`. If it returns anything: auto-commit with standard message OR refuse to merge. This is a CODE CHANGE, not another lesson entry.
- **AD entry**: AD-XXX "Subagent commit enforcement — mechanical gate"

### Concern 2: Auto-Eval Loop Still Untested (5 sessions deferred)
- **History**: Sessions 67, 68, 69, 70, and now 71. Cannot nest `claude -p` from within Claude session.
- **Script**: `./scripts/run_session.sh` — 455 lines, 6-stage orchestration. Never tested live.
- **Required action**: Either test it in this session's pre-work (run from terminal, not from Claude Code), OR honestly document that it's untested and stop counting as a deliverable. If errors occur, capture the exact error output and fix in this session.
- **Decision**: If Nolan has tested before this session, incorporate results. If not, Phase 0 includes a manual test instruction with error capture.

### Concern 3: Deploy Verification Was Incomplete
- **Issue**: Railway Docker build was still in progress when Session 70 ended. Phase 2's 9 UX items verified against code merge, not production.
- **Required action**: Re-verify ALL 9 UX fixes from Session 70 in production. Browser verification table must show actual production URLs, not code diffs.

### Concern 4: ML Banner Vocabulary Change (MEDIUM, not LOW)
- **Issue**: Subagent A changed "ML MATCH: MODERATE" → "Possible match" without a DD entry.
- **Risk**: "Possible match" communicates different certainty than "ML MATCH: MODERATE". A community member seeing "Possible match" on a strong algorithmic signal might dismiss it.
- **Required action**: AD entry documenting vocabulary choices (Strong/Good/Possible/Weak), whether labels map correctly to underlying distance thresholds, and rationale.
- **AD entry**: AD-XXX "ML match vocabulary — user-facing confidence labels"

### Concern 5: Parallelization Skill Validation
- **Result**: 8/14 correct on first test. 6 gaps were minor.
- **Next step**: Wire into UserPromptSubmit hook so it fires automatically on incoming prompts.

### Concern 6: Test Count and Cumulative Progress
- **Status**: 3671 tests, all passing. +621 tests across sessions 68-70.
- **Note**: Test count should be verified at session start (may have changed if auto-eval was run).

---

## 2. DOGFOODING FINDINGS — FEB 26, 2026

Nolan went through the full flow at rhodesli.nolanandrewfox.com and found these issues:

### Bug: Enter Key Does Not Create Person (HIGH)
- **Where**: Face identification modal (Photo Context → "Name These Faces")
- **Expected**: Typing a name and hitting Enter should create the identity
- **Actual**: Must physically click with mouse. Enter does nothing.
- **Fix**: Add keydown listener for Enter on the identity creation input. Submit form on Enter.

### Bug: No Way to Connect Person to GEDCOM from Main Flow (HIGH)
- **Where**: After creating an identity, there's no obvious way to connect them to their genealogical record
- **Current workaround**: Click Public Page → scroll to bottom → find "Family Tree Link" section
- **Required**: GEDCOM connection should be accessible from:
  1. The identity creation flow itself (after naming, prompt to link)
  2. The People tab in Library (each person card should have a "Connect to Tree" action)
  3. The person detail/face card view

### Bug: GEDCOM Data May Not Be Updated / Ranking Issues (MEDIUM-HIGH)
- **Symptom**: Family tree link search for "Natenel Menashe" shows results that appear:
  - Alphabetically sorted (not by match strength)
  - Cut off after ~10 results with no pagination or "show more"
  - Generic "Menashe No dates" entry ranked first (should be lowest)
- **Expected**: Results ranked by match strength (exact name match first, then fuzzy matches). Pagination or "show more" for additional results.
- **Screenshots**: sh_4.webp and sh_5.webp show the two states of this UI

### Bug: Face Card Photos Regressed — Even Smaller (HIGH — UX regression)
- **Context**: Nolan previously flagged that cropped face photos on face cards were too small. This was supposed to be fixed.
- **Current state**: Photos are now EVEN SMALLER than before. This is a regression.
- **Additionally**: More blank space on the face card than before (also a regression — previously flagged)
- **Screenshot**: sh_2.webp shows the People page with tiny face photos and excessive whitespace
- **Required**: Face photos should be significantly larger. Reduce whitespace. The face photo is the most important element on a face card.

### Bug: "Run Face Analysis" Button — Silent Failure (MEDIUM)
- **Where**: Photo detail page → Face Analysis section → "Run Face Analysis" button
- **Behavior**: Clicking it appears to either silently fail or has no UX feedback whatsoever
- **Screenshot**: sh_3.webp shows the button and "No face descriptions available yet" message
- **Required**: Either show a loading spinner + progress feedback, OR show results when complete, OR show an error message if it fails. Never silently fail.

### Missing Feature: People Tab → Tree Integration (MEDIUM)
- **Current**: To see someone in the tree or connect them to GEDCOM, you must:
  1. Go to People tab
  2. Click Public Page
  3. Scroll to bottom
  4. Find Family Tree Link section
- **Required**: From the People tab, each person should have direct actions:
  1. "Connect to Tree" (if not yet linked to GEDCOM)
  2. "View in Tree" (if already linked)
  3. These should be accessible without leaving the People page

### Screenshot Review — Additional Issues Found
- **sh_3.webp**: AI Analysis sections (Scene, Visible Text, Tags, Photo Detective Evidence, Subject Ages) are all collapsed. Is there data in them? If so, the most useful ones should be expanded by default. If not, they shouldn't show as empty sections.
- **sh_5.webp**: "Often appears with" section at bottom is good — shows Rachel Ama..., Rica Sharho..., Solomon Me... But names are truncated. Should show full names or at least enough to be identifiable.
- **sh_4.webp/sh_2.webp**: The quality score (23.27, 26.63) is shown but with no context — what does this number mean to a user? Consider adding a label like "Photo Quality: Good" or hiding the raw number from the public view.

---

## 3. PARALLELIZATION — GIT WORKTREES BEST PRACTICES

### Why Worktrees (Validated Pattern)
- Anthropic officially recommends for multi-session Claude Code workflows
- Each worktree = isolated working directory with own branch
- Shared git history, independent file state
- `claude --worktree feature-name` creates isolated environment

### Merge Conflict Prevention (CRITICAL for multiple simultaneous sessions)
Best practices from community and Anthropic docs:

1. **File ownership**: Each worktree should "own" specific files. Map tasks so they don't touch the same files.
2. **Interface-first splits**: Split by feature boundary, not by layer. "Fix face cards" and "Fix GEDCOM search" touch different files.
3. **Merge order matters**: Merge docs-only tracks first (no conflicts), then independent feature tracks, then tracks with shared dependencies last.
4. **Test after every merge**: `pytest tests/ -x -q` after each `git merge --no-ff`.
5. **Short-lived branches**: Merge frequently. Don't let worktrees diverge for hours.
6. **Lock file convention**: If two tracks MUST touch the same file, designate one as primary and the other defers (adds to a TODO that the primary track picks up).

### Recommended Worktree Structure for This Session
```
.claude/worktrees/
  track-a/  → UX fixes (face cards, enter key, Run Face Analysis)
  track-b/  → GEDCOM integration (search ranking, pagination, People tab actions)
  track-c/  → Harness & infrastructure (subagent enforcement, auto-eval, ML vocabulary DD)
```

### File Ownership Map
| Track | Owns | Must Not Touch |
|-------|------|----------------|
| A (UX) | templates/, static/css/, app/routes/photos.py, app/routes/people.py (UI parts) | core/, rhodesli_ml/, scripts/ |
| B (GEDCOM) | app/routes/tree.py, app/gedcom.py, app/routes/person.py, templates/person*.html | scripts/, .claude/ |
| C (Harness) | scripts/, .claude/, docs/, ALGORITHMIC_DECISIONS.md | templates/, app/routes/ |

### Running Multiple Claude Code Sessions
Nolan's goal: dogfood → identify issues → spin up parallel Claude Code sessions for each.

**Workflow:**
1. Start session: `cd rhodesli && claude --worktree track-name`
2. Each session gets its own prompt file: `session-71a-prompt.md`, `session-71b-prompt.md`, `session-71c-prompt.md`
3. Sessions run independently. When done, each pushes to its branch.
4. Final merge session (can be manual or orchestrated):
   ```bash
   git checkout main
   git merge session-71/track-c --no-ff  # docs first
   pytest tests/ -x -q
   git merge session-71/track-a --no-ff  # UX
   pytest tests/ -x -q
   git merge session-71/track-b --no-ff  # GEDCOM (most likely to conflict)
   pytest tests/ -x -q
   ```

---

## 4. CLAUDE CHROME INTEGRATION TESTING

### What Claude Chrome Is
- Browser automation agent (beta) — can navigate, click, fill forms, verify UX
- Perfect for dogfooding verification: "go to this URL, try this flow, report what happens"

### Testing Plan
After each track merges and deploys, use Claude Chrome to:
1. Navigate to rhodesli.nolanandrewfox.com
2. Try the face identification flow (name a face, hit Enter)
3. Try connecting a person to GEDCOM
4. Check face card sizes and whitespace
5. Click "Run Face Analysis" and observe behavior
6. Report pass/fail for each item

### How to Invoke
Either run as a separate Claude session with browser access, or integrate browser verification into the session's verification gate.

---

## 5. CROSS-REFERENCES

- **Session 70 Assessment**: Full text provided in prompt
- **ML Roadmap**: date estimation (done) → similarity calibration (NEXT) → LoRA
- **Confirmed birth years = ground truth anchors**: Active learning + regression gate are core architecture
- **ALGORITHMIC_DECISIONS.md**: Must be updated with full decision provenance for any ML/vocabulary changes
- **Prompt naming**: session-71x-prompt.md (e.g., session-71a-prompt.md for Track A)
- **Context naming**: session-71-context.md (this file, shared across tracks)
- **Deploy**: via git push (not Railway dashboard)
- **Testing**: Run smoke test after deploys
- **Context management**: Use /clear (not /compact) between phases
