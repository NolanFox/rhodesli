# Task: Fix Face Box Regression

**Status**: COMPLETE

## Problem Statement
Photos show only 1 face box when there should be multiple.
Example: Image 972 shows "14 faces detected" but only 1 green box displays.

## Root Cause
In commit d7f6e2f ("fix: graceful degradation when photo dimensions unavailable"),
the face overlay loop in `photo_view_content()` was wrapped in `if has_dimensions:`.
However, only the bbox percentage calculations (lines computing left_pct, top_pct, etc.)
were indented into the `for` loop. The rest of the loop body -- identity lookup,
overlay div construction, and `face_overlays.append()` -- remained at the `if` block
level, outside the `for` loop. This caused them to execute only once (using the last
face's variables) instead of once per face.

## Fix Applied
Re-indented lines 2696-2744 of app/main.py from 8-space (if-level) to 12-space
(for-loop level), restoring the full loop body.

## Plan
- [x] 1. Find where face boxes are rendered in app/main.py
- [x] 2. Identify what recent change broke the face iteration
- [x] 3. Fix the root cause (indentation)
- [x] 4. Verify syntax compiles
- [x] 5. Commit and push
