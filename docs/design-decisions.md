# Design Decisions

This document tracks product and UX decisions. Each entry is authoritative and should not be revisited without explicit discussion.

---

## D1: Photo Browser Scope

**Date:** 2026-01-29
**Status:** Decided

**Context:** Users need to browse photos globally, not just through identity-grouped faces.

**Decision:** Separate route `/photos` with dedicated light-table surface.

**Rationale:**
- Main dashboard remains identity-focused
- Enables future filtering/sorting without cluttering identity review
- Clear mental model: "review identities" vs "browse photos"

**Tradeoffs:**
- Additional route to maintain
- Navigation between views requires clear affordances

---

## D2: Skip vs Reject Semantics

**Date:** 2026-01-29
**Status:** Decided

**Context:** Need to distinguish between "I don't know" and "These are NOT the same person."

**Decision:** Split semantics with distinct actions.

| Action | Meaning | Recoverable | Generates Signal |
|--------|---------|-------------|------------------|
| Skip | Temporary deferral | Yes | No |
| Reject ("Not Same Person") | Strong negative | No (intentional) | Yes (`negative_ids`) |

**Rationale:**
- Epistemic humility: uncertainty is not rejection
- Negative signals must be explicit and intentional
- Skip supports iterative review over time

**Tradeoffs:**
- Two actions instead of one increases UI complexity
- Must clearly communicate difference to users

---

## D3: Pagination Strategy

**Date:** 2026-01-29
**Status:** Decided

**Context:** Find Similar returns limited results; users need to see more.

**Decision:** Explicit "Load More" button.

**Rationale:**
- HTMX-compatible with modal-first navigation
- User controls when to load more (no surprise fetches)
- Simpler than infinite scroll state management

**Tradeoffs:**
- Requires explicit user action
- Must track offset state

---

## D4: Navigation Model

**Date:** 2026-01-29
**Status:** Decided

**Context:** Clicking faces/photos created confusing navigation state.

**Decision:** Modal-first navigation for photo context.

**Rationale:**
- Preserves identity-review flow
- Back button behaves predictably (closes modal, not page exit)
- Reduces context switching

**Tradeoffs:**
- Modals have accessibility considerations
- Deep linking to specific photos requires separate handling

---

## Template for New Decisions

```markdown
## D[N]: [Title]

**Date:** YYYY-MM-DD
**Status:** Proposed | Decided | Superseded

**Context:** [What problem or question prompted this?]

**Decision:** [What was decided?]

**Rationale:** [Why this option?]

**Tradeoffs:** [Known downsides or risks]

**Revisit If:** [Conditions that would warrant reconsideration]
```
