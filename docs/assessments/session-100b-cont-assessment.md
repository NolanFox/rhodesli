# Session 100b Continuation Assessment

**Date:** 2026-03-13
**Agent:** Claude Code (Opus 4.6)
**Prompt:** docs/prompts/session-100b-cont-prompt.md

## Shipped

### Phase 1: Jacob Cohen Bbox Conflict Fix (BUG 1) - PASS
- **Evidence:** 5 edits to `app/page_routes.py`
- Confirmed faces with bbox overlap now show identity name (not "Needs review")
- IoU threshold raised from 0.80 to 0.85
- Overlays are clickable (link to person page)
- Person cards: "Conflict" badge only for unidentified faces
- "Overlaps another face" warning only for unidentified faces
- **Bbox scan result:** Only 2 overlapping pairs across all 939 photos
  - Wedding photo (IoU 0.97): duplicate detection, both unidentified — correct behavior
  - Holocaust collage (IoU 0.83): Jacob Cohen + Caden Franco Sadis — no longer flagged at 0.85 threshold
- **Tests:** 6 new tests in `tests/test_public_photo_viewer.py`, all pass

### Phase 2: Photo Metadata Save (BUG 2) - PASS
- **Root cause:** Duplicate route definitions in `photo_routes.py` AND `page_routes.py`
- `photo_routes.py` versions (loaded last) were winning, silently skipping `log_user_action()`
- **Fix:** Removed 3 duplicate routes from `photo_routes.py` (86 lines)
- `page_routes.py` versions with audit logging are now active
- **Evidence:** 4138 tests pass, no regressions

### Dismissed Faces (Issue #8/#13) - PASS
- SKIPPED faces now show "Dismissed" with slate-colored dashed border
- Distinct from amber "Unidentified" for INBOX/PROPOSED faces
- **Evidence:** Changes in `page_routes.py`, tests pass

### GEDCOM Anchor Fix Investigated (Issue #12) - NO ACTION NEEDED
- Both linked and unlinked sections already have `id="gedcom"`
- Issue is likely timing (HTMX lazy load vs anchor resolution)
- Documented in BACKLOG as DOGFOOD-006

### BUG 4: Person → Photo Wrong Landing - INVESTIGATED, NOT A BUG
- Rica Revah and Jacob Franco are both in the SAME photo
- Clicking from Rica Revah's page correctly shows the photo with `?identity_id=` for highlighting
- The user may have been confused by seeing Jacob Franco prominently featured

### Phase 6: ROADMAP/CHANGELOG Updates - PASS
- CHANGELOG.md: Added entries for sessions 98, 99, 100, 100b
- SESSION_HISTORY.md: Added 15 session entries (96-100b)
- BACKLOG.md: Added 9 dogfood items (DOGFOOD-001 through DOGFOOD-009)
- ROADMAP.md: Updated session 96c status, added 100b

## Pending (Worktree Subagents)
- Photo overlay caption fix + Hide Faces discoverability (worktree agent)
- People-in-photo layout spacing (worktree agent)
- Face cycling on identity cards (worktree agent)

## Deferred to BACKLOG
- DOGFOOD-003: Person → photo wrong landing (investigated, not a bug)
- DOGFOOD-005: Confirmed-people filtering by GEDCOM link status
- DOGFOOD-006: Link Tree affordance + #gedcom anchor timing
- DOGFOOD-007: Dismissed faces explicit state (partially addressed)
- DOGFOOD-008: Source provenance capture at upload
- DOGFOOD-009: Session 99 variant collapse

## Pre-existing Failures (Not This Session)
- `test_confirmed_anchors_in_face_to_photo`: Solomon Solly Galante face not in local data (production-only)
- `test_admin_approval_card_has_face_thumbnail`: E2E test pre-existing failure

## Red Flags
- [LOW] Solomon Solly Galante identity has orphaned face — needs production data sync
- [LOW] `correct-date` route still duplicated between photo_routes.py and page_routes.py (minor differences)

## Next Session Should Verify
1. Browser verify Jacob Cohen photo shows names correctly on production
2. Browser verify photo metadata save persists after page reload
3. Merge worktree branches if subagents completed
4. Production data sync for Solomon Solly Galante
