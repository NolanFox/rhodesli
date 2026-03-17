# Session 111d Log — Outstanding Feedback Fix Sprint
Started: 2026-03-17
Prompt: docs/prompts/session-111d-prompt.md

## Phase Checklist
- [x] Phase 0: Orient + CI Fix
- [x] Phase 1: P0 Confirm Button Fix (FB-068)
- [ ] Phase 2: P0 Performance (FB-069, FB-025)
- [ ] Phase 3: P0 Photo Overlay + Tagging (FB-066, FB-036/037)
- [ ] Phase 4: P1 UX Fixes
- [ ] Phase 5: P2 Fixes
- [ ] Phase 6: Deploy + Verify
- [ ] Phase 7: Harness Outputs

## Phase 0: Orient + CI Fix
- Fixed `test_partial_has_public_page_link` — UI changed from "Public Page" to "View Photo" but test was never updated
- Commit: 9a94303, pushed to main

## Phase 1: FB-068 Confirm Button + Face Overlay Cache
- **FB-068**: Confirm button now merges with best match when confidence >= MODERATE
  - Both `/confirm/{id}` and `/inbox/{id}/confirm` endpoints updated
  - Passes `resolved_name=target_name` to handle name conflicts automatically
  - Card fades out with "Merged into {Name}" on success
  - Falls through to regular confirm when no match or LOW confidence
- **Face overlay fix** (user-reported during session): `_photo_dimensions_cache` never invalidated in `_invalidate_all_caches()`, causing newly uploaded photos to show no bounding boxes. Added invalidation + Supabase fallback.
- 5 new tests, all pass
- Commit: b19c8a9, pushed to main

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed
