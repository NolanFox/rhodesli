# Task: Overnight Polish & UX Overhaul

**Session**: 2026-02-06 (session 6)
**Status**: IN PROGRESS

## Phase 1: Critical Bug Fix — Uploaded Photos
- [x] Investigated uploaded photos not rendering in R2 mode
- [x] Fixed `photo_url()` to detect `data/uploads` paths and serve locally
- [x] Updated 4 call sites to pass `filepath` parameter
- [x] Committed: `fix: uploaded photos not rendering in R2 mode`

## Phase 2: UX Overhaul (5 parallel agents)
- [x] 2A: Merge system overhaul — undo merge, direction auto-correction, name conflict modal, bulk ops
- [x] 2B: Landing page redesign — Rhodes heritage branding, interactive face detection overlays, stats
- [x] 2C: Sidebar & navigation — collapsible with localStorage, search-as-you-type, sort controls
- [x] 2D: Face card & photo viewing — carousel pagination, photo lightbox with overlays, comparison modal
- [x] 2E: Inbox workflow speed — no-reload HTMX actions, animations, bulk merge/reject, Match mode
- [x] Fixed 9 pre-existing test failures (gallery, neighbor placeholder, inbox contract, photo paths)
- [x] All 484 tests passing
- [x] Committed: `feat: UX overhaul — merge system, landing page, sidebar, face cards, inbox workflow`

## Phase 3: Pending Upload Queue
- [ ] Create `data/pending_uploads.json` tracker
- [ ] Revert `POST /upload` from `_check_admin` to `_check_login` with moderation
- [ ] Admin pending review page (`/admin/pending`)
- [ ] Sidebar pending count badge
- [ ] Email notification to admin via Resend API (optional)
- [ ] Create `scripts/process_pending.py`
- [ ] Tests for pending upload flow

## Phase 4: ML Clustering Pipeline
- [ ] Create `scripts/build_golden_set.py` — extract ground truth from confirmed identities
- [ ] Create `scripts/evaluate_golden_set.py` — precision/recall/F1 at various thresholds
- [ ] Create `scripts/cluster_new_faces.py` — match new faces against confirmed centroids

## Phase 5: Documentation Updates
- [x] Update `tasks/todo.md` (this file)
- [ ] Update `tasks/lessons.md` with new learnings
- [ ] Update `docs/PHOTO_WORKFLOW.md` with pending queue section
- [ ] Update `docs/SESSION_LOG.md` with session 15 entry

## Phase 6: Final Integration
- [ ] Run full test suite
- [ ] Push to main
- [ ] Write session summary

## Previous Session (2026-02-05)
- Email Templates: COMPLETE
- Regression Test Suite: COMPLETE (59 tests)
- Testing harness in CLAUDE.md: COMPLETE
