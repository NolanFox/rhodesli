# Session 141 Context — Fix Sprint + Refactor + Hardening

**Predecessor:** Session 140 (v0.99.51) — P0 auth fix + OAuth redirect
**Date:** 2026-03-27

## What Sessions 138-140 Delivered
- 13 feedback items, 8 fixed (FB-001/004/005/006/008/011/012/013/014)
- Auth fully restored (broken since Session 90b)
- 418 missing crops regenerated
- People page name filter, bulk merge auto-advance, Edit in Admin deep link
- Performance: dict lookup O(1), best_face_id cache
- REFACTOR-001 Phase 2: 848 lines from main.py

## Outstanding Items (7 total)

### 1. Structural test for _main_mod references (Lesson 157)
- Prevent another auth-style regression
- Test that all `_main_mod.X` refs across all route files resolve to real attributes
- Python script already proven: `for ref in re.findall('_main_mod\.(\w+)', content): assert hasattr(app.main, ref)`
- Also: scan for `create=True` in test patches and warn

### 2. FB-002: Link to merged identity result
- After merge in focus mode, show "View merged result → [Name]" link in toast
- The toast already renders via OOB swap — just need to include a link to the surviving identity's person page
- Key code: identity_routes.py merge handler (~line 2338), toast_with_undo in main.py

### 3. FB-003: Merge auto-confirm (needs PRD analysis)
- User wants: merge → auto-confirm → advance
- Risk: Session 111d showed auto-merge on confirm caused data loss
- Need to analyze: when is auto-confirm safe? (Only when merging INTO a confirmed identity? Only when the surviving identity has a name?)
- PRD scope: define auto-confirm rules with safety constraints

### 4. FB-007: Choose hero face thumbnail
- Google Photos lets you pick which face is the "hero" for a person
- Current: `get_best_face_id()` picks by quality score
- Need: admin UI button on face cards to "Set as Primary"
- Storage: add `primary_face_id` field to identity record
- `get_best_face_id()` checks primary_face_id first, falls back to quality

### 5. REFACTOR-001 Phase 3: identity_card extraction
- identity_card (574 lines) + identity_card_expanded (282 lines) = 856 lines
- 18+ dependencies on main.py module-level caches
- Research agent completed full dependency map (Session 139 context)
- Estimated: main.py 9,790 → ~8,940

### 6. Performance: heapq sort + parallel cold start
- Focus mode sort uses `sorted()` on all ~1500 items, then takes top 10
- Fix: `heapq.nsmallest(10, items, key=_focus_sort_key)`
- Cold start: parallelize Supabase fetches with ThreadPoolExecutor

### 7. TOOLS-005: Estimate v2 (if time permits)
- GEDCOM upload + text hints + geography retry
- PRD-055 exists, 13 xfail test skeletons ready
- Multi-session scope — start with text hints (simplest)

## Parallelization Plan
```
Track A (worktree): Structural test + FB-002 toast link (independent, small files)
Track B (worktree): FB-007 hero face picker (independent, touches identity_routes + main.py cards)
Track C (worktree): Performance heapq + cold start (independent, touches main.py sort + startup)
Track D (sequential after merge): REFACTOR-001 Phase 3 (touches main.py heavily)
Track E (worktree): FB-003 PRD analysis (docs only, independent)
```
Tracks A, B, C, E can run in parallel worktrees.
Track D must run after A/B/C merge (all touch main.py).

## Key Files
- app/identity_routes.py — merge handler, bulk merge
- app/main.py — identity_card, get_best_face_id, startup, sort
- app/perf_cache.py — neighbors, global matrix
- core/registry.py — confirm_identity, identity state
- tests/conftest.py — cache resets for xdist
