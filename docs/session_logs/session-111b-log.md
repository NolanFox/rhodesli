# Session 111b Log — Community Prefix Sweep + UX Fix Sprint

**Started:** 2026-03-16 ~19:00 EDT
**Prompt:** docs/prompts/session-111b-prompt.md
**Mode:** Implementation

## Phase Checklist
- [x] Phase 0: Orient + Verify Session 111 Fixes
- [x] Phase 1: Community Prefix Sweep — 3 Parallel Worktree Tracks
- [x] Phase 2: Regression Prevention Test
- [x] Phase 3: Top UX Fixes (3 of 4 — FB-057 already done)
- [x] Phase 4: Deploy + Browser Verify
- [x] Phase 5: Harness Outputs

## What Shipped

### Phase 0
- Session 111 commits confirmed on main, pushed
- Baseline: 2401 passed, 1 pre-existing failure
- `data/identities.json` modified but NOT committed (Lesson 141)

### Phase 1 — Community Prefix Sweep (80+ fixes)
3 parallel worktree subagents:
- **Track A** (worktree-agent-aa6c9b05): discoveries_routes, estimate_routes, match_facecompare_routes, event_routes, page_routes, person_routes — 16 fixes
- **Track B** (worktree-agent-a744b14a): identity_routes — 17 HX-Redirect fixes
- **Track C** (worktree-agent-a542ed8f): compare_routes, page_routes, admin_routes — 21 fixes
- **Follow-up audit**: browse_routes, compare_routes, notification_routes, page_routes, person_routes — 14 more fixes caught by regression test

All merges clean. 4519 tests pass.

### Phase 2 — Regression Test
- `tests/test_community_prefix_audit.py` — greps all `*_routes.py` for hardcoded link patterns
- Catches: `href="/person/"`, `href="/photo/"`, `HX-Redirect", "/person/"`, etc.
- Allows known exceptions (comments, API endpoints, auth paths)

### Phase 3 — UX Fixes
- **FB-026**: `_get_confirmed_identity_suggestions()` now sorts by embedding distance (cosine) instead of face count
- **FB-052**: Confirm button in triage shows "Confirm as {Name}" when `_get_best_match_for_identity()` returns a strong match
- **FB-059**: Discovery tab shows 3 pulsing skeleton cards + "Loading discoveries..." while HTMX fetches content
- **FB-057**: Focus mode auto-advance already implemented — verified existing `get_next_focus_card()` calls in all confirm/skip/reject handlers

### Phase 4 — Deploy
- `git push origin main` triggered RAILPACK builder (known issue Lesson 117)
- `railway up` deployed with DOCKERFILE builder — SUCCESS
- Browser verified on production:
  - Fox Family landing page loads correctly
  - Similar Identities panel with community-prefixed links
  - Discovery loading skeleton visible, then content loads
  - "View photo" navigates to `/c/fox-family/photo/...`

## Commits
- `d327008` fix(P0): community prefix on discoveries, estimate, facecompare, event routes
- `eea9cb6` fix(P0): community prefix on 17 identity_routes.py HX-Redirects
- `9641ee9` fix(P0): community prefix on compare, page, admin routes
- `ddf8473` fix(P0): remaining 14 community prefix gaps + regression audit test
- `2024ced` fix(P0): community prefix on 5 more route files + FB-041 through FB-057
- `8d9ce42` docs: session 111b assessment + screenshots

## Verification Gate
- [x] All community prefix gaps fixed (80+)
- [x] Regression test prevents future gaps
- [x] All tests pass (4519 passed, excluding 1 pre-existing)
- [x] Discovery tab shows loading indicator
- [x] Deployed to production (SUCCESS)
- [x] Browser verified (PARTIAL — missed Proposals page, see post-session notes)
- [x] `git log origin/main..HEAD` is empty
- [x] Assessment written
- [x] No data file changes committed
- [x] CHANGELOG updated (v0.99.16)
- [x] ROADMAP updated (session entry, version bump)
- [x] BACKLOG updated (COMMUNITY-015 marked mostly fixed)
- [x] CI fix: test_get_photo_metadata cache ordering bug fixed
- [x] Session 111c prompt written

## Post-Session Notes
- **Proposals page is BROKEN** — no thumbnails, no actions, raw distances. Missed during browser verification. P0 for Session 111c.
- **Lesson saved**: Browser verification must check ALL admin surfaces, not just pages changed in the session.
- **CI fix**: `test_get_photo_metadata_prefers_loaded_registry_values_in_postgres_mode` — stale JSON metadata overwrote fresh registry values via `.update()`. Fixed by popping source/collection/source_url before merge. Also fixed prewarm thread race in test with `_cache_lock`.
