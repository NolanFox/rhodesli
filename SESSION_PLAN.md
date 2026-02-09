# Session 4 Plan — Overnight: Stabilize + Share-Ready

## Current State
- 799 tests passing
- v0.11.0 (Phase A complete)
- Event delegation lightbox already in place

## Phase 1: Photo Navigation — Complete the Gaps
**Gap identified:** Arrow buttons exist in photo grid (photoNavTo) and identity lightbox
(/api/identity/{id}/photos), BUT face card clicks, search results, and browse mode face
thumbnails all open /photo/{id}/partial WITHOUT navigation context → no arrows.

**Fix:**
1. Face card "View Photo" clicks → use identity lightbox route instead of bare photo partial
2. Search result clicks → pass search result list as navigation context
3. Ensure all photo open paths have prev/next arrows
4. Fix confirmed face click: navigate to identity, not tag dialog
5. Write E2E tests for arrow visibility and keyboard nav

## Phase 2: Mobile Responsive
- Hamburger menu at <768px
- Bottom tab navigation
- Responsive photo grid (2/3/4 columns)
- Mobile match mode vertical stacking

## Phase 3: Landing Page Enhancement
- Hero section with real archive photo
- Live stats ("23 of 181 faces identified")
- CTAs: Browse Photos, Help Identify
- Progress dashboard

## Phase 4: Inline Face Actions
- Hover actions on face overlays (confirm/skip/reject)
- ML hints for skipped faces
- Verify face count fix (BUG-002)

## Phase 5: Search Polish
- Fuzzy name search (Levenshtein)
- Search match highlighting

## Phase 6: Admin Tools
- Admin export endpoint (ZIP of JSON data)
- Merge history verification

## Phase 7: Docs & Cleanup
- Update ROADMAP.md, CHANGELOG.md, tasks/todo.md
- Final test run and push
