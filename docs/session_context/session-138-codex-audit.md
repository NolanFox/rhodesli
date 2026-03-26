# Session 138 Codex CLI Audit

**Auditor**: Codex CLI v0.115.0 (gpt-5.4)
**Agent type**: Independent (fresh context)
**Scope**: Session 138 changes — identity_routes.py, main.py, person_routes.py, page_routes.py, registry.py, cards.py, nav.py
**Date**: 2026-03-26

## Findings

### P0: None

### P1: FB-012 community filter under-fills from truncated pool
- `get_all_neighbors()` returns max 20 results, but community filtering after that can eliminate most
- **Fix applied**: Increased fetch_limit from 20 to 60 when community_filter is "same" or "cross"
- Commit: e7ea7c8

### P2: FB-013 cache invalidation incomplete
- `invalidate_neighbors_cache()` only called in primary reject path
- Other paths: reject-match, unreject, bulk-reject all missed
- **Fix applied**: Added cache invalidation to all 3 additional paths
- Commit: e7ea7c8

### P3: No issues
- `_is_real_name` removal safe — duplicate-name protection still applies to real names only
- `negative_ids` filter uses correct `identity:{id}` format
- `cards.py` imports safe — lazy `app.main` imports, no circular dependency

## Assessment
- **Value**: STRONG — P1 finding would have caused real user-facing bugs (empty Load More results)
- **Would we have found this ourselves?**: The P1 pool truncation issue — unlikely without testing with community filter. The P2 cache paths — eventually, but Codex found it faster.
