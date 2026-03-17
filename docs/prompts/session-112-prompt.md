# Session 112 — Single Source of Truth + FB Cleanup (PRD-051 Phase 1)

## Context
@docs/session_context/session-112-context.md
@docs/prds/051_single_source_of_truth.md

Session 111d exposed the 8th data corruption incident from three-source data divergence (Lessons 56→69→78→85→133→141→144→147→150). This session implements PRD-051 Phase 1: make Supabase the single read source for identities and photos. No more JSON reads in production. Also closes out 6 remaining FB items from the 111 series.

## CRITICAL CONSTRAINTS — READ BEFORE STARTING

1. **ZERO REGRESSIONS.** Every change must be tested before AND after. If you're not sure a change is safe, plan it out first. Ask if unclear.
2. **Plan before coding.** Before modifying ANY read path, write out: what reads from this path, what would break if it returns different data, what test covers it.
3. **No fly-by-night decisions.** Every architectural choice gets documented in the session log with rationale.
4. **Browser verify EVERYTHING.** Every phase that touches data loading must be verified on production. READ-ONLY browser checks — NEVER click action buttons (Lesson 149).
5. **Measure twice, cut once.** Session 111d shipped 3 regressions. That cannot happen again.
6. **Preserve Session 111f additions.** `save_registry()` now has smart cache invalidation (surgical `invalidate_neighbors_cache(identity_id=...)` + `invalidate_cluster_review_caches(changed_ids=...)` + `mark_confirmed_dirty()`). These MUST be preserved. `app/perf_cache.py` calls `load_registry()` and `get_face_data()` — test that it still works after read-path changes.
7. **Rollback plan.** Keep `DATA_SOURCE` as an env var escape hatch for 48h post-deploy. If production breaks, set `DATA_SOURCE=json` on Railway and redeploy. Only remove in Phase 3 after 48h with no incidents.
8. **Supabase disk IO budget is depleting.** Email received 2026-03-17. Removing JSON fallback means more Supabase reads on cache miss. TTL caches mitigate this (most reads are cached), and `_build_caches()` runs once at startup. Monitor Supabase dashboard after deploy. If IO spikes, rollback immediately.

## Pre-Requisites
1. Read `tasks/lessons.md` — especially Lessons 56, 69, 78, 85, 133, 141, 144, 147, 149, 150
2. Read `docs/prds/051_single_source_of_truth.md` — the full PRD
3. Read `docs/session_context/session-112-context.md` — research findings and risks
4. Read `docs/CODING_RULES.md`
5. Set `.claude/current_session.txt` to `112`
6. Set `.claude/session_mode.txt` to `implementation`
7. Run `make test-fast` — record baseline test count

---

## Phase 0: Audit + Plan (20 min)

**Do NOT write code in this phase.** This is planning only.

1. `git log --oneline -10` — confirm 111f on main (not 111d — sessions 111e and 111f have shipped since this prompt was first written)
2. Map every split-brain vector — grep for ALL of these in `app/`:
   - `json.load` (any JSON file read)
   - `DATA_SOURCE` checks
   - `REGISTRY_PATH` reads
   - `photo_index_path` reads
   - `.load(` calls on data paths
3. For EACH vector, document in session log:
   - File and line number (DO NOT rely on line numbers in this prompt — grep fresh)
   - What Supabase function would replace it
   - What breaks if removed (downstream callers)
   - What test covers it
4. **Build the `_build_caches()` mapping table** (see context file for template)
5. Verify `app/perf_cache.py` will still work after changes (it calls `load_registry()` + `get_face_data()`)
6. Write the plan to the session log BEFORE starting Phase 1
7. /clear after this phase

---

## Phase 1: Identity Read Path — Supabase Only (30 min)

### 1A: `load_registry()` — remove JSON fallback
- Find `load_registry()` in `app/main.py` (grep for `def load_registry`)
- Remove the `if DATA_SOURCE == "postgres"` branch — always call `IdentityRegistry.load_from_postgres()`
- **Failure mode:** If Supabase fails, log error with `logging.error()` and RE-RAISE the exception. Do NOT return an empty registry — that would make every page show 0 identities, which is worse than stale JSON. Let the caller handle the error (500 page). The JSON backup exists for manual recovery, not automatic fallback.
- Keep JSON write in `save_registry()` as backup — label it "backup only, never read in production"
- Keep `DATA_SOURCE` env var alive (rollback escape hatch) but change the default from `"json"` to `"postgres"`

### 1B: `save_registry()` — verify write-through
- Verify `save_registry()` writes to Supabase synchronously (not background thread) when DATA_SOURCE=postgres
- Verify `changed_ids` parameter works correctly with Supabase writes
- Verify `identity_overrides` table is updated consistently (Session 111d bug)
- **PRESERVE** the smart cache invalidation from Session 111f:
  - `invalidate_neighbors_cache(identity_id=cid)` for surgical invalidation
  - `invalidate_cluster_review_caches(changed_ids=changed_ids)` for surgical cluster cache
  - `mark_confirmed_dirty()` via `invalidate_cluster_review_caches()`
- DO NOT remove or simplify the JSON-mode background thread path yet — keep as dead code until Phase 3

### Tests (write BEFORE implementing)
- `test_load_registry_reads_from_supabase` — mock Supabase, verify JSON is NOT read
- `test_save_registry_writes_to_supabase` — verify Supabase write is called
- `test_load_registry_raises_on_supabase_failure` — no silent fallback, error propagates
- `test_perf_cache_works_with_supabase_registry` — `get_confirmed_distances()` returns results
- Run ALL existing registry tests to catch regressions

### Commit + /clear after this phase

---

## Phase 2: Photo Read Path — Supabase Only (30 min)

### 2A: `_build_caches()` — the critical fix

Find `_build_caches()` in `app/main.py` (grep for `def _build_caches`).

Currently this function reads from BOTH `photo_index.json` (via `json.load()`) AND `load_photo_registry()`. The JSON read builds `best_raw_entries` which provides `filename_to_face_ids_ordered` and `filename_to_photo_index_id`. The registry read builds `best_registry_entries` which provides source/collection/face_ids/metadata.

**The fix:** Remove the `json.load(photo_index_path)` block entirely. The photo registry already has ALL the same data (face_ids, path, source, collection, metadata). The JSON read was only needed as a fallback when registry and embeddings had mismatched IDs — but since Session 105b, all IDs are consistent.

**Mapping table** (verify these against actual Supabase `photos` + `photo_faces` tables):

| `photo_index.json` field | PhotoRegistry method | Supabase table.column |
|--------------------------|---------------------|----------------------|
| `photos[pid].path` | `get_photo_path(pid)` | `photos.path` |
| `photos[pid].face_ids` | `get_faces_in_photo(pid)` | `photo_faces.face_id` |
| `photos[pid].source` | `get_source(pid)` | `photos.source` |
| `photos[pid].collection` | `get_collection(pid)` | `photos.collection` |
| `photos[pid].source_url` | `get_source_url(pid)` | `photos.source_url` |
| `photos[pid].width/height` | `get_metadata(pid)` | `photos.width`, `photos.height` |
| `photos[pid].upload_date` | `get_metadata(pid)` | `photos.upload_date` |
| `face_to_photo[face_id]` | `get_photo_for_face(face_id)` | `photo_faces.photo_id` |

**Verify this mapping is complete** by reading `_build_caches()` line by line and checking every field it reads from `photo_index_raw`.

**CAUTION:** `filename_to_face_ids_ordered` preserves the ORDER of faces from `photo_index.json`. The registry's `get_faces_in_photo()` may return faces in a different order. If face overlay rendering depends on face order, sort consistently (e.g., by face_id alphabetically).

### 2B: `load_photo_registry()` — remove JSON fallback
- Same pattern as 1A — always load from Supabase, raise on failure

### 2C: `_load_photo_dimensions_cache()` — use photo registry
- Find `_load_photo_dimensions_cache()` (grep for it)
- Currently reads `photo_index.json` directly
- Replace with data from `load_photo_registry()`

### Tests (write BEFORE implementing)
- `test_build_caches_does_not_read_json` — verify no `json.load()` call on photo_index
- `test_photo_dimensions_from_supabase` — dimensions come from registry, not JSON
- `test_face_order_preserved` — face overlays render in consistent order
- Run ALL existing photo/face tests

### Commit + /clear after this phase

---

## Phase 3: Clean Up DATA_SOURCE (15 min)

**IMPORTANT:** Do NOT remove `DATA_SOURCE` env var entirely. Change the default to `"postgres"` but keep the `"json"` code paths as dead code for 48h rollback safety. Add a deprecation log warning if `DATA_SOURCE=json` is set.

1. Change default: `DATA_SOURCE = os.environ.get("DATA_SOURCE", "postgres")`
2. Add warning: `if DATA_SOURCE == "json": logging.warning("DATA_SOURCE=json is deprecated. Use postgres.")`
3. Remove `DATA_SOURCE` from `.env.example` comments (it's no longer needed)
4. Update CLAUDE.md rules referencing DATA_SOURCE
5. Leave the json code paths in place — they'll be removed in a future cleanup session after 48h

### Commit + /clear after this phase

---

## Phase 4: FB Item Cleanup (20 min)

Close out the 6 remaining FB items from the 111 series. These are small, independent fixes.

### FB-031: Face grid broken on gear/settings click
- **Root cause:** `face_card()` had `min-w-[150px]` causing overflow in narrow identity card containers
- **Fix:** Find `face_card` or the gear/settings expand panel in `app/main.py`. Remove `min-w-[150px]`, use responsive grid `grid-cols-2 sm:grid-cols-3 gap-2`
- **Test:** Verify in browser (READ-ONLY) that People page gear icon expands a clean grid

### FB-051: Photo filename search not working
- **Investigation:** Search endpoint at `/api/search` should match filenames. Grep for the search handler, check if `_photo_cache` filename lookup is populated, check if results include community prefix in links
- **Fix:** If search works but links lack community prefix, add `_nav_prefix_from_request()`. If `_photo_cache` isn't populated, check if `_build_caches()` runs before search.
- **Test:** `curl` the search endpoint with a known filename

### FB-057: Focus mode auto-advance after action
- **Verify on production (READ-ONLY):** Navigate to focus mode, read the DOM of confirm/skip/reject buttons. Check `hx-target` and response format. If the response swaps in a new card, it works. If it only updates the current card, it doesn't auto-advance.
- **If broken:** The HTMX response from confirm/skip/reject should return the NEXT identity card to replace the current focus container.

### FB-064: Override merge redirect — verify community prefix
- **Verify on production (READ-ONLY):** Navigate to Fox Family focus mode. Read an Override button's `hx-post` URL via JS. Verify it includes `/c/fox-family/` prefix.
- **Document result:** PASS or FAIL with evidence

### FB-071: Approve should also confirm the identity
- **Find** the approve endpoint in `app/admin_routes.py` or `app/engagement_routes.py`
- **Check** if there's already an "Also confirm" checkbox
- **Fix:** When approving a name, if the identity is INBOX/PROPOSED, also call `registry.confirm_identity()`. Use the existing checkbox if present, or add one.
- **Test:** Unit test that approve with confirm=true promotes state to CONFIRMED

### FB-076: Community awareness on approve
- **Verify:** Read the approve endpoint. Check if it associates the identity with the correct community via `identity_communities` table.
- **If missing:** After confirm, ensure `_update_identity_community()` or equivalent is called.
- **Document result:** PASS or FAIL with evidence

### Commit after all FB fixes

---

## Phase 5: Deploy + Exhaustive Verification (20 min)

1. Run full test suite: `make test-fast` + `make test-ml`
2. `git push origin main`
3. Deploy via `railway deploy` (not git push — avoids RAILPACK builder issue)
4. Wait for deploy SUCCESS (verify builder is DOCKERFILE)
5. **MANDATORY production checks (READ-ONLY — no clicking action buttons):**
   - [ ] Home page loads with photos and face counts
   - [ ] People page shows all confirmed identities (count matches pre-deploy)
   - [ ] New Matches page loads with identity cards
   - [ ] Focus mode shows identity with Similar panel
   - [ ] Photo page shows face overlays with bounding boxes
   - [ ] Search returns results (including filename search if FB-051 fixed)
   - [ ] Person page loads for confirmed identity
   - [ ] Person page loads for INBOX identity
   - [ ] Speed-run page loads in <500ms (perf_cache still working)
   - [ ] Neighbors API returns in <500ms
   - [ ] Approvals page loads with history (FB-072 regression check)
   - [ ] Face grid on People page gear icon renders cleanly (FB-031)
6. **Data persistence test (ask user to perform):**
   - Ask user to confirm one identity, then hard refresh — verify it persisted
   - Ask user to merge one identity, then hard refresh — verify it persisted
7. **Direct Supabase edit test:**
   - Read an identity name via Supabase query
   - Wait 120s (TTL)
   - Verify the app shows the current Supabase value (not a stale cache)
8. **Rollback readiness:**
   - Verify `DATA_SOURCE=json` is NOT set on Railway (should use default "postgres")
   - Confirm you could set it to "json" and redeploy as rollback if needed

---

## Phase 6: Harness Outputs (10 min)

1. Assessment: `docs/assessments/session-112-assessment.md`
   - Include FB item status for all 6 items (FIXED/VERIFIED/DEFERRED)
   - Include performance comparison (before/after for key endpoints)
2. Session log: `docs/session_logs/session-112-log.md`
3. ROADMAP: Add session entry, update version
4. CHANGELOG: Session 112 entry
5. BACKLOG: Update DATA-024 status + FB item statuses
6. Verify `git log origin/main..HEAD` is empty

---

## Parallelization Plan

| Track | Phase | Files Touched | Dependencies |
|-------|-------|---------------|-------------|
| Main | 0, 5, 6 | docs, config | Sequential |
| Worktree A | 1 (identity read path) | `app/main.py` (load_registry, save_registry) | None |
| Worktree B | 2 (photo read path) | `app/main.py` (_build_caches, load_photo_registry, _load_photo_dimensions_cache) | Depends on A (same file) |
| Worktree C | 4 (FB fixes) | `app/main.py` (face_card), `app/admin_routes.py`, `app/identity_routes.py` | None |

**IMPORTANT:** Phases 1 and 2 both touch `app/main.py` — they CANNOT run in parallel worktrees. Run them sequentially. Phase 4 (FB fixes) CAN run in parallel with Phase 1 if it only touches different files (admin_routes, identity_routes). But FB-031 touches main.py, so be careful.

**Recommended order:** Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6

---

## Verification Checklist (before declaring done)

### Data Path
- [ ] No `json.load()` calls on `identities.json` or `photo_index.json` in `app/` read paths
- [ ] `_build_caches()` uses `load_photo_registry()` not `json.load()`
- [ ] `_load_photo_dimensions_cache()` uses photo registry not `json.load()`
- [ ] `load_registry()` always loads from Supabase (when DATA_SOURCE=postgres)
- [ ] `save_registry()` writes Supabase synchronously + JSON as backup
- [ ] `DATA_SOURCE` default changed from "json" to "postgres"
- [ ] JSON code paths still exist as rollback (not removed yet)

### Performance (111f preserved)
- [ ] `app/perf_cache.py` still builds confirmed matrix correctly
- [ ] `invalidate_neighbors_cache(identity_id=...)` surgical invalidation preserved
- [ ] `invalidate_cluster_review_caches(changed_ids=...)` preserved
- [ ] Focus mode still loads in <500ms warm
- [ ] Neighbors API still responds in <500ms warm

### FB Items
- [ ] FB-031: Face grid renders cleanly (browser verified)
- [ ] FB-051: Filename search works or documented why not
- [ ] FB-057: Focus auto-advance verified or documented
- [ ] FB-064: Override redirect verified correct
- [ ] FB-071: Approve confirms identity (if checkbox checked)
- [ ] FB-076: Approve community association verified

### Standard
- [ ] All admin actions persist across app restart (user-verified)
- [ ] All tests pass (app + ML)
- [ ] Deployed and browser verified (READ-ONLY)
- [ ] `git log origin/main..HEAD` is empty
- [ ] Assessment written with evidence
