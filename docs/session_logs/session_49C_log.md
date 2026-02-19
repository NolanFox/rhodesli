# Session 49C Log
Started: 2026-02-19
Prompt: docs/prompts/session_49C_prompt.md

## Phase Checklist
- [x] Phase 0: Orient — save prompt, create session files
- [x] Phase 1: Fix photo 404 for community/inbox photos — _photo_id_aliases map
- [x] Phase 2: Fix compare upload silent failure — onchange="requestSubmit()"
- [x] Phase 3: Fix version display v0.0.0 — COPY CHANGELOG.md in Dockerfile
- [x] Phase 4: Fix collection name truncation everywhere — 6 locations, truncate→leading-snug
- [x] Phase 5: Verification gate — all PASS
- [x] Phase 6: Update BACKLOG with deferred items + CHANGELOG + ROADMAP

## Verification Gate
- [x] Phase 1: _photo_id_aliases references: 15 (PASS)
- [x] Phase 2: onchange="requestSubmit()" on file input (PASS)
- [x] Phase 3: v0.0.0 only appears as fallback, COPY CHANGELOG.md in Dockerfile (PASS)
- [x] Phase 4: 0 collection-style truncation violations remaining (PASS)
- [x] Tests: 9 new, 2385 total passing (PASS)
- [x] Feature Reality Contract passed

## What Was Built
- `_photo_id_aliases` dict in `_build_caches()` mapping photo_index.json IDs → SHA256 cache IDs
- `get_photo_metadata()` now checks alias map when direct lookup fails
- Compare upload file input auto-submits form on file selection
- Dockerfile COPYs CHANGELOG.md for production version display
- 6 CSS truncate→leading-snug fixes across identify/person/compare/photo-grid pages
- Community feedback context document with product insights

## Deferred to Future Sessions
- Quick-identify from photo view (HIGH — added to BACKLOG)
- Batch identity entry from external source (HIGH — added to BACKLOG)
- Facebook integration research (LOW — added to BACKLOG)
