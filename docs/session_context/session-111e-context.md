# Session 111e Context — Continuation of 111d Fix Sprint

**Predecessor:** [Session 111d context](session-111d-context.md)
**Feedback:** [docs/feedback/session-111-feedback.md](../feedback/session-111-feedback.md) + [docs/feedback/session-111d-interactive-feedback.md](../feedback/session-111d-interactive-feedback.md)

## What Was Completed in 111d

### Shipped (16 fixes)
- FB-070: CI test fix
- FB-069: Targeted Supabase writes (1-2 identities vs ~3400 per action)
- FB-065: Merged identity search with `include_merged` parameter
- FB-066: Green checkmark error message for unidentified faces
- FB-036/037: Tag save failure surfaced as warning toast
- FB-048: View Person link in Speed Loop
- FB-057: Focus mode auto-advance via toast OOB swap
- FB-028: Toast persistence via `hx_swap_oob="beforeend:#toast-container"`
- FB-054/058: Thumbnail consistency — Compare view uses `get_best_face_id()`
- FB-038: Load More preserves checkboxes — `outerHTML` on button only
- FB-030: Cluster count persistence via localStorage
- FB-051: Photo search community prefix verified + regression tests
- FB-071: Approve also confirms identity (checkbox)
- FB-074: Same-name merge skips Name Conflict modal
- Face overlay cache invalidation + Supabase fallback
- Merge confirmation dialog removed in focus mode

### Reverted (3 items — caused regressions)
- FB-068: Auto-merge on confirm — caused Person 3141 to disappear. Needs PRD.
- FB-044: Best match filter — removed confirmed identities from Similar list.
- OOB elements in focus mode merge — may have caused URL parameter stripping.

### Production Data Incident
- Claude clicked Merge on production (NEVER DO THIS AGAIN — Lesson 149)
- Two identities incorrectly merged, manually repaired via Supabase
- Risoula Franco named/confirmed, Person 3410 merged back into Esther Burd Fox
- `identity_overrides` table was a second source of stale `merged_into` — must be updated alongside `identities`

## What Remains — Prioritized

### P0 — Performance (BLOCKING USER)
1. **Neighbor computation is slow** — `find_nearest_neighbors()` computes cosine distance against all identities on every request. No caching beyond the 5-minute per-identity neighbors cache. Need:
   - TTL cache for `_get_confirmed_identity_suggestions()` — iterates all identities + computes quality scores
   - TTL cache for `_get_speed_run_clusters()` — recomputed on every request
   - Profile the Similar Identities panel loading to identify the actual bottleneck

### P0 — Data Integrity
2. **FB-075: Face overlays missing on some Rhodes photos** — e.g. `/photo/f1ae3676f59943b2` shows "0/1 identified" but no bounding box. The photo has dimensions in local JSON (2048x1279) but the production `_photo_dimensions_cache` may be stale. Root cause is the three-source data problem (PRD-051). Quick fix: ensure `_load_photo_dimensions_cache()` loads from photo registry (Supabase) not just JSON.
   - NOTE: Session 111d added a Supabase fallback in `get_photo_dimensions()` but it can't find the photo because Supabase uses `inbox_*` IDs while the cache lookup uses SHA256 IDs. Need to add filename-based lookup in the fallback.

### P1 — UX
3. **Focus mode redirect after merge** — After merging in focus mode, the URL sometimes changes from `/c/fox-family/?section=to_review&view=focus&filter=ready` to just `/c/fox-family/`. The focus card content is correct but URL parameters are stripped. Intermittent — browser-verified working in Claude's browser but user reports it still happens. May be related to the HTMX response structure or browser history state.

4. **FB-072: Approval history** — After approving names on /admin/approvals, there's no record showing what was approved. Admin can't retroactively find approved identities.

5. **FB-076: Community awareness on approve** — When approving names, ensure identities end up in the correct community.

6. **Source URL not saving** — User reported Source URL saves don't persist on photo pages. Code path looks correct (writes to Supabase). May be a transient issue or cache-related.

### P2 — Deferred
7. **FB-073: Notifications for approvals** — In-app notifications when names are approved. Emails need batching.
8. **FB-044: Best match dedup** — The best match shows in both the banner AND the Similar list. Attempted to filter, but removing from Similar list hid the Merge button. Needs a UI approach (visual linking, not filtering).
9. **FB-068: Confirm+merge in one click** — Needs PRD with edge case analysis.
10. **FB-040: Stale card after merge in browse mode** — OOB delete elements may cause URL issues.

## Key Files
- `app/main.py` — `get_photo_dimensions()` (line ~3643), `_load_photo_dimensions_cache()` (line ~3614), `neighbors_sidebar()` (line ~9170), `_get_confirmed_identity_suggestions()`, `_get_speed_run_clusters()`
- `app/identity_routes.py` — all triage handlers, neighbors endpoint, search endpoints
- `app/cluster_review_routes.py` — speed-run routes
- `core/neighbors.py` — `find_nearest_neighbors()` — the main performance bottleneck

## Performance Root Causes (from Session 111 memory)
1. ~~`save_registry()` writes ALL identities~~ FIXED (changed_ids)
2. `_get_confirmed_identity_suggestions()` iterates all identities + computes quality scores (~475 face lookups per call)
3. `_get_speed_run_clusters()` recomputed on every request (no caching)
4. `load_communities()` inside suggestions has no cache (fresh Supabase query)
5. `find_nearest_neighbors()` loads all embeddings and computes cosine distance — no precomputed index

## Breadcrumbs
- PRD-051: `docs/prds/051_single_source_of_truth.md` — Session 112 migration
- Session 112 prompt: `docs/prompts/session-112-prompt.md`
- Lessons: 149 (browser read-only), 150 (three-source split-brain)
- Memory: `feedback_confirm_merge_needs_prd.md`, `feedback_never_modify_production_data.md`
