# Session 162 Phase 5 — App-side TTL Audit

**Date**: 2026-05-23 UTC

## TL;DR

All GEDCOM readers in `app/` go through `_GEDCOM_CACHE_TTL_SECONDS = 300` (5-minute) TTL caches with a 30-second failure backoff. No hot-loop bugs. **No mutations needed.**

## Findings

### TTL constants (app/relationship_routes.py:236-237)
```python
_GEDCOM_CACHE_TTL_SECONDS = 300         # 5 min — appropriate for upload-only changes
_GEDCOM_FAILURE_BACKOFF_SECONDS = 30    # circuit breaker on cache load failure
```

### Cached read paths (all under app/relationship_routes.py)

| Function | View/Table | Cache var | TTL |
|----------|-----------|-----------|----:|
| `_load_gedcom_individuals()` (:301) | `current_gedcom_individuals_v2` → v1 → raw fallback | `_gedcom_individuals_cache` | 300s |
| `_load_gedcom_face_links()` (:391) | `gedcom_face_links` | `_gedcom_face_links_cache` | 300s |
| `_load_gedcom_redirects()` (:438) | `gedcom_redirects` | `_gedcom_redirects_cache` | 300s |
| `_load_current_gedcom_relationship_edges()` (:497) | `current_gedcom_relationships` (Phase 1a fix) | `_gedcom_tree_relationships_cache` | 300s |

All readers:
- Return stale cache during the failure backoff window
- Re-load only on TTL expiry (no per-request hits)
- Now benefit from the Phase 1a view fix — cold-load goes from 754ms → expected sub-100ms

### Targeted (non-cached) path

`_load_gedcom_relationship_edges_for_ids()` (:602) is a targeted-edges path used by some person-detail views. It does NOT use the global cache (intentionally — it's filtered per request).

This path was hit by Codex P1.4. Phase 1a fixed it to filter `is_current = true` on the raw-table fallback. ✓

### Other GEDCOM reads in app/

`app/gedcom_dual_read.py` — uses the v2 view with a v1 view fallback. No raw `gedcom_*` table reads; healthy. (This was added in Session 158 PRD-063 carry.)

### What I did NOT touch

- Cache TTL itself is fine at 300s. GEDCOM data only changes on admin upload (~1× per session, rare).
- The failure backoff (30s) is the right balance — fast enough to retry after a flake, slow enough to avoid thundering herd.
- No new caches introduced (per anti-goal in prompt: "DO NOT add new TTL caches in Phase 5 without explicit user OK").

## Verdict

Phase 1a's view fix is the structural fix. With existing 300s TTL caching in front, the new query plan is hit at most ~12×/hour per worker. Expected post-fix per-worker burn: ~12 × 50ms (warm cache hit) = 600 ms/hour, down from ~12 × 754ms = 9 sec/hour. ~93% reduction on the cache-miss path.

No code changes from Phase 5. The audit confirms Phase 1a is sufficient.
