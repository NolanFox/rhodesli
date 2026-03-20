# Session 125 Context — Performance Completion + UX Quick Wins

**Predecessor:** [Session 124 Context](session-124-context.md)
**Codex Audit:** [Session 123 Codex Performance Audit](session-123-codex-perf-audit.txt)
**Antigravity Audit:** [Session 124 Antigravity UX Audit](session-124-antigravity-ux-audit.md)

## Goal

Complete ALL remaining Codex performance findings + ship 15 UX quick wins. Three-track parallel execution: Claude Code (complex perf), Codex (contained fixes), Antigravity (CSS/template).

## Codex Audit Status

| # | Finding | Status | Session |
|---|---------|--------|---------|
| 1 | Registry cache SWR | **THIS SESSION** | 125 |
| 2 | Recursive prefetch cascade | DONE | 124 |
| 3 | Review groups O(n²) cache | DONE | 124 |
| 4 | Cold start optimization | **THIS SESSION** | 125 |
| 5 | Community indexes SQL | DONE (needs Supabase execution) | 124 |
| 6 | Unified embeddings parse | **THIS SESSION** | 125 |
| 7 | Similarity corpus rebuild | SKIP — neighbors.py FROZEN | — |
| 8 | perf_cache metadata overhead | **THIS SESSION (Codex)** | 125 |
| 9 | CDN Tailwind precompile | DEFERRED — PERF-012 | — |
| 10 | Surgical cache invalidation | **THIS SESSION** | 125 |

## Three-Track Architecture

### Track A: Claude Code (owns app/main.py, cluster_review_routes.py)
Sequential phases — these files are too interconnected to parallelize.

**Phase 1: PERF #6 — Unified embeddings parse**
- Problem: embeddings.npy (12MB) parsed THREE times: `get_face_data()` (line ~3577), `load_embeddings_for_photos()` (line ~3680), `get_crop_files()` (line ~4517)
- Fix: Single `_unified_embeddings_cache` parsed once in `_build_caches()`, three functions become thin accessors
- Files: app/main.py, core/embeddings_io.py
- Risk: MEDIUM — all three are read-only from same source, backward-compatible API

**Phase 2: PERF #1 — Registry SWR refresh**
- Problem: `load_registry()` TTL miss blocks request for full Supabase reload (~200ms+). N concurrent requests all fire redundant queries.
- Fix: Stale-while-revalidate — serve stale cache immediately, background thread refreshes with lock
- Files: app/main.py (load_registry ~line 1234)
- Risk: MEDIUM — threading needs careful lock management

**Phase 3: PERF #4 — Cold start optimization**
- Problem: startup_event() blocks on Supabase health check + sync before accepting requests
- Fix: Move health check + sync into background prewarm thread, server accepts requests immediately
- Files: app/main.py (startup_event ~line 783)
- Risk: LOW — server already handles missing caches with lazy loading

**Phase 4: PERF #10 + FB-161 + UX-076 + FB-151 (cluster_review_routes.py bundle)**
- PERF #10: Change `_invalidate_all_caches()` calls in GEDCOM link/unlink to surgical `changed_ids`
- FB-161: Track reviewed identity IDs in speed-run session, filter from queue
- UX-076: Speed-run reject should advance to next card
- FB-151: Show full suggestion name (not truncated)
- Files: app/cluster_review_routes.py
- Risk: MEDIUM — speed-run is heavily used

**Phase 5: UX-080 — 404 page styling**
- Quick win: Add Tailwind classes to 404 error page
- File: app/main.py (~line 1184)

### Track B: Codex (owns perf_cache.py, browse_routes.py, identity_routes.py, compare_routes.py)
All items are in files Claude Code does NOT touch. Can run fully in parallel.

| Fix | File | Description |
|-----|------|-------------|
| PERF #8 | app/perf_cache.py | Cache registry reference during rebuild, avoid redundant reload |
| UX-114 | app/browse_routes.py | Replace fragile `onfocus="this.select()"` |
| FB-157 | app/browse_routes.py | Add clickable person links to identity cards |
| FB-158 | app/browse_routes.py | Add distance/confidence to manual search results |
| FB-163 | app/identity_routes.py | Add community badge to tag-search results |

### Track C: Antigravity (owns page_routes.py, person_routes.py ONLY)
CSS/template changes only. No logic. No data.

| Fix | File | Description |
|-----|------|-------------|
| UX-081 | app/page_routes.py | About page navbar consistency |
| UX-106 | app/page_routes.py | Unify CTA phrasing |
| UX-107 | app/person_routes.py | Add tooltip to "Identified" badge |

## File Ownership (CRITICAL — prevents merge conflicts)

| File | Owner | Others MUST NOT touch |
|------|-------|-----------------------|
| app/main.py | Claude Code | Codex, Antigravity |
| app/cluster_review_routes.py | Claude Code | Codex, Antigravity |
| core/embeddings_io.py | Claude Code | Codex, Antigravity |
| app/perf_cache.py | Codex | Claude Code, Antigravity |
| app/browse_routes.py | Codex | Claude Code, Antigravity |
| app/identity_routes.py | Codex | Claude Code, Antigravity |
| app/page_routes.py | Antigravity | Claude Code, Codex |
| app/person_routes.py | Antigravity | Claude Code, Codex |
| core/neighbors.py | FROZEN | ALL |
| data/* | FROZEN | ALL |

## Merge Order
1. Claude Code commits to main (sequential phases)
2. After all Claude Code phases done: merge Codex branch
3. After Codex merged: merge Antigravity branch
4. Full test suite after each merge
5. Deploy + browser verify

## Safety Gates
- `make test-fast` after every phase commit
- No touching `data/` files under any circumstances
- No `--no-verify` on any commit
- Browser verify speed-run + landing page + person page after deploy
- If any test fails: fix before proceeding, never skip

## Breadcrumbs
- Codex audit findings: `docs/session_context/session-123-codex-perf-audit.txt`
- UX quick wins: `docs/BACKLOG.md` (UX-076, UX-080, UX-081, UX-106, UX-107, UX-114)
- Feedback items: `docs/feedback/session-119-feedback.md` (FB-009), `docs/BACKLOG.md` (FB-151, FB-157, FB-158, FB-161, FB-163)
- Session 124 assessment: `docs/assessments/session-124-assessment.md`
- Antigravity constraints: memory `feedback_antigravity_constraints.md`
