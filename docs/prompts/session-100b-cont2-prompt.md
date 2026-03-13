# Session 100b Continuation 2 Prompt

**Read first:** `docs/session_context/session-100b-context.md` and `docs/assessments/session-100b-cont-assessment.md`

## What's Done (Commits on Main)
1. BUG 1 FIXED: Confirmed faces show names on bbox overlap (IoU 0.85), 6 tests added
2. BUG 2 FIXED: Removed 3 duplicate photo metadata routes from photo_routes.py
3. Dismissed faces show "Dismissed" label (slate color) on photo overlays
4. CHANGELOG/SESSION_HISTORY/BACKLOG all updated for sessions 96-100
5. ROADMAP updated with session 100b status
6. Assessment written

## Worktree Branches to Merge
Three worktree subagents were launched. Their branches need careful merging because they branched from pre-fix main (commit 4c50a4d). Current main is 16a272f.

### worktree-agent-a387c6f3 (1 commit: c51b8ee)
- **Fix:** People-in-photo layout grid consistency
- **Changes:** `app/page_routes.py` — CSS grid layout for person cards
- **WARNING:** This branch also reverts BUG 1 fixes and dismissed faces changes because it branched early. Cherry-pick ONLY the layout CSS changes (`.person-strip, .person-grid` grid rules, card sizing unification, link wrapper changes). Do NOT take any bbox_conflict or overlay changes from this branch.

### worktree-agent-a03216f8 (may have commits)
- **Fix:** Photo overlay caption obstruction + Hide Faces discoverability
- **Same warning:** Branched from pre-fix main. Cherry-pick only overlay positioning changes.

### worktree-agent-a3323c47 (may have commits)
- **Fix:** Face cycling on identity cards (prev/next arrows for multi-face identities)
- **Same warning:** Cherry-pick only face cycling changes.

### Merge Strategy
For each branch with commits:
1. `git diff main..{branch} -- app/page_routes.py` to see changes
2. Identify only the NEW functionality (not reverts of our fixes)
3. Apply those changes manually to main's page_routes.py
4. Run tests: `source venv/bin/activate && pytest tests/ -x -q --ignore=tests/e2e/ -k "not test_confirmed_anchors"`
5. Commit

After all merges, clean up worktrees:
```bash
git worktree remove .claude/worktrees/agent-a387c6f3
git worktree remove .claude/worktrees/agent-a03216f8
git worktree remove .claude/worktrees/agent-a3323c47
```

## Remaining Dogfood Issues (Not Yet Done)
- Issue #10: Confirmed-people GEDCOM filtering (user wants this)
- Issue #7: Photo overlays obscure caption (worktree may have fix)
- Issue #9: Hide Faces discoverability (worktree may have fix)
- BUG 3: Face card cycling (worktree may have fix)

## Pre-existing Test Failures (Known, Don't Fix)
- `test_confirmed_anchors_in_face_to_photo`: Solomon Solly Galante face not in local data
- `test_admin_approval_card_has_face_thumbnail`: E2E test failure

## Phase 7: Deploy + Browser Verify
After merging worktree branches:
1. `git push origin main`
2. Wait for Railway deploy
3. Browser verify:
   - Jacob Cohen photo (d5bc8746012a6da3): faces show names, not "Needs review"
   - Photo metadata save: edit collection, reload, verify persists
   - People-in-photo layout: consistent grid, no gaps
4. Take screenshots for evidence

## Phase 8: Session Closure
1. Update assessment with final status
2. Update ROADMAP session 100b → COMPLETE
3. Ensure both test suites pass
4. Final push
