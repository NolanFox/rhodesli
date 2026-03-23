# PRD-056: app/main.py Refactoring — Eliminate _main_mod Coupling

**Author:** Nolan Fox (requirements), Claude (spec)
**Date:** 2026-03-22
**Status:** Draft
**Session:** 135 (research + PRD), TBD (implementation)
**Context:** docs/session_context/session-135-research.md

---

## Problem Statement

`app/main.py` is 11,765 lines with 173 functions. It is the single largest
file in the codebase and the primary bottleneck for parallel development.

**Why this matters now:**
1. **Parallel development blocked (Lesson 88):** Worktree tracks touching
   `app/main.py` must run sequentially. Since main.py contains UI components,
   data loaders, auth helpers, middleware, and caches, most feature work
   touches it — making parallel subagent sessions impossible for overlapping
   file regions.
2. **Massive coupling surface:** 19 extracted route files import `app.main as
   _main_mod` and reference **215 unique attributes** through it (1,997 total
   references). The top offenders: `page_routes.py` (482 refs),
   `identity_routes.py` (425 refs), `admin_routes.py` (206 refs),
   `compare_routes.py` (195 refs). Every route file is tightly coupled to
   main.py's internal API.
3. **Cognitive load:** UI rendering, data access, caching, auth, middleware,
   startup logic, and proposal management all coexist in one file with no
   clear boundaries.

**Prior extraction work:** Session 91b reduced main.py from 26,100 to 9,383
lines by extracting 17 route files. Session 92 extracted compare and estimate
routes (5,381 lines). Extraction stalled because the remaining functions are
shared state (registries, caches, helpers) that route files depend on via the
`_main_mod` pattern.

## Who This Is For

- **Claude Code agents** — parallel worktrees without merge conflicts
- **Nolan (admin)** — faster feature iteration, easier code review
- **Future contributors** — lower barrier to understanding the codebase

## Developer Flows

### Flow 1: Adding a new UI component (current vs. after)

**Today:**
1. Open `app/main.py` (11,765 lines), find a similar component function
2. Add new function to main.py (anywhere — no organizational convention)
3. If another worktree track is editing main.py, **merge conflict**
4. Route files access it via `_main_mod.new_function()`

**After Phase 1:**
1. Open `app/components/cards.py` (300-500 lines), find similar component
2. Add new function to the appropriate component module
3. Other worktree tracks editing main.py or other modules: **no conflict**
4. Route files import directly: `from app.components.cards import new_function`

### Flow 2: Understanding a route file's dependencies (current vs. after)

**Today:**
1. Open route file, see `import app.main as _main_mod`
2. Search for `_main_mod.` — find 50-400+ opaque references
3. Must read main.py to understand each one (pure renderer? side effect?)

**After Phase 3:**
1. Open route file, see explicit imports from named modules
2. Import list shows exactly what the route needs and where it comes from
3. Module names convey intent: `data_access`, `components`, `auth_helpers`

## Phased Approach

### Phase 1: UI Components Extraction (~5,500 lines) — LOW risk

Extract pure rendering functions (data in, FT elements out, no side effects).

**Target modules:**

| Module | Contents | Est. lines |
|--------|----------|-----------|
| `app/components/cards.py` | `identity_card`, `face_card`, `neighbor_card`, suggestion cards | ~800 |
| `app/components/badges.py` | `_cross_community_badge`, `_promotion_badge`, date badges, confidence tiers | ~400 |
| `app/components/nav.py` | `_public_nav_links`, `sidebar`, `_build_triage_bar`, share button, OG tags | ~600 |
| `app/components/photo.py` | `_build_ai_analysis_section`, `_build_ai_sections_list`, `_build_face_alignment_section` | ~1,500 |
| `app/components/forms.py` | `_place_datalist`, `_photo_collection_datalist`, form helpers | ~200 |
| `app/components/layouts.py` | Page shell, 404 handler, `_posthog_script`, CSS/JS head elements | ~500 |
| `app/components/__init__.py` | Re-exports for backward compatibility | ~30 |

**Why LOW risk:** Pure functions with no shared state access. Extraction is
mechanical find-and-replace. Any function that reads `_main_mod._photo_cache`
or similar stays in main.py for Phase 2.

**Acceptance criteria:**
- [ ] Each component module importable independently (no circular imports)
- [ ] `_main_mod` reference count drops by 300+ (from 1,997)
- [ ] `app/main.py` drops below 7,000 lines
- [ ] `make test-fast` passes (3,696+ tests, zero regressions)
- [ ] Two route files modifiable in parallel worktrees without conflict

### Phase 2: Helpers, Proposals, Community Logic (~1,700 lines) — MEDIUM risk

Extract stateful helpers that read from caches but can be parameterized.

**Target modules:**

| Module | Contents | Est. lines |
|--------|----------|-----------|
| `app/proposals.py` | `_load_proposals`, `_get_proposals_for_identity`, proposal index, cache | ~400 |
| `app/community.py` | `_get_community_photo_ids`, `_get_community_identity_ids`, community middleware helpers | ~400 |
| `app/search.py` | `_search_photos`, `_load_search_index`, `_get_decade_counts`, `_get_tag_counts` | ~300 |
| `app/auth_helpers.py` | `_check_admin`, `_check_login`, `_check_contributor`, `_get_user_role` | ~200 |
| `app/dates.py` | Date label loading, birth year estimates, ML review decisions | ~400 |

**Key risk:** Functions read `_photo_cache`, `_proposals_cache`, etc. Must
refactor from closure-based global state to parameter-based injection.

**Acceptance criteria:**
- [ ] `_main_mod` reference count drops below 800
- [ ] Auth helpers importable without circular imports
- [ ] Community routing unchanged (verified by `test_community_routing_safety.py`)
- [ ] `make test-fast` passes

### Phase 3: Data Layer, Middleware, Caches (~3,000 lines) — HIGH risk

Extract the core data access layer and cache management.

**Target modules:**

| Module | Contents | Est. lines |
|--------|----------|-----------|
| `app/data_access.py` | `load_registry`, `save_registry`, `load_photo_registry`, `save_photo_registry`, `load_face_embeddings`, `get_face_data` | ~800 |
| `app/cache.py` | All `_*_cache` dicts, `_invalidate_all_caches`, `_build_caches`, TTL management | ~500 |
| `app/startup.py` | `startup_event`, `shutdown_event`, disk cleanup, health checks | ~500 |
| `app/middleware.py` | `CommunityMiddleware`, `CachedStaticFiles`, route reordering | ~300 |

**Key risks:**
- Circular imports: `data_access` needs `core/registry`, routes need `data_access`
- Cache invalidation has subtle timing dependencies across modules
- Startup sequence has strict ordering: data load -> cache warm -> middleware -> routes
- This is where the `_main_mod` pattern originates — full elimination

**Import graph must be strictly layered:**
```
core/ -> app/data_access.py -> app/components/ -> route files
                            -> app/cache.py
```

**Acceptance criteria:**
- [ ] `_main_mod` pattern eliminated (0 references across all route files)
- [ ] `app/main.py` under 1,500 lines (app factory + route registration)
- [ ] No circular imports (verified by import test)
- [ ] `make test-fast` passes
- [ ] Production deploy succeeds, health check 200

## Most-Referenced _main_mod Attributes

Top 15 attributes driving the coupling (must be routed to new homes):

| Attribute | Refs | Target module |
|-----------|------|--------------|
| `toast` | 161 | `app/components/layouts.py` |
| `load_registry` | 160 | `app/data_access.py` (Phase 3) |
| `_check_admin` | 129 | `app/auth_helpers.py` (Phase 2) |
| `is_auth_enabled` | 102 | `app/auth_helpers.py` (Phase 2) |
| `data_path` | 85 | `core/config.py` (already exists) |
| `get_current_user` | 83 | `app/auth_helpers.py` (Phase 2) |
| `community_url_prefix` | 82 | `app/community.py` (Phase 2) |
| `get_crop_files` | 64 | `app/data_access.py` (Phase 3) |
| `_photo_cache` | 64 | `app/cache.py` (Phase 3) |
| `resolve_face_image_url` | 52 | `app/components/cards.py` (Phase 1) |
| `save_registry` | 51 | `app/data_access.py` (Phase 3) |
| `load_photo_registry` | 47 | `app/data_access.py` (Phase 3) |
| `get_identity_for_face` | 45 | `app/data_access.py` (Phase 3) |
| `get_photo_metadata` | 43 | `app/data_access.py` (Phase 3) |
| `log_user_action` | 37 | `app/audit.py` (already exists) |

## Risk Analysis

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Circular imports | HIGH | Strict layering enforced by import test |
| Test mock paths breaking | MEDIUM | `app.main.load_registry` -> `app.data_access.load_registry`. Batch find-replace. Re-export from main.py during transition |
| `_main_mod` references missed | MEDIUM | Automated grep count; regression test asserts count below target |
| Route registration (`rt`) breaks | LOW | `rt` stays in `app/main.py`, route files keep `from app.main import rt` |
| Cache invalidation timing | HIGH | Phase 3 only. Single cache module with explicit invalidation API |
| Performance from import overhead | LOW | Python caches imports; no runtime cost after startup |

## Migration Pattern (per function)

1. **Copy** function to target module with its imports
2. **Add re-export** in `app/main.py`: `from app.components.cards import identity_card`
3. **Update route files** to import from new location (or use re-export)
4. **Run** `make test-fast` — fix breakage
5. **Remove** re-export from main.py once all consumers updated
6. **Commit** atomically per logical group

The re-export step provides backward compatibility during migration,
allowing incremental route file updates instead of big-bang changes.

## Recommended Tooling

- **Codex CLI** for bulk extraction in Phase 1 (mechanical, parallelizable)
- **Claude Code** for Phase 2-3 (requires understanding of state dependencies)
- **Claude Code audit** after each phase (circular imports, test coverage, _main_mod count)
- **grep regression script:** `grep -rc '_main_mod\.' app/ | awk -F: '{s+=$2}END{print s}'`

## Out of Scope

- Splitting `page_routes.py` (13,029 lines) — separate PRD if needed
- Framework migration (FastHTML -> React/Next.js)
- Database schema changes
- Performance optimization (separate concern)
- Renaming functions (preserve API names to minimize test churn)
- Splitting `core/` modules (already well-factored)

## Priority Order

1. **Phase 1** — highest value, lowest risk, unblocks parallel UX development
2. **Phase 2** — medium value, reduces coupling, cleans up auth/proposal imports
3. **Phase 3** — deferred until Phases 1-2 are stable in production

## Success Metrics

| Metric | Before | Phase 1 | Phase 2 | Phase 3 |
|--------|--------|---------|---------|---------|
| `main.py` lines | 11,765 | ~6,200 | ~4,500 | <1,500 |
| `_main_mod` refs | 1,997 | ~1,700 | ~800 | 0 |
| Parallel UX work | blocked | unblocked | unblocked | fully unblocked |
| Unique attributes | 215 | ~180 | ~100 | 0 |

## Effort Estimate

| Phase | Sessions | Risk |
|-------|----------|------|
| Phase 1 | 1-2 | LOW (subagents per component module) |
| Phase 2 | 1 | MEDIUM (proposals + auth parallelizable) |
| Phase 3 | 2 | HIGH (sequential, touches shared state) |

## References

- `docs/session_context/session-135-research.md` — Full refactoring audit
- Lesson 88 (`tasks/lessons/harness-lessons.md`) — Parallel worktree blocking
- BACKLOG UX-204 — Face card consolidation (subsumed by Phase 1)
- BACKLOG ARCH-001 — Rhodes-specific hardcoding (separate concern)
- Session 91b — Prior extraction (26,100 -> 9,383 lines, 17 route files)
- Session 92 — Compare + estimate route extraction (5,381 lines)
- DD-017 (`docs/DESIGN_DECISIONS.md`) — This refactoring decision
