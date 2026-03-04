# Session 86 Prompt: Fix P1 UX + MLS Experiment + Gemini Batch

## Context
Session 86 combines three workstreams from the Claude Opus evaluation:
1. Fix 6 P1 UX bugs + face labels + connected navigation
2. MLS vs Euclidean experiment (AD-027)
3. Gemini batch re-run (144 failed photos, ~$10 API cost, $20 ceiling)

## Execution Plan

### Act 0: Orient + Data Sync (5 min)
- Set current_session.txt to "86"
- Save prompt, create session log
- Sync production data

### Act 1: Partial Monolith Split (2 hours)
Extract in order:
1. `app/utils.py` — pure functions, no deps
2. `app/data_loaders.py` — cache variables + load/invalidate functions
3. `app/routes/compare.py` — /compare/* routes
4. `app/routes/estimate.py` — /estimate/* routes

### Act 2: Launch Parallel Tracks
**Track A** (worktree: session-86/ux-compare-estimate):
- Fix UX-045/046 (compare loading + auto-scroll)
- Fix UX-053-057 (estimate upload flow)

**Track B** (worktree: session-86/mls-experiment):
- Evaluate MLS vs Euclidean on golden set
- Document results in AD-027

**Track C** (worktree: session-86/gemini-retry):
- Retry 144 failed Gemini photos
- $20 budget ceiling

### Act 3: UX-037 — Merge Direction Confirmation (45 min)
- Add hx_confirm to merge buttons showing survivor identity

### Act 4: UX-039 — Person Page Admin Controls (60 min)
- Inline rename, confirm/reject, merge search, GEDCOM link

### Act 5: Face Labels + Connected Navigation (45 min)
- Verify face labels visible for all users
- Fix dead-end navigation

### Act 6: Merge Parallel Tracks (15 min)
### Act 7: Browser Verification (20 min)
### Act 8: Assessment + Final Docs (15 min)
