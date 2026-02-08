# Task: BUG-002 Face Count Label Accuracy

## Status: Not Started

## Overview
Photo view shows "6 faces detected" when only 2 face boxes are visible and all faces are tagged. The count label reads from raw detection results (which may include low-confidence faces) rather than the filtered/displayed count.

## Current State
- Face count label shows total detections (e.g., 6)
- Face box overlays only show faces above confidence threshold (e.g., 2)
- Mismatch undermines user trust in the system

## Desired State
- Face count label matches the number of visible face boxes
- If filtering by confidence, label reflects filtered count
- Optional: show "2 faces (6 detected)" to surface hidden low-confidence detections

## Implementation Steps
- [ ] Step 1: Write failing test asserting count label matches displayed boxes
- [ ] Step 2: Find where face count label is generated in photo view
- [ ] Step 3: Apply same confidence filter to count as to box rendering
- [ ] Step 4: Verify fix on photos with mixed confidence detections

## Acceptance Criteria
- [ ] Count label matches number of visible face boxes
- [ ] No discrepancy on any test photo
- [ ] Regression test prevents future mismatch

## Files to Modify
- `app/main.py` — photo view face count label generation
- `tests/test_photo_context.py` — count accuracy test

## Related
- Backlog ID: BUG-002, FE-025, QA-003
- See: `docs/BACKLOG.md` section 2.3
