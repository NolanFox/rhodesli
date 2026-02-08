# Task: BUG-003 Merge Direction Safety

## Status: Not Started

## Overview
When merging from Focus Mode (unidentified person → Find Similar → Merge to named identity), the merge overwrites the named identity's data with the unidentified person's data. This makes Focus Mode's primary workflow destructive. The merge must always preserve the richer identity.

## Current State
- Focus Mode starts with an unidentified person
- Find Similar finds a named match
- Merging replaces the named identity with unidentified data
- No conflict resolution when both identities have names

## Desired State
- Merge always preserves the identity with: a name (over unnamed), more faces, more metadata
- When merging two named identities, show conflict UI: pick primary name, keep both as aliases
- Merge creates a reversible history record with before/after snapshots
- All tests pass including direction-specific scenarios

## Implementation Steps
- [ ] Step 1: Write failing tests for merge direction scenarios (unnamed→named, named→unnamed, named→named)
- [ ] Step 2: Implement direction-aware merge logic in the merge handler
- [ ] Step 3: Add merge history record creation (reversible)
- [ ] Step 4: Handle named conflict case (both have names)
- [ ] Step 5: Verify Focus Mode → Find Similar → Merge workflow

## Acceptance Criteria
- [ ] Merging unnamed into named preserves the named identity's name and metadata
- [ ] Merging named into unnamed preserves the named identity's name and metadata
- [ ] Merge history record is created with sufficient data to reverse
- [ ] All existing merge tests still pass
- [ ] New direction-specific tests pass

## Files to Modify
- `app/main.py` — merge route handler logic
- `tests/test_permissions.py` or new `tests/test_merge.py` — direction tests

## Related
- Backlog ID: BUG-003, BE-001, BE-002
- See: `docs/BACKLOG.md` section 3.1 (Merge System Redesign)
- See: `docs/design/MERGE_DESIGN.md`
