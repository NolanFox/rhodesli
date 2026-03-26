# Session 139 Context — Mega Fix Sprint + Triage Workflow Redesign

**Predecessor:** Session 138 (v0.99.49) — Interactive feedback + refactor Phase 2
**Date:** 2026-03-26

## What Session 138 Delivered
- 13 feedback items received, 5 fixed (FB-006, FB-012, FB-013 + 2 Codex)
- REFACTOR-001 Phase 2: 848 lines extracted from main.py (10,638→9,790)
- Codex CLI audit (gpt-5.4): STRONG value, caught P1 fetch limit issue

## Research Findings (5 parallel agents)

### R1: Missing Crops Root Cause
- **photo_faces table does NOT have bbox/quality columns** — only face_id + photo_id
- bbox/quality data lives exclusively in embeddings.npy
- **Two crop generation paths**:
  - Web upload: `_background_ingest()` uploads crops to R2 immediately after ingest
  - CLI ingest: `generate_crop()` writes to `app/static/crops/`, then `upload_to_r2.py` syncs
- **Root cause**: The ~750 Rhodes community faces were ingested via CLI but their crops may not have been uploaded to R2, OR the local crop files don't exist
- **Fix**: Script to check which face_ids have embeddings but no crop on R2, regenerate from source photos + bbox in embeddings.npy, upload to R2

### R2: Focus Mode Merge Behavior
- **The merge endpoint DOES have from_focus support** — returns `get_next_focus_card()` like confirm/skip/reject
- **Possible bug**: The `exclude_id=actual_target_id` may be wrong after direction swap — it excludes the surviving identity, not the source that was in the focus card
- **FB-008 Bulk merge**: The bulk-merge endpoint has **zero from_focus support** — returns only a toast, replaces neighbors panel content
- **Fix**:
  1. Verify merge auto-advance works (may be an HTMX response parsing issue)
  2. Add from_focus support to bulk-merge endpoint

### R3: Confirm vs Identify Design
- **Google Photos**: No explicit "confirm." Clusters just exist. Name is separate optional action.
- **Apple Photos**: Similar — unnamed groups are valid. Naming is separate.
- **Current Rhodesli**: Code already partially supports this — `_is_real_name()`, `is_identified` computed in page_routes
- **Recommended approach**: Option A — add `is_named` derived field (no schema change needed, compute from name)
- **Filters needed**: People page filter "All" / "Named" / "Needs Name"
- **FB-014 (150-card limit)**: "Edit in Admin" links to `#identity-{id}` anchor, but card may not be loaded. Fix: add `/api/identity/{id}/focus` endpoint that loads a specific identity directly in focus mode

### R4: Performance Opportunities
1. **get_best_face_id() — O(N*M) quality scoring** per identity card render. Fix: precompute + cache best_face_id per identity
2. **_global_identity_info linear scan — O(N²)** in perf_cache. Fix: build dict lookup (2-line change)
3. **150-card limit sorts all ~1500 items** before truncating. Fix: avoid quality-based sorting in browse mode
4. **_focus_sort_key runs quality scoring** on all items during sort. Fix: precompute sort keys
5. **Template rendering**: identity_card is 566 lines of Python generating HTML. Consider caching rendered HTML fragments

### R5: Refactor Phase 2 Remainder
- **identity_card_expanded**: 272 lines, 9 main.py dependencies (5 unextracted)
- **identity_card**: 566 lines, 18+ main.py dependencies (10 unextracted)
- **Shared dependencies** (10 functions needed by both): _sequential_display_name, get_best_face_id, resolve_face_image_url, get_photo_id_for_face, get_face_quality, _proposal_banner, _proposal_badge_inline, _get_identities_with_proposals, _get_proposal_target_count, _get_best_match_for_identity
- **Extraction order**: Extract shared utility functions first, then identity_card_expanded, then identity_card
- **Risk**: HIGH — these functions read module-level caches (_photo_registry_cache, _face_data_cache, etc.)
- **Estimated reduction**: ~850 lines from main.py → target ~8,940

## Dependency Graph for Parallelization

```
Track A (data fix — independent): Missing crops pipeline
Track B (UX fixes — sequential):
  B1: Focus mode merge advance fix
  B2: Bulk merge from_focus support
  B3: "Edit in Admin" deep link fix (FB-014)
Track C (design + implement — sequential):
  C1: PRD for triage workflow (confirm vs identify)
  C2: People page "Needs Name" filter
  C3: Focus mode identity direct-load endpoint
Track D (refactor — sequential, touches main.py):
  D1: Extract shared utility functions
  D2: Extract identity_card_expanded
  D3: Extract identity_card
Track E (performance — can parallel with D):
  E1: _global_identity_info dict lookup (2-line fix)
  E2: Precompute best_face_id cache
  E3: Optimize sort key computation
```

## Cross-references
- BACKLOG: FB-001/011 (crops), FB-002/003/010 (merge advance), FB-004/005 (confirm vs identify), FB-008 (bulk merge), FB-014 (150-card limit)
- Lessons: 149 (browser read-only), 154 (merge verification), 88 (monolithic main.py)
- PRDs needed: triage workflow redesign (FB-004)
