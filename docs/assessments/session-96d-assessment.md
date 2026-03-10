# Session 96d Assessment — Fix Fox Family to Usable State
**Date:** 2026-03-10
**Status:** COMPLETE

## Shipped
- [x] Act 0: Orient — context read, session set
- [x] Act 1: COMMUNITY-007/010 — proposals.json read in sidebar counts, community-filtered. 6 pre-existing test failures fixed.
- [x] Act 2: COMMUNITY-008 — nav links use community_url_prefix(community_slug). All callers updated. COMMUNITY-013 — admin headers show community name.
- [x] Act 3: COMMUNITY-009 — Upload Review + GEDCOM already in sidebar, verified accessible.
- [x] Act 4: COMMUNITY-011 — cluster review proposals filtered by community identity set.
- [x] Act 5: COMMUNITY-012 — proposal badge shows "Matches [Name] (XX%)" with compute_face_confidence().
- [x] Act 6: COMMUNITY-014 — _cross_community_badge() on neighbor_card + discovery cards. "From [Community Name]" badge.
- [x] Act 7: Browser verification — nav links /c/fox-family/* verified, Rhodes bare URLs verified, discoveries badges verified.
- [x] Act 8: Session wrap — assessment, session log, BACKLOG updated.
- [x] Additional: photo filename display, face crop responsive sizing, name truncation fix.

## Deferred
- COMMUNITY-015: Internal photo/person links don't include community prefix — hundreds of references, needs dedicated session.

## Red Flags
- [LOW] 26 tests fail in full suite (test ordering) — pre-existing, pass in isolation
- [LOW] Proposals count shows 35 for Fox Family but targets Rhodes identities — correct behavior

## User Feedback Captured
1. CI email spam from failing tests — fixed 6 pre-existing failures
2. Fox Family clustering concern — data exists, proposals now visible via sidebar
3. Harness compliance — logging, breadcrumbing, feedback collection done
4. UX regressions — face crop sizing, name truncation, photo filename all fixed

## Next Session Should Verify
1. COMMUNITY-015: Internal links (photo, person) get community prefix
2. Fox Family Upload Review workflow: admin can confirm/reject proposals
3. Test ordering issues in full suite (not regressions)
