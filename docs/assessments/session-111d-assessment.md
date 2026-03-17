# Session 111d Assessment

## Shipped

- [x] Phase 0: CI fix — `test_partial_has_public_page_link` updated to match current UI
  - Evidence: `pytest tests/test_internal_photo_links.py::TestPhotoModalShareButton` — 3 passed
  - Commit: 9a94303

- [x] Phase 2: FB-069 Performance — targeted Supabase writes
  - `save_registry()` now accepts `changed_ids` parameter
  - All triage operations (confirm, merge, skip, reject, tag, reject-pair) pass 1-2 IDs instead of ~3400
  - Before: 34 Supabase API calls per confirm. After: 1 API call.
  - Evidence: 2 tests verify `changed_ids` is passed
  - Commit: 99929f2

- [x] Face overlay cache fix (user-reported during session)
  - `_photo_dimensions_cache` never invalidated in `_invalidate_all_caches()` — new uploads had no bounding boxes
  - Added cache invalidation + Supabase photo registry fallback
  - Commit: b19c8a9

- [x] FB-065: Post-merge findability — search finds merged identities with "Merged into {Name}"
  - `search_identities()` includes merged identities, ranked after non-merged
  - 5 new tests
  - Commit: 4709520

- [x] FB-044: Best match deduped from Similar Identities list
  - Neighbors endpoint filters out the best match identity
  - Commit: 4709520

- [x] FB-066: Green checkmark returns clear error for unidentified faces
  - "Name this person first, then confirm." instead of silent failure
  - 3 new tests
  - Commit: e12c63d

- [x] FB-036/037: Tag save failure surfaced as warning toast
  - When Supabase write fails, user sees "sync failed" warning instead of false success
  - 2 new tests
  - Commit: e12c63d

- [x] FB-048: "View Person" link in Speed Loop tag popup
  - Opens person page in new tab without interrupting Speed Loop
  - Commit: e12c63d

- [x] FB-040: Focus mode merge stale card fix
  - OOB delete elements now included in focus mode merge response
  - Commit: e12c63d

## REGRESSION — Shipped and Reverted

- [x] FB-068: Auto-merge on confirm — REVERTED
  - Attempted to make "Confirm as {Name}" button auto-merge with best match
  - Caused Person 3141 to disappear from UI (name conflict edge case)
  - Reverted immediately. Confirm now only promotes state (original behavior).
  - **Lesson:** Complex workflow changes need PRD with edge case analysis. Saved to memory.
  - Commit (revert): c5323ea

## Deferred

- FB-068: Confirm+merge in one click — needs PRD (complex workflow, caused regression)
- FB-057: Focus mode auto-advance — investigation shows buttons/handlers are correct; likely confirm failing for unidentified names (now addressed by FB-066)
- FB-054/058: Thumbnail mismatch — needs investigation of face selection logic
- FB-031: Face grid CSS — low priority, cosmetic
- FB-030: Cluster count persistence — needs server-side session state design
- FB-028: Toast persistence (P2) — HTMX swap lifecycle issue
- FB-038: View More checkboxes (P2) — client-side state management

## Red Flags

- [HIGH] Auto-merge regression caused user to lose access to Person 3141 temporarily. Identity was preserved (INBOX state) but invisible in triage UI. REVERTED.
- [MEDIUM] Performance fix (`changed_ids`) changes Supabase write behavior — needs monitoring for missed writes.
- [LOW] FB-057 root cause may be FB-066 (confirm failing silently for unnamed faces). Production verification needed.

## Next Session Should Verify

1. Person 3141 is accessible and confirmable after rename
2. Confirm/skip/reject all work in focus mode
3. Performance improvement is noticeable during triage
4. Face overlays appear on newly uploaded photos
5. Tag persistence in Speed Loop
