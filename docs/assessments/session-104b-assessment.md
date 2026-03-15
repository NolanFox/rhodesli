# Session 104b Assessment

## Shipped
- [x] Phase 1: Diagnose face card rendering — Evidence: Production API confirmed `identity_id: null` for all 20 Robert Mattatia faces. Root cause: Supabase `anchor_ids` stored as JSON strings instead of JSONB arrays. `DATA_SOURCE=postgres` on production.
- [x] Phase 2: Fix face tagging — Evidence: `_ensure_list()` in `load_from_postgres()`, `_ensure_list_for_supabase()` in shadow writes, 20 Supabase rows repaired, data synced via `/api/sync/push`. Browser verified: both photos show "Robert Mattatia" with identity_id populated.
- [x] Phase 3: Verify + prevent — Evidence: 3 regression tests (`test_string_encoded_anchor_ids_coerced_to_list`, `test_string_anchor_ids_face_lookup_works`, `test_string_encoded_anchor_ids_coerced`). 76 tests pass.
- [x] Hook audit (user-requested) — Evidence: 4 bugs found and fixed. All enforcement hooks now exit 2. UserPromptSubmit, Stop, PreToolUse Bash, PostToolUse Bash all block correctly.

## Deferred
- Phase 4: Claude Benatar UX items (compare result shows both photos, dismiss mechanism, interaction logging) — Reason: P0 fix was the priority. BACKLOG: existing items cover these.
- Lesson 142 — Should be added in next session with full context.

## Red Flags
- [HIGH] Test suite has widespread ordering-dependent flakes — full suite fails on different tests each run (test_og_meta_tags, test_search, test_public_browsing, test_ux_fixes). `test-gate.sh fast` now runs targeted core tests only. BACKLOG: PERF-001.
- [MEDIUM] `init_railway_volume.py` blocks identities.json sync when volume has more confirmed identities — new PROPOSED/INBOX identities from git never reach production volume. Only sync API bypass works. Should be fixed to merge rather than skip.

## Next Session Should Verify
1. Deploy the code fix (`git push`) so future deploys have `_ensure_list` protection
2. Verify both photo pages still work after deploy
3. Add Lesson 142 (Supabase JSONB columns can receive string-encoded arrays from Python)
4. Fix `init_railway_volume.py` merge logic for identities
5. Address Phase 4 Claude Benatar UX items
