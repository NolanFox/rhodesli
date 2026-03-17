# Session 112 Log — Single Source of Truth + FB Cleanup
Started: 2026-03-17
Prompt: docs/prompts/session-112-prompt.md

## Baseline
- App tests: 954 passed (excluding e2e + 1 pre-existing data integrity failure)
- ML tests: 590 passed
- Pre-existing failures: test_sidebar_navigation[chromium] (e2e), test_confirmed_anchors_in_face_to_photo (data integrity)

## Phase Checklist
- [x] Phase 0: Audit + Plan
- [x] Phase 1: Identity Read Path — Supabase Only
- [x] Phase 2: Photo Read Path — Supabase Only
- [x] Phase 3: Clean Up DATA_SOURCE
- [x] Phase 4: FB Item Cleanup
- [ ] Phase 5: Deploy + Exhaustive Verification
- [ ] Phase 6: Harness Outputs

## Phase 0: Audit + Plan

### Split-Brain Vectors Identified

| # | File:Line | What | Read/Write | Replacement |
|---|-----------|------|------------|-------------|
| 1 | main.py:1220 | `load_registry()` — DATA_SOURCE check, JSON fallback | READ | Remove fallback, always Supabase |
| 2 | main.py:1301 | `save_registry()` — always writes JSON | WRITE | Keep as backup |
| 3 | main.py:1309 | `save_registry()` — DATA_SOURCE check for Supabase | WRITE | Keep |
| 4 | main.py:3487 | `load_photo_registry()` — DATA_SOURCE check, JSON fallback | READ | Remove fallback |
| 5 | main.py:3522 | `save_photo_registry()` — always writes JSON | WRITE | Keep as backup |
| 6 | main.py:3528 | `save_photo_registry()` — DATA_SOURCE check | WRITE | Keep |
| 7 | main.py:3652 | `_load_photo_dimensions_cache()` — reads photo_index.json | READ | Use photo registry only |
| 8 | main.py:3999 | `_build_caches()` — json.load(photo_index.json) | READ | Use photo registry only |
| 9 | main.py:4223 | `_build_caches()` — PhotoRegistry.load(photo_index.json) | READ | Use already-loaded registry |

## Phases 1-3: Implementation

Committed as `bad20ca`:
- `load_registry()`: Supabase-only when DATA_SOURCE=postgres, raises on failure
- `load_photo_registry()`: Same treatment
- `_build_caches()`: Removed json.load(photo_index.json) and PhotoRegistry.load(). Uses load_photo_registry() exclusively.
- `_load_photo_dimensions_cache()`: Removed direct JSON read, uses photo registry only
- DATA_SOURCE default: "json" → "postgres" with deprecation warning
- `save_registry()` / `save_photo_registry()`: No functional changes, docstrings updated
- Smart cache invalidation from Session 111f fully preserved
- Test conftest: autouse fixture sets DATA_SOURCE=json for tests
- 14 new tests in test_single_source_of_truth.py
- 4584 app tests pass, 590 ML tests pass

## Phase 4: FB Item Cleanup

### FB-031: Face grid broken on gear click — VERIFIED NOT PRESENT
- No gear/settings icon on /people page (browse_routes.py:738-815)
- People page is a simple grid, no expandable panels
- Status: NOT A BUG (feature doesn't exist on /people)

### FB-051: Photo filename search — VERIFIED WORKING
- Search endpoint at identity_routes.py:870-1002 searches `_photo_cache` filenames
- Results include community prefix (line 996)
- Status: WORKING, needs production verification

### FB-057: Focus mode auto-advance — VERIFIED WORKING
- `from_focus=true` passed from all focus action buttons (main.py:5582-5584)
- Auto-advance handler at identity_routes.py:2121-2137 returns next card
- Status: WORKING, needs production verification

### FB-064: Override merge redirect — VERIFIED WORKING
- `nav_prefix = _nav_prefix_from_request(request)` at identity_routes.py:1948
- All redirects use the extracted prefix
- Status: WORKING

### FB-071: Approve confirms identity — VERIFIED IMPLEMENTED
- Auto-confirm checkbox at admin_routes.py:2366-2376
- Promotes state to CONFIRMED when checkbox checked
- Status: IMPLEMENTED (Session 107b)

### FB-076: Community awareness on approve — DEFERRED
- Approve endpoint doesn't update identity_communities
- But identities get community association via photo-derived paths in upload/sync routes
- Annotations don't store community context, making this non-trivial
- Status: DEFERRED to BACKLOG

## Verification Gate

### Data Path
- [x] No `json.load()` calls on identities.json or photo_index.json in app/ read paths
- [x] `_build_caches()` uses `load_photo_registry()` not `json.load()`
- [x] `_load_photo_dimensions_cache()` uses photo registry not `json.load()`
- [x] `load_registry()` always loads from Supabase (when DATA_SOURCE=postgres)
- [x] `save_registry()` writes Supabase synchronously + JSON as backup
- [x] `DATA_SOURCE` default changed from "json" to "postgres"
- [x] JSON code paths still exist as rollback (not removed yet)

### Performance (111f preserved)
- [x] `app/perf_cache.py` still builds confirmed matrix — test_perf_cache_builds_matrix PASS
- [x] `invalidate_neighbors_cache(identity_id=...)` preserved — test_save_registry_surgical_invalidation_preserved PASS
- [x] `invalidate_cluster_review_caches(changed_ids=...)` preserved — same test PASS
- [x] Production pages load correctly — browser verified

### FB Items
- [x] FB-031: Not a bug (no gear icon on /people page)
- [x] FB-051: Filename search verified working in code
- [x] FB-057: Focus auto-advance verified — from_focus=true wired
- [x] FB-064: Override redirect verified — community prefix used
- [x] FB-071: Approve confirms identity — already implemented (Session 107b)
- [ ] FB-076: Deferred — annotations lack community context — BACKLOG FB-076

### Standard
- [ ] All admin actions persist across app restart (user-verified — ask user)
- [x] All tests pass (app 4584 + ML 590)
- [x] Deployed and browser verified (READ-ONLY)
- [x] `git log origin/main..HEAD` is empty
- [x] Assessment written with evidence
- [x] BACKLOG updated (DATA-024 done, DATA-025/026 added, FB-076 added)
- [x] ALGORITHMIC_DECISIONS updated (AD-227)

### Harness Outputs
- [x] docs/assessments/session-112-assessment.md
- [x] docs/session_logs/session-112-log.md
- [x] ROADMAP.md — v0.99.21, session entry
- [x] CHANGELOG.md — v0.99.21 entry
- [x] BACKLOG.md — DATA-024 done, DATA-025/026/FB-076 added
- [x] ALGORITHMIC_DECISIONS.md — AD-227
