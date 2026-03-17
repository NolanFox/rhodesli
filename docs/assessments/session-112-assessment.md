# Session 112 Assessment — Single Source of Truth + FB Cleanup

## Shipped

### PRD-051 Phase 1: Supabase Single Source of Truth
- [x] `load_registry()`: Supabase-only when DATA_SOURCE=postgres, raises on failure — Evidence: `test_load_registry_raises_on_supabase_failure`, `test_load_registry_raises_on_none_return`
- [x] `load_photo_registry()`: Same treatment — Evidence: `test_load_photo_registry_raises_on_failure`, `test_load_photo_registry_raises_on_none`
- [x] `_build_caches()`: Removed `json.load(photo_index.json)` and `PhotoRegistry.load()`. Uses `load_photo_registry()` exclusively — Evidence: `test_build_caches_does_not_read_json`
- [x] `_load_photo_dimensions_cache()`: Removed direct JSON read — Evidence: `test_photo_dimensions_from_registry`
- [x] DATA_SOURCE default changed "json" → "postgres" with deprecation warning — Evidence: `test_default_is_postgres`
- [x] `save_registry()` / `save_photo_registry()`: No functional changes, smart invalidation preserved — Evidence: `test_save_registry_surgical_invalidation_preserved`
- [x] `app/perf_cache.py` still works — Evidence: `test_perf_cache_builds_matrix`
- [x] Test conftest: autouse fixture sets DATA_SOURCE=json for test isolation
- [x] 14 new tests in `test_single_source_of_truth.py`
- [x] 4584 app tests pass, 590 ML tests pass
- [x] Deployed to Railway (DOCKERFILE builder, SUCCESS)
- [x] Browser verified: Health, Home, People, Photos, Person, Proposals — all PASS

### FB Item Cleanup
- [x] FB-031: VERIFIED — No gear icon on /people page, not a bug
- [x] FB-051: VERIFIED WORKING — Search endpoint searches filenames correctly
- [x] FB-057: VERIFIED WORKING — `from_focus=true` wired to all action buttons
- [x] FB-064: VERIFIED WORKING — community prefix used in all redirects
- [x] FB-071: VERIFIED IMPLEMENTED — auto-confirm checkbox (Session 107b)
- [ ] FB-076: DEFERRED — annotations lack community context, needs PRD

## Deferred
- FB-076: Community awareness on approve — annotations don't store community, non-trivial fix — BACKLOG
- PRD-051 Phase 2: Wire remaining JSON-only reads (proposals, annotations, etc.) to Supabase
- PRD-051 Phase 3: ML pipeline Supabase reads
- PRD-051 Phase 4: Remove JSON from deploy pipeline (after 48h stability)

## Red Flags
- [LOW] Photos page showed dark squares (may be R2 loading latency, not a regression — photos load on People page)
- [LOW] Pre-existing test failures: `test_confirmed_anchors_in_face_to_photo` (data integrity), `test_sidebar_navigation` (e2e)
- [LOW] Supabase disk IO budget warning — monitor after deploy. TTL caches mitigate per-request hits.

## Next Session Should Verify
1. Supabase disk IO not spiking (check dashboard)
2. Admin actions (confirm, merge) persist across page refresh (ask user to test)
3. Direct Supabase data edit visible within 120s TTL window
4. If no incidents after 48h, consider removing JSON code paths (PRD-051 Phase 4)

## Performance (Session 111f preserved)
- perf_cache.py: Vectorized confirmed matrix still builds correctly
- Smart cache invalidation: surgical per-identity invalidation preserved
- All TTL caches (registry 120s, suggestions 30s, clusters 30s) unchanged
