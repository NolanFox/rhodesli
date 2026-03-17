# Session 111e Log — Performance + Remaining Fixes
Started: 2026-03-17T04:00Z
Prompt: docs/prompts/session-111e-prompt.md

## Phase Checklist
- [x] Phase 0: Orient — confirmed 111d complete, read context
- [x] Phase 1: Performance — TTL caches for suggestions + speed-run clusters
- [x] Phase 2: FB-077 Confirm button UX — inline error for unidentified persons
- [x] Phase 3: FB-075 Face overlay fix — photo dimensions from Supabase registry
- [x] Phase 4: P1 fixes — focus URL, approval history
- [ ] Phase 5: Deploy + Verify — deployed, awaiting verification
- [ ] Phase 6: Harness outputs

## Implementation Details

### Phase 1: Performance
- Added `_speed_run_cache` (keyed by community_slug, 30s TTL) for `_get_speed_run_clusters()`
- Added `_suggestions_cache` (keyed by identity_id + community_slug, 30s TTL) for `_get_confirmed_identity_suggestions()`
- `invalidate_cluster_review_caches()` exported and called from:
  - `save_registry()` — every identity mutation
  - `_invalidate_all_caches()` — full cache reset
- Test ordering issue fixed: `_mock_registry()` now clears caches

### Phase 2: FB-077 Confirm Button
- Pre-check for `Unidentified Person *` names BEFORE calling `registry.confirm_identity()`
- Person page: returns inline amber error div with id="person-admin-actions"
- Focus mode: returns 409 + warning toast
- 2 new tests

### Phase 3: FB-075 Face Overlays
- `_load_photo_dimensions_cache()` now also populates from `load_photo_registry()` (Supabase-backed)
- Photos uploaded after local JSON was synced now have dimensions available
- Won't overwrite entries from local JSON (authoritative source)

### Phase 4: P1 Fixes
- Focus mode URL stripping: added `hx_push_url="false"` to confirm/skip/reject/merge buttons
- FB-072 Approval history: "Recently Approved" section at bottom of /admin/approvals showing last 20

### Deferred
- Phase 1C (profile find_nearest_neighbors) — needs timing analysis in production, not critical after caching
- Source URL not saving — needs production investigation, may be transient
- FB-076 community awareness on approve — needs production verification

## Test Results
- App tests: 4547 passed, 10 failed (pre-existing share/download + session-82e)
- ML tests: 590 passed
- New tests: 8 (4 cache, 2 confirm UX, 2 invalidation)

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed
