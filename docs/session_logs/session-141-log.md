# Session 141 Log — Fix Sprint + Refactor + Hardening

**Started:** 2026-03-26
**Prompt:** docs/prompts/session-141-prompt.md
**Context:** docs/session_context/session-141-context.md

## Phase Checklist
- [x] Phase 0: Setup — baseline 3780 tests pass (44s)
- [x] Track A: Structural test + FB-002 toast link (worktree, 6 tests)
- [x] Track B: Hero face picker (worktree, 17 tests)
- [x] Track C: Performance quick wins (worktree, 11 tests)
- [x] Track E: FB-003 PRD analysis (worktree, docs only)
- [x] Merge parallel tracks — all 4 merged cleanly
- [x] Track D: REFACTOR-001 Phase 3 — identity_card extraction (937 lines, main.py 9867→8930)
- [ ] Codex audits (deferred — no codex available)
- [x] Final test: 3813 passed
- [ ] Deploy + browser verify (pending)

## Track Details

### Track A (worktree-agent-afe3e811)
- `tests/test_main_mod_references.py`: 2 tests — structural _main_mod validation + create=True scanner
- `app/identity_routes.py`: toast_with_merge_undo gains target_name + View link
- 4 toast tests

### Track B (worktree-agent-a611d9de)
- `app/main.py`: get_best_face_id checks primary_face_id first
- `app/components/cards.py`: face_card star button for admin
- `app/identity_routes.py`: POST /api/identity/{id}/set-primary-face/{face_id}
- `app/supabase_data.py`: shadow_write includes primary_face_id
- `core/registry.py`: load_from_postgres reads primary_face_id
- 17 tests

### Track C (session-141/track-c-performance)
- heapq.nsmallest at 2 locations in main.py
- ThreadPoolExecutor for parallel cold start
- 11 tests

### Track D (sequential on main)
- Created `app/components/identity_cards.py` (6 functions, ~940 lines)
- Updated `app/components/__init__.py` re-exports
- Fixed 2 test files (aria labels + mock path for gedcom links)

### Track E (session-141/track-e-merge-autoconfirm-prd)
- `docs/prds/058_merge_auto_confirm.md` (213 lines)

## Verification Gate
- [x] All phases re-checked against original prompt
- [x] Feature Reality Contract passed
- [x] `make test-fast` passes (3813)
- [ ] Browser verified on production
