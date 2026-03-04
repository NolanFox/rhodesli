# Session 86 Log
Started: 2026-03-04
Prompt: docs/prompts/session-86-prompt.md
Version: v0.88.0 → v0.89.0

## Phase Checklist
- [x] Act 0: Orient + Data Sync — synced 17 new photos, 73 new identities
- [x] Act 1: Partial Monolith Split — extracted app/utils.py (8 functions). Skipped data_loaders (too risky)
- [x] Act 2: Launch Parallel Tracks — Track B (MLS) + Track C (Gemini) in worktrees
- [x] Act 3: UX-037 — Merge confirmation dialogs on all ~10 merge buttons
- [x] Act 4: UX-039 — Inline admin controls (rename, state actions, merge search)
- [x] Act 5: Face Labels + Connected Navigation — confirmed faces visible for all users
- [x] Act 6: Merge Parallel Tracks — cherry-picked MLS + Gemini commits
- [x] Act 7: Browser Verification — curl-based production verification (6/6 PASS)
- [x] Act 8: Assessment + Final Docs

## Track Results

### Track B: MLS vs Euclidean (AD-027 Resolution)
- Euclidean AUC: 0.9903 vs MLS AUC: 0.9454
- Decision: Keep Euclidean (current default). MLS underperforms due to scalar sigma.
- 38 new tests in tests/test_mls_vs_euclidean.py

### Track C: Gemini Retry
- 2/2 remaining photos processed with gemini-2.5-flash
- Cost: $0.0004. 271/271 photos now have Gemini alignments.

## Browser Verification Summary (6/6 PASS)
- [x] Person page action bar: Timeline, Map, Tree, Connections, Compare present
- [x] Compare CTA on person page
- [x] Tree link with person_id
- [x] No admin controls for unauthenticated users (correct)
- [x] Face overlay legend visible on photo page
- [x] Confirmed face overlays display:block for all users (Zeb Capuano verified)

## Commits
1. d69460b - docs(session): session 86 orient
2. fefee23 - refactor(app): extract pure utility functions to app/utils.py
3. 07fe04f - fix(merge): UX-037 confirmation dialog on all merge buttons
4. e22939f - feat(person): UX-039 inline admin controls on person page
5. d210a55 - feat(ux): face labels visible for all users + connected nav tests
6. 8e3a65d - eval(ml): resolve AD-027 — MLS vs Euclidean (Euclidean wins)
7. 4d582a7 - fix(ml): complete Gemini alignment for last 2 blocked photos
8. 817d9af - fix(ux): face labels on public photo page visible for confirmed faces

## Red Flags
- Pre-existing test ordering failures (test_neighbors_with_container_id, test_face_card_has_share_button) — flaky under xdist
- data_loaders extraction deferred (48+ functions, 24 cache vars, circular dep risk)
- compare/estimate route extraction deferred (tight coupling to main.py caches)
