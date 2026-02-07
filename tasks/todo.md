# Task: Photo Bug Fix + Documentation Restructure

**Session**: 2026-02-07 (session 7)
**Status**: COMPLETE

## Phase 1: Fix Photo Source Lookup Bug
- [x] Root cause: `_build_caches()` used SHA256 IDs but photo_index.json uses inbox_* IDs for Betty Capeluto photos
- [x] Fix: Added filename-based fallback in `_build_caches()` source merge
- [x] All 13 Betty Capeluto photos now resolve correctly
- [x] 6 new tests: source lookup, collection counts, consistency checks
- [x] All 553 tests passing
- [x] Committed: `fix: resolve photo source lookup for inbox-style photo IDs`

## Phase 2: Documentation Restructure
- [x] Split SYSTEM_DESIGN_WEB.md (1372 lines) into 6 focused files:
  - docs/architecture/OVERVIEW.md (111 lines)
  - docs/architecture/DATA_MODEL.md (139 lines)
  - docs/architecture/PERMISSIONS.md (77 lines)
  - docs/architecture/PHOTO_STORAGE.md (118 lines)
  - docs/design/FUTURE_COMMUNITY.md (230 lines)
  - docs/DECISIONS.md (68 lines)
- [x] Rewrote CLAUDE.md to 72 lines (progressive disclosure pattern)
- [x] Deleted SYSTEM_DESIGN_WEB.md monolith
- [x] Added lessons 23-25 to tasks/lessons.md
- [x] Updated MEMORY.md
- [x] Committed: `refactor: split SYSTEM_DESIGN_WEB.md into focused docs, restructure CLAUDE.md`

## Phase 3: Verification
- [x] All 553 tests passing
- [x] CLAUDE.md: 72 lines (target: <80)
- [x] SYSTEM_DESIGN_WEB.md: deleted
- [x] All new architecture docs: <300 lines
- [ ] Pushed to main

## Previous Session (2026-02-06)
- UX Overhaul: COMPLETE (merge system, landing page, sidebar, face cards, inbox workflow)
- 484 tests passing at end of session
