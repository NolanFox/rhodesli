# Session 111f Context — Final Sprint: Performance + Remaining FB Items

**Predecessor:** [Session 111e context](session-111e-context.md)
**Feedback:** [docs/feedback/session-111-feedback.md](../feedback/session-111-feedback.md) + [docs/feedback/session-111d-interactive-feedback.md](../feedback/session-111d-interactive-feedback.md)

## Goal

Close out ALL remaining 111-series feedback. After this session, every FB item from FB-025 through FB-077 must be either FIXED, DEFERRED-with-PRD, or DEFERRED-with-BACKLOG. No loose ends.

## Session 112 Conflict Avoidance

Session 112 (PRD-051 Phase 1) will touch these functions in `app/main.py`:
- `load_registry()` (~line 1195)
- `save_registry()` (~line 1246)
- `_build_caches()` (~line 3931)
- `_load_photo_dimensions_cache()` (~line 3629)
- `load_photo_registry()`
- All `DATA_SOURCE` conditional branches

**Rule:** Session 111f MUST NOT modify these functions' read-path logic. Performance work should target:
- The hot-path **callers** (cluster_review_routes.py, identity_routes.py)
- The **computation** (vectorized distance, precomputed matrices)
- The **cache invalidation strategy** (smarter invalidation, not broader caching)
- NOT the data loading/saving infrastructure that 112 will rewrite

## Remaining FB Items — Prioritized

### P0 — Performance (BLOCKING USER)

**FB-069/FB-025: Site is too slow to use.**

Root causes (ordered by impact):

1. **Cache invalidation is too aggressive.** `save_registry()` calls `invalidate_neighbors_cache()` + `invalidate_cluster_review_caches()` on EVERY action. The 30s/300s TTL caches are immediately blown on every confirm/skip/merge. In a speed-run session, every action forces cold recalculation.
   - **Fix:** Don't invalidate caches for the CURRENT identity's neighbors on confirm. Only invalidate the specific identity's cache entry, not ALL entries. For cluster caches, remove the confirmed identity from the cached list instead of rebuilding.
   - **2nd-order effect:** Stale data risk. Mitigate by invalidating only the affected identity's cache key, not the entire cache.

2. **`_get_confirmed_identity_suggestions()` uses per-face Python-loop `cdist`.** Iterates all 3433 identities, filters ~95 CONFIRMED, then runs `cdist([target], [emb])` one face at a time. With ~5 faces per confirmed identity = 475 individual `cdist` calls.
   - **Fix:** Precompute a normalized embedding matrix for all CONFIRMED identities at startup. On query, compute `1 - np.dot(target_normalized, confirmed_matrix.T)` in one vectorized call. This replaces 475 `cdist` calls with 1 matrix multiply.
   - **2nd-order effect:** Matrix must be updated when identities are confirmed/merged. Use lazy rebuild: mark dirty, rebuild on next access.
   - **3rd-order effect:** Memory. 95 confirmed × 5 faces × 512 dims × 4 bytes = ~1MB. Negligible.

3. **`find_nearest_neighbors()` in `core/neighbors.py` is O(N*M) brute force.** Scans all 3433 identities with per-identity `cdist`. 300s cache but invalidated on every `save_registry()`.
   - **Fix:** Same vectorized approach. Build a global embedding matrix at startup. Use `np.dot` for batch distance. Cache the matrix, only rebuild on upload/sync, NOT on confirm/merge.
   - **2nd-order effect:** `core/neighbors.py` is marked FROZEN in CLAUDE.md. The fix should add a NEW optimized function alongside, not modify the existing one. Callers switch to the new function.
   - **IMPORTANT:** neighbors.py FROZEN means we add `find_nearest_neighbors_fast()` and update callers, NOT modify the frozen function.

4. **Discovery tab (FB-059) is extremely slow.** Same root cause — triggers `find_nearest_neighbors` for multiple identities without batching.
   - **Fix:** Lazy-load discovery cards (already has skeleton from 111b). Add a precomputed "top discoveries" cache that rebuilds in background on startup and after uploads, not per-request.

### P0 — Partial Fixes That Need Completion

5. **FB-036/037: Speed Loop tagging doesn't persist.** Warning toast was added but the UNDERLYING Supabase save failure is unresolved. Tags vanish on reload.
   - **Investigation:** Read the tag endpoint. Trace the save path. Check if `save_registry(changed_ids=...)` is being used. Check if the Supabase write returns an error that's being swallowed.
   - **Fix depends on root cause.** May need to switch from background thread to synchronous write for tags.

6. **FB-064: Override merge redirect — needs production verification.** Code looks correct (`_nav_prefix_from_request()`). Just verify on production via DOM read (READ-ONLY).

### P1 — UX Fixes

7. **FB-040: Stale card after merge in browse mode.** Focus mode is fixed (111d). Browse mode still shows the merged-from card. Need OOB swap to remove `#identity-{source_id}` card.

8. **FB-030: Cluster count resets.** localStorage persistence added (111d) but server-side session state is missing. The count resets when navigating away. Need server-side persistence via URL parameter chain or session cookie.

9. **FB-059: Discovery tab slow.** Needs precomputed cache (see performance section above).

10. **FB-076: Community awareness on approve.** Verify the approve endpoint correctly associates identities with the right community. DOM read on production.

11. **FB-057: Focus mode auto-advance.** Marked partial. Verify on production that confirm/skip/reject advance to next card correctly.

### P2 — Quick Wins (if time)

12. **FB-044: Best match in both banner AND Similar list.** Need visual linking (highlight in Similar list with "Best Match" badge) rather than filtering.
13. **FB-038: Load More resets checkboxes.** Use `hx-swap="beforeend"` for pagination instead of replacing.
14. **FB-028: Toast persistence.** OOB swap added (111d). Verify it works.

### Explicitly Deferred (BACKLOG only, not for this session)

- FB-035 (cluster quality) → ML-102
- FB-042/043/045/046 (Help Identify UX) → UX-102/103/105/106
- FB-049 (Sentry circular import) → INFRA-005
- FB-052/068 (confirm-as-merge) → UX-108, needs PRD
- FB-053 (identity ID format) → UX-109
- FB-060 (Compare on Discovery) → UX-113
- FB-073 (approval notifications) → P2

## Performance Research Findings

### Vectorized Cosine Distance (replaces per-face cdist loops)

The standard optimization for all-vs-all cosine distance:
1. **Normalize once:** `normalized = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)`
2. **Batch compute:** `distances = 1 - np.dot(query_normalized, corpus_normalized.T)`
3. **Top-k:** `np.argpartition(distances, k)[:k]`

This replaces O(N) Python-loop cdist calls with a single BLAS-optimized matrix multiply. Expected speedup: 10-100x for 95 confirmed identities.

### Smart Cache Invalidation

Current problem: every `save_registry()` call blows ALL neighbor and cluster caches. Fix:
- **Surgical invalidation:** Only remove the specific identity from caches, not flush everything.
- **Confirmed identity matrix:** Rebuild lazily. Mark dirty flag on confirm/merge, rebuild on next `_get_confirmed_identity_suggestions()` call.
- **Neighbor cache:** Don't invalidate on confirm/skip. Only invalidate on merge (which changes identity composition). Skip and reject don't change the neighbor graph.

### HTMX Lazy Loading

Already partially implemented (enrichment panel). Apply same pattern to:
- Discovery cards (load skeletons first, fetch content via `hx-trigger="intersect"`)
- Neighbor panels (already lazy in focus mode, verify in browse mode)

## Key Files (with Session 112 conflict notes)

| File | 111f Can Modify? | Notes |
|------|-----------------|-------|
| `app/cluster_review_routes.py` | YES | Cache strategy, enrichment panel, suggestions |
| `app/identity_routes.py` | YES | Neighbor endpoint, cache invalidation, tag endpoint |
| `core/neighbors.py` | ADD ONLY | FROZEN — add new function, don't modify existing |
| `app/main.py` | CAREFUL | Can modify: `neighbor_card()`, focus buttons, UI rendering. Cannot modify: `load_registry()`, `save_registry()`, `_build_caches()`, `_load_photo_dimensions_cache()` |
| `app/admin_routes.py` | YES | Approvals, community verify |
| `app/browse_routes.py` | YES | Browse mode stale card fix |
| `tests/` | YES | All new tests |

## SDD Applicability

- **Performance caching (Phase 1):** No PRD needed — optimization of existing behavior, no user-facing workflow changes.
- **FB-036/037 tag persistence (Phase 2):** Bug fix, no PRD needed — expected behavior is already well-defined (tags should save).
- **FB-040 stale card (Phase 3):** Bug fix, no PRD needed.
- **FB-044 best match dedup (Phase 4):** Small UX change — AD entry sufficient, no PRD.

## Breadcrumbs
- PRD-051: `docs/prds/051_single_source_of_truth.md` — Session 112 scope
- Session 112 prompt: `docs/prompts/session-112-prompt.md`
- Performance memory: Speed-Run Performance Root Causes in MEMORY.md
- Lessons: 149 (browser read-only), 150 (three-source split-brain)
