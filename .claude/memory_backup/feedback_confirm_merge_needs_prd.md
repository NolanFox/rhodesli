---
name: Confirm-merge needs PRD
description: Auto-merge on confirm caused production regression (Person 3141 disappeared). Complex workflow changes need PRD/SDD approach, not inline fixes.
type: feedback
---

Never auto-merge on confirm without a PRD. Session 111d attempted to make the "Confirm as {Name}" button auto-merge with the best match. This caused identities to disappear from the UI because:
1. Name conflicts returned success=False silently
2. Unidentified persons failed confirm_identity() name check
3. The fade-out card response removed the identity from DOM even when merge failed in edge cases

**Why:** The confirm button is the most critical triage action. Changing its behavior requires understanding all edge cases: unidentified names, co-occurrence blocks, name conflicts, merge direction swaps, focus mode vs browse mode, person page vs card view.

**How to apply:** Any change to confirm/merge/reject behavior needs:
1. PRD with user flow analysis
2. Edge case enumeration (at least 8 cases for confirm)
3. Tests for EVERY edge case BEFORE implementation
4. Production browser verification before declaring done
5. Never deploy workflow changes without user testing first
