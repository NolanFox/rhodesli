# Session 111f — Final Sprint: Performance Overhaul + Remaining Fixes

## Context
@docs/session_context/session-111f-context.md
@docs/feedback/session-111-feedback.md
@docs/feedback/session-111d-interactive-feedback.md

This is the FINAL session in the 111 series. Every remaining FB item must be resolved. The #1 priority is performance — the site is too slow to use for triage. Secondary: close all partial fixes and verify deferred items.

## CRITICAL CONSTRAINTS
1. **ZERO REGRESSIONS.** Run full test suite before AND after every phase. Compare test counts.
2. **NEVER click action buttons on production.** Browser is READ-ONLY (Lesson 149).
3. **DO NOT modify Session 112 target functions:** `load_registry()`, `save_registry()`, `_build_caches()`, `_load_photo_dimensions_cache()`, or any `DATA_SOURCE` branches in `app/main.py`. See context file for full list.
4. **`core/neighbors.py` is FROZEN.** Add new functions alongside, update callers. Never modify existing functions.
5. **Plan before coding.** Write your approach for each phase BEFORE writing code. Think about 2nd and 3rd order effects.
6. **SDD where applicable.** Write acceptance tests BEFORE implementation for any behavior change.
7. **/clear between acts.** Non-negotiable. Commit, then /clear.

## Pre-Requisites
1. Read `tasks/lessons.md` — especially Lessons 149, 150
2. Read `docs/session_context/session-111f-context.md` — full analysis + Session 112 conflicts
3. Read `docs/prompts/session-112-prompt.md` — know what 112 will touch
4. Set `.claude/current_session.txt` to `111f`
5. Set `.claude/session_mode.txt` to `implementation`
6. Run `make test-fast` — record baseline test count

---

## Phase 0: Orient + Plan (10 min)

1. `git log --oneline -5` — confirm 111e complete
2. Read context file for the full remaining work list
3. Read Session 112 prompt to understand conflict zones
4. Write a brief plan for each subsequent phase, noting:
   - What files will be touched
   - What could go wrong (2nd/3rd order effects)
   - What tests will verify the change
5. Verify current test counts (baseline)

---

## Phase 1: Performance — Vectorized Distance Computation (45 min)

**The single highest-impact change. Replaces O(N) Python-loop cdist with vectorized matrix multiply.**

### 1A: Build a precomputed confirmed-identity embedding matrix

Create a new module `app/perf_cache.py` (keeps main.py clean, avoids 112 conflicts):

```python
# Confirmed identity embedding matrix — precomputed for fast cosine distance
# Rebuilt lazily when confirmed identities change (confirm/merge only)
_confirmed_matrix = None       # shape (num_confirmed_faces, 512), L2-normalized
_confirmed_face_map = None     # list of (identity_id, face_id) tuples, parallel to matrix rows
_confirmed_dirty = True        # rebuild on next access

def mark_confirmed_dirty():
    """Called on confirm/merge only — NOT on skip/reject."""
    global _confirmed_dirty
    _confirmed_dirty = True

def get_confirmed_distances(target_embedding, community_slug=None):
    """Return sorted list of (identity_id, min_distance) for all confirmed identities.
    Uses vectorized np.dot instead of per-face cdist loops.
    """
    # Lazy rebuild if dirty
    # Normalize target, dot product with matrix, group by identity, return top-k
```

### 1B: Rewire `_get_confirmed_identity_suggestions()` to use the matrix

In `app/cluster_review_routes.py`:
- Replace the Python loop over all identities + per-face `cdist` calls
- Call `get_confirmed_distances(target_embedding, community_slug)`
- Keep the community-scoping logic (same vs cross community)
- Keep the 30s TTL cache from 111e as a second layer

### 1C: Smart cache invalidation

In `app/main.py` `save_registry()`:
- KEEP `invalidate_cluster_review_caches()` call (removes stale cache entries)
- CHANGE `invalidate_neighbors_cache()`: only invalidate the specific identity, not ALL entries
- ADD `mark_confirmed_dirty()` call — but ONLY when the action is confirm or merge, not skip/reject

In `app/identity_routes.py`:
- Modify `invalidate_neighbors_cache()` to accept an optional `identity_id` parameter
- When provided, only remove that identity's cache entry
- When None, flush all (for upload/sync paths)

### 1D: Optimized neighbor search

In `core/neighbors.py`, ADD (do not modify existing):
```python
def find_nearest_neighbors_fast(target_identity_id, registry, face_data, photo_registry, ...):
    """Vectorized version of find_nearest_neighbors.
    Builds a global normalized embedding matrix and uses np.dot for batch distance.
    """
```

Update the caller in `app/identity_routes.py` `/api/identity/{identity_id}/neighbors` to use the fast version.

### Tests
- Vectorized distances match loop-based distances (within floating point tolerance)
- Cache is NOT invalidated on skip/reject
- Cache IS invalidated on confirm/merge
- Confirmed matrix rebuilds after confirm
- Suggestions return same results as before (regression test)

### 2nd/3rd Order Effects to Watch
- **Floating point:** Vectorized `np.dot` may give slightly different results than per-face `cdist(metric="cosine")`. Use `np.allclose(atol=1e-6)` in tests.
- **Memory:** Matrix is ~1MB for current data. Log the size.
- **Thread safety:** Matrix rebuild is not atomic. Use a lock or copy-on-write.
- **Empty confirmed list:** Handle 0 confirmed identities gracefully (return empty).

---

## Phase 2: Tag Persistence Fix — FB-036/037 (20 min)

**Tags don't persist. Warning toast was added but root cause is unresolved.**

### Investigation
1. Read the tag/assign endpoint in `app/identity_routes.py`
2. Trace the save path: does it use `save_registry(changed_ids=...)`?
3. Check if the Supabase write is synchronous or background thread
4. Check if any error is being swallowed by `except: pass`

### Likely Fix
- If background thread: make synchronous for tags (user expects immediate persistence)
- If `except: pass`: surface the error
- If `changed_ids` is missing: add it

### Tests
- Tag assignment endpoint returns success and tag persists in registry
- Tag assignment with Supabase failure returns error toast (not false success)

---

## Phase 3: Browse Mode Stale Card — FB-040 (15 min)

**After merge in browse mode, the merged-from card stays visible.**

### Fix
In the merge handler in `app/identity_routes.py`, for the non-focus, non-person-page path:
- Add an OOB swap element that removes `#identity-{source_id}` from the DOM
- Use `hx_swap_oob="delete:#identity-{actual_source_id}"` (HTMX delete swap)

### Tests
- Merge response includes OOB delete element for source identity card
- Source identity card ID matches the OOB target

### 2nd Order Effect
- The source card might not have `id="identity-{source_id}"` in all views. Verify the card ID format in browse_routes.py vs main.py rendering.

---

## Phase 4: Production Verification + Quick Wins (20 min)

### Verify on production (READ-ONLY):
- **FB-064:** Override merge redirect — read the override button's `hx-post` URL via JS, verify it includes community prefix
- **FB-076:** Approve endpoint community — read the approve button's target URL, verify community context
- **FB-057:** Focus mode auto-advance — read the focus container DOM after a page load, verify it has correct hx-target
- **FB-030:** Cluster count — read localStorage for the counter key, verify it persists

### Quick wins (if time):
- **FB-044:** Add "Best Match" badge to the matching entry in Similar list instead of filtering it out
- **FB-038:** Change Load More button's hx-swap from "innerHTML" to "afterend" to preserve checkboxes

### Document ALL verifications
Log every verification result (PASS/FAIL + evidence) in session log.

---

## Phase 5: Deploy + Comprehensive Verify (15 min)

1. Run BOTH test suites: `pytest tests/` AND `pytest rhodesli_ml/tests/`
2. `git push origin main`
3. Deploy via `railway up` (not git push — avoids RAILPACK builder issue)
4. Wait for SUCCESS status
5. **MANDATORY production checks (READ-ONLY):**
   - [ ] Focus mode loads in <3s (was 5-10s)
   - [ ] Speed-run cluster loads in <2s
   - [ ] Enrichment panel (suggestions) loads in <1s
   - [ ] Discovery tab shows loading skeleton, then content
   - [ ] Tag assignment persists (verify via DOM read, NOT by clicking)
   - [ ] Merged card removed in browse mode
   - [ ] Focus mode URL preserved after action
   - [ ] Approval history visible on /admin/approvals
   - [ ] Face overlays present on Rhodes photos
   - [ ] Override merge button has correct community prefix
6. `git log origin/main..HEAD` is empty

---

## Phase 6: Harness Outputs (10 min)

1. **Assessment:** `docs/assessments/session-111f-assessment.md`
   - Every FB item from FB-025 to FB-077 with final status
   - Performance measurements (before/after if available)
   - Red flags and deferred items with BACKLOG IDs
2. **Session log:** `docs/session_logs/session-111f-log.md`
3. **Feedback files:** Update BOTH feedback files — mark ALL items as FIXED/DEFERRED with session reference
4. **ROADMAP:** Add session entry, update version to v0.99.20
5. **CHANGELOG:** Session 111f entry with all fixes
6. **BACKLOG:** Update status for all resolved items
7. `git log origin/main..HEAD` is empty

---

## Parallelization Plan

| Track | Phase | Files Touched | Dependencies |
|-------|-------|---------------|-------------|
| Main | 0, 5, 6 | docs, config | Sequential |
| Worktree A | 1A+1B (vectorized distance) | `app/perf_cache.py` (NEW), `app/cluster_review_routes.py` | None |
| Worktree B | 1C+1D (smart invalidation + fast neighbors) | `app/identity_routes.py`, `core/neighbors.py` (ADD only) | None |
| Worktree C | 2+3 (tag fix + stale card) | `app/identity_routes.py` (tag endpoints), `app/main.py` (merge OOB) | None |

**Merge order:** A → B → C (B touches identity_routes.py, C touches it too — merge B first, resolve conflicts in C)

**CRITICAL merge safety:**
- After each merge: run `make test-fast`
- After all merges: run full test suite
- Track A and B can run simultaneously (different files)
- Track C can run simultaneously with A (different functions in identity_routes.py) but must merge AFTER B

---

## Verification Checklist (before declaring done)

- [ ] Performance: suggestions endpoint <1s (was 3-5s)
- [ ] Performance: focus mode total load <3s
- [ ] Performance: neighbor cache NOT blown on skip/reject
- [ ] Tag persistence: tags survive page reload
- [ ] Stale card: merged-from card removed in browse mode
- [ ] All FB items FB-025 to FB-077 have final status documented
- [ ] Tests: app tests pass (count ≥ previous)
- [ ] Tests: ML tests pass
- [ ] Tests: new tests for vectorized distance, cache invalidation, tag persistence
- [ ] Deployed and pushed
- [ ] `git log origin/main..HEAD` is empty
- [ ] Assessment written with evidence
- [ ] Session 112 functions untouched (grep to verify)
