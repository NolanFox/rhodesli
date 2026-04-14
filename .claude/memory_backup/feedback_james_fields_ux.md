---
name: james_fields_ux_bugs
description: 9 UX bugs found during James Fields end-to-end test — merge buttons broken, override broken, slow operations, duplicate cards
type: feedback
---

Session 109b user test exposed 9 bugs in the identify/merge workflow:

**P0 (Broken):**
- FB-019: Individual merge buttons silently fail (only bulk merge works)
- FB-021: Override button shows tooltip but does nothing

**P1 (Bad UX):**
- FB-016: Rename very slow, appears broken
- FB-017: Confirm creates duplicate giant face card with stale buttons
- FB-018: Find Similar requires page refresh after confirm
- FB-020: Every merge closes Similar panel (60s+ workflow for 5 merges)
- FB-023: GEDCOM linking very slow
- FB-024: General slowness throughout all actions

**P2 (Missing):**
- FB-022: No batch override merge (must go one by one)

**Why:** The cross-batch matching backend works correctly (1355 matches found, proposals visible). But the frontend actions for acting on those proposals are broken or extremely friction-heavy.

**How to apply:** Session 110 prompt written. Fix merge buttons, override, confirm UI, panel persistence. Add loading indicators. This is the #1 priority before any new features.
