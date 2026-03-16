# Session 111b — Community Prefix Comprehensive Sweep + UX Fix Sprint

## Context
@docs/session_context/session-111b-context.md
@docs/feedback/session-111-feedback.md

## Pre-Requisites
1. Read `tasks/lessons.md` + `tasks/todo.md`
2. Read `docs/feedback/session-111-feedback.md` — FB-025 through FB-063
3. Read session-111b-context.md — full audit results with line numbers
4. Set `.claude/current_session.txt` to `111b`
5. Set `.claude/session_mode.txt` to `implementation`

---

## Phase 0: Orient + Verify Session 111 Fixes (5 min)

1. `git log --oneline -8` — confirm 4 Session 111 commits are on main
2. `git push origin main` — deploy Session 111 fixes
3. Run `make test-fast` — confirm baseline passes (known pre-existing failure: `test_partial_has_public_page_link`)
4. Verify no uncommitted data files: `git diff --name-only` — `data/identities.json` is production-origin, do NOT commit (Lesson 141)

---

## Phase 1: Community Prefix Sweep — Parallel Worktree Execution (45 min)

### Problem
66+ user-facing links across 8 route files are hardcoded without `/c/{slug}/` prefix. This is the #1 recurring user complaint (FB-041, FB-047, FB-063). Prior sessions fixed individual files reactively. This phase does a comprehensive sweep.

### The Correct Pattern (from browse_routes.py)
```python
# In route handlers with request parameter:
community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
nav_prefix = _main_mod.community_url_prefix(community_slug)

# Or use the helper in identity_routes.py:
nav_prefix = _nav_prefix_from_request(request)

# Then ALL user-facing links use nav_prefix:
href=f"{nav_prefix}/person/{identity_id}"
href=f"{nav_prefix}/photo/{photo_id}"
hx_get=f"{nav_prefix}/api/identity/{identity_id}/neighbors"
HttpHeader("HX-Redirect", f"{nav_prefix}/person/{canonical_id}")
```

### Safety Rules — READ BEFORE TOUCHING ANY FILE
- **Do NOT modify `/api/` endpoint URLs** — they are skipped by CommunityMiddleware
- **Do NOT change function behavior** — only add `nav_prefix` to link string interpolation
- **Do NOT remove existing nav_prefix usage** — only ADD where missing
- **Adding `request=None` to a handler signature is OK** when needed for nav_prefix
- **Adding `nav_prefix` parameter to helper functions is OK** — but preserve backwards compatibility with `nav_prefix=""` default
- **Run tests after every file** — no regressions tolerated
- **Do NOT touch data files** — `data/identities.json` is production-origin (Lesson 141)

### Parallelization Strategy — 3 Worktree Tracks

File overlap analysis: ALL target files are independent (each subagent edits different `.py` files). Zero merge conflict risk.

**Track A** (worktree: `session-111b/track-a`): Small standalone files
- `app/discoveries_routes.py` — 9 gaps. Key fix: pass `nav_prefix` into `_build_discovery_card()` helper. Lines: 725, 737, 763, 784, 886, 908, 953, 1041, 1175
- `app/estimate_routes.py` — 3 gaps. File has NO community awareness — add `request=None` to handlers, extract `nav_prefix`. Lines: 102, 216, 443
- `app/match_facecompare_routes.py` — 2 gaps. Already has `nav_prefix` in some places. Verify lines 715, 724 still need fixing.
- `app/event_routes.py` — 2 gaps. Already has `community_slug` in some handlers. Verify lines 303, 905.

**Track B** (worktree: `session-111b/track-b`): identity_routes.py (17 HX-Redirect gaps)
- `app/identity_routes.py` — 17 `HttpHeader("HX-Redirect", ...)` missing nav_prefix.
- File already has `_nav_prefix_from_request()` helper and uses it in many places — just not in the redirects.
- Lines: 96, 368, 1545, 1548, 1604, 1607, 1773, 1776, 2162, 2238, 2554, 3339, 3443, 3540, 3629, 3757, 3871.
- For each: verify handler has `request` param, extract `nav_prefix`, use in redirect URL.

**Track C** (worktree: `session-111b/track-c`): compare + page + admin
- `app/compare_routes.py` — 9 gaps ADDITIONAL to Session 111 fix. Main GET route (line 42) may need `request` parameter. Lines: 702, 826, 2577, 2582, 2963, 3556, 3559, 5795, 5808.
- `app/page_routes.py` — 5 gaps. Line 516 has hardcoded `/c/{slug}/upload` instead of using `community_url_prefix()`. Lines: 516, 919, 12607, 12674, 733-734.
- `app/admin_routes.py` — verify minor gaps (photo links). May already be fixed from Session 111.

### Execution Order
1. Create `.claude/parallel_session_active` to block main commits
2. Launch 3 worktree subagents in parallel (Agent tool with `isolation: "worktree"`)
3. Each subagent: fix all gaps in assigned files → run `pytest tests/ -x -q --ignore=tests/e2e -k "not test_partial_has_public_page_link"` → commit
4. After all 3 complete: `./scripts/merge.sh session-111b/track-a session-111b/track-b session-111b/track-c`
5. Run full test suite on merged main
6. Remove `.claude/parallel_session_active`
7. Single commit message: `fix(P0): community prefix sweep — 66 gaps across 8 route files`

### Each Subagent Must:
1. Read the AUDIT LINE NUMBERS from session-111b-context.md for their assigned files
2. For each gap: read surrounding code, verify it's actually missing `nav_prefix`, fix it
3. **VERIFY each fix**: the line should now have `{nav_prefix}` in the link string
4. Run tests for the specific files they touched
5. Commit with descriptive message including file list

---

## Phase 2: Regression Prevention Test (15 min)

After Phase 1 merge, add a test that PREVENTS future community prefix regressions.

**File:** `tests/test_community_prefix_audit.py`

```python
"""
Regression test: all user-facing links in route files must use nav_prefix.
Greps for common hardcoded link patterns and fails if found.
Prevents the community prefix whack-a-mole pattern (Lessons 109, 111).
"""
```

Test should:
1. Grep all `app/*_routes.py` files for patterns like:
   - `href="/person/` (should be `href=f"{nav_prefix}/person/`)
   - `href="/photo/` (should be `href=f"{nav_prefix}/photo/`)
   - `href="/compare?` (should be `href=f"{nav_prefix}/compare?`)
   - `href="/identify/` (should be `href=f"{nav_prefix}/identify/`)
   - `href="/timeline?` (should be `href=f"{nav_prefix}/timeline?`)
   - `HX-Redirect", "/person/` (should include `nav_prefix`)
   - `HX-Redirect", "/?` (should include `nav_prefix`)
2. Allow KNOWN exceptions (e.g., links inside string literals that aren't rendered)
3. Fail with descriptive message showing file, line, and the hardcoded pattern

---

## Phase 3: Top UX Fixes — Sequential (30 min)

After Phase 1+2 are merged and green, fix these P0/P1 items sequentially:

### Fix 1: FB-057 — Focus mode auto-advance after action (P1)
- After confirm/skip/reject in Focus mode, HTMX response should swap in next identity card
- Currently requires manual page refresh — defeats the purpose of Focus mode
- File: `app/identity_routes.py` confirm/skip/reject handlers — check HTMX return targets
- File: `app/main.py` Focus mode rendering — check swap targets
- Test: Confirm in Focus mode returns next identity card (not empty response)

### Fix 2: FB-026 — Suggested matches sorted by ML similarity not face count (P1)
- `_get_confirmed_identity_suggestions()` in `app/cluster_review_routes.py` sorts by `-s["face_count"]`
- Should sort by embedding distance so the closest ML match appears first
- This directly impacts triage efficiency — user sees best match first instead of biggest identity
- Test: Suggestions returned in ascending distance order

### Fix 3: FB-059 — Discovery tab loading indicator (P1)
- Add `hx-indicator` with skeleton placeholder so users know it's loading
- Quick win — 5 minute fix, big perceived performance improvement
- File: `app/main.py` or `app/discoveries_routes.py` — wherever the Discovery tab trigger is

### Fix 4: FB-052 — "Confirm" shows merge with suggested match context (P0 UX — partial)
- Full fix needs PRD-level design. But partial fix NOW:
- When STRONG MATCH exists, add text to Confirm button: "Confirm as {Name}"
- Add a separate smaller "Confirm as New Person" link below
- This alone saves the user from the most confusing UX moment
- File: `app/main.py` `identity_card()` function

Commit after each fix. Run tests before each commit.

---

## Phase 4: Deploy + Browser Verify (15 min)

1. `git push origin main`
2. Wait for deploy, verify with `mcp__railway-mcp-server__list-deployments`
3. Browser verify on production (Claude Chrome — admin is logged in):
   - `/c/fox-family/` → New Matches → click a person → verify Similar Identities links have `/c/fox-family/` prefix
   - `/person/{fox-family-person-id}` without prefix → verify auto-redirect to `/c/fox-family/person/{id}`
   - Discovery tab → verify loading indicator shows → verify links have prefix
   - Focus mode → confirm → verify auto-advance to next card
   - Bulk merge → verify human-readable failure reasons
4. Screenshots to `docs/screenshots/session-111b/`

---

## Phase 5: Harness Outputs (10 min)

1. **Assessment:** `docs/assessments/session-111b-assessment.md` — per-phase PASS/FAIL with evidence
2. **Feedback file:** Update `docs/feedback/session-111-feedback.md` — mark FIXED items
3. **BACKLOG:** Update status for resolved items
4. **ROADMAP:** Update COMMUNITY-016 status
5. **CHANGELOG:** Session 111b entry
6. **SESSION_LOG:** Update and archive
7. **Verify:** `git log origin/main..HEAD` is empty (Lesson 148)

---

## Verification Checklist (before declaring done)

- [ ] All 66+ community prefix gaps fixed (Phase 1)
- [ ] Regression test prevents future gaps (Phase 2)
- [ ] All tests pass (excluding known pre-existing: `test_partial_has_public_page_link`)
- [ ] Focus mode auto-advances (Phase 3 Fix 1)
- [ ] Suggestions sorted by ML similarity (Phase 3 Fix 2)
- [ ] Discovery tab shows loading indicator (Phase 3 Fix 3)
- [ ] Confirm button shows merge context (Phase 3 Fix 4)
- [ ] Deployed to production
- [ ] Browser verified with screenshots
- [ ] `git log origin/main..HEAD` is empty
- [ ] Assessment written with evidence
- [ ] No data file changes committed (Lesson 141)

## Reference: Test Verification Identities

| Identity | Community | Use For |
|----------|-----------|---------|
| Debbie Fox Schapiro (67e830ac) | Both Rhodes + Fox | Test auto-redirect from `/person/67e830ac...` |
| Person 3037 | Fox Family | Test Similar Identities links from Debbie's page |
| Person 3462 | Fox Family | Test Similar Identities links from Debbie's page |
| Esther Burd Fox | Fox Family | Test speed-run suggested match sorting |
| Charles Fox | Fox Family | Test Focus mode auto-advance after confirm |
