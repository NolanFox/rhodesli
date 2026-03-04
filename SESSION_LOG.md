# Session 86 Log — P1 UX Fixes + MLS Experiment + Gemini Completion
## Mission: Fix P1 UX bugs, resolve AD-027 (MLS vs Euclidean), complete Gemini alignments
## Started: 2026-03-04
## Version: v0.88.0 → v0.89.0
## Predecessor: Session 85c (v0.88.0)
## Detailed log: docs/session_logs/session-86-log.md

### Act 0: Orient + Data Sync
- [x] Set `.claude/current_session.txt` to `86`
- [x] Synced production data: 17 new photos, 73 new identities
- [x] Commit: d69460b

### Act 1: Partial Monolith Split
- [x] Extracted app/utils.py — 8 pure functions, zero deps
- [x] Skipped data_loaders extraction (48+ functions, circular dep risk)
- [x] Commit: fefee23

### Act 2: Parallel Tracks
- [x] Track B (MLS experiment): Euclidean AUC 0.9903 vs MLS 0.9454. AD-027 resolved.
- [x] Track C (Gemini retry): 2/2 remaining photos processed. 271/271 complete.
- [x] Commits: 8e3a65d, 4d582a7

### Act 3: UX-037 — Merge Confirmation
- [x] hx_confirm on ~10 merge buttons with both identity names
- [x] 3 new tests
- [x] Commit: 07fe04f

### Act 4: UX-039 — Person Page Admin Controls
- [x] Inline rename form, confirm/skip/reject buttons, merge search
- [x] 5 new tests (admin + non-admin)
- [x] Commit: e22939f

### Act 5: Face Labels + Connected Navigation
- [x] Confirmed face overlays visible for ALL users (admin + public photo pages)
- [x] Person page action bar: Timeline, Map, Tree, Connections, Compare
- [x] 6 new tests
- [x] Commits: d210a55, 817d9af

### Act 6: Merge Parallel Tracks
- [x] Cherry-picked MLS evaluation and Gemini results
- [x] Cleaned up 3 worktrees

### Act 7: Browser Verification (6/6 PASS)
- [x] Person page action bar verified
- [x] Compare CTA on person page verified
- [x] Tree link with person_id verified
- [x] No admin controls for unauthenticated (correct)
- [x] Face overlay legend visible
- [x] Confirmed face overlays display:block for all users

### Red Flags
- Pre-existing test ordering failures under xdist
- data_loaders/compare/estimate extraction deferred
- Chrome extension unavailable — curl verification used
