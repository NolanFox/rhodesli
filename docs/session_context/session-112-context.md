# Session 112 Context — Single Source of Truth Migration + FB Cleanup

**Predecessor:** [Session 111f context](session-111f-context.md) (NOT 111d — sessions 111e and 111f shipped after this context was first written)
**PRD:** [docs/prds/051_single_source_of_truth.md](../prds/051_single_source_of_truth.md)

## Why This Session Exists

Session 111d exposed the 8th data corruption incident caused by three-source data divergence (Lesson 150). The pattern:
1. Admin action writes to Supabase + JSON
2. Something goes wrong (background thread fails, cache stale, volume not updated)
3. Next read comes from a different source → stale/wrong data served
4. User sees corrupted state, data repair is manual and error-prone

Previous incidents: Lessons 56, 69, 78, 85, 133, 141, 144, 147, 150.

## What Shipped Since This Context Was First Written

Sessions 111e and 111f shipped performance + fix work that this session must not regress:

- **Session 111e (v0.99.19):** TTL caches for suggestions (30s) and speed-run clusters (30s). FB-072 approval history. FB-075 face overlays. FB-077 confirm UX.
- **Session 111f (v0.99.20):** `app/perf_cache.py` — precomputed vectorized confirmed identity matrix. Smart cache invalidation in `save_registry()` (surgical per-identity, not full flush). `find_nearest_neighbors_fast()` added to `core/neighbors.py`. Focus mode 124ms warm, Speed-run 171ms warm.

**Key code to preserve in `save_registry()`:**
```python
# Smart cache invalidation (Session 111f) — DO NOT REMOVE
if changed_ids:
    for cid in changed_ids:
        invalidate_neighbors_cache(identity_id=cid)
else:
    invalidate_neighbors_cache()

if changed_ids:
    invalidate_cluster_review_caches(changed_ids=changed_ids)
else:
    invalidate_cluster_review_caches()
```

## Research Findings

### Current Read Paths (Production, DATA_SOURCE=postgres)

| Function | Reads From | JSON Fallback? | TTL Cache |
|----------|-----------|---------------|-----------|
| `load_registry()` | Supabase `identities` + `identity_overrides` | YES — falls back to `identities.json` | 120s |
| `load_photo_registry()` | Supabase `photos` + `photo_faces` | YES — falls back to `photo_index.json` | None (one-shot) |
| `_build_caches()` | **Both `photo_index.json` AND `load_photo_registry()`** | N/A | None (one-shot) |
| `_load_photo_dimensions_cache()` | Always `photo_index.json` | N/A | None (one-shot) |
| `_load_date_labels()` | Supabase `date_labels` | YES | None (one-shot) |
| `_load_photo_locations()` | Supabase `photo_locations` | YES | None (one-shot) |

### Critical Split-Brain Vector

`_build_caches()` in `app/main.py` calls `json.load(photo_index_path)` DIRECTLY — AND calls `load_photo_registry()`. It builds filename-based fallback maps from BOTH sources and merges them. The JSON read is the #1 remaining split-brain vector.

### `_build_caches()` Field Mapping — JSON vs Supabase

This is the critical mapping for eliminating the JSON read. **Verify during Phase 0.**

| `photo_index.json` field | PhotoRegistry method | Supabase table.column |
|--------------------------|---------------------|----------------------|
| `photos[pid].path` | `get_photo_path(pid)` | `photos.path` |
| `photos[pid].face_ids` | `get_faces_in_photo(pid)` | `photo_faces.face_id` |
| `photos[pid].source` | `get_source(pid)` | `photos.source` |
| `photos[pid].collection` | `get_collection(pid)` | `photos.collection` |
| `photos[pid].source_url` | `get_source_url(pid)` | `photos.source_url` |
| `photos[pid].width` | `get_metadata(pid)["width"]` | `photos.width` |
| `photos[pid].height` | `get_metadata(pid)["height"]` | `photos.height` |
| `photos[pid].upload_date` | `get_metadata(pid)["upload_date"]` | `photos.upload_date` |
| `photos[pid].uploaded_by` | `get_metadata(pid)["uploaded_by"]` | `photos.uploaded_by` |
| `photos[pid].job_id` | `get_metadata(pid)["job_id"]` | `photos.job_id` |
| `face_to_photo[face_id]` | `get_photo_for_face(face_id)` | `photo_faces.photo_id` |

**CAUTION:** `_build_caches()` uses `filename_to_face_ids_ordered` which preserves face_id ORDER from `photo_index.json`. The registry's `get_faces_in_photo()` may return faces in different order. Sort consistently by face_id to avoid face overlay rendering differences.

### What Cannot Move to Supabase
- `embeddings.npy` — 12.5 MB NumPy binary, used for all face comparison
- Static reference files (`surname_variants.json`, `rhodes_context_events.json`) — never change at runtime

### Supabase Resource Constraints — CRITICAL (2026-03-17)

**Disk IO Budget warning received.** Supabase emailed: "Your project is depleting its Disk IO Budget." This means:
- Response times on requests can increase noticeably
- CPU usage rises due to IO wait
- Instance may become unresponsive

**Impact on this session:** Eliminating JSON fallback means MORE Supabase reads (every cache miss hits Supabase instead of local JSON). This could WORSEN the disk IO situation.

**Mitigations:**
1. TTL caches are already in place (120s for registry, 30s for suggestions/clusters). These prevent per-request Supabase hits.
2. `_build_caches()` runs ONCE at startup, not per-request. Switching from JSON to Supabase here adds 1 extra query at boot, not ongoing load.
3. Monitor Supabase dashboard after deploy. If IO spikes, rollback via `DATA_SOURCE=json`.
4. Consider upgrading compute add-on ($25/mo) if the warning persists after this session.
5. BACKLOG: EGRESS-004 — investigate which queries consume the most IO (check Supabase query stats).

### Egress Budget Impact
- Current: ~1-2 GB/month with 1 admin (free plan: 5GB, grace period until 2026-04-13)
- After migration: slightly higher due to removing JSON fallback (more Supabase reads on cache miss)
- Manageable within free plan for now — but disk IO is a new constraint to watch

## Known Gaps and Risks

1. **`_build_caches()` refactor is complex** — it builds `_photo_cache`, `_face_to_photo_cache`, and `_photo_id_aliases` from a combination of embeddings and photo_index. The JSON read can be eliminated because the photo registry already has all the same data, but the replacement must produce identical data structures.

2. **`identity_overrides` table** — Session 111d showed this table can hold stale `merged_into` values even when `identities` is fixed. Must understand when overrides are written and ensure they're consistent.

3. **ML pipeline** — Currently reads JSON directly. Phase 1 doesn't change ML, but local dev should work with `DATA_SOURCE=postgres` after this session.

4. **Regression risk** — This touches the core data loading path. Every page depends on `load_registry()` and `_build_caches()`. Must be tested exhaustively.

5. **`app/perf_cache.py` dependency** — Session 111f added a vectorized distance cache that calls `load_registry()` and `get_face_data()`. If `load_registry()` raises on Supabase failure (instead of returning stale JSON), `perf_cache` will propagate the error. This is correct behavior (fail loud) but must be tested.

6. **Failure mode design** — Returning an empty registry on Supabase failure would make every page show 0 identities. This is WORSE than stale JSON. Better to raise and let the caller handle it (500 page). The JSON backup exists for manual recovery or env var rollback, not automatic fallback.

## Outstanding FB Items (from Session 111 series)

These 6 items were not resolved in sessions 111-111f and are included in this session:

| FB | Description | Severity | Investigation Notes |
|----|-------------|----------|-------------------|
| FB-031 | Face grid broken on gear click (People page) | P1 | `min-w-[150px]` overflow in narrow containers |
| FB-051 | Photo filename search not working | P1 | Search endpoint exists but may lack community prefix or cache population |
| FB-057 | Focus mode doesn't auto-advance after action | P1 | HTMX response may not swap in next card |
| FB-064 | Override merge redirect drops community | P0 | Code uses `_nav_prefix_from_request()` — may already be fixed, needs verification |
| FB-071 | Approve should also confirm identity | P0 | Approve endpoint doesn't promote state |
| FB-076 | Community awareness on approve | P1 | Approve may not associate identity with community |

## Acceptance Criteria

- No `json.load()` on `identities.json` or `photo_index.json` in production read paths
- `DATA_SOURCE` default changed to "postgres" (json path kept as rollback for 48h)
- Direct Supabase data edits visible in app within 120s without deploy restart
- All admin actions (confirm, merge, reject, skip, tag) persist across app restart
- Session 111f performance preserved (focus <500ms warm, neighbors <500ms warm)
- All 6 FB items resolved (FIXED or VERIFIED with evidence)
- All existing tests pass
- Browser verified on production

## Breadcrumbs
- PRD: `docs/prds/051_single_source_of_truth.md`
- Lessons: 56, 69, 78, 85, 133, 141, 144, 147, 149, 150 in `tasks/lessons.md`
- BACKLOG: DATA-024 (single source of truth migration)
- Session 111f assessment: `docs/assessments/session-111f-assessment.md`
- Memory: `feedback_confirm_merge_needs_prd.md`, `feedback_never_modify_production_data.md`
