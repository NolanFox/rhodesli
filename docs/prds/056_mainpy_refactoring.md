# PRD-056: main.py Refactoring — UI Component Extraction

**Status:** Planning
**Author:** Session 135
**Date:** 2026-03-22
**References:** Lesson 88 (parallel worktree blocking), Session 135 research audit
**Research:** [docs/session_context/session-135-research.md](../session_context/session-135-research.md)

---

## Problem

`app/main.py` is 11,735 lines with 173 functions. It is the single largest blocker to parallel development. Per Lesson 88, any session track that touches `app/main.py` must be sequential — parallel worktree development is impossible when multiple tracks need to modify the same file.

Previous extraction sessions moved route handlers into `app/page_routes.py`, `app/identity_routes.py`, `app/match_facecompare_routes.py`, `app/cluster_review_routes.py`, and `app/estimate_routes.py`. However, these extracted files depend on a `_main_mod` pattern (importing the main module to access shared state), creating 482 references in `page_routes.py` and 422 in `identity_routes.py`.

What remains in `main.py`:
- ~5,500 lines of UI component/rendering functions (cards, grids, panels, modals)
- ~1,700 lines of helpers, proposal logic, community logic
- ~3,000 lines of data layer, middleware, caches, and startup

## Phased Approach

### Phase 1: Extract UI Components (~5,500 lines) — LOW risk

**Target:** Pure rendering functions that take data as arguments and return FastHTML elements. These have no dependency on registry state or `_main_mod`.

**Destination:** `app/components/` package with domain-grouped modules:
- `app/components/cards.py` — identity cards, face cards, photo cards, suggestion cards
- `app/components/grids.py` — photo grids, people grids, face grids
- `app/components/panels.py` — detail panels, info panels, enrichment panels
- `app/components/modals.py` — login modal, confirm modal, merge modal
- `app/components/navigation.py` — sidebar, nav bar, breadcrumbs, pagination
- `app/components/badges.py` — state badges, confidence badges, community badges
- `app/components/forms.py` — upload forms, search forms, filter forms
- `app/components/__init__.py` — re-exports for convenience

**Why LOW risk:**
- Pure functions: take data in, return FT elements out
- No shared state access needed
- No `_main_mod` dependency
- Easy to test in isolation
- Import changes are mechanical (find/replace)

**Acceptance criteria:**
1. All UI component functions moved to `app/components/`
2. `app/main.py` reduced by ~5,500 lines
3. All existing tests pass without modification (imports updated)
4. No new `_main_mod` references introduced
5. `make test-fast` passes
6. At least 2 route files can be modified in parallel worktrees without conflict

### Phase 2: Extract Helpers, Proposals, Community (~1,700 lines) — MEDIUM risk

**Target:** Business logic that accesses registry state but can be parameterized.

**Destination:**
- `app/proposals.py` — proposal generation, filtering, enrichment
- `app/community_logic.py` — community scoping, cross-community badges, workspace logic
- `app/helpers.py` — utility functions shared across routes

**Why MEDIUM risk:**
- Some functions currently access global state via closure
- Need to refactor from closure-based to parameter-based (pass registry as argument)
- Proposal logic interacts with multiple data sources (identities, embeddings, GEDCOM)
- Community middleware integration has subtle routing dependencies

**Acceptance criteria:**
1. All helper/proposal/community functions extracted
2. No closure-based global state access — all state passed as parameters
3. All existing tests pass
4. Community routing behavior unchanged (verified by `test_community_routing_safety.py`)

### Phase 3: Extract Data Layer, Middleware, Caches (~3,000 lines) — HIGH risk

**Target:** Registry loading, cache management, middleware, startup sequence.

**Destination:**
- `app/registry.py` — IdentityRegistry + PhotoRegistry access layer
- `app/caches.py` — TTL caches, perf_cache integration, cache invalidation
- `app/middleware.py` — CommunityMiddleware, auth middleware, request context
- `app/startup.py` — app initialization, background tasks, health checks

**Why HIGH risk:**
- Registry is the core shared state — every route file depends on it
- Cache invalidation has subtle timing dependencies
- Middleware ordering affects auth, community scoping, and API routing
- Startup sequence has dependency ordering (data load → cache warm → middleware → routes)
- This is where the `_main_mod` pattern lives — extraction requires replacing it

**Acceptance criteria:**
1. `app/main.py` reduced to <500 lines (app factory + route registration)
2. `_main_mod` pattern eliminated from all route files
3. Registry access through explicit dependency injection or module-level singleton
4. All existing tests pass
5. Production deploy succeeds with health check
6. No performance regression (startup time, request latency)

## Out of Scope

- **Phase 4: Eliminate `_main_mod` entirely** — This is a prerequisite for Phase 3 but could be its own initiative if Phase 3 is deferred. Not planned for initial execution.
- **Framework migration** — No change to FastHTML/HTMX stack (see ROADMAP "Future Evaluation" trigger)
- **Route file refactoring** — The 5 existing route files (`page_routes.py`, `identity_routes.py`, etc.) stay as-is
- **Test reorganization** — Tests may need import updates but no structural test refactoring

## Key Risks

| Risk | Mitigation |
|------|------------|
| `_main_mod` circular imports | Phase 1 avoids this entirely; Phase 2 uses parameter injection |
| Import path breakage across 3,600+ tests | Mechanical find/replace; re-export from `__init__.py` for backwards compat |
| Subtle rendering bugs from moved functions | Browser verification of all major pages post-extraction |
| Performance regression from import overhead | Benchmark startup time before/after |
| Merge conflicts with in-flight work | Execute during a quiet period; no parallel sessions |

## Recommended Execution Approach

**Phase 1 (recommended first session):**
1. **Codex** for mechanical extraction — identify pure functions, move to modules, update imports across codebase
2. **Claude Code** for audit/verification — run full test suite, browser verify all pages, check for subtle breakage
3. Estimated effort: 1 day (4-6 hours Codex + 2-3 hours Claude Code audit)

**Phases 2-3:** Defer until Phase 1 is validated in production. Each phase is a separate session.

## Success Metrics

- `app/main.py` line count: 11,735 → ~6,200 (Phase 1) → ~4,500 (Phase 2) → <500 (Phase 3)
- Parallel worktree capability: blocked → unblocked for UX work (Phase 1)
- `_main_mod` references: 904+ → 904+ (Phase 1, unchanged) → reduced (Phase 2) → 0 (Phase 3)

## Breadcrumbs

- Research: `docs/session_context/session-135-research.md` (Main.py Refactoring Audit)
- Lesson 88: `tasks/lessons/harness-lessons.md` — parallel worktree blocking
- BACKLOG: REFACTOR-001
- ROADMAP: Near-Term — Infrastructure
