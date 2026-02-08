# Task: BUG-004 Collection Stats Inconsistency

## Status: Not Started

## Overview
Photo gallery shows inconsistent collection statistics — denominator mismatches, incorrect photo counts. This has been reported 3 times across sessions 10-11 and claimed fixed but persists.

## Current State
- Collection stats cards show incorrect photo counts
- Denominator mismatches in "X of Y" displays
- Previous fixes didn't hold — likely a filtering/aggregation logic issue

## Desired State
- Collection stats accurately reflect the number of photos in each collection
- Filtered views show correct "showing X of Y" counts
- Stats are consistent across all pages that display them

## Implementation Steps
- [ ] Step 1: Write tests asserting correct counts for known test collections
- [ ] Step 2: Trace stat generation path — identify where counts diverge
- [ ] Step 3: Fix counting logic to be consistent with displayed photos
- [ ] Step 4: Verify on multiple collection pages

## Acceptance Criteria
- [ ] Stats match actual photo counts per collection
- [ ] Filtered views show correct subset counts
- [ ] Regression tests prevent future count mismatches

## Files to Modify
- `app/main.py` — collection stats generation and display
- `tests/test_photo_context.py` or new test file — stats accuracy tests

## Related
- Backlog ID: BUG-004
- See: `docs/BACKLOG.md` section 1
