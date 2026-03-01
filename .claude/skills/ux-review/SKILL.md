---
name: ux-review
description: 'Spawn a UX review subagent that examines all screenshots taken by
  Claude Chrome or Playwright. Evaluates design quality, finds visual bugs, and
  resolves bugs via a separate git worktree and subagent. MUST run after any
  session that changes UI. Invoked automatically at session end.'
---

# UX Review Skill

## Trigger
Run after ANY session that modifies app/main.py, static/, or templates.
Run at session end as part of Act 7 verification.

## Steps

### 1. Collect Screenshots
Gather ALL screenshots from current session:
- `docs/screenshots/session-*/*.png`
- `/tmp/*.png` (Claude Chrome captures)
- Any Playwright captures

### 2. Spawn Worktree Subagent
Create worktree `session-NN/ux-fixes` for isolated fixes.

### 3. Evaluate Each Screenshot Against Criteria
- Touch targets >= 44px on mobile
- WCAG AA contrast ratios
- Layout consistency across pages
- No broken images, cut-off text, missing icons
- Navigation flows work (links lead to expected pages)
- Responsive at 375px, 768px, 1024px viewports
- Visual hierarchy is clear
- Empty states handled gracefully
- Face photos are dominant (60%+ of card visual weight)
- Action buttons are discoverable
- Text is readable at default zoom

### 4. Fix Bugs in Worktree
For each bug found:
1. Fix in the worktree branch
2. Screenshot the fix
3. Log finding with before/after evidence

### 5. Merge Back
Merge worktree to main after all fixes.

### 6. Log Results
Append to session log:
```
## UX Review
- Bugs found: N
- Fixed: N
- Deferred: N (with reasons for each)
```
