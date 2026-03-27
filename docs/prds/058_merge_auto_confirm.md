# PRD-058: Merge Auto-Confirm

**Author:** Session 141 (Track E)
**Date:** 2026-03-26
**Status:** Draft
**Session:** 141 (PRD only, no implementation)
**References:** Lesson 149, FB-068 (Session 111d), DD-018, PRD-048

---

## Problem Statement

When an admin merges two identities in focus mode or speed-run, the resulting
identity sometimes remains in PROPOSED or INBOX state even when the merge target
is already a CONFIRMED person. This forces the admin to perform a redundant
manual confirm step after every merge into a known person.

Session 111d attempted auto-merge (automatically merging without user click) and
caused data loss -- Person 3141 disappeared. That feature was reverted (FB-068).
This PRD addresses a different, safer operation: auto-CONFIRM after a
user-initiated merge, only when the target is already confirmed.

### The Distinction

| Term | Meaning | Risk |
|------|---------|------|
| **Auto-merge** | System merges without user click | HIGH -- caused Person 3141 loss |
| **Auto-confirm** | After user-initiated merge, auto-set state to CONFIRMED | LOW -- user already validated the merge |

This PRD is about auto-confirm only. Auto-merge remains out of scope.

---

## User Flows

### Flow 1: Merge INTO a CONFIRMED Identity (Auto-Confirm)

1. Admin is in focus mode or speed-run reviewing a PROPOSED/INBOX identity
2. Admin searches for a known person (e.g., "Albert Fox") in the merge search
3. Admin clicks "Same Person" to merge into Albert Fox (CONFIRMED)
4. System merges: source faces transfer to Albert Fox's anchor_ids
5. **NEW:** System detects target is CONFIRMED -- no state change needed
   (target stays CONFIRMED, source gets `merged_into` pointer)
6. Toast: "Merged into Albert Fox (Confirmed)" with link to person page
7. Admin continues triage -- no extra confirm step required

### Flow 2: Merge Two Non-Confirmed Identities (No Auto-Confirm)

1. Admin is reviewing a PROPOSED identity with 3 faces
2. Admin finds another PROPOSED identity that looks like the same person
3. Admin clicks "Same Person" to merge
4. System merges faces into the target identity
5. Target remains PROPOSED -- admin must manually confirm later
6. Toast: "Merged into Unidentified Person 42" (no auto-confirm)

### Flow 3: Merge a CONFIRMED INTO a Non-Confirmed (Direction Guard)

1. Admin accidentally tries to merge a CONFIRMED identity into an INBOX identity
2. System detects the source is CONFIRMED and the target is not
3. **Option A (recommended):** System reverses the merge direction --
   the CONFIRMED identity becomes the target, preserving its state and name
4. Toast: "Merged into [Confirmed Name] (direction reversed to preserve confirmation)"
5. The CONFIRMED identity retains its name, state, and all metadata

### Flow 4: Merge Two CONFIRMED Identities (Confirmation Gate)

1. Admin merges two CONFIRMED identities (e.g., discovered they are the same person)
2. Existing confirmation gate (Session 127) fires: "Are you sure? Both are confirmed."
3. After confirmation, merge proceeds -- target stays CONFIRMED
4. Source gets `merged_into` pointer
5. Toast: "Merged [Source Name] into [Target Name]"

---

## Acceptance Criteria

### Auto-Confirm Logic
- [ ] When target.state == "CONFIRMED", merged result stays CONFIRMED with no extra step
- [ ] When target.state != "CONFIRMED", merge proceeds without state change (current behavior)
- [ ] Source identity's faces transfer to target's anchor_ids (existing behavior, no change)
- [ ] audit_log entry records the auto-confirm alongside the merge action

### Direction Guard
- [ ] When source.state == "CONFIRMED" and target.state != "CONFIRMED", merge direction reverses
- [ ] Reversed merge preserves the CONFIRMED identity's name, state, anchor_ids, and metadata
- [ ] Toast communicates the reversal clearly to the admin
- [ ] If both are CONFIRMED, no reversal occurs (user chose the direction intentionally)

### Toast Feedback
- [ ] Toast for merge-into-confirmed: "Merged into [Name] (Confirmed)" with person link
- [ ] Toast for merge-into-non-confirmed: "Merged into [Name]" (current behavior)
- [ ] Toast for direction reversal: includes "(direction reversed)" indicator

### Safety
- [ ] No auto-merge (system-initiated merge without user click) -- out of scope
- [ ] Existing confirmation gate for CONFIRMED targets (Session 127) preserved
- [ ] Post-merge face verification (Session 131) still runs
- [ ] audit_log captures merge direction, auto-confirm flag, and any direction reversal

### Backward Compatibility
- [ ] All existing merge tests continue to pass
- [ ] Merge between two non-confirmed identities unchanged
- [ ] Merge confirmation gate for CONFIRMED identities unchanged

---

## Data Model Changes

No new tables or columns required.

### Existing fields used

| Table/Field | Usage |
|-------------|-------|
| `identities.state` | Read to determine auto-confirm eligibility |
| `identities.merged_into` | Written on source identity (existing behavior) |
| `identities.anchor_ids` | Faces transferred to target (existing behavior) |
| `audit_log.action` | New value: `merge_auto_confirm` (or extend existing `merge` action metadata) |
| `audit_log.details` | JSON: `{"auto_confirmed": true, "direction_reversed": false}` |

---

## Technical Notes

### Implementation Location

The merge handler lives in `app/identity_routes.py`. The relevant function is
`merge_identities()` which already:
- Transfers faces from source to target
- Sets `merged_into` on source
- Runs post-merge face verification (Session 131)
- Writes audit_log entry

The auto-confirm change is a post-merge check: if `target.state == "CONFIRMED"`,
no additional action is needed (the target already has the correct state).
The main change is the **direction guard** and **toast feedback**.

### Direction Guard Implementation

Before calling `merge_identities(source_id, target_id)`:
```
if source.state == "CONFIRMED" and target.state != "CONFIRMED":
    # Swap: make the CONFIRMED identity the target
    source_id, target_id = target_id, source_id
```

This is a 3-line change in the merge route handler, not in `merge_identities()` itself.

### Edge Cases

1. **Both CONFIRMED:** No swap. User chose direction intentionally. Existing
   confirmation gate (Session 127) already warns the admin.

2. **Source has more faces than target:** Direction guard still fires if source
   is CONFIRMED. Preserving confirmed status is more important than face count.
   The admin can always detach faces later.

3. **Source has a name, target does not:** If the target is CONFIRMED, it already
   has a name. If the source is CONFIRMED and target is not, the direction guard
   swaps them, preserving the source's name on the (now-target) identity.

4. **Merge in batch validation page:** Same logic applies. The batch merge
   endpoint should call the same direction-guarded merge path.

---

## Out of Scope

- **Auto-merge** (system-initiated merge without user click) -- explicitly excluded
  per Session 111d incident and Lesson 149
- **Batch merge auto-confirm** across multiple pairs in one action -- separate UX,
  separate risks, needs its own PRD if desired
- **Auto-confirm on single-identity confirm** (already exists as a separate action)
- **Changing the confirmation gate** for merging two CONFIRMED identities
  (Session 127 behavior preserved)

---

## Priority

**P2 -- Quality of life.** The admin can always confirm manually after merge.
This saves one click per merge-into-confirmed, which adds up during triage
sessions (typically 20-50 merges per session). The direction guard is the
higher-value change -- it prevents accidental loss of confirmed status.

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Direction reversal confuses admin | Low | Clear toast message explains what happened |
| Auto-confirm on wrong merge | Low | User already clicked "Same Person" -- this is confirmation |
| Batch merge inconsistency | Medium | Ensure batch merge uses same code path |
| Stale state after cache TTL | Low | State is read fresh for merge operations |

### Cautionary Reference

Session 111d's auto-merge attempt (FB-068) failed because it merged identities
without explicit user action. The key difference here: auto-confirm only fires
AFTER the user has explicitly chosen to merge. The user action is the safety gate.

---

## Breadcrumbs

- **Lesson 149:** Browser automation catastrophe -- never auto-modify production data
- **FB-068 (Session 111d):** Auto-merge attempted and REVERTED
- **Session 127:** Merge confirmation gate for CONFIRMED people
- **Session 131:** Post-merge face verification
- **DD-018:** Speed-Run vs Focus Mode
- **PRD-048:** Speed-run enrichment
- **BACKLOG:** FB-003 (merge auto-confirm)
