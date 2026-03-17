# Session 111d — Outstanding Feedback Fix Sprint

## Context
@docs/session_context/session-111d-context.md
@docs/feedback/session-111-feedback.md

Sessions 111 through 111c generated 70 feedback items during interactive Fox Family triage. About 15 were fixed. This session fixes the remaining ~25 actionable items. No new features — fix sprint only.

## Pre-Requisites
1. Read `tasks/lessons.md` + `tasks/todo.md`
2. Read `docs/feedback/session-111-feedback.md` — every FB item
3. Read `docs/session_context/session-111d-context.md` — prioritization and parallelization plan
4. Set `.claude/current_session.txt` to `111d`
5. Set `.claude/session_mode.txt` to `implementation`

---

## Phase 0: Orient + CI Fix (10 min)

1. `git log --oneline -5` — confirm 111c on main
2. Fix the pre-existing CI test failure that's sending GitHub emails:
   - `tests/test_internal_photo_links.py::TestPhotoModalShareButton::test_partial_has_public_page_link`
   - Read the test, read the current UI code it tests, fix the assertion to match reality
   - Run `make test-fast` to confirm fix
3. Commit and push so CI goes green and emails stop

---

## Phase 1: P0 Confirm Button Fix — FB-068 + FB-052 (30 min)

**The single most important fix.** The "Confirm as {Name}" button appears to do nothing.

### Investigation Steps
1. Find the confirm button's `hx_post` URL (search for `confirm_url` in `app/main.py` around line 9880)
2. Trace the endpoint handler — is it `/confirm/{identity_id}` or `/inbox/{identity_id}/confirm`?
3. Check: does the handler return a valid HTMX response that swaps `#identity-{identity_id}`?
4. Test on production: open browser console, click the button, check for HTMX errors or failed requests

### Fix
- The button says "Confirm as {Name}" but the endpoint only confirms (promotes state). It must ALSO merge with the best match when one exists.
- Modify the confirm handler: when `_get_best_match_for_identity()` returns a strong match, execute `registry.merge_identities()` with the target BEFORE confirming.
- The HTMX response must visibly update the card (success state) or remove it.
- Add a "Confirm as New Person" button as an alternative when a strong match exists.

### Tests
- Confirm with strong match: merges into matched identity
- Confirm without match: promotes to CONFIRMED as before
- HTMX response replaces the card

---

## Phase 2: P0 Performance — FB-069 + FB-025 (30 min, WORKTREE)

**Root causes from memory — implement fixes:**

### Fix 1: Targeted Supabase writes in `save_registry()`
- Currently `save_registry()` writes ALL ~3,400 identities to Supabase on every confirm
- Change to only write the identities that were modified (track dirty IDs)
- File: `app/main.py` `save_registry()` and `core/registry.py`

### Fix 2: Cache confirmed identity suggestions
- `_get_confirmed_identity_suggestions()` iterates ALL identities + computes quality scores on every call
- Add a TTL cache (30s) keyed by identity_id
- File: `app/cluster_review_routes.py`

### Fix 3: Cache speed-run cluster list
- `_get_speed_run_clusters()` recomputed on every request
- Cache for 30s, invalidate on confirm/merge/skip
- File: `app/cluster_review_routes.py`

### Tests
- Confirm action completes in <2s (was 5-10s)
- Second call to suggestions endpoint returns cached result
- Cache invalidation works after merge

---

## Phase 3: P0 Photo Overlay + Tagging — FB-066 + FB-036/037 (30 min, WORKTREE)

### FB-066: Green checkmark doesn't work
1. Read the quick-action endpoint: `app/identity_routes.py` `/api/face/quick-action`
2. Read the button generation: `app/page_routes.py` around line 3999
3. The button targets `#photo-modal-content` — verify this element exists in the photo modal DOM
4. Check: does the endpoint return a valid response? Does it set correct headers?
5. Test: use browser console → Network tab → click green checkmark → check request/response
6. Fix the issue (likely HTMX target mismatch or response format)

### FB-036/037: Speed Loop tagging doesn't persist
1. Find the tag assignment endpoint: search for `/api/face/tag` in `app/identity_routes.py`
2. Trace the save path: does it call `save_registry()`? Does save succeed?
3. Check if the endpoint returns a success response or silently fails
4. Fix: ensure tag assignment persists and returns visible confirmation

### Tests
- Quick-action confirm changes face overlay color (green = confirmed)
- Tag assignment persists after page reload
- Tag assignment returns success toast

---

## Phase 4: P1 UX Fixes (30 min, WORKTREE)

These are independent fixes that can run in parallel with Phase 2/3.

### FB-057: Focus mode doesn't auto-advance
- Confirm/skip/reject handlers in `app/identity_routes.py` should return the next focus card
- Check: is `from_focus=true` being passed? Does the response target `#focus-container`?
- Fix: ensure handlers return `get_next_focus_card()` result when `from_focus=true`

### FB-040: Stale card after merge
- Merge handler already has OOB delete for `#identity-{source_id}`
- Check: does the card have `id="identity-{source_id}"` in the DOM?
- Fix: ensure card IDs match the OOB delete targets

### FB-054/058: Thumbnail mismatch
- Use `get_best_face_id()` consistently in both neighbor_card and person page
- File: `app/main.py` neighbor_card rendering

### FB-048: "View Person" link in tag popup
- Add link to `/person/{identity_id}` in the tag dropdown bottom actions
- File: `app/page_routes.py` around line 3958

### FB-065: Post-merge findability
- Modify `search_identities()` in `core/registry.py` to include merged identities
- Return with `merged_into_name` field so UI can show "Merged into {Name}"
- Show in search results: "Person 3053 → merged into Charles Fox"

### FB-031: Face grid distorted
- Remove `min-w-[150px]` from face_card, use responsive grid
- File: `app/main.py` face_card rendering

### FB-051: Photo filename search
- Verify `/api/search` photo results include community prefix in links
- Test: search for a filename on production

### FB-030: Cluster count persistence
- Store reviewed count in server-side session or pass through URL chain
- File: `app/cluster_review_routes.py`

### FB-064: Override redirect verification
- Test on production: open Fox Family focus mode, find a co-occurrence blocked merge, click Override
- If redirect is wrong, fix the nav_prefix in the override button URL

### Tests
- Focus mode auto-advances after confirm
- Merged identity card removed from DOM
- Search for merged identity finds the target
- Face grid renders cleanly in narrow container

---

## Phase 5: P2 Fixes (15 min — as time allows)

### FB-028: Toast persistence
- Use OOB swap to keep toast visible across HTMX swaps

### FB-038: "View More" preserves checkboxes
- Change pagination from innerHTML to beforeend swap
- Store checked IDs in hidden input

### FB-044: Best match excluded from Similar list
- Filter out the best match identity_id from the neighbors query

---

## Phase 6: Deploy + Verify (15 min)

1. `git push origin main`
2. Wait for deploy SUCCESS (use `mcp__railway-mcp-server__list-deployments`)
3. Verify builder is `DOCKERFILE` (not `RAILPACK`)
4. **MANDATORY production checks:**
   - [ ] "Confirm as {Name}" button works — merges and shows feedback
   - [ ] Green checkmark on photo overlay confirms face
   - [ ] Speed Loop tagging persists after refresh
   - [ ] Focus mode auto-advances after confirm
   - [ ] Search for a merged identity (e.g. "3053") finds the target
   - [ ] Search for identity beyond card 150 works
   - [ ] Select All in Similar Identities works
   - [ ] GitHub CI is green (no more failure emails)
   - [ ] Speed-run confirm feels faster (<2s)
5. Screenshots to `docs/screenshots/session-111d/`

---

## Phase 7: Harness Outputs (10 min)

1. **Assessment:** `docs/assessments/session-111d-assessment.md`
2. **Feedback file:** Update `docs/feedback/session-111-feedback.md` — mark ALL fixed items
3. **BACKLOG:** Update status for all resolved items
4. **ROADMAP:** Add session entry, update version
5. **CHANGELOG:** Session 111d entry
6. **Session log:** `docs/session_logs/session-111d-log.md`
7. **Verify:** `git log origin/main..HEAD` is empty (Lesson 148)

---

## Parallelization Plan

Use git worktrees for independent tracks:

| Track | Phases | Files Touched | Can Parallel? |
|-------|--------|---------------|---------------|
| Main | 0, 1, 6, 7 | `app/main.py`, `app/identity_routes.py`, tests, docs | Sequential |
| Worktree A | 2 (Performance) | `core/registry.py`, `app/cluster_review_routes.py` | Yes |
| Worktree B | 3 (Photo overlay + tagging) | `app/page_routes.py`, `app/identity_routes.py` (tag endpoints only) | Yes |
| Worktree C | 4 (P1 UX batch) | `app/main.py` (neighbor_card), `core/registry.py` (search) | After Track A merges |

**Merge order:** A → B → C → Main (run tests after each merge)

**CRITICAL:** Track C touches `app/main.py` and `core/registry.py` — must merge AFTER Track A to avoid conflicts.

---

## Verification Checklist (before declaring done)

- [ ] "Confirm as {Name}" button merges with suggested match
- [ ] Green checkmark on photo overlay works
- [ ] Speed Loop tagging persists
- [ ] Focus mode auto-advances
- [ ] Performance: confirm action <2s
- [ ] GitHub CI is green
- [ ] Search finds merged identities
- [ ] All tests pass
- [ ] Deployed and pushed
- [ ] `git log origin/main..HEAD` is empty
- [ ] Assessment written with evidence
