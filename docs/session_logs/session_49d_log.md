# Session 49D Log — P0 + P1 Bug Fixes
Started: 2026-02-21
Prompt: docs/prompts/session_49d_prompt.md

## Phase Checklist
- [x] Phase 0: Orient — data synced (no divergence), 1293/1294 tests pass (1 pre-existing state pollution), browser testing via Chrome ext
- [x] Phase 1: P0 Fixes (UX-036, UX-070-072, UX-044/052) — UX-036 already fixed (regression tests added), UX-070-072 fixed (photo-modal-content id on /photo/ page), UX-044/052 fixed (upload messaging per AD-110). 15 tests.
- [x] Phase 2: P1 Fixes (UX-092, UX-080/081, UX-042, UX-100/101) — All 6 fixed. 20 tests.
- [ ] Phase 3: Harness Files
- [ ] Phase 4: Deploy + Verify
- [ ] Phase 5: Verification Gate

## Pre-Existing Issues
- Test state pollution: test_nav_consistency /map test fails in full suite, passes in isolation
- Known pattern from Session 49B-Final (127 similar failures, 0 real bugs)

## Browser Tool
- Tool used: Claude in Chrome extension (MCP) for Phase 0/1
- Chrome extension disconnected during Phase 2, fell back to curl verification

## Phase 2 Details
- **UX-092**: Birth year Accept button moved inside form (eliminates race condition with Save Edit)
- **UX-080**: 404 page — added Tailwind CDN script tag
- **UX-081**: About page — replaced "← Back to Archive" with proper navbar (Photos, People, Timeline, About)
- **UX-042**: /identify/ page — added "See full photo →" text links on photo cards
- **UX-100**: Accept/reject banners auto-dismiss after 4s with opacity transition
- **UX-101**: Pending count updates via hx-swap-oob on accept/reject

## New Issues Found During Verification
(none — browser screenshots limited due to extension disconnect)

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed
