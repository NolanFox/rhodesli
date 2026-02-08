# Task: BUG-001 Lightbox Arrow Navigation

## Status: Not Started

## Overview
Lightbox arrow buttons disappear after the first photo in the gallery. This is the 3rd fix attempt — must write comprehensive regression tests BEFORE touching the implementation. Only keyboard arrows work; mouse users (especially older family members) are stuck.

## Current State
- First photo shows right arrow correctly
- All subsequent photos lack left/right arrows for mouse navigation
- Keyboard arrows (left/right) still work
- `photoNavTo` function and HTMX swap lifecycle are suspected root cause
- Previous fixes: commit 55fea1e (Phase 2), commit 50e5dc4 (Phase 1) — both regressed

## Desired State
- Arrow buttons visible on every photo in the lightbox (first, middle, last)
- Arrows survive HTMX content swaps
- Left arrow hidden on first photo, right arrow hidden on last photo
- Both keyboard and mouse navigation work consistently

## Implementation Steps
- [ ] Step 1: Write 5+ regression tests covering arrow rendering after HTMX swaps
- [ ] Step 2: Investigate `photoNavTo` function and HTMX swap lifecycle
- [ ] Step 3: Identify root cause of arrow disappearance after swap
- [ ] Step 4: Implement fix (likely needs `htmx:afterSwap` re-initialization)
- [ ] Step 5: Verify all tests pass, manually test on live site

## Acceptance Criteria
- [ ] Arrow buttons visible on photo 1, photo 2, middle photo, last photo
- [ ] Left arrow hidden on first photo only
- [ ] Right arrow hidden on last photo only
- [ ] Arrows survive HTMX swaps (not just initial render)
- [ ] At least 5 regression tests covering these scenarios
- [ ] Keyboard navigation still works

## Files to Modify
- `app/main.py` — lightbox rendering, `photoNavTo`, HTMX swap handlers
- `tests/test_lightbox.py` or `tests/test_regression.py` — arrow regression tests

## Related
- Backlog ID: BUG-001, FE-001, QA-001
- See: `docs/BACKLOG.md` section 2.1 (Navigation & Lightbox)
