# UX Principles

Non-negotiable invariants that all future changes must respect.

---

## P1: Nothing Irreversible Without Explicit Undo

Every destructive or significant action must have a recovery path.

- Merges can be undone via detach
- Confirms can be contested
- Skipped items remain accessible
- Only explicit "Reject" actions are intentionally permanent

**Violation test:** If a user says "I made a mistake," can they recover?

---

## P2: Skip Never Means Lose

Deferring a decision must not remove access to the item.

- Skipped faces must remain browsable
- Skipped identities must be recoverable
- "Not now" is not "never"

**Violation test:** Can a user find something they skipped last week?

---

## P3: Global Dataset Access

Users must be able to browse the entire dataset, not only through per-face interactions.

- Photo browser provides light-table view
- Faces not in identities remain accessible
- No orphaned data invisible to UI

**Violation test:** Is there data in the system the user cannot reach?

---

## P4: Iterative Review Over Time

The system supports returning to previously-seen items.

- State changes are logged and reversible
- No single-pass "you saw it, it's gone" patterns
- Users can refine decisions as understanding improves

**Violation test:** Can a user improve their work over multiple sessions?

---

## P5: Transparency of State

Users should always know where they are and what state they're in.

- Current mode is visible (reviewing, browsing, finding similar)
- Pending actions are clear
- Exit paths are explicit

**Violation test:** Does the user know how to "get back" from any screen?

---

## P6: Conservative Defaults, Explicit Actions

The system does not make autonomous decisions about identity.

- Clustering proposes; humans confirm
- Merges require explicit action
- Negative signals require explicit rejection

**Violation test:** Did the system change anything without user action?
