# Session 138 Assessment

**Date:** 2026-03-26
**Version:** v0.99.49
**Status:** COMPLETE

## Shipped

- [x] **Phase 0: Setup + Supabase Verify** — Supabase Pro confirmed (3757 identities), baseline 3748 tests pass
- [x] **Track 1: Quick Fixes** — Mobile nav `|` separator filtered, xfail rate-limit patches fixed (3 files)
- [x] **FB-006 (P0): Enable confirm for unidentified persons** — Removed all blocks across 5 files + core/registry.py. 4 test files updated.
- [x] **FB-012: Community filter + Load More** — Apply community filter before pagination slice
- [x] **FB-013: Rejected identities filtered from neighbors** — Added negative_ids filtering + cache invalidation
- [x] **Codex P1: Fetch limit increase** — 20→60 when community filter active
- [x] **Codex P2: Cache invalidation** — Added to reject-match, unreject, bulk-reject
- [x] **Track 2: REFACTOR-001 Phase 2** — 848 lines extracted from main.py (10,638→9,790)
  - cards.py: 8 functions (699 lines)
  - badges.py: _cross_community_badge
  - nav.py: _build_triage_bar

## Feedback Items (13 total)

| ID | Severity | Title | Status |
|----|----------|-------|--------|
| FB-001 | P2 | Missing thumbnails Person 174/196 | Data issue — crops missing on R2 |
| FB-002 | P1 | No navigation to merged identity | BACKLOG |
| FB-003 | P1 | Merge should auto-confirm | Needs PRD |
| FB-004 | P1 | Confirm vs Identify conceptual confusion | Needs PRD |
| FB-005 | P2 | Filter confirmed-unnamed people | BACKLOG |
| FB-006 | P0 | Confirm button disabled for unidentified | **FIXED** |
| FB-007 | P3 | Can't choose hero face thumbnail | BACKLOG |
| FB-008 | P1 | Bulk merge fails in focus mode | BACKLOG |
| FB-009 | P0 | Confirm grayed on production (pre-deploy) | **FIXED** |
| FB-010 | P1 | After merge, doesn't advance to next | Same as FB-003 |
| FB-011 | P1 | Person 163 missing crop — systemic issue | Data issue |
| FB-012 | P2 | Load More + community filter broken | **FIXED** |
| FB-013 | P1 | "Not Same" rejections not persisting | **FIXED** |

## Deferred

- **identity_card** (574 lines) and **identity_card_expanded** (282 lines) — too tightly coupled to main.py for safe extraction this session. Needs more dependency analysis.
- **FB-003/FB-010**: Merge→auto-confirm→advance workflow needs PRD
- **FB-004**: Confirm vs Identify separation needs PRD
- **FB-001/FB-011**: Missing crops need pipeline run to regenerate/upload

## Red Flags

- **MEDIUM**: 750/1000 faces in photo_faces have NULL bbox/quality — these likely have no crop files on R2. Affects many Rhodes community identities. Needs data pipeline fix.

## AI Tool Usage

- **Tool**: Codex CLI v0.115.0 (gpt-5.4)
- **Agent type**: Independent (fresh context)
- **Task**: Security + code quality audit of Session 138 changes
- **Findings**: 3 total (1 P1, 1 P2, 1 P3-clean)
- **Acted on**: P1 fetch limit fix + P2 cache invalidation — both committed
- **Discarded**: None
- **Value assessment**: STRONG — P1 finding caught a real user-facing bug
- **Would we have found this ourselves?**: The P1 pool truncation — unlikely without community-filtered testing. The P2 cache paths — eventually.

## Next Session Should Verify

1. Confirm button works on production for all identity types
2. "Not Same" rejections persist after page reload
3. "Same community only" + Load More works correctly
4. Plan PRD for confirm vs identify workflow separation (FB-003/FB-004)
5. Investigate missing crops (FB-001/FB-011) — 750 faces need crop regeneration
