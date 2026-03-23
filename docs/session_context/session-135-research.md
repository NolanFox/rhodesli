# Session 135 — Background Agent Research Findings

**Date:** 2026-03-22
**Context:** [session-135-context.md](session-135-context.md)

---

## FB-002: Load More Performance Audit

**Key finding:** Bottleneck is matrix CONSTRUCTION (100-200ms per call), not distance computation (<5ms). The `find_nearest_neighbors()` path rebuilds the full embedding matrix on every request.

**Top recommendations (ranked):**
1. **Precompute global embedding matrix at startup** — pattern already exists in `perf_cache.py`. Eliminates 100-200ms matrix rebuild per request.
2. Cache `find_nearest_neighbors()` results with TTL (quick win, ~10 lines).
3. Batch prefetch for paginated views — compute next page distances during current page render.
4. **Nuclear option (Finding 10):** Precompute ALL neighbor lists at startup, making every query O(1). High memory (~50MB for 3K faces) but eliminates all runtime distance computation.

**Current flow:** Request → build matrix → compute distances → sort → return. The build step dominates.

---

## FB-003: Async Distance UX Design (Mini-PRD)

**Pattern:** Search results load instantly (text-only cards), then each card lazy-loads its distance badge via `hx-trigger="load"`.

**New endpoint:** `GET /api/identity/{source_id}/distance/{target_id}` — returns a single distance badge fragment.

**UX animation sequence:**
1. Card renders with scanning animation (CSS sweep gradient)
2. HTMX fires background distance request on load
3. Badge reveals with scale+blur CSS transition when response arrives

**Effort estimate:** ~1-2 hours total
- 30 lines: endpoint implementation
- 15 lines: card template modification (placeholder + hx-get)
- 30 lines: CSS animations (sweep + reveal)

**Benefit:** Perceived instant search, distance is progressive enhancement not blocking.

---

## FB-004: Lightbox Navigation Audit

**Root cause:** Click delegation handler checks `photoNavTo` (global variable) before `data-nav-url` (element-scoped attribute). When both exist, global wins, causing wrong navigation.

**Fix:** 3-line change in click handler to prioritize `data-nav-url` over `photoNavTo`.

**Secondary finding:** "Not Same" button broken on 5 of 6 compare surfaces. The button posts to `/not-same/` route which doesn't exist. Should map to `/reject/` endpoint. Affects: match view, focus mode, speed-run, find-similar, discovery panel (5 surfaces). Only cluster review wires it correctly.

---

## Site-wide Performance Audit (15 findings)

### Quick Wins (< 30 min each)
1. **GZipMiddleware** — 1 line addition, HIGH impact on HTML/JSON response sizes
2. **Cache landing page stats** — TTL cache for photo/identity counts (~10 lines)
3. **Cache-Control headers** on public pages — `max-age=300` for browse, person pages (~5 lines)
4. **Tailwind CDN JIT → pre-built CSS** — biggest single page load improvement, eliminates runtime CSS compilation

### Medium Effort (1-2 hours)
5. **Extract inline CSS/JS to static files** — 15-20KB savings per HTML response, enables browser caching
6. **`list_identities()` optimization** — copies 22K+ dicts per dashboard load, needs view/projection
7. **`resolve_face_image_url()` optimization** — regex scan runs per face, should be cached or simplified

### Larger Projects
8. **R2 photo thumbnails** — currently serving full-resolution images for grid thumbnails. Cloudflare Image Resizing or pre-generated thumbnail variants would cut bandwidth significantly.
9. **HTTP cache headers audit** — no cache headers on any public pages currently

---

## Main.py Refactoring Audit

**Current state:** 11,735 lines, 173 functions, 4 route handler groups still inline.

### Extraction Phases (recommended order)

| Phase | Target | Lines | Risk | Benefit |
|-------|--------|-------|------|---------|
| 1 | UI components → `app/components/` | ~5,500 | LOW | Unblocks parallel worktrees |
| 2 | Helpers, proposals, community logic | ~1,700 | MEDIUM | Cleaner separation |
| 3 | Data layer, middleware, caches | ~3,000 | HIGH | Full decoupling |

**Key blocker:** `_main_mod` pattern — 482 references in `page_routes.py`, 422 in `identity_routes.py`. Every extracted route file imports the main module to access shared state. Phase 1 avoids this by extracting pure rendering functions that don't need registry access.

**Strategic benefit:** Unblocks parallel worktree development (Lesson 88 — tracks touching `app/main.py` must be sequential). After Phase 1, most UX work can happen in `app/components/` without conflicts.
