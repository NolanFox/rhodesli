# Session 125 — Performance Completion + UX Quick Wins

@docs/session_context/session-125-context.md
@docs/session_context/session-123-codex-perf-audit.txt
@tasks/lessons.md

## Goal

Complete all remaining Codex performance findings (#1, #4, #6, #8, #10) and ship 15+ UX quick wins. Three parallel tracks: you handle complex perf, Codex handles contained fixes, Antigravity handles CSS/template. You are the orchestrator — merge their output, run tests, deploy, verify.

## CRITICAL CONSTRAINTS

1. **Browser automation is READ-ONLY on production** (Lesson 149).
2. **DO NOT touch**: `core/neighbors.py` (frozen), `core/pfe.py`, `data/*` files.
3. **Every change gets tests** — happy path + failure + regression.
4. **/clear between phases** — commit first, then /clear immediately.
5. **File ownership**: You own `app/main.py` and `app/cluster_review_routes.py`. Codex owns `app/perf_cache.py`, `app/browse_routes.py`, `app/identity_routes.py`. Antigravity owns `app/page_routes.py`, `app/person_routes.py`. Do NOT touch files owned by others.
6. **Safety first**: If a perf optimization seems risky, skip it and log to BACKLOG. No regressions.
7. **No data issues**: Never modify JSON data files. Supabase writes only through existing save functions.
8. **Gap check**: Re-read this prompt at end. Auto-fix any gaps.

## Pre-Requisites

```bash
echo "125" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline — must pass
```

Read: `docs/session_context/session-125-context.md`

---

## Phase 0: Orient + Execute SQL Indexes (5 min)

1. Create session log `docs/session_logs/session-125-log.md`
2. Execute community indexes on Supabase:
```python
# Use Python with load_dotenv() to get Supabase credentials
from dotenv import load_dotenv
load_dotenv()
# Then use supabase client to execute:
# CREATE INDEX IF NOT EXISTS idx_photo_communities_community_id ON photo_communities (community_id);
# CREATE INDEX IF NOT EXISTS idx_identity_communities_community_id ON identity_communities (community_id);
```
3. Verify indexes exist with a Supabase query.

**Commit:** `infra: session 125 phase 0 — community indexes executed on Supabase`
**/clear**

---

## Phase 1: PERF #6 — Unified Embeddings Parse (45 min)

### The Problem
`embeddings.npy` (12MB, ~3500 faces) is parsed THREE separate times into THREE caches:
1. `get_face_data()` → face_id → {mu, det_score, quality} dict
2. `load_embeddings_for_photos()` → photo grouping for face overlays
3. `get_crop_files()` → set of crop filenames

### The Fix
1. Read `core/embeddings_io.py` and `app/main.py` to understand all three parse paths
2. Create a unified parse in `_build_caches()` that loads embeddings.npy ONCE
3. Derive all three views from the single parse
4. The three existing functions become thin accessors over the cached data
5. Backward-compatible API — callers don't change

### Key constraint
- `get_face_data()` is called from many places — it must return the SAME dict format
- `get_crop_files()` returns a set — same contract
- Thread safety: use the same `_cache_lock` pattern already in main.py

### Tests
- Test unified cache populates all three views
- Test get_face_data() returns same format as before
- Test get_crop_files() returns same set as before
- Test single np.load call (mock np.load, verify called once)

**Commit:** `perf: session 125 phase 1 — unified embeddings parse (Codex #6)`
**/clear**

---

## Phase 2: PERF #1 — Registry Cache SWR (30 min)

### The Problem
`load_registry()` uses a 120s TTL cache. On TTL miss, the calling HTTP request blocks while Supabase reloads ALL identities (~200ms+). Multiple concurrent requests all trigger redundant reloads.

### The Fix
Stale-while-revalidate pattern:
1. Add module-level `_registry_refresh_lock = threading.Lock()`
2. When TTL expires: return stale cache immediately, spawn background thread to refresh
3. Background thread acquires lock (non-blocking `acquire(blocking=False)`)
4. If lock already held → another thread is refreshing → skip, return stale
5. On refresh complete → update cache timestamp

### Key constraint
- NEVER block a request on registry refresh
- If Supabase is down, serve stale indefinitely (existing behavior)
- First request after cold start still blocks (no stale to serve) — this is fine

### Tests
- Test stale cache is returned when TTL expired (not blocking)
- Test only one refresh thread runs at a time (lock prevents thundering herd)
- Test fresh cache is used after background refresh completes
- Test cold start still works (no stale to serve → blocks as before)

**Commit:** `perf: session 125 phase 2 — registry SWR refresh (Codex #1)`
**/clear**

---

## Phase 3: PERF #4 — Cold Start Optimization (30 min)

### The Problem
`startup_event()` does too much sequentially: disk cleanup, Supabase health check, full sync, cache prewarm, parity check. Server doesn't accept requests until all complete.

### The Fix
1. Read `startup_event()` in main.py (search for `@app.on_event("startup")`)
2. Keep only essential sync (mkdir, disk cleanup) in the main startup path
3. Move Supabase health check, sync, and parity check into the existing background prewarm thread
4. Server accepts requests immediately — lazy loading handles missing caches

### Key constraint
- The app already has lazy cache loading (`load_registry()`, `get_face_data()`, etc.)
- Don't remove any functionality — just defer it to background
- Health endpoint must still work (it checks cache state, not startup completion)

### Tests
- Test startup completes without Supabase (graceful degradation)
- Test caches are populated after background prewarm

**Commit:** `perf: session 125 phase 3 — cold start optimization (Codex #4)`
**/clear**

---

## Phase 4: cluster_review_routes.py Bundle (45 min)

Four co-located fixes in the same file:

### 4A: PERF #10 — Surgical Cache Invalidation
- Find remaining `_invalidate_all_caches()` calls in cluster_review_routes.py
- Change to `invalidate_cluster_review_caches(changed_ids={identity_id})`
- Verify `save_registry()` callers already pass `changed_ids` (Session 123 PERF-B)

### 4B: FB-161 — Speed-Run Skip Re-appearance
- Dismissed/skipped identities reappear in speed-run queue
- Add `reviewed_ids` parameter tracking: accumulate confirmed/rejected/skipped/dismissed IDs
- Pass through as hidden param or query string, filter in `_get_speed_run_clusters()`

### 4C: UX-076 — Speed-Run Reject Advance
- Verify reject action advances to next card (should call `_speed_run_next_card`)
- If not advancing, fix the return path

### 4D: FB-151 — Suggestion Name Truncation
- Find where suggestion names are truncated in speed-run cards
- Increase max-width or use `title` attribute for full name on hover

### Tests
- Test surgical invalidation only clears affected identities
- Test reviewed_ids accumulates and filters correctly
- Test reject returns a new card (not empty)
- Test full name is accessible (title attribute or wider display)

**Commit:** `perf+fix: session 125 phase 4 — cluster review bundle (Codex #10, FB-161, UX-076, FB-151)`
**/clear**

---

## Phase 5: UX-080 — 404 Page Styling (5 min)

- Find the 404 handler in main.py
- Add Tailwind classes for consistent dark theme styling
- Include a "Back to Home" link

**Commit:** `fix(ux): session 125 phase 5 — styled 404 page (UX-080)`
**/clear**

---

## Phase 6: Merge Codex + Antigravity + Final Verification (30 min)

### 6A: Check for Codex output
- Look for branch `session-125/codex-fixes` or uncommitted Codex changes
- If Codex committed: `./scripts/merge.sh session-125/codex-fixes`
- If Codex made direct changes: review diff, run tests, commit
- If no Codex output: note in assessment, items go to BACKLOG

### 6B: Check for Antigravity output
- Look for branch `session-125/antigravity-ux` or file changes in page_routes.py/person_routes.py
- If found: review diff, run tests, merge/commit
- If no output: note in assessment

### 6C: Full test suite
```bash
make test-fast  # Must pass with all merged changes
```

### 6D: Deploy + Browser verify
- `git push origin main`
- Wait for Railway deploy SUCCESS
- Browser verify:
  1. Speed-run page (no recursive prefetch, reviewed items filtered)
  2. Landing page (CTAs, mobile)
  3. Person page (tooltips)
  4. 404 page (styled)

### 6E: Security audit
Review all changed files for auth guards, injection, XSS.

### 6F: Harness outputs
1. Assessment: `docs/assessments/session-125-assessment.md`
2. CHANGELOG: v0.99.35
3. ROADMAP + SESSION_HISTORY
4. BACKLOG updates (mark done, add any new items)

**Commit:** `docs: session 125 harness outputs`
**Push to origin main**

---

## Verification Gate

| Check | Method | Expected |
|-------|--------|----------|
| Unified embeddings (single parse)? | Test | np.load called once, three views populated |
| Registry SWR (no blocking)? | Test | Stale served immediately, background refresh |
| Cold start faster? | Test | Startup defers Supabase to background |
| Surgical invalidation? | Test | Only changed IDs cleared |
| Speed-run skip tracking? | Test | Reviewed IDs filtered from queue |
| Reject advances? | Test | New card returned |
| 404 styled? | Browser | Dark theme, back link |
| Codex items merged? | git log | Commit exists or BACKLOG note |
| Antigravity items merged? | git log | Commit exists or BACKLOG note |
| All tests pass? | `make test-fast` | PASS |
| Assessment exists? | File check | Exists |
| `git log origin/main..HEAD` empty? | git log | Empty |

## Parallelization

- **Phase 0**: Sequential (infrastructure)
- **Phases 1-3**: Sequential (all in app/main.py)
- **Phase 4**: Sequential after Phase 3 (different file, but wait for main.py stability)
- **Phase 5**: Quick, after Phase 4
- **Phase 6**: After all phases + Codex/Antigravity output available
