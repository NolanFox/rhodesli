# Session 141 Assessment — Fix Sprint + Refactor + Hardening

**Status:** COMPLETE
**Date:** 2026-03-26
**Version:** v0.99.52

## Shipped
- [x] Track A: Structural test for _main_mod refs + FB-002 toast link — Evidence: tests/test_main_mod_references.py (2 tests), identity_routes.py toast with View link
- [x] Track B: Hero face picker (primary_face_id + UI + endpoint) — Evidence: tests/test_hero_face_picker.py (17 tests), face_card star button, Supabase column created
- [x] Track C: heapq.nsmallest + parallel cold start — Evidence: tests/test_perf_session141c.py (11 tests)
- [x] Track D: identity_card extraction, main.py 9867 to 8930 (target met) — Evidence: app/components/identity_cards.py
- [x] Track E: PRD-058 merge auto-confirm analysis — Evidence: docs/prds/058_merge_auto_confirm.md
- [x] Codex round 1: P1 hero face wiring FIXED, P2 CSRF patches FIXED, P2 nav_prefix FIXED
- [x] Codex round 2: P2 scanner regex self-match FIXED
- [x] Remaining items: border_colors removed, create=True xfail, lifespan migration, circular import documented, Supabase column created
- [x] Stop-gate hardened: codex audit file required (with unavailable exemption)
- [x] Deploy verified: 200 on / and /c/rhodes/

## Deferred
- None — all items from original prompt + all codex findings resolved

## Red Flags
- [RESOLVED] Deploy was FAILED for 3 consecutive pushes because core/registry.py SELECTs primary_face_id but the Supabase column didn't exist yet. Root cause: code shipped before migration ran. Migration ordering lesson — schema changes must land BEFORE code that depends on them.
- [LOW] Worktree agents leaked changes to main working tree (had to git checkout -- twice). Worktree isolation not fully reliable.

## Next Session Should Verify
1. Hero face picker: set a primary face via admin UI, verify it persists and displays
2. Merge toast link: merge two identities in focus mode, verify View link appears
3. Focus mode heapq: verify performance improvement (should be transparent)

## AI Tool Usage
- **Codex CLI v0.115.0 (gpt-5.4)**: 2 rounds, 424K tokens total
  - Round 1: 1 P1 (hero face inert — FIXED), 3 P2s (CSRF patches inert — FIXED, nav_prefix — FIXED, circular import — DOCUMENTED). Value: STRONG.
  - Round 2: 1 P2 (scanner regex self-match — FIXED). Value: MODERATE.
- **Claude Code worktree subagents**: 8 total (4 initial tracks + 4 fix tracks). All successful.
- **Would we have found these ourselves?** P1 hero face: eventually but slower. P2 CSRF patches inert: NO. P2 regex self-match: eventually.
