# Open Questions

Intentionally unresolved items. These are deferred, not forgotten.

---

## Q1: Skip UI Location and Affordance

**Status:** Deferred
**Related:** D2, P2

Where does "Skip" appear in the UI? Is it per-identity, per-face, or per-neighbor-suggestion?

**Current state:** No skip mechanism implemented yet.

**Considerations:**
- Skip on identity card vs skip on neighbor card
- Visual treatment (subtle vs prominent)
- Where skipped items surface for re-review

---

## Q2: Skipped Items View Design

**Status:** Deferred
**Related:** P2, B4

How do users access skipped items?

**Options considered:**
- Separate "Skipped" lane alongside Proposed/Confirmed/Contested
- Filter toggle on existing lanes
- Dedicated `/skipped` route

**Not yet decided:** Which approach best fits the mental model.

---

## Q3: Photo Browser Filtering

**Status:** Explicitly out of scope for Phase 5
**Related:** D1

What filtering/sorting capabilities should `/photos` support?

**Deferred until:** Basic browser (E2-E4) is complete and tested.

---

## Q4: Negative Pair Visibility

**Status:** Deferred
**Related:** D2, D1-D4

Should users be able to see which pairs they've marked as "Not Same Person"?

**Considerations:**
- Audit trail for mistakes
- Could become noisy at scale
- May want "undo reject" eventually (violates current D2?)

---

## Q5: Keyboard Navigation

**Status:** Deferred

Should the review workflow support keyboard shortcuts?

**Examples:**
- `j/k` for next/prev identity
- `y/n` for confirm/contest
- `Esc` to close modals

**Deferred until:** Core flows are stable.

---

## Template

```markdown
## Q[N]: [Title]

**Status:** Open | Deferred | Resolved (see D[X])
**Related:** [Decision or Principle IDs]

[Description of the question]

**Considerations:**
- [Option or factor]
- [Option or factor]

**Deferred until:** [Condition or milestone]
```
