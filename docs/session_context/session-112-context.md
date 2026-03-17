# Session 112 Context — Single Source of Truth Migration (PRD-051 Phase 1)

**Predecessor:** [Session 111d context](session-111d-context.md)
**PRD:** [docs/prds/051_single_source_of_truth.md](../prds/051_single_source_of_truth.md)

## Why This Session Exists

Session 111d exposed the 8th data corruption incident caused by three-source data divergence (Lesson 150). The pattern:
1. Admin action writes to Supabase + JSON
2. Something goes wrong (background thread fails, cache stale, volume not updated)
3. Next read comes from a different source → stale/wrong data served
4. User sees corrupted state, data repair is manual and error-prone

Previous incidents: Lessons 56, 69, 78, 85, 133, 141, 144, 147, 150.

## Research Findings (Session 111d Deep Research)

### Current Read Paths (Production, DATA_SOURCE=postgres)

| Function | Reads From | JSON Fallback? | TTL Cache |
|----------|-----------|---------------|-----------|
| `load_registry()` | Supabase `identities` + `identity_overrides` | YES — falls back to `identities.json` | 120s |
| `load_photo_registry()` | Supabase `photos` + `photo_faces` | YES — falls back to `photo_index.json` | None (one-shot) |
| `_build_caches()` | **Always `photo_index.json` via `json.load()`** | N/A — JSON is primary | None (one-shot) |
| `_load_photo_dimensions_cache()` | Always `photo_index.json` | N/A | None (one-shot) |
| `_load_date_labels()` | Supabase `date_labels` | YES | None (one-shot) |
| `_load_photo_locations()` | Supabase `photo_locations` | YES | None (one-shot) |

### Critical Split-Brain Vector

`_build_caches()` at `app/main.py:3931` calls `json.load(photo_index_path)` DIRECTLY — bypassing `load_photo_registry()` entirely. This means even in postgres mode, photo display depends on the Railway volume's `photo_index.json`. This is the #1 remaining split-brain vector.

### What Cannot Move to Supabase
- `embeddings.npy` — 12.5 MB NumPy binary, used for all face comparison
- Static reference files (`surname_variants.json`, `rhodes_context_events.json`) — never change at runtime

### Egress Budget Impact
- Current: ~1-2 GB/month with 1 admin (free plan: 5GB, grace period until 2026-04-13)
- After migration: slightly higher due to removing JSON fallback (more Supabase reads on cache miss)
- Manageable within free plan for now

## Known Gaps and Risks

1. **`_build_caches()` refactor is complex** — it builds `_photo_cache`, `_face_to_photo_cache`, and `_photo_id_aliases` from a combination of embeddings and photo_index. Changing the photo_index source from JSON to Supabase must preserve all the filename-based fallback logic.

2. **`identity_overrides` table** — Session 111d showed this table can hold stale `merged_into` values even when `identities` is fixed. Must understand when overrides are written and ensure they're consistent.

3. **ML pipeline** — Currently reads JSON directly. Phase 1 doesn't change ML, but local dev should work with `DATA_SOURCE=postgres` after this session.

4. **Regression risk** — This touches the core data loading path. Every page depends on `load_registry()` and `_build_caches()`. Must be tested exhaustively.

## Acceptance Criteria

- No `json.load()` on `identities.json` or `photo_index.json` in production read paths
- Direct Supabase data edits visible in app within 120s without deploy restart
- All admin actions (confirm, merge, reject, skip, tag) persist across app restart
- All existing tests pass
- Browser verified on production

## Breadcrumbs
- PRD: `docs/prds/051_single_source_of_truth.md`
- Lessons: 56, 69, 78, 85, 133, 141, 144, 147, 149, 150 in `tasks/lessons.md`
- BACKLOG: DATA-024 (single source of truth migration)
- Memory: `feedback_confirm_merge_needs_prd.md`, `feedback_never_modify_production_data.md`
