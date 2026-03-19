# Session 123 Context — Performance + UX + Upload Audit Sprint

**Predecessor:** [Session 122 Context](session-122-context.md)
**Cross-AI Research:** Codex performance audit (in progress), Antigravity UX review (GUI-only)

## Problem Statement

Three threads converge: (1) admin triage is too slow for Fox Family ingestion, (2) upload pipeline has regressed for the 6th time, (3) community members can't self-serve the growth loop. This session tackles the highest-ROI items from each thread.

## Performance Analysis (Curated from Research)

### What Codex Confirmed
- `save_registry()` writes ALL identities to Supabase on every confirm — already optimized via `changed_ids` in Session 111d but callers may not pass it
- `_get_speed_run_clusters()` TTL increased to 120s (Session 122) — verified effective
- `perf_cache.py` vectorized matrix already efficient (O(1) matrix multiply)
- Multiple `np.load(embeddings.npy)` calls across routes — should be cached

### Actionable Fixes (After Critical Assessment)

**PERF-A: Deduplicate embeddings.npy loads (Quick Win)**
- `np.load(embeddings.npy, allow_pickle=True)` called in 6+ places across app
- Already cached in `get_face_data()` at main.py:3569 — but some routes bypass the cache
- Fix: Ensure ALL routes use `get_face_data()` instead of direct np.load
- Files: `app/compare_routes.py:3877`, `app/sync_routes.py:1211`, `app/main.py:3694,4547`
- Impact: Eliminate ~50ms per redundant load

**PERF-B: save_registry changed_ids propagation**
- `save_registry(registry, changed_ids=...)` exists but some callers pass None
- When changed_ids is None, it writes ALL identities to Supabase (~3500 rows)
- Fix: Audit all save_registry callers, ensure changed_ids is passed
- Files: grep for `save_registry(` across app/
- Impact: Reduce Supabase writes from 3500 to 1-5 rows per operation (99%+ reduction)

**PERF-C: REJECTED — _build_caches is already efficient**
- Codex + my investigation both confirm it loads once, iterates in-memory
- No fix needed

**PERF-D: REJECTED — Tree page 6.4s**
- Complex D3 + GEDCOM issue, not a quick fix
- Needs dedicated profiling session, out of scope for this sprint

## UX Fixes (Curated — Good Decisions)

### What Makes Sense Now

**UX-A: Enrichment panel workflow reorder (FB-103/104)**
- Current: name → merge search → GEDCOM (wrong order)
- Fix: merge search FIRST → name → GEDCOM link
- Rationale: When you find a match, you merge first, then refine name and GEDCOM
- Files: `app/cluster_review_routes.py` or `app/main.py` (enrichment panel rendering)
- Quick win, high impact on triage speed

**UX-B: Landing page CTAs for visitors (UX-130)**
- Current: landing page shows photos but no clear action for non-admin visitors
- Fix: Add "Help Identify Someone", "Compare a Face", "Explore the Archive" buttons
- Mobile-first: large touch targets, clear hierarchy
- Files: `app/page_routes.py` (landing page handler)

**UX-C: REJECTED — Compare tool redesign (UX-077/078)**
- Too complex for this sprint, needs its own PRD
- TOOLS-003 realtime compare (just shipped) is the first step toward this

**UX-D: REJECTED — Cross-community badges (COMMUNITY-004)**
- Already partially addressed by UX-208 (Session 121) — always-show badge
- Full multi-community indicator needs WORKSPACE-001 to be live first

## Upload Pipeline Audit

**UPLOAD-003: 6th regression**
- Session 119: 404 dead links after approval, missing thumbnails
- Root cause candidates: R2 upload race condition, staging cleanup too aggressive, photo_index not updated
- Fix: End-to-end trace of upload → staging → R2 → Postgres pipeline
- This is investigation, not blind fixing

## Parallelization

| Track | Files | Can Parallelize? |
|-------|-------|-----------------|
| PERF-A (embeddings dedup) | compare_routes.py, sync_routes.py, main.py | Risky — main.py overlap |
| PERF-B (save_registry audit) | Multiple route files | YES — worktree (audit + fix callers) |
| UX-A (enrichment reorder) | cluster_review_routes.py or main.py | YES — worktree if separate file |
| UX-B (landing CTAs) | page_routes.py | YES — worktree |
| Upload audit | upload_routes.py, admin_routes.py | Sequential (investigation) |

**Recommended execution:**
- Worktree A: UX-B (landing CTAs — page_routes.py only)
- Worktree B: PERF-B (save_registry audit — read-only investigation + targeted fixes)
- Sequential on main: PERF-A → UX-A → Upload audit → Security audit → Harness

## Reminder
User will do upload testing tonight — remind at session end.
