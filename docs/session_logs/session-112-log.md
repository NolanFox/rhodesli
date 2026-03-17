# Session 112 Log — Single Source of Truth + FB Cleanup
Started: 2026-03-17
Prompt: docs/prompts/session-112-prompt.md

## Baseline
- App tests: 954 passed (excluding e2e + 1 pre-existing data integrity failure)
- ML tests: 590 passed
- Pre-existing failures: test_sidebar_navigation[chromium] (e2e), test_confirmed_anchors_in_face_to_photo (data integrity)

## Phase Checklist
- [ ] Phase 0: Audit + Plan
- [ ] Phase 1: Identity Read Path — Supabase Only
- [ ] Phase 2: Photo Read Path — Supabase Only
- [ ] Phase 3: Clean Up DATA_SOURCE
- [ ] Phase 4: FB Item Cleanup
- [ ] Phase 5: Deploy + Exhaustive Verification
- [ ] Phase 6: Harness Outputs

## Phase 0: Audit + Plan

### Split-Brain Vectors Identified

| # | File:Line | What | Read/Write | Replacement |
|---|-----------|------|------------|-------------|
| 1 | main.py:1220 | `load_registry()` — DATA_SOURCE check, JSON fallback at 1233 | READ | Remove fallback, always use Supabase |
| 2 | main.py:1301 | `save_registry()` — always writes JSON | WRITE | Keep as backup only (no change needed) |
| 3 | main.py:1309 | `save_registry()` — DATA_SOURCE check for Supabase write | WRITE | Keep (already correct behavior) |
| 4 | main.py:3487 | `load_photo_registry()` — DATA_SOURCE check, JSON fallback at 3497 | READ | Remove fallback, always use Supabase |
| 5 | main.py:3522 | `save_photo_registry()` — always writes JSON | WRITE | Keep as backup only (no change needed) |
| 6 | main.py:3528 | `save_photo_registry()` — DATA_SOURCE check | WRITE | Keep (already correct) |
| 7 | main.py:3652 | `_load_photo_dimensions_cache()` — reads photo_index.json directly | READ | Use load_photo_registry() only |
| 8 | main.py:3999 | `_build_caches()` — json.load(photo_index.json) | READ | Use load_photo_registry() only |
| 9 | main.py:4223 | `_build_caches()` — PhotoRegistry.load(photo_index.json) for aliases | READ | Use already-loaded photo_registry |

### Plan

**Phase 1: Identity Read Path**
- `load_registry()`: Remove JSON fallback. If DATA_SOURCE=postgres (default), always use Supabase. If fails, re-raise. Keep JSON fallback ONLY when DATA_SOURCE=json (rollback escape hatch).
- `save_registry()`: No functional change needed — already does the right thing. Update docstring/comments.
- Tests first, then implement.

**Phase 2: Photo Read Path**
- `load_photo_registry()`: Same treatment as load_registry.
- `_load_photo_dimensions_cache()`: Remove direct json.load, use only load_photo_registry().
- `_build_caches()`: Remove json.load(photo_index.json) at line 3999. Remove PhotoRegistry.load() at line 4223. Use already-loaded photo_registry variable. Build best_raw_entries from photo_registry instead of raw JSON.
- Key risk: face ordering. Sort by face_id to keep deterministic.
- Tests first, then implement.

**Phase 3: DATA_SOURCE default**
- Change default to "postgres"
- Add deprecation warning for "json"

**Phase 4: FB fixes** — independent, after data path changes

**Phase 5: Deploy + verify**

### perf_cache.py Analysis
- Calls `load_registry()` and `get_face_data()` — both will work fine after changes
- `mark_confirmed_dirty()` is called by `save_registry()` via `invalidate_cluster_review_caches()` — preserved
- No JSON reads in perf_cache.py — safe

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed
